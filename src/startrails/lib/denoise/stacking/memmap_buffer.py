"""Cross-platform memory-mapped frame storage on disk."""

from __future__ import annotations
import atexit
import gc
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

_ACTIVE_SCRATCH_FILES = set()


def _cleanup_all():
    for p in list(_ACTIVE_SCRATCH_FILES):
        try:
            if p.exists():
                p.unlink(missing_ok=True)
        except Exception:
            pass
    _ACTIVE_SCRATCH_FILES.clear()


atexit.register(_cleanup_all)


class MemmapFrameBuffer:
    """Temporary disk-backed memory-mapped array for stacking operations.

    Allows processing datasets of arbitrary size with constant RAM usage.
    - On Windows: explicitly closes underlying _mmap handle and triggers garbage
      collection before unlinking to prevent file lock PermissionErrors.
    - Context manager and atexit handler ensure scratch files are always cleaned up,
      even on cancellation, exceptions, or unexpected exit.
    """

    def __init__(
        self,
        shape: Tuple[int, ...],
        dtype: np.dtype,
        scratch_dir: Optional[Path | str] = None,
        prefix: str = "startrails_mmap_",
    ):
        target_dir = None
        if scratch_dir is not None:
            p = Path(scratch_dir).resolve()
            if p.is_dir() and os.access(str(p), os.W_OK):
                target_dir = str(p)

        if target_dir is None:
            target_dir = tempfile.gettempdir()

        fd, name = tempfile.mkstemp(prefix=prefix, suffix=".raw", dir=target_dir)
        os.close(fd)
        self.filepath: Optional[Path] = Path(name)
        _ACTIVE_SCRATCH_FILES.add(self.filepath)
        self.shape = shape
        self.dtype = np.dtype(dtype)
        self.mmap: Optional[np.memmap] = np.memmap(
            str(self.filepath),
            dtype=self.dtype,
            mode="w+",
            shape=self.shape,
        )

    def close(self) -> None:
        """Close the memory map and delete the temporary file."""
        if hasattr(self, "mmap") and self.mmap is not None:
            try:
                self.mmap.flush()
            except Exception:
                pass
            # On Windows, explicitly close the mmap handle before unlinking
            if hasattr(self.mmap, "_mmap") and self.mmap._mmap is not None:
                try:
                    self.mmap._mmap.close()
                except Exception:
                    pass
            self.mmap = None

        if os.name == "nt":
            gc.collect()

        if hasattr(self, "filepath") and self.filepath is not None:
            _ACTIVE_SCRATCH_FILES.discard(self.filepath)
            for _ in range(5):
                try:
                    if self.filepath.exists():
                        self.filepath.unlink(missing_ok=True)
                    break
                except Exception:
                    time.sleep(0.05)
            self.filepath = None

    def __enter__(self) -> "MemmapFrameBuffer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
