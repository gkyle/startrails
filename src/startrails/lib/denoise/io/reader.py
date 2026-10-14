"""Image reader supporting TIFF, JPEG, PNG, and raw formats as normalized float32 arrays."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union
import cv2
import numpy as np
from PIL import Image
from startrails.lib.image_io import imread, normalize_image

try:
    import rawpy
except ImportError:
    rawpy = None

RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".pef", ".raf", ".srw"
}


@dataclass
class ImageData:
    """Container for loaded image array and metadata."""
    data: np.ndarray  # float32 array in [0.0, 1.0], shape (H, W, 3) or (H, W)
    path: Path
    width: int
    height: int
    channels: int
    bit_depth: int = 16
    icc_profile: Optional[bytes] = None


class ImageReader:
    """Reads image files into normalized float32 NumPy arrays."""

    @staticmethod
    def is_raw(filepath: Union[str, Path]) -> bool:
        """Check if file is a camera RAW file based on extension."""
        return Path(filepath).suffix.lower() in RAW_EXTENSIONS

    @classmethod
    def read(
        cls,
        filepath: Union[str, Path],
        as_linear: bool = False,
        half_size: bool = False,
    ) -> ImageData:
        """Read an image file (TIFF, JPEG, PNG, or RAW) as a normalized float32 array."""
        path = Path(filepath).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        suffix = path.suffix.lower()

        if suffix in RAW_EXTENSIONS:
            return cls._read_raw(path, as_linear=as_linear, half_size=half_size)
        elif suffix in (".tif", ".tiff"):
            return cls._read_tiff(path)
        else:
            return cls._read_standard(path)

    @classmethod
    def _read_raw(cls, path: Path, as_linear: bool, half_size: bool) -> ImageData:
        if rawpy is None:
            raise ImportError(
                f"Cannot read RAW file {path.name}: 'rawpy' is not installed."
            )

        with rawpy.imread(str(path)) as raw:
            if as_linear:
                rgb = raw.postprocess(
                    output_bps=16,
                    no_auto_bright=True,
                    use_camera_wb=True,
                    gamma=(1, 1),
                    half_size=half_size,
                )
            else:
                rgb = raw.postprocess(
                    output_bps=16,
                    use_camera_wb=True,
                    half_size=half_size,
                )

            arr = rgb.astype(np.float32) / 65535.0
            h, w = arr.shape[:2]
            channels = arr.shape[2] if arr.ndim == 3 else 1
            return ImageData(data=arr, path=path, width=w, height=h, channels=channels, bit_depth=16)

    @classmethod
    def _read_tiff(cls, path: Path) -> ImageData:
        return cls._read_standard(path)

    @classmethod
    def _read_standard(cls, path: Path) -> ImageData:
        # Pixel decoding uses the same precision/channel contract as operations.
        pixels = imread(path, to_rgb=True)
        bit_depth = pixels.dtype.itemsize * 8
        arr = normalize_image(pixels)
        if arr.ndim == 3 and arr.shape[2] == 4:
            arr = arr[..., :3]
        icc_profile = None
        try:
            with Image.open(path) as image:
                icc_profile = image.info.get("icc_profile")
        except OSError:
            pass
        height, width = arr.shape[:2]
        channels = arr.shape[2] if arr.ndim == 3 else 1
        return ImageData(arr, path, width, height, channels, bit_depth, icc_profile)

