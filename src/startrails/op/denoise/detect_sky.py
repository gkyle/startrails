"""Observable operation for automatic celestial sky segmentation."""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Union
import numpy as np

from startrails.op.denoise.base import DenoiseOperation
from startrails.lib.util import imread
from startrails.lib.denoise.sky_detector import AutoSkyDetector


class DetectSky(DenoiseOperation):
    """Detects celestial sky region on a base image."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)

    def detect(
        self,
        image_or_path: Union[np.ndarray, str, Path],
        model_type: str = "auto",
        model_path: Optional[str] = None,
        device: str = "auto",
        input_size: int = 1024,
    ) -> Optional[np.ndarray]:
        """Run sky detection.

        Args:
            image_or_path: Input image array or filepath.
            model_type: "auto", "segformer", "nightstack", or "heuristic".
            model_path: Optional custom path or HF model id.
            device: "auto", "cuda", or "cpu".
            input_size: Maximum dimension during neural inference.

        Returns:
            2D float32 sky confidence mask (H, W) in [0.0, 1.0], or None if cancelled.
        """
        self.startJob(2)

        if self.shouldInterrupt():
            return None

        if isinstance(image_or_path, (str, Path)):
            img = imread(image_or_path, to_rgb=True, as_float=True)
        else:
            img = image_or_path

        self.updateJob(1)

        if self.shouldInterrupt():
            return None

        mask = AutoSkyDetector.detect(
            img,
            model_type=model_type,
            model_path=model_path,
            device=device,
            input_size=input_size,
        )

        if self.shouldInterrupt():
            return None

        self.updateJob(1)
        return mask
