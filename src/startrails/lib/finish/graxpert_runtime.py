"""GraXpert PyTorch session initialization, device resolution, and tiled inference engine."""

from __future__ import annotations

from concurrent.futures import CancelledError
from pathlib import Path
from typing import Callable, Optional, Union

import numpy as np
import torch
import torch.nn as nn

from startrails.lib.finish.graxpert import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_STRIDE,
    GRAXPERT_MODEL_RELATIVE_PATH,
    WINDOW_SIZE,
    compute_graxpert_stats,
    graxpert_model_identity,
    graxpert_tile_postprocess,
    graxpert_tile_preprocess,
    load_graxpert_model,
)
from startrails.lib.gpu import (
    CUDA_ALLOCATION_ERROR_MARKERS,
    free_gpu_memory,
    is_cuda_allocation_failure,
    resolve_torch_device as resolve_graxpert_device,
)
from startrails.lib.image_io import validate_image_array
from startrails.paths import APPLICATION_DIR


class GraXpertSession:
    """Manages an active GraXpert PyTorch model session and seamless tiled denoising."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        *,
        device: Union[str, torch.device] = "auto",
    ):
        self.model_path = (
            Path(model_path)
            if model_path is not None
            else (APPLICATION_DIR / "models" / GRAXPERT_MODEL_RELATIVE_PATH)
        )
        if not self.model_path.is_file():
            raise FileNotFoundError(f"GraXpert model file not found: {self.model_path}")

        self.configured_device = resolve_graxpert_device(device)
        self.device = self.configured_device
        self.dtype = torch.float16 if self.device.type == "cuda" else torch.float32
        self.fallback_reason: Optional[str] = None
        self.model_identity = graxpert_model_identity()

        try:
            self.model = load_graxpert_model(self.model_path, self.device, dtype=self.dtype)
        except Exception as error:
            if not self._can_retry_on_cpu(error):
                raise
            self._activate_cpu_fallback(error)

    @property
    def execution_device(self) -> str:
        """Return the active torch device string used for execution (including CPU fallback)."""
        return str(self.device)

    def _can_retry_on_cpu(self, error: BaseException) -> bool:
        return self.device.type != "cpu" and is_cuda_allocation_failure(error)

    def _activate_cpu_fallback(self, error: BaseException) -> None:
        """Retry the whole image on CPU after a recognized GPU allocation failure."""
        failed_device = self.device
        cpu_device = torch.device("cpu")
        try:
            if hasattr(self, "model") and isinstance(self.model, nn.Module):
                self.model = self.model.to(device=cpu_device, dtype=torch.float32)
                self.model.eval()
            else:
                self.model = load_graxpert_model(self.model_path, cpu_device, dtype=torch.float32)
        except Exception as cpu_error:
            raise RuntimeError(
                f"GraXpert {failed_device} execution failed ({error}); CPU retry also failed: {cpu_error}"
            ) from cpu_error
        self.device = cpu_device
        self.dtype = torch.float32
        self.fallback_reason = f"{failed_device} allocation failure: {error}; retried on cpu."

    def denoise_full_strength(
        self,
        image: np.ndarray,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        progress_bar: Optional[Callable[[int, int, int, bool, Optional[dict]], None]] = None,
        should_interrupt: Optional[Callable[[], bool]] = None,
    ) -> np.ndarray:
        """Return the full-strength GraXpert endpoint with overlapping tiled blending.

        Interactive strength/scope blending happens in the composition owner, never
        here, so this endpoint can be cached once per separation/model identity.
        Recognized GPU allocation failures retry the image on CPU; other errors
        surface unchanged.
        """
        validate_image_array(image)
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")

        try:
            return self._denoise_with_active_device(
                image,
                batch_size=batch_size,
                progress_bar=progress_bar,
                should_interrupt=should_interrupt,
            )
        except Exception as error:
            if not self._can_retry_on_cpu(error):
                raise
            self._activate_cpu_fallback(error)
            return self._denoise_with_active_device(
                image,
                batch_size=batch_size,
                progress_bar=progress_bar,
                should_interrupt=should_interrupt,
            )

    @torch.inference_mode()
    def _denoise_with_active_device(
        self,
        image: np.ndarray,
        *,
        batch_size: int,
        progress_bar: Optional[Callable[[int, int, int, bool, Optional[dict]], None]],
        should_interrupt: Optional[Callable[[], bool]],
    ) -> np.ndarray:
        if should_interrupt and should_interrupt():
            raise CancelledError("GraXpert denoising cancelled before start")

        source_h, source_w, c = image.shape
        median, mad = compute_graxpert_stats(image)
        # The model has a fixed 256-pixel input. Symmetric padding also handles
        # a one-pixel dimension; crop only after full-size tile accumulation.
        padded = (
            np.pad(
                image,
                ((0, max(0, WINDOW_SIZE - source_h)), (0, max(0, WINDOW_SIZE - source_w)), (0, 0)),
                mode="symmetric",
            )
            if source_h < WINDOW_SIZE or source_w < WINDOW_SIZE
            else image
        )
        h, w = padded.shape[:2]

        # 2D Hann window for smooth overlap interpolation without boundary grid seams
        w1d = np.sin(np.pi * (np.arange(WINDOW_SIZE) + 0.5) / WINDOW_SIZE) ** 2
        window_weight = np.outer(w1d, w1d)[:, :, None].astype(np.float32)

        y_coords = list(range(0, max(1, h - WINDOW_SIZE + 1), DEFAULT_STRIDE))
        if not y_coords or y_coords[-1] + WINDOW_SIZE < h:
            y_coords.append(max(0, h - WINDOW_SIZE))

        x_coords = list(range(0, max(1, w - WINDOW_SIZE + 1), DEFAULT_STRIDE))
        if not x_coords or x_coords[-1] + WINDOW_SIZE < w:
            x_coords.append(max(0, w - WINDOW_SIZE))

        tile_positions = [
            (min(y, max(0, h - WINDOW_SIZE)), min(x, max(0, w - WINDOW_SIZE)))
            for y in y_coords
            for x in x_coords
        ]
        total_tiles = len(tile_positions)
        accum_denoised = np.zeros((h, w, c), dtype=np.float32)
        accum_weight = np.zeros((h, w, 1), dtype=np.float32)

        completed_tiles = 0
        if progress_bar is not None:
            progress_bar(total_tiles, 0, 0, False, {"desc": "Denoising starless image..."})

        for b_idx in range(0, total_tiles, batch_size):
            if should_interrupt and should_interrupt():
                raise CancelledError("GraXpert denoising cancelled by user")

            batch_pos = tile_positions[b_idx : b_idx + batch_size]
            tiles = [
                graxpert_tile_preprocess(padded[y : y + WINDOW_SIZE, x : x + WINDOW_SIZE], median, mad)
                for y, x in batch_pos
            ]
            batch_arr = np.stack(tiles, axis=0).astype(np.float32, copy=False)
            batch_tensor = torch.from_numpy(batch_arr).to(device=self.device, dtype=self.dtype)

            out_tensor = self.model(batch_tensor)
            if isinstance(out_tensor, torch.Tensor):
                out_batch = out_tensor.detach().cpu().float().numpy()
            else:
                out_batch = np.asarray(out_tensor, dtype=np.float32)

            for i, (y, x) in enumerate(batch_pos):
                orig_tile = padded[y : y + WINDOW_SIZE, x : x + WINDOW_SIZE]
                denoised_tile = graxpert_tile_postprocess(out_batch[i], orig_tile, median, mad)
                accum_denoised[y : y + WINDOW_SIZE, x : x + WINDOW_SIZE] += denoised_tile * window_weight
                accum_weight[y : y + WINDOW_SIZE, x : x + WINDOW_SIZE] += window_weight

            step_tiles = len(batch_pos)
            completed_tiles += step_tiles
            if progress_bar is not None:
                progress_bar(
                    total_tiles,
                    step_tiles,
                    completed_tiles,
                    completed_tiles == total_tiles,
                    {"desc": f"Denoising tile {completed_tiles}/{total_tiles}..."},
                )

        if should_interrupt and should_interrupt():
            raise CancelledError("GraXpert denoising cancelled by user")

        # Every covered weight is positive, even at image corners. Flooring tiny
        # Hann weights would darken those pixels instead of normalizing them.
        denoised_full = (accum_denoised / accum_weight)[:source_h, :source_w]
        denoised_full = np.clip(denoised_full, 0.0, 1.0).astype(np.float32)

        if self.device.type != "cpu":
            free_gpu_memory()

        return denoised_full


__all__ = [
    "CUDA_ALLOCATION_ERROR_MARKERS",
    "GraXpertSession",
    "is_cuda_allocation_failure",
    "resolve_graxpert_device",
]
