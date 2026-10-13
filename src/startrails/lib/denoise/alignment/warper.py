"""Image warping with subpixel interpolation and coverage tracking."""

from __future__ import annotations
from typing import Tuple
import cv2
import numpy as np


class ImageWarper:
    """Applies affine or perspective transformations with subpixel precision."""

    @classmethod
    def warp(
        cls,
        image: np.ndarray,
        matrix: np.ndarray,
        output_shape: Tuple[int, int],
        border_mode: int = cv2.BORDER_CONSTANT,
        border_value: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Warp image and compute binary coverage mask of valid pixels.

        Args:
            image: float32 image array (H, W, 3) or (H, W)
            matrix: 2x3 affine matrix or 3x3 homography matrix
            output_shape: (H_out, W_out)
            border_mode: OpenCV border mode
            border_value: fill value for out-of-bounds pixels

        Returns:
            (warped_image, coverage_mask):
                - warped_image: float32 array of shape (H_out, W_out, C)
                - coverage_mask: bool array of shape (H_out, W_out) where True = valid warped pixel
        """
        h_out, w_out = output_shape[:2]
        dsize = (w_out, h_out)

        in_h, in_w = image.shape[:2]
        ones_mask = np.full((in_h, in_w), 255, dtype=np.uint8)

        if matrix.shape == (2, 3):
            warped = cv2.warpAffine(
                image,
                matrix,
                dsize,
                flags=cv2.INTER_CUBIC,
                borderMode=border_mode,
                borderValue=border_value,
            )
            warped_mask = cv2.warpAffine(
                ones_mask,
                matrix,
                dsize,
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
        elif matrix.shape == (3, 3):
            warped = cv2.warpPerspective(
                image,
                matrix,
                dsize,
                flags=cv2.INTER_CUBIC,
                borderMode=border_mode,
                borderValue=border_value,
            )
            warped_mask = cv2.warpPerspective(
                ones_mask,
                matrix,
                dsize,
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
        else:
            raise ValueError(f"Unsupported matrix shape: {matrix.shape}")

        coverage = (warped_mask == 255)
        return warped, coverage

    @classmethod
    def warp_mask(
        cls,
        mask: np.ndarray,
        matrix: np.ndarray,
        output_shape: Tuple[int, int],
    ) -> np.ndarray:
        """Fast warping of mask without duplicate coverage tracking."""
        h_out, w_out = output_shape[:2]
        dsize = (w_out, h_out)
        if matrix.shape == (2, 3):
            return cv2.warpAffine(
                mask,
                matrix,
                dsize,
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0.0,
            )
        elif matrix.shape == (3, 3):
            return cv2.warpPerspective(
                mask,
                matrix,
                dsize,
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0.0,
            )
        else:
            raise ValueError(f"Unsupported matrix shape: {matrix.shape}")

    @classmethod
    def compute_tapered_mask(
        cls,
        binary_mask: np.ndarray,
        taper_radius: float = 5.0,
    ) -> np.ndarray:
        """Compute soft-tapered coverage weights from a binary coverage mask."""
        mask_u8 = (binary_mask > 0).astype(np.uint8)
        if taper_radius <= 0:
            return mask_u8.astype(np.float32)

        total_valid = int(np.count_nonzero(mask_u8))
        if total_valid == 0:
            return np.zeros(mask_u8.shape, dtype=np.float32)
        if total_valid == mask_u8.size:
            return np.ones(mask_u8.shape, dtype=np.float32)

        dist = cv2.distanceTransform(mask_u8, cv2.DIST_L2, 3)
        t = np.clip(dist / float(taper_radius), 0.0, 1.0)
        tapered = t * t * (3.0 - 2.0 * t)
        return tapered.astype(np.float32)
