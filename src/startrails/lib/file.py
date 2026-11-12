import os
import time
from enum import Enum
from uuid import uuid4
import weakref


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


OP_STACKED_KEEP = "Stacked Keep"
OP_STACKED_REMOVE = "Stacked"
STACKED_OPERATIONS = (OP_STACKED_REMOVE, OP_STACKED_KEEP)
OP_FILL_GAPS = "FillGaps"
OP_FILL_GAPS_MASK = "FillGapsMask"

STACKED_REMOVE_STEM = "startrails-stacked"
STACKED_KEEP_STEM = "startrails-stacked-keep"
FINAL_OUTPUT_STEM = "startrails-final"
FINAL_MASK_STEM = "startrails-final-mask"

OUTPUT_STEMS_BY_OPERATION = {
    OP_STACKED_REMOVE: STACKED_REMOVE_STEM,
    OP_STACKED_KEEP: STACKED_KEEP_STEM,
    OP_FILL_GAPS: FINAL_OUTPUT_STEM,
    OP_FILL_GAPS_MASK: FINAL_MASK_STEM,
}


def _output_stem(file: OutputFile) -> str:
    # The on-disk path is authoritative; a stale display basename must not decide identity.
    return os.path.splitext(os.path.basename(file.path))[0]


def _existing_outputs(outputs) -> list[OutputFile]:
    """Return output records whose file exists; selection never prefers missing files."""
    existing = []
    for file in outputs:
        if not isinstance(file, OutputFile):
            continue
        path = file.path
        if path and os.path.isfile(path):
            existing.append(file)
    return existing


def _last_match(outputs, predicate) -> OutputFile | None:
    """Return the newest record in project order that satisfies predicate."""
    return next((f for f in reversed(outputs) if predicate(f)), None)


def preferred_stacked_output(outputs) -> OutputFile | None:
    """Return the preferred existing stacked output.

    Canonical file stems outrank legacy operation labels, so a legacy
    ``operation="Stacked"`` record cannot shadow an existing canonical keep.
    Legacy records fall back newest-first instead of using the first entry.
    """
    existing = _existing_outputs(outputs)
    for stem in (STACKED_REMOVE_STEM, STACKED_KEEP_STEM):
        match = _last_match(existing, lambda f, stem=stem: _output_stem(f) == stem)
        if match is not None:
            return match
    return _last_match(existing, lambda f: f.operation in STACKED_OPERATIONS)


def filled_output(outputs) -> OutputFile | None:
    """Return the preferred existing Fill Gaps image, never a mask or missing record."""
    existing = [
        f
        for f in _existing_outputs(outputs)
        if f.operation != OP_FILL_GAPS_MASK and _output_stem(f) != FINAL_MASK_STEM
    ]
    match = _last_match(existing, lambda f: _output_stem(f) == FINAL_OUTPUT_STEM)
    if match is not None:
        return match
    return _last_match(existing, lambda f: f.operation == OP_FILL_GAPS)


class DenoiseInputFile(File):
    """File representation for denoise inputs (star or dark/noise frames)."""

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
        self._project_ref = None
        self.aligned = False

    def bind_project(self, project):
        self._project_ref = weakref.ref(project)

    @property
    def is_reference(self):
        project = self._project_ref() if self._project_ref is not None else None
        return project is not None and project.get_reference_file() is self

    def __getstate__(self):
        return {name: value for name, value in self.__dict__.items()
                if name not in ("_project_ref", "is_reference")}
