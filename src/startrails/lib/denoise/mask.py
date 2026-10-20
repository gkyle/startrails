"""Sky mask handling and rasterization for 2D celestial masks."""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np
from PIL import Image


class MaskHandler:
    """Creates, loads, and evaluates sky region masks."""

    @classmethod
    def create_mask(
        cls,
        shape: Tuple[int, int],
        mask_path: Optional[str | Path] = None,
        mask_array: Optional[np.ndarray] = None,
        feather_radius: int = 0,
    ) -> np.ndarray:
        """Generate a 2D float32 mask of shape (H, W) where 1.0 is Sky and 0.0 is Ground.

        If a mask array or file path is provided, it is loaded and scaled to match shape.
        If no mask is provided, defaults to full sky (100% sky, all 1.0).
        """
        h, w = shape[:2]

        if mask_array is not None:
            if mask_array.shape != (h, w):
                mask = cv2.resize(mask_array.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
            else:
                mask = mask_array.astype(np.float32)
            if feather_radius > 0:
                ksize = feather_radius * 2 + 1
                mask = cv2.GaussianBlur(mask, (ksize, ksize), feather_radius)
            return np.clip(mask, 0.0, 1.0)

        if mask_path is not None and Path(mask_path).exists():
            return cls.load_brush_mask(shape, mask_path, feather_radius)

        return np.ones((h, w), dtype=np.float32)

    @classmethod
    def load_mask(cls, path: str | Path, shape: Optional[Tuple[int, int]] = None) -> np.ndarray:
        """Load a 2D mask image as float32 array in [0.0, 1.0]."""
        return cls.load_brush_mask(shape=shape, mask_path=path)

    @classmethod
    def load_brush_mask(
        cls,
        shape: Optional[Tuple[int, int]] = None,
        mask_path: str | Path = "",
        feather_radius: int = 0,
    ) -> np.ndarray:
        """Load an irregular mask image (mask.png) and optionally resize to match target shape."""
        with Image.open(mask_path) as img:
            gray_img = img.convert("L")
            mask = np.array(gray_img, dtype=np.float32) / 255.0

        if shape is not None:
            h, w = shape[:2]
            if mask.shape != (h, w):
                mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)

        if feather_radius > 0:
            ksize = feather_radius * 2 + 1
            mask = cv2.GaussianBlur(mask, (ksize, ksize), feather_radius)

        return np.clip(mask, 0.0, 1.0)

    @classmethod
    def save_mask(cls, mask: np.ndarray, path: str | Path, **kwargs) -> Path:
        """Save a 2D float32 or uint8 mask to an 8-bit grayscale PNG."""
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if mask.dtype != np.uint8:
            u8 = (np.clip(mask, 0.0, 1.0) * 255.0).astype(np.uint8)
        else:
            u8 = mask

        img = Image.fromarray(u8, mode="L")
        img.save(path)
        return path

    @classmethod
    def save_brush_mask(cls, mask: np.ndarray, path: str | Path) -> Path:
        """Save a 2D mask to an 8-bit grayscale PNG."""
        return cls.save_mask(mask, path)

    @classmethod
    def compute_gradient_mask(
        cls,
        coverages: list[np.ndarray],
        sky_mask: Optional[np.ndarray] = None,
        foreground_mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Compute gradient mask representing the fraction of frames in the sky used to determine pixels."""
        if not coverages:
            raise ValueError("No coverages provided.")
        h, w = coverages[0].shape[:2]
        n_frames = float(len(coverages))
        counts = np.zeros((h, w), dtype=np.float32)
        for cov in coverages:
            counts += cov.astype(np.float32)

        warped_fraction = counts / n_frames

        if sky_mask is not None:
            sky = sky_mask.astype(np.float32)
            gradient_mask = np.clip(sky - warped_fraction, 0.0, 1.0)
        elif foreground_mask is not None:
            sky = 1.0 - foreground_mask.astype(np.float32)
            gradient_mask = np.clip(sky - warped_fraction, 0.0, 1.0)
        else:
            gradient_mask = np.clip(1.0 - warped_fraction, 0.0, 1.0)

        return gradient_mask.astype(np.float32)
