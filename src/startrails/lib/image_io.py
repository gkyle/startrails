"""Shared image decoding, normalization, codec options, and file-lock fallback."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union
import cv2
import numpy


DEFAULT_IMAGE_WRITE_JPEG_QUALITY = 100
IMWRITE_OPTIONS = [cv2.IMWRITE_JPEG_QUALITY, DEFAULT_IMAGE_WRITE_JPEG_QUALITY]
_BT601_RED_WEIGHT = 0.299
_BT601_GREEN_WEIGHT = 0.587
_BT601_BLUE_WEIGHT = 0.114


def rgb_luminance(image: numpy.ndarray) -> numpy.ndarray:
    """Return BT.601 luma for an RGB array."""
    return (
        _BT601_RED_WEIGHT * image[..., 0]
        + _BT601_GREEN_WEIGHT * image[..., 1]
        + _BT601_BLUE_WEIGHT * image[..., 2]
    )


def normalize_image(img):
    """Normalize into one owned float32 buffer without modifying the input."""
    scale = None if img.dtype in (numpy.float32, numpy.float64) else float(numpy.iinfo(img.dtype).max)
    result = img.astype(numpy.float32)
    if scale is not None:
        result /= scale
    numpy.clip(result, 0.0, 1.0, out=result)
    return result


def imread(
    filepath: Union[str, Path],
    to_rgb: bool = False,
    as_float: bool = False,
) -> numpy.ndarray:
    """Read an image file (TIFF, JPEG, PNG, etc.) as a NumPy array.

    Args:
        filepath: Path to the image file.
        to_rgb: If True, convert BGR (or BGRA) to RGB (or RGBA).
        as_float: If True, normalize array to float32 in [0.0, 1.0].

    Returns:
        numpy.ndarray representing the image.
    """
    path = Path(filepath).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not decode image: {path}")

    if to_rgb and img.ndim == 3 and img.shape[2] >= 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    if as_float:
        img = normalize_image(img)

    return img


def imwrite(
    outfile: Union[str, Path],
    img: numpy.ndarray,
    convertBGR: bool = False,
    quality: int = DEFAULT_IMAGE_WRITE_JPEG_QUALITY,
    compression: bool = True,
    optimize: bool = False,
    tiff_uint8_as_uint16: bool = False,
    eight_bit: bool = False,
) -> Path:
    """Atomically write an image, handling CuPy arrays, float scaling, and codec options.

    Args:
        outfile: Destination path.
        img: Image array (numpy or cupy, uint8, uint16, or float32 [0.0, 1.0]).
        convertBGR: If True, converts RGB to BGR before saving.
        quality: JPEG compression quality (1-100).
        compression: Whether to apply lossless Deflate compression for TIFF.

    Returns:
        Path to the saved image file.
    """
    if not isinstance(img, numpy.ndarray):  # convert cupy array to numpy
        import cupy as cp
        img = cp.asnumpy(img)

    path = Path(outfile).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    suffix = path.suffix.lower()

    # Float array scaling: scale float32/float64 to integer ranges for standard codecs
    if img.dtype in (numpy.float32, numpy.float64):
        if suffix in (".tif", ".tiff"):
            img = numpy.clip(img * 65535.0 + 0.5, 0.0, 65535.0).astype(numpy.uint16)
        else:
            img = numpy.clip(img * 255.0 + 0.5, 0.0, 255.0).astype(numpy.uint8)

    if suffix in (".tif", ".tiff") and tiff_uint8_as_uint16 and img.dtype == numpy.uint8:
        img = img.astype(numpy.uint16) * 257
    if eight_bit and img.dtype == numpy.uint16 and suffix not in (".tif", ".tiff"):
        img = (img / 256).astype(numpy.uint8)

    if convertBGR and img.ndim == 3 and img.shape[2] >= 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    options = []
    if suffix in (".jpg", ".jpeg"):
        options = [cv2.IMWRITE_JPEG_QUALITY, quality]
    elif suffix in (".tif", ".tiff"):
        # COMPRESSION_ADOBE_DEFLATE = 8 in libtiff
        comp_val = 8 if compression else 1
        options = [cv2.IMWRITE_TIFF_COMPRESSION, comp_val]

    def _encode_image(target_path: Path):
        if optimize and suffix not in (".tif", ".tiff"):
            from PIL import Image
            rgb = img
            if img.ndim == 3 and img.shape[2] == 3:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            elif img.ndim == 3 and img.shape[2] == 4:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
            settings = {}
            if suffix in (".jpg", ".jpeg"):
                settings.update(quality=quality, optimize=optimize)
            Image.fromarray(rgb).save(target_path, **settings)
            return
        success, encoded = cv2.imencode(suffix, img, options)
        if not success:
            raise ValueError(f"Could not encode image for '{target_path}'")
        with target_path.open("wb") as output:
            output.write(encoded)

    def _do_write(target_path: Path):
        # The UI can read a previous progress update while the worker saves the
        # next one. Stage on the same filesystem so replacement is atomic and
        # readers keep seeing a complete image throughout encoding and writing.
        with TemporaryDirectory(dir=target_path.parent, prefix=".image-") as directory:
            staged_path = Path(directory) / target_path.name
            _encode_image(staged_path)
            staged_path.replace(target_path)

    try:
        _do_write(path)
        return path
    except OSError as e:
        if getattr(e, "errno", None) in (22, 13) or getattr(e, "winerror", None) in (5, 32, 1224):
            counter = 1
            while True:
                alt_path = path.with_stem(f"{path.stem}_{counter}")
                if not alt_path.exists():
                    break
                counter += 1
            print(
                f"\n[WARNING] Output file '{path.name}' is open in another application. "
                f"Saving to '{alt_path.name}' instead.",
                file=sys.stderr,
            )
            _do_write(alt_path)
            return alt_path
        raise
