"""Image writer supporting 16-bit TIFF and 8-bit JPEG/PNG with color profile support."""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional, Union
import cv2
import numpy as np
from PIL import Image


class ImageWriter:
    """Exports float32 [0.0, 1.0] or integer image arrays to disk."""

    @classmethod
    def write(
        cls,
        data: np.ndarray,
        filepath: Union[str, Path],
        icc_profile: Optional[bytes] = None,
        compression: str = "deflate",
        quality: int = 95,
        **kwargs,
    ) -> Path:
        """Write image data to file.

        Args:
            data: float32 array in [0.0, 1.0] or uint8/uint16 array, shape (H, W, 3) or (H, W).
            filepath: Destination path (*.tif, *.tiff, *.jpg, *.jpeg, *.png).
            icc_profile: Optional embedded ICC color profile bytes.
            compression: Compression for TIFF ('none', 'deflate', 'lzw').
            quality: JPEG compression quality (1-100).

        Returns:
            Saved Path object (or alternate path if original was locked by another app).
        """
        path = Path(filepath).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        if data.dtype in (np.float32, np.float64):
            arr = np.clip(data, 0.0, 1.0)
        else:
            arr = data

        suffix = path.suffix.lower()

        def _do_write(target_path: Path) -> None:
            if suffix in (".tif", ".tiff"):
                cls._write_tiff(arr, target_path, icc_profile=icc_profile, compression=compression)
            elif suffix in (".jpg", ".jpeg"):
                cls._write_jpeg(arr, target_path, icc_profile=icc_profile, quality=quality)
            else:
                cls._write_standard(arr, target_path, icc_profile=icc_profile)

        try:
            _do_write(path)
            return path
        except OSError as e:
            # Handle Windows file locks (ERROR_USER_MAPPED_FILE 1224, EACCES 13, EINVAL 22)
            if getattr(e, "errno", None) in (22, 13) or getattr(e, "winerror", None) in (5, 32, 1224):
                counter = 1
                while True:
                    alt_path = path.with_stem(f"{path.stem}_{counter}")
                    if not alt_path.exists():
                        break
                    counter += 1
                print(
                    f"\n[WARNING] Output file '{path.name}' is currently locked by another application. "
                    f"Saving to '{alt_path.name}' instead.",
                    file=sys.stderr,
                )
                _do_write(alt_path)
                return alt_path
            raise

    @classmethod
    def _write_tiff(
        cls,
        arr: np.ndarray,
        path: Path,
        icc_profile: Optional[bytes] = None,
        compression: str = "deflate",
    ) -> None:
        """Write 16-bit TIFF file."""
        if arr.dtype in (np.float32, np.float64):
            u16 = (arr * 65535.0 + 0.5).astype(np.uint16)
        elif arr.dtype == np.uint8:
            u16 = (arr.astype(np.uint16) * 257)
        else:
            u16 = arr.astype(np.uint16)

        # Use OpenCV TIFF write with Deflate compression if available
        comp_val = 8 if compression.lower() != "none" else 1
        options = [cv2.IMWRITE_TIFF_COMPRESSION, comp_val]

        if u16.ndim == 3 and u16.shape[2] >= 3:
            bgr16 = cv2.cvtColor(u16, cv2.COLOR_RGB2BGR) if u16.shape[2] == 3 else cv2.cvtColor(u16, cv2.COLOR_RGBA2BGRA)
            success = cv2.imwrite(str(path), bgr16, options)
        else:
            success = cv2.imwrite(str(path), u16, options)

        if not success:
            # Fallback to Pillow
            img = Image.fromarray(u16)
            save_kwargs = {}
            if icc_profile:
                save_kwargs["icc_profile"] = icc_profile
            img.save(path, **save_kwargs)

    @classmethod
    def _write_jpeg(
        cls,
        arr: np.ndarray,
        path: Path,
        icc_profile: Optional[bytes] = None,
        quality: int = 95,
    ) -> None:
        """Write 8-bit JPEG file."""
        if arr.dtype in (np.float32, np.float64):
            u8 = (arr * 255.0 + 0.5).astype(np.uint8)
        elif arr.dtype == np.uint16:
            u8 = (arr / 256).astype(np.uint8)
        else:
            u8 = arr.astype(np.uint8)

        img = Image.fromarray(u8)
        save_kwargs = {"format": "JPEG", "quality": quality, "optimize": True}
        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile
        img.save(path, **save_kwargs)

    @classmethod
    def _write_standard(
        cls,
        arr: np.ndarray,
        path: Path,
        icc_profile: Optional[bytes] = None,
    ) -> None:
        """Write standard 8-bit image (PNG, BMP, etc.)."""
        if arr.dtype in (np.float32, np.float64):
            u8 = (arr * 255.0 + 0.5).astype(np.uint8)
        elif arr.dtype == np.uint16:
            u8 = (arr / 256).astype(np.uint8)
        else:
            u8 = arr.astype(np.uint8)

        img = Image.fromarray(u8)
        save_kwargs = {}
        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile
        img.save(path, **save_kwargs)
