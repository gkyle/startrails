"""Shared workflow operations for sky mask detection and boundary refinement."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

import numpy as np

from startrails.op.denoise.detect_sky import DetectSky
from startrails.op.denoise.refine_mask import RefineMask

if TYPE_CHECKING:
    from startrails.lib.util import Observable


class SkyMaskingWorkflowMixin:
    """Provides unified sky detection and contour refinement across workflows."""

    app: Any
    _session_operation: Optional[Observable]

    def _new_operation(self, operation_type: Any, *args: Any, **kwargs: Any) -> Any: ...

    def save_project(self) -> None: ...

    def do_detect_sky(
        self,
        image_or_path: Union[np.ndarray, str, Path],
        progress_bar: Optional[Any] = None,
        *,
        model_type: str,
        model_path: Optional[str],
        device: str,
        input_size: int,
    ) -> Optional[np.ndarray]:
        """Run autonomous neural sky detection."""
        detector = self._new_operation(DetectSky)
        if progress_bar is not None:
            detector.addObserver(progress_bar)
        self.app.activeOperation = detector
        try:
            mask = detector.detect(
                image_or_path,
                model_type=model_type,
                model_path=model_path,
                device=device,
                input_size=input_size,
            )
            return mask
        finally:
            self.app.activeOperation = self._session_operation
            if progress_bar is not None:
                detector.removeObserver(progress_bar)
            self.save_project()

    def do_refine_mask(
        self,
        image_or_path: Union[np.ndarray, str, Path],
        coarse_mask: np.ndarray,
        progress_bar: Optional[Any] = None,
        *,
        search_radius: Optional[int],
        erosion_pixels: int,
        foliage_protection: bool,
    ) -> Optional[np.ndarray]:
        """Refine sky mask boundaries against high-frequency horizon contours."""
        refiner = self._new_operation(RefineMask)
        if progress_bar is not None:
            refiner.addObserver(progress_bar)
        self.app.activeOperation = refiner
        try:
            refined = refiner.refine(
                image_or_path,
                coarse_mask,
                search_radius=search_radius,
                erosion_pixels=erosion_pixels,
                foliage_protection=foliage_protection,
            )
            return refined
        finally:
            self.app.activeOperation = self._session_operation
            if progress_bar is not None:
                refiner.removeObserver(progress_bar)
            self.save_project()
