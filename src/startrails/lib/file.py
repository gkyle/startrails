import os
import time
from enum import Enum
from uuid import uuid4


def extract_file_datetime(path: str) -> float:
    """Extract photo capture datetime from EXIF DateTimeOriginal/DateTime, falling back to os.path.getmtime."""
    if not path:
        return 0.0
    try:
        from PIL import Image
        from PIL.ExifTags import IFD
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                exif_ifd = exif.get_ifd(IFD.Exif)
                dto = exif_ifd.get(36867) or exif.get(306)
                if dto:
                    t = time.strptime(str(dto), "%Y:%m:%d %H:%M:%S")
                    return float(time.mktime(t))
    except Exception:
        pass
    try:
        return float(os.path.getmtime(path))
    except (OSError, TypeError):
        return 0.0


class Unpickle:
    # forces reinitialization of instance during unpickling so that fields that weren't present at pickling time are present at run time.
    def __getstate__(self):
        return super().__getstate__()

    def __setstate__(self, state: dict):
        self.__init__()
        self.__dict__.update(state)


class File(Unpickle):

    def __init__(self, basename=None, path=None, timestamp=None, mtime=None):
        super().__init__()
        self.basename = basename
        self.path = path
        val = mtime if mtime is not None else timestamp
        if val is not None:
            self.mtime = float(val)
        elif path:
            self.mtime = extract_file_datetime(path)
        else:
            self.mtime = 0.0
        self.timestamp = self.mtime

    def get_mtime(self, refresh: bool = False) -> float:
        if (refresh or not getattr(self, "mtime", None)) and self.path:
            self.mtime = extract_file_datetime(self.path)
        m = getattr(self, "mtime", 0.0) or getattr(self, "timestamp", 0.0) or 0.0
        self.mtime = m
        self.timestamp = m
        return m

    def get_timestamp(self, refresh: bool = False) -> float:
        return self.get_mtime(refresh=refresh)


class InputFile(File):

    def __init__(self, basename=None, path=None, timestamp=None, mtime=None):
        super().__init__(basename, path, timestamp=timestamp, mtime=mtime)
        self.sourceId = uuid4().hex
        self.streaksMasks = []
        self.streaksManualMasks = []
        self.streaksManualDeletedMasks = []
        self.activeMaskPoints = []
        self.excludeFromStack = False


class OutputFile(File):

    def __init__(self, basename=None, path=None, operation=None, fadeGradient=None, timestamp=None, mtime=None):
        super().__init__(basename, path, timestamp=timestamp, mtime=mtime)
        self.operation = operation
        self.fadeGradient = fadeGradient
        # Sidecars are relative to this output's directory, never embedded in JSON.
        self.sourceMap = None
        self.sourceStack = None
        self.gapMask = None


class Operation(Enum):
    STACK = 1
    FILL_GAPS = 2
    FILL_GAPS_MASK = 3


class DenoiseInputFile(File):
    """File representation for denoise inputs (star, dark/noise, or flat/vignetting)."""

    def __init__(
        self,
        basename: str | None = None,
        path: str | None = None,
        timestamp: float | None = None,
        mtime: float | None = None,
        file_id: str | None = None,
    ):
        super().__init__(basename=basename, path=path, timestamp=timestamp, mtime=mtime)
        self.file_id = file_id or uuid4().hex
        self.is_reference = False
        self.aligned = False

