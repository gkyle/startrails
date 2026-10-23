"""Automatic sky segmentation for astrophotography landscapes."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional, Tuple

import cv2
import numpy as np

from startrails.lib.denoise.defaults import (
    DEFAULT_SKY_DETECTION_DEVICE,
    DEFAULT_SKY_DETECTION_INPUT_SIZE,
    DENOISE_DEFAULTS,
)
from startrails.paths import APPLICATION_DIR

logger = logging.getLogger(__name__)

# Global cache for loaded model weights
_MODEL_CACHE: dict[str, Tuple[Any, Any, str, int]] = {}


class AutoSkyDetector:
    """Detect celestial sky region autonomously without requiring manual user brush masks."""

    DEFAULT_NIGHT_MODEL = str(APPLICATION_DIR / "models/detectSky/nightstack")
    DEFAULT_SEGFORMER_MODEL = "nvidia/segformer-b0-finetuned-ade-512-512"

    @classmethod
    def detect(
        cls,
        image: np.ndarray,
        model_type: str = DENOISE_DEFAULTS.auto_mask_model,
        model_path: Optional[str] = None,
        device: str = DEFAULT_SKY_DETECTION_DEVICE,
        input_size: int = DEFAULT_SKY_DETECTION_INPUT_SIZE,
    ) -> np.ndarray:
        """Segment celestial sky in the input image.

        Args:
            image: 2D or 3D numpy array (H, W) or (H, W, C), uint8 [0, 255] or float [0.0, 1.0]
            model_type: "nightstack" (default) or "segformer"
            model_path: Optional custom path or HF model id
            device: "auto", "cuda", or "cpu"
            input_size: Maximum dimension to downsample image during neural inference

        Returns:
            sky_confidence: 2D float32 array (H, W) in [0.0, 1.0]
        """
        # 1. Normalize image to 8-bit RGB
        h, w = image.shape[:2]
        if image.dtype in (np.float32, np.float64):
            img_8u = np.clip(image * 255.0, 0, 255).astype(np.uint8)
        elif image.dtype == np.uint16:
            img_8u = (image >> 8).astype(np.uint8)
        else:
            img_8u = image.astype(np.uint8)

        if img_8u.ndim == 2:
            rgb = cv2.cvtColor(img_8u, cv2.COLOR_GRAY2RGB)
        elif img_8u.shape[2] == 4:
            rgb = cv2.cvtColor(img_8u, cv2.COLOR_RGBA2RGB)
        elif img_8u.shape[2] == 3:
            rgb = img_8u
        else:
            raise ValueError(f"Unsupported image shape: {image.shape}")

        # 2. Determine engine & model path
        selected_model = (model_type or "nightstack").lower()
        if selected_model == "nightstack":
            model_path = model_path or cls.DEFAULT_NIGHT_MODEL
        elif selected_model == "segformer":
            model_path = model_path or cls.DEFAULT_SEGFORMER_MODEL
        else:
            raise ValueError(
                f"Unknown model_type: '{model_type}'. Expected 'nightstack' or 'segformer'."
            )

        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

        # 3. Execute neural inference
        try:
            return cls._detect_segformer(
                rgb,
                model_path=model_path,
                device=device,
                input_size=input_size,
            )
        except Exception as e:
            if device != "cpu":
                logger.warning(
                    f"Neural inference on {device} failed ({e}). Retrying neural inference on CPU..."
                )
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    return cls._detect_segformer(
                        rgb,
                        model_path=model_path,
                        device="cpu",
                        input_size=input_size,
                    )
                except Exception as e_cpu:
                    logger.error(f"CPU neural inference failed: {e_cpu}")
                    raise
            raise

    @classmethod
    def _get_segformer_model(
        cls,
        model_path: str,
        device_str: str,
    ) -> Tuple[Any, Any, str, int]:
        """Load and cache SegFormer model and processor."""
        import torch
        from transformers import AutoImageProcessor, SegformerForSemanticSegmentation

        target_path = model_path
        target_p = Path(target_path)
        if target_p.is_file():
            target_path = str(target_p.parent)

        if device_str == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            device = device_str

        cache_key = f"{target_path}_{device}"
        if cache_key in _MODEL_CACHE:
            proc, mod, dev, sky_idx = _MODEL_CACHE[cache_key]
            return proc, mod, dev, sky_idx

        hf_token = os.environ.get("HF_TOKEN")
        logger.info(f"Loading sky segmentation model from {target_path} on {device}...")
        processor = AutoImageProcessor.from_pretrained(target_path, token=hf_token)
        model = SegformerForSemanticSegmentation.from_pretrained(target_path, token=hf_token).to(device).eval()

        id2label = getattr(model.config, "id2label", {})
        sky_idx = 2  # Default ADE20K sky index
        for idx, label in id2label.items():
            if str(label).lower() == "sky":
                sky_idx = int(idx)
                break

        _MODEL_CACHE[cache_key] = (processor, model, device, sky_idx)
        return processor, model, device, sky_idx

    @classmethod
    def _detect_segformer(
        cls,
        rgb: np.ndarray,
        model_path: str,
        device: str,
        input_size: int,
    ) -> np.ndarray:
        """Inference with SegFormer."""
        import torch

        h, w = rgb.shape[:2]
        processor, model, dev, sky_idx = cls._get_segformer_model(model_path, device)

        scale = min(1.0, float(input_size) / max(h, w))
        if scale < 1.0:
            sw, sh = max(16, int(round(w * scale))), max(16, int(round(h * scale)))
            small_rgb = cv2.resize(rgb, (sw, sh), interpolation=cv2.INTER_AREA)
        else:
            small_rgb = rgb
            sw, sh = w, h

        inputs = processor(images=small_rgb, return_tensors="pt", do_resize=False)
        try:
            pixel_values = inputs["pixel_values"].to(dev)
            with torch.no_grad():
                outputs = model(pixel_values=pixel_values)
                logits = outputs.logits
                probs_feat = torch.softmax(logits, dim=1)[0, sky_idx].float().cpu().numpy()
                probs = cv2.resize(probs_feat, (w, h), interpolation=cv2.INTER_LINEAR)
        finally:
            if dev == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()

        return np.clip(probs, 0.0, 1.0).astype(np.float32)
