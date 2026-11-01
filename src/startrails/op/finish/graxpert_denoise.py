"""Observable operation for executing GraXpert AI denoising on starless plates."""

from __future__ import annotations

from concurrent.futures import CancelledError
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.finish.defaults import FinishSettings
from startrails.lib.finish.graxpert_runtime import GraXpertSession
from startrails.lib.image_io import imwrite, validate_image_array
from startrails.lib.util import Observable


class GraXpertDenoise(Observable):
    """Observable operation for full-frame tiled GraXpert denoising with smooth Hann blending."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)
        self._last_completed_tiles: int = 0

    def denoise(
        self,
        image: np.ndarray,
        *,
        strength: float,
        sky_mask: Optional[np.ndarray],
        sky_only: bool,
        session: Optional[GraXpertSession],
        output_path: Optional[Union[str, Path]] = None,
        bit_depth: int,
        settings: FinishSettings,
    ) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Denoise input image with Hann-window tiled blending, progress reporting, and optional masking."""
        validate_image_array(image)
        if not np.isfinite(strength) or not 0 <= strength <= 1:
            raise ValueError("Denoise strength must be between 0 and 1.")
        if sky_only and strength > 0:
            if sky_mask is None:
                raise ValueError("Sky-only denoising requires a sky mask.")
            if sky_mask.dtype != np.float32 or sky_mask.shape != image.shape[:2]:
                raise ValueError("Sky mask dimensions must match the image.")
            if not np.isfinite(sky_mask).all() or np.any(sky_mask < 0) or np.any(sky_mask > 1):
                raise ValueError("Sky mask must be finite and in [0,1].")
        if self.shouldInterrupt():
            return None
        self._last_completed_tiles = 0

        progress_started = False

        def on_progress(total: int, step: int, current: int, is_done: bool, payload: Optional[dict]) -> None:
            nonlocal progress_started
            if not progress_started and total > 0:
                self.startJob(total)
                progress_started = True
            delta = current - self._last_completed_tiles
            if delta > 0:
                self._last_completed_tiles = current
                desc = payload.get("desc") if payload else f"Denoising tile {current}/{total}..."
                self.updateJob(delta, {"desc": desc})

        try:
            if strength == 0:
                denoised = image.copy()
            else:
                if session is None:
                    raise ValueError("A configured GraXpert session is required for denoising.")
                denoised = session.denoise_image(
                    image, strength=strength, progress_bar=on_progress, should_interrupt=self.shouldInterrupt
                )
        except CancelledError:
            return None

        if self.shouldInterrupt():
            return None

        if sky_only and strength > 0:
            weight = sky_mask[..., None]
            denoised = image * (1 - weight) + denoised * weight

        written_path: Optional[Path] = None
        if output_path is not None:
            dest = Path(output_path).resolve()
            try:
                with ArtifactTransaction(self.shouldInterrupt) as transaction:
                    staged = transaction.stage(dest)
                    imwrite(
                        staged,
                        denoised,
                        convertBGR=True,
                        bit_depth=bit_depth,
                        quality=settings.jpeg_quality,
                        optimize=settings.jpeg_optimize,
                        compression=settings.tiff_deflate_compression,
                    )
                    if self.shouldInterrupt():
                        return None
                    transaction.commit()
            except CancelledError:
                return None
            written_path = dest

        return denoised, written_path


__all__ = ["GraXpertDenoise"]
