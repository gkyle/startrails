"""Automatic sky segmentation for astrophotography landscapes."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Global cache for loaded model weights
_MODEL_CACHE: dict[str, Tuple[Any, Any, str, int]] = {}


def _get_local_nightstack_dir() -> Optional[Path]:
    """Find local nightstack weights directory in repository or current working directory."""
    root = Path(__file__).resolve()
    while root.parent != root:
        if (root / "models" / "detectSky" / "nightstack").is_dir():
            target = root / "models" / "detectSky" / "nightstack"
            if (target / "model.safetensors").exists() or (target / "config.json").exists():
                return target.resolve()
        root = root.parent
    candidate = Path("models/detectSky/nightstack").resolve()
    if candidate.is_dir() and ((candidate / "model.safetensors").exists() or (candidate / "config.json").exists()):
        return candidate
    return None


class AutoSkyDetector:
    """Detect celestial sky region autonomously without requiring manual user brush masks."""

    DEFAULT_NIGHT_MODEL = "dvd1016/nightstack-v6-segformer-b0"
    DEFAULT_SEGFORMER_MODEL = "nvidia/segformer-b0-finetuned-ade-512-512"

    @classmethod
    def detect(
        cls,
        image: np.ndarray,
        model_type: str = "auto",
        model_path: Optional[str] = None,
        device: str = "auto",
        input_size: int = 1024,
    ) -> np.ndarray:
        """Segment celestial sky in the input image.

        Args:
            image: 2D or 3D numpy array (H, W) or (H, W, C), uint8 [0, 255] or float [0.0, 1.0]
            model_type: "auto", "segformer", "nightstack", or "heuristic"
            model_path: Optional custom path or HF model id
            device: "auto", "cuda", or "cpu"
            input_size: Maximum dimension to downsample image during neural inference (default: 1024)

        Returns:
            sky_confidence: 2D float32 array (H, W) in [0.0, 1.0]
        """
        # 1. Normalize image to 8-bit RGB
        h, w = image.shape[:2]
        if image.dtype in (np.float32, np.float64):
            img_8u = np.clip(image * 255.0, 0, 255).astype(np.uint8)
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

        # 2. Determine engine
        selected_model = model_type.lower()
        if selected_model == "auto":
            if model_path is not None:
                selected_model = "nightstack"
            else:
                try:
                    import torch
                    import transformers
                    selected_model = "nightstack"
                except ImportError:
                    logger.info("PyTorch or Transformers not installed. Using heuristic sky detection.")
                    selected_model = "heuristic"

        if selected_model == "nightstack" and model_path is None:
            local_dir = _get_local_nightstack_dir()
            if local_dir is not None:
                model_path = str(local_dir)
            else:
                model_path = cls.DEFAULT_NIGHT_MODEL
        elif selected_model == "segformer" and model_path is None:
            model_path = cls.DEFAULT_SEGFORMER_MODEL

        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

        # 3. Dispatch to engine
        if selected_model in ("segformer", "nightstack"):
            try:
                return cls._detect_segformer(
                    rgb,
                    model_path=model_path,
                    device=device,
                    input_size=input_size,
                )
            except Exception as e:
                logger.warning(f"Neural inference on {device} failed ({e}). Retrying neural inference on CPU...")
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
                    logger.warning(f"CPU neural inference failed ({e_cpu}). Falling back to heuristic detector.")
                    return cls._detect_heuristic(rgb)
        elif selected_model == "heuristic":
            return cls._detect_heuristic(rgb)
        else:
            raise ValueError(f"Unknown model_type: {model_type}. Expected 'auto', 'segformer', 'nightstack', or 'heuristic'.")

    @classmethod
    def _get_segformer_model(
        cls,
        model_path: Optional[str] = None,
        device_str: str = "auto",
    ) -> Tuple[Any, Any, str, int]:
        """Load and cache SegFormer model and processor."""
        import torch
        from transformers import AutoImageProcessor, SegformerForSemanticSegmentation

        target_path = model_path or cls.DEFAULT_SEGFORMER_MODEL
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
        model_path: Optional[str] = None,
        device: str = "auto",
        input_size: int = 1024,
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

        inputs = processor(images=small_rgb, return_tensors="pt")
        try:
            pixel_values = inputs["pixel_values"].to(dev)
            with torch.no_grad():
                outputs = model(pixel_values=pixel_values)
                logits = outputs.logits
                upsampled = torch.nn.functional.interpolate(
                    logits, size=(h, w), mode="bilinear", align_corners=False
                )
                probs = torch.softmax(upsampled, dim=1)[0, sky_idx].float().cpu().numpy()
        except Exception as err:
            if dev == "cuda":
                logger.warning(
                    f"CUDA neural inference failed ({err}). Clearing CUDA cache and retrying on CPU to guarantee neural mask precision..."
                )
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                return cls._detect_segformer(
                    rgb,
                    model_path=model_path,
                    device="cpu",
                    input_size=input_size,
                )
            raise

        actual_path = str(model_path or getattr(model.config, "_name_or_path", "")).lower()
        if "ade" in actual_path and np.mean(probs > 0.5) < 0.05:
            logger.warning(
                f"SegFormer (ADE20K) detected only {np.mean(probs > 0.5)*100:.2f}% sky. "
                "Automatically falling back to astrophotography-tuned NightStack model..."
            )
            local_dir = _get_local_nightstack_dir()
            night_model_path = str(local_dir) if local_dir else cls.DEFAULT_NIGHT_MODEL
            return cls._detect_segformer(
                rgb,
                model_path=night_model_path,
                device=device,
                input_size=input_size,
            )

        return np.clip(probs, 0.0, 1.0).astype(np.float32)

    @classmethod
    def _detect_heuristic(cls, rgb: np.ndarray) -> np.ndarray:
        """Physics & astrophotography-specific heuristic sky detection fallback."""
        h, w = rgb.shape[:2]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0

        dw = min(600, w)
        dh = int(round(h * (dw / w)))
        s_gray = cv2.resize(gray, (dw, dh), interpolation=cv2.INTER_AREA)
        s_rgb = cv2.resize(rgb, (dw, dh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0

        # 1. Star Detection via Difference of Gaussians (DoG)
        g1 = cv2.GaussianBlur(s_gray, (3, 3), 0.8)
        g2 = cv2.GaussianBlur(s_gray, (7, 7), 2.0)
        dog = np.maximum(g1 - g2, 0)
        star_thresh = max(0.015, float(np.percentile(dog, 95)))
        stars = (dog > star_thresh).astype(np.float32)
        star_density = cv2.boxFilter(stars, -1, (51, 51))

        # 2. Color Gradient Prior
        b_ratio = s_rgb[..., 2] / (s_rgb[..., 0] + s_rgb[..., 1] + 1e-3)
        b_score = np.clip((b_ratio - 0.7) * 2.0, 0.0, 1.0)

        # 3. Celestial Signal & Elevation Gating
        sky_signal = (star_density * 4.0) + (b_score * 0.8)
        y_coords = np.linspace(0, 1, dh)[:, None]
        elev_gate = np.clip(1.2 - y_coords, 0.0, 1.0)
        raw_prob = np.clip(sky_signal * elev_gate, 0.0, 1.0)

        # Clean coarse mask
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        coarse = cv2.morphologyEx(raw_prob, cv2.MORPH_CLOSE, k)

        prob_full = cv2.resize(coarse, (w, h), interpolation=cv2.INTER_LINEAR)
        return np.clip(prob_full, 0.0, 1.0).astype(np.float32)
