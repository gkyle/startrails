import os
import sys
from pathlib import Path
from typing import Optional, Union
import cv2
import numpy
try:
    import cupy as cp
except:
    pass

IMWRITE_OPTIONS = [cv2.IMWRITE_JPEG_QUALITY, 100]


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
        if img.dtype == numpy.uint8:
            img = (img.astype(numpy.float32) / 255.0).clip(0.0, 1.0)
        elif img.dtype == numpy.uint16:
            img = (img.astype(numpy.float32) / 65535.0).clip(0.0, 1.0)
        elif img.dtype in (numpy.float32, numpy.float64):
            img = img.astype(numpy.float32).clip(0.0, 1.0)
        else:
            max_v = float(numpy.iinfo(img.dtype).max)
            img = (img.astype(numpy.float32) / max_v).clip(0.0, 1.0)

    return img


def imwrite(
    outfile: Union[str, Path],
    img: numpy.ndarray,
    convertBGR: bool = False,
    quality: int = 100,
    compression: bool = True,
) -> Path:
    """Write an image to disk, handling CuPy arrays, float32 scaling, and TIFF/JPEG options.

    Args:
        outfile: Destination path.
        img: Image array (numpy or cupy, uint8, uint16, or float32 [0.0, 1.0]).
        convertBGR: If True, converts RGB to BGR before saving.
        quality: JPEG compression quality (1-100).
        compression: Whether to apply lossless Deflate compression for TIFF.

    Returns:
        Path to the saved image file.
    """
    try:
        if not isinstance(img, numpy.ndarray):  # convert cupy array to numpy
            img = cp.asnumpy(img)
    except:
        pass

    path = Path(outfile).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    suffix = path.suffix.lower()

    # Float array scaling: scale float32/float64 to integer ranges for standard codecs
    if img.dtype in (numpy.float32, numpy.float64):
        clipped = numpy.clip(img, 0.0, 1.0)
        if suffix in (".tif", ".tiff"):
            img = (clipped * 65535.0 + 0.5).astype(numpy.uint16)
        else:
            img = (clipped * 255.0 + 0.5).astype(numpy.uint8)

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

    def _do_write(target_path: Path):
        success = cv2.imwrite(str(target_path), img, options if options else IMWRITE_OPTIONS)
        if not success:
            raise OSError(f"Could not write image to '{target_path}'")

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


def applyMask(image, masks):
    for mask in masks:
        cv2.fillPoly(image, [mask], (0, 0, 0))
    return image


class Job:
    def __init__(self, total):
        self.total = total
        self.count = 0
        self.done = False
        self.interrupt = False


class Observable():
    def __init__(self):
        self.job: Job = None
        self.observers = []

    def startJob(self, total):
        self.job = Job(total)
        self.notifyObservers()

    def updateJob(self, increment, data=None):
        if not self.job is None:
            self.job.count += increment
            if self.job.count >= self.job.total:
                self.job.done = True

        self.notifyObservers(increment, data)

    def notifyObservers(self, increment=0, data=None):
        for observer in self.observers:
            observer(
                self.job.total,
                increment,
                self.job.count,
                self.job.done,
                data)

    def requestInterrupt(self):
        if self.job is not None:
            self.job.interrupt = True

    def shouldInterrupt(self):
        return self.job.interrupt if self.job is not None else False

    def addObserver(self, observer):
        self.observers.append(observer)

    def removeObserver(self, observer):
        self.observers.remove(observer)
