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
    MODEL_SCALE_FACTOR,
    MODEL_THRESHOLD,
    WINDOW_SIZE,
    compute_graxpert_stats,
    graxpert_inference_dtype,
    graxpert_model_identity,
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
        self.dtype = graxpert_inference_dtype(self.device)
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
        window_weight = torch.from_numpy(np.outer(w1d, w1d).astype(np.float32)).to(device=self.device)

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

        # Keep padded image, normalization, gating, and Hann accumulation on
        # self.device in NCHW to eliminate per-batch CPU/GPU round-trips and
        # per-forward NHWC/NCHW transposes.
        padded_t = (
            torch.from_numpy(np.ascontiguousarray(padded))
            .to(device=self.device, dtype=torch.float32)
            .permute(2, 0, 1)
            .contiguous()
        )
        med_t = torch.from_numpy(median).to(device=self.device, dtype=torch.float32).view(c, 1, 1)
        mad_t = torch.from_numpy(mad).to(device=self.device, dtype=torch.float32).view(c, 1, 1)
        orig_scaled = (padded_t - med_t) / mad_t * MODEL_SCALE_FACTOR
        del padded_t
        inp_scaled = orig_scaled.clamp(-MODEL_THRESHOLD, MODEL_THRESHOLD).to(dtype=self.dtype)

        accum_denoised = torch.zeros((c, h, w), dtype=torch.float32, device=self.device)
        accum_weight = torch.zeros((h, w), dtype=torch.float32, device=self.device)

        completed_tiles = 0
        if progress_bar is not None:
            progress_bar(total_tiles, 0, 0, False, {"desc": "Denoising starless image..."})

        for b_idx in range(0, total_tiles, batch_size):
            if should_interrupt and should_interrupt():
                raise CancelledError("GraXpert denoising cancelled by user")

            batch_pos = tile_positions[b_idx : b_idx + batch_size]
            batch_tensor = torch.stack(
                [inp_scaled[:, y : y + WINDOW_SIZE, x : x + WINDOW_SIZE] for y, x in batch_pos]
            )

            out_tensor = self.model(batch_tensor)
            if isinstance(out_tensor, torch.Tensor):
                out_batch = out_tensor.detach().to(device=self.device, dtype=torch.float32)
            else:
                out_batch = torch.as_tensor(np.asarray(out_tensor, dtype=np.float32), device=self.device)

            for i, (y, x) in enumerate(batch_pos):
                orig_tile_scaled = orig_scaled[:, y : y + WINDOW_SIZE, x : x + WINDOW_SIZE]
                gated = torch.where(orig_tile_scaled < MODEL_THRESHOLD, out_batch[i], orig_tile_scaled)
                restored = (gated / MODEL_SCALE_FACTOR * mad_t + med_t).clamp(0.0, 1.0)
                accum_denoised[:, y : y + WINDOW_SIZE, x : x + WINDOW_SIZE] += restored * window_weight
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
        denoised_t = (accum_denoised / accum_weight)[:, :source_h, :source_w].clamp(0.0, 1.0)
        denoised_full = denoised_t.permute(1, 2, 0).cpu().numpy().astype(np.float32, copy=False)

        if self.device.type != "cpu":
            free_gpu_memory()

        return denoised_full


__all__ = [
    "CUDA_ALLOCATION_ERROR_MARKERS",
    "GraXpertSession",
    "is_cuda_allocation_failure",
    "resolve_graxpert_device",
]
