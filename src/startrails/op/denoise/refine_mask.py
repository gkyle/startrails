"""Observable operation for content-aware sky mask edge refinement."""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Union
import numpy as np

from startrails.lib.util import Observable, imread
from startrails.lib.denoise.io.mask import MaskHandler
from startrails.lib.denoise.io.mask_refiner import MaskRefiner


class RefineMask(Observable):
    """Refines rough sky mask edges to natural physical horizons."""

    def __init__(self):
        super().__init__()

    def refine(
        self,
        image_or_path: Union[np.ndarray, str, Path],
        rough_mask: np.ndarray,
        search_radius: Optional[int] = None,
        erosion_pixels: int = 5,
        foliage_protection: bool = True,
        export_path: Optional[Union[str, Path]] = None,
    ) -> Optional[np.ndarray]:
        """Refine sky mask against base image.

        Args:
            image_or_path: Input image array or filepath.
            rough_mask: 2D array where ~1.0 is Sky and ~0.0 is Ground.
            search_radius: Optional boundary search ribbon radius.
            erosion_pixels: Inward erosion to prevent foreground bleed.
            foliage_protection: Preserve fine porous details.
            export_path: Optional destination to save refined PNG.

        Returns:
            Refined 2D float32 mask (H, W) in [0.0, 1.0], or None if cancelled.
        """
        self.startJob(1)

        if self.shouldInterrupt():
            return None

        if isinstance(image_or_path, (str, Path)):
            img = imread(image_or_path, to_rgb=True, as_float=True)
        else:
            img = image_or_path

        if self.shouldInterrupt():
            return None

        refined = MaskRefiner.refine(
            img,
            rough_mask,
            search_radius=search_radius,
            erosion_pixels=erosion_pixels,
            foliage_protection=foliage_protection,
        )

        if self.shouldInterrupt():
            return None

        if export_path is not None:
            MaskHandler.save_mask(refined, export_path)

        self.updateJob(1, refined)
        return refined
