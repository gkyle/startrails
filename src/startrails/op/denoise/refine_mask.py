"""Observable operation for content-aware sky mask edge refinement."""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Union
import numpy as np

from startrails.op.denoise.base import DenoiseOperation
from startrails.lib.util import imread
from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.denoise.mask_refiner import MaskRefiner


class RefineMask(DenoiseOperation):
    """Refines rough sky mask edges to natural physical horizons."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)

    def refine(
        self,
        image_or_path: Union[np.ndarray, str, Path],
        rough_mask: np.ndarray,
        search_radius: Optional[int],
        erosion_pixels: int,
        foliage_protection: bool,
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
        self.startJob(2)
        self.updateJob(0, {"desc": "Preparing sky mask refinement..."})

        if self.shouldInterrupt():
            return None

        if isinstance(image_or_path, (str, Path)):
            img = imread(image_or_path, to_rgb=True, as_float=True)
        else:
            img = image_or_path
            if img.dtype != np.float32:
                from startrails.lib.image_io import normalize_image
                img = normalize_image(img)

        if self.shouldInterrupt():
            return None

        def on_region_progress(completed: int, total: int):
            if completed == 0:
                # Reserve one unit each for global preparation and finalization.
                self.job.total = total + 2
            description = (
                f"Refining sky mask: {completed}/{total} tiles processed."
                if total else "Cleaning refined sky mask..."
            )
            if total and completed == total:
                description += " Cleaning mask..."
            self.updateJob(1, {
                "desc": description,
                "completed_tiles": completed,
                "total_tiles": total,
            })

        refined = MaskRefiner.refine(
            img,
            rough_mask,
            search_radius=search_radius,
            erosion_pixels=erosion_pixels,
            foliage_protection=foliage_protection,
            progress_callback=on_region_progress,
            should_interrupt=self.shouldInterrupt,
        )

        if refined is None or self.shouldInterrupt():
            return None

        if export_path is not None:
            self.updateJob(0, {"desc": "Saving refined sky mask..."})
            if self.shouldInterrupt():
                return None
            MaskHandler.save_mask(refined, export_path)

        if self.shouldInterrupt():
            return None
        self.updateJob(1, {"desc": "Sky mask refinement complete"})
        return refined
