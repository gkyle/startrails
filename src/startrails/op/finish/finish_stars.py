"""Observable operation applying star effects to the separated star layer."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.finish.defaults import INTERMEDIATE_BIT_DEPTH, FinishSettings
from startrails.lib.finish.star_effects import apply_star_effects
from startrails.lib.image_io import imwrite
from startrails.lib.util import Observable


class FinishStars(Observable):
    """Cancelable wrapper around star effects and lossless intermediate writing."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)
        self._started = False
        self._last_completed = 0

    def finish(
        self,
        stars: np.ndarray,
        sky_mask: np.ndarray,
        settings: FinishSettings,
        *,
        source: np.ndarray,
        output_path: Path,
        artifacts: ArtifactTransaction,
    ) -> Optional[Path]:
        """Apply the effects and stage a 16-bit TIFF without publishing it.

        Returns the resolved destination once written, or None when interrupted.
        The caller owns the transaction so publication remains atomic with the
        project state change. ``source`` is the original normalized source used to
        distinguish saturated cores, where the separated star residual can be < 1.
        """
        self._started = False
        self._last_completed = 0

        def on_progress(done: int, total: int, description: str) -> None:
            if not self._started and total > 0:
                self.startJob(total)
                self._started = True
            increment = done - self._last_completed
            if increment > 0:
                self._last_completed = done
                self.updateJob(increment, {"desc": description})

        if self.shouldInterrupt():
            return None
        finished = apply_star_effects(
            stars,
            sky_mask,
            settings,
            source=source,
            should_interrupt=self.shouldInterrupt,
            progress_callback=on_progress,
        )
        # The effect result is the only working buffer needed from here on.
        del stars, sky_mask, source
        if finished is None or self.shouldInterrupt():
            return None
        if self._started and self.job is not None and not self.job.done:
            self.updateJob(self.job.total - self.job.count, {"desc": "Star effects complete."})

        destination = Path(output_path).resolve()
        staged = artifacts.stage(destination)
        written = imwrite(
            staged,
            finished,
            convertBGR=True,
            bit_depth=INTERMEDIATE_BIT_DEPTH,
            compression=settings.tiff_deflate_compression,
        )
        if written != staged:
            written.unlink(missing_ok=True)
            raise OSError("Finished stars staging path changed unexpectedly; nothing was published.")
        return destination


__all__ = ["FinishStars"]
