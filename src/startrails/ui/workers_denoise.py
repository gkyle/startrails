"""Background workers for denoise mode mask detection, refinement, and live horizon preview."""

from __future__ import annotations
import logging
from typing import Optional
import numpy as np

from PySide6.QtCore import QThread, Signal

from startrails.lib.denoise.io.sky_detector import AutoSkyDetector
from startrails.lib.denoise.io.mask_refiner import MaskRefiner
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor

logger = logging.getLogger(__name__)


class AutoMaskWorker(QThread):
    """Background worker executing automatic sky detection followed by mask refinement."""

    progressStatus = Signal(str)
    finishedSuccess = Signal(object)
    failedError = Signal(str)

    def __init__(
        self,
        image: np.ndarray,
        model_type: str = "heuristic",
        model_path: Optional[str] = None,
        search_radius: Optional[int] = None,
        erosion_pixels: int = 5,
        device: str = "auto",
        parent=None,
    ):
        super().__init__(parent)
        self.image = image
        self.model_type = model_type
        self.model_path = model_path
        self.search_radius = search_radius
        self.erosion_pixels = erosion_pixels
        self.device = device

    def run(self):
        try:
            self.progressStatus.emit(f"Detecting celestial sky ({self.model_type})...")
            coarse_mask = AutoSkyDetector.detect(
                self.image,
                model_type=self.model_type,
                model_path=self.model_path,
                device=self.device,
            )

            self.progressStatus.emit(
                f"Refining detected sky mask (erosion: {self.erosion_pixels}px)..."
            )
            refined_mask = MaskRefiner.refine(
                self.image,
                coarse_mask,
                search_radius=self.search_radius,
                erosion_pixels=self.erosion_pixels,
            )
            self.finishedSuccess.emit(refined_mask)
        except Exception as e:
            logger.exception("AutoMaskWorker encountered an error")
            self.failedError.emit(str(e))


class RefineMaskWorker(QThread):
    """Background worker executing boundary mask refinement."""

    progressStatus = Signal(str)
    finishedSuccess = Signal(object)
    failedError = Signal(str)

    def __init__(
        self,
        image: np.ndarray,
        rough_mask: np.ndarray,
        search_radius: Optional[int] = None,
        erosion_pixels: int = 5,
        parent=None,
    ):
        super().__init__(parent)
        self.image = image
        self.rough_mask = rough_mask
        self.search_radius = search_radius
        self.erosion_pixels = erosion_pixels

    def run(self):
        try:
            self.progressStatus.emit(
                f"Refining mask boundary (erosion: {self.erosion_pixels}px)..."
            )
            refined = MaskRefiner.refine(
                self.image,
                self.rough_mask,
                search_radius=self.search_radius,
                erosion_pixels=self.erosion_pixels,
            )
            self.finishedSuccess.emit(refined)
        except Exception as e:
            logger.exception("RefineMaskWorker encountered an error")
            self.failedError.emit(str(e))


class HorizonOverlayWorker(QThread):
    """Background worker executing interactive horizon composite overlay computation."""

    finishedOverlay = Signal(object, object, int)  # roi, rect, request_id
    failedError = Signal(str, int)

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
            roi, rect = self.compositor.composite_overlay(
                horizon_blend_percent=self.params.get("blend", 60.0),
                horizon_denoise_strength=self.params.get("denoise_strength", 0.2),
                denoise_enabled=self.params.get("denoise_enabled", True),
                horizon_blur_radius=self.params.get("blur_radius", 2.0),
                enable_corrections=self.params.get("enable_corrections", True),
                horizon_color_denoise_strength=self.params.get("color_denoise"),
                horizon_value_denoise_strength=self.params.get("value_denoise"),
                cancel_check=self.is_cancelled,
            )
            if self._is_cancelled or roi is None:
                return
            self.finishedOverlay.emit(roi, rect, self.request_id)
        except Exception as e:
            if not self._is_cancelled:
                logger.exception("HorizonOverlayWorker encountered an error")
                self.failedError.emit(str(e), self.request_id)


class FinalCompositeSaveWorker(QThread):
    """Background worker executing full composite generation and asynchronously writing _final.tif."""

    finishedSave = Signal(object, object, int)  # out_path (Path), full_image (np.ndarray), request_id
    failedError = Signal(str, int)

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
            )
            if self._is_cancelled or full_img is None:
                return

            from pathlib import Path
            from startrails.lib.util import imwrite
            out_path = Path(self.output_path).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            written = imwrite(out_path, full_img, convertBGR=True)
            if self._is_cancelled:
                return
            self.finishedSave.emit(written, full_img, self.request_id)
        except Exception as e:
            if not self._is_cancelled:
                logger.exception("FinalCompositeSaveWorker encountered an error")
                self.failedError.emit(str(e), self.request_id)

