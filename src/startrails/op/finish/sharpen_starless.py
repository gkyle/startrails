"""Observable operation applying two-scale Structure/Detail to the starless plate."""

from __future__ import annotations

from typing import Optional

import numpy as np

from startrails.lib.finish.starless_filters import DEFAULT_CHUNK_ROWS, sharpen_starless
from startrails.lib.util import Observable


class SharpenStarless(Observable):
    """Cancelable wrapper around the bounded two-scale luminance enhancement."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)
        self._started = False
        self._last_completed = 0

    def sharpen(
        self,
        image: np.ndarray,
        sky_mask: np.ndarray,
        *,
        structure_amount: float,
        detail_amount: float,
        chunk_rows: int = DEFAULT_CHUNK_ROWS,
    ) -> Optional[np.ndarray]:
        """Return the enhanced plate, or None when the job is interrupted."""
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
        result = sharpen_starless(
            image,
            sky_mask,
            structure_amount,
            detail_amount,
            chunk_rows=chunk_rows,
            should_interrupt=self.shouldInterrupt,
            progress_callback=on_progress,
        )
        if self.shouldInterrupt():
            return None
        return result


__all__ = ["SharpenStarless"]
