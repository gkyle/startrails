"""Image reader supporting TIFF, JPEG, PNG, and raw formats as normalized float32 arrays."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union
import cv2
import numpy as np
from PIL import Image

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
        icc_profile = None
        try:
            with Image.open(path) as img:
                icc_profile = img.info.get("icc_profile")
        except Exception:
            pass

        arr = None
        # Tier 1: Pillow
        try:
            with Image.open(path) as img:
                arr = np.array(img)
        except Exception:
            pass

        # Tier 2: OpenCV
        if arr is None:
            try:
                bgr = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
                if bgr is not None:
                    if bgr.ndim == 3 and bgr.shape[2] >= 3:
                        arr = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                    else:
                        arr = bgr
            except Exception:
                pass

        if arr is None:
            raise ValueError(f"Could not decode TIFF image '{path.name}'.")

        arr = cls._normalize_array(arr)
        h, w = arr.shape[:2]
        channels = arr.shape[2] if arr.ndim == 3 else 1
        return ImageData(data=arr, path=path, width=w, height=h, channels=channels, bit_depth=16, icc_profile=icc_profile)

    @classmethod
    def _read_standard(cls, path: Path) -> ImageData:
        with Image.open(path) as img:
            icc_profile = img.info.get("icc_profile")
            arr = np.array(img)
            arr = cls._normalize_array(arr)
            h, w = arr.shape[:2]
            channels = arr.shape[2] if arr.ndim == 3 else 1
            return ImageData(data=arr, path=path, width=w, height=h, channels=channels, bit_depth=8, icc_profile=icc_profile)

    @staticmethod
    def _normalize_array(arr: np.ndarray) -> np.ndarray:
        """Normalize integer arrays (uint8, uint16) to float32 [0.0, 1.0]."""
        if arr.ndim == 2:
            pass  # keep 2D array 2D
        elif arr.ndim == 3 and arr.shape[2] == 4:
            arr = arr[..., :3]

        if arr.dtype == np.uint8:
            return (arr.astype(np.float32) / 255.0).clip(0.0, 1.0)
        elif arr.dtype == np.uint16:
            return (arr.astype(np.float32) / 65535.0).clip(0.0, 1.0)
        elif arr.dtype in (np.float32, np.float64):
            arr32 = arr.astype(np.float32)
            max_v = float(np.max(arr32)) if arr32.size > 0 else 1.0
            if max_v > 256.0:
                arr32 /= 65535.0
            elif max_v > 1.0:
                arr32 /= 255.0
            return arr32.clip(0.0, 1.0)
        else:
            return (arr.astype(np.float32) / float(np.iinfo(arr.dtype).max)).clip(0.0, 1.0)
