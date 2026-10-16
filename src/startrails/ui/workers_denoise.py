"""Background workers for denoise mode mask detection, refinement, and live horizon preview."""

from __future__ import annotations
import logging
from typing import Any

from PySide6.QtCore import QThread, Signal

from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor

logger = logging.getLogger(__name__)


class HorizonOverlayWorker(QThread):
    """Background worker executing interactive horizon composite overlay computation."""

    finished_patches = Signal(object, int)  # [(pixels, rect), ...], request_id
    failed_error = Signal(str, int)

    def __init__(
        self,
        compositor: HorizonCompositor,
        params: dict,
        request_id: int,
        parent=None,
    ):
        super().__init__(parent)
        self.compositor = compositor
        self.params = params
        self.request_id = request_id
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self):
        if self._is_cancelled:
            return
        try:
            patches = self.compositor.composite_patches(
                horizon_blend_percent=self.params.get("blend", 60.0),
                horizon_denoise_strength=self.params.get("denoise_strength", 0.2),
                denoise_enabled=self.params.get("denoise_enabled", True),
                horizon_blur_radius=self.params.get("blur_radius", 2.0),
                enable_corrections=self.params.get("enable_corrections", True),
                horizon_color_denoise_strength=self.params.get("color_denoise"),
                horizon_value_denoise_strength=self.params.get("value_denoise"),
                cancel_check=self.is_cancelled,
            )
            if self._is_cancelled or patches is None:
                return
            self.finished_patches.emit(patches, self.request_id)
        except Exception as e:
            if not self._is_cancelled:
                logger.exception("HorizonOverlayWorker encountered an error")
                self.failed_error.emit(str(e), self.request_id)


class FinalCompositeSaveWorker(QThread):
    """Background worker executing full composite generation and asynchronously writing _final.tif."""

    finished_save = Signal(object, int)  # out_path (Path), request_id
    failed_error = Signal(str, int)

    def __init__(
        self,
        compositor: HorizonCompositor,
        params: dict,
        output_path: Any,
        request_id: int,
        parent=None,
    ):
        super().__init__(parent)
        self.compositor = compositor
        self.params = params
        self.output_path = output_path
        self.staged_path = None
        self.request_id = request_id
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self):
        if self._is_cancelled:
            return
        try:
            full_img = self.compositor.composite(
                horizon_blend_percent=self.params.get("blend", 60.0),
                horizon_denoise_strength=self.params.get("denoise_strength", 0.2),
                denoise_enabled=self.params.get("denoise_enabled", True),
                horizon_blur_radius=self.params.get("blur_radius", 2.0),
                enable_corrections=self.params.get("enable_corrections", True),
                horizon_color_denoise_strength=self.params.get("color_denoise"),
                horizon_value_denoise_strength=self.params.get("value_denoise"),
                cancel_check=self.is_cancelled,
            )
            if self._is_cancelled or full_img is None:
                return

            from pathlib import Path
            from startrails.lib.util import imwrite
            out_path = Path(self.output_path).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            import tempfile
            with tempfile.NamedTemporaryFile(dir=out_path.parent, suffix=out_path.suffix, delete=False) as staged:
                self.staged_path = Path(staged.name)
            written = imwrite(self.staged_path, full_img, convertBGR=True)
            if self._is_cancelled:
                self.staged_path.unlink(missing_ok=True)
                return
            self.finished_save.emit(written, self.request_id)
        except Exception as e:
            if self.staged_path is not None:
                self.staged_path.unlink(missing_ok=True)
            if not self._is_cancelled:
                logger.exception("FinalCompositeSaveWorker encountered an error")
                self.failed_error.emit(str(e), self.request_id)


HorizonOverlayWorker.failedError = property(lambda self: self.failed_error)

FinalCompositeSaveWorker.failedError = property(lambda self: self.failed_error)

FinalCompositeSaveWorker.finishedSave = property(lambda self: self.finished_save)
