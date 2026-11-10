"""Observable operation for full-frame Nox star removal inference."""

from __future__ import annotations

from concurrent.futures import CancelledError
from contextlib import nullcontext
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.finish.defaults import FinishSettings
from startrails.lib.finish.nox import NoxSession, validate_separation_stride
from startrails.lib.image_io import imwrite, validate_image_array
from startrails.lib.util import Observable


class RemoveStars(Observable):
    """Observable operation for full-frame tiled Nox star removal with Hann blending."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)
        self._last_completed_tiles: int = 0

    def remove_stars(
        self,
        image: np.ndarray,
        *,
        session: NoxSession,
        stride: int,
        settings: FinishSettings,
        bit_depth: int,
        output_path: Optional[Union[str, Path]] = None,
        artifacts: Optional[ArtifactTransaction] = None,
    ) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Return the unmasked starless image, optionally writing its cache artifact."""
        validate_image_array(image)
        validate_separation_stride(stride)
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
                desc = payload.get("desc") if payload else f"Separating stars tile {current}/{total}..."
                self.updateJob(delta, {"desc": desc})

        try:
            starless = session.remove_stars(
                image,
                stride=stride,
                progress_bar=on_progress,
                should_interrupt=self.shouldInterrupt,
            )
        except CancelledError:
            return None

        if self.shouldInterrupt():
            return None

        written_path: Optional[Path] = None
        if output_path is not None:
            dest = Path(output_path).resolve()
            transaction = artifacts or ArtifactTransaction(self.shouldInterrupt)
            with nullcontext(transaction) if artifacts is not None else transaction:
                staged = transaction.stage(dest)
                written = imwrite(
                    staged,
                    starless,
                    convertBGR=True,
                    bit_depth=bit_depth,
                    quality=settings.jpeg_quality,
                    optimize=settings.jpeg_optimize,
                    compression=settings.tiff_deflate_compression,
                )
                if written != staged:
                    written.unlink(missing_ok=True)
                    raise OSError("Star removal staging path changed unexpectedly; output was not published.")
                if self.shouldInterrupt():
                    return None
                if artifacts is None:
                    transaction.commit()
            written_path = dest

        return starless, written_path


__all__ = ["RemoveStars"]

