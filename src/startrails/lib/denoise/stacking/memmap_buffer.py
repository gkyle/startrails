"""Temporary frame storage with bounded, short-lived memory mappings."""

from __future__ import annotations

import atexit
from contextlib import contextmanager
import logging
from math import prod
import os
from pathlib import Path
import tempfile
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)
_ACTIVE_SCRATCH_FILES: set[Path] = set()


def _cleanup_all():
    for path in list(_ACTIVE_SCRATCH_FILES):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue
        _ACTIVE_SCRATCH_FILES.discard(path)


atexit.register(_cleanup_all)


class MemmapFrameBuffer:
    """Disk-backed frames without a persistent mapping of the entire stack.

    Each I/O operation maps at most window_bytes (or one image row), copies its
    pixels and closes the mapping before moving on. Reads return owned arrays,
    never views into closed mappings. Concurrent readers use independent maps.
    Resident mappings are bounded independently of frame count; decoded images,
    returned chunks and the operating system's file cache have separate costs.
    Context-manager cleanup closes scratch storage on completion or cancellation.
    """

    def __init__(
        self,
        shape: tuple[int, ...],
        dtype: np.dtype,
        scratch_dir: Optional[Path | str] = None,
        prefix: str = "startrails_mmap_",
        window_bytes: int = 8 * 1024**2,
    ):
        self.filepath: Optional[Path] = None
        self.shape = tuple(int(size) for size in shape)
        if len(self.shape) not in (3, 4) or any(size <= 0 for size in self.shape):
            raise ValueError("Frame storage requires positive (N, H, W[, C]) dimensions.")
        if window_bytes <= 0:
            raise ValueError("window_bytes must be positive.")
        self.dtype = np.dtype(dtype)
        if self.dtype.hasobject:
            raise ValueError("Frame storage requires a numeric dtype.")
        self.frame_shape = self.shape[1:]
        self._row_bytes = prod(self.frame_shape[1:]) * self.dtype.itemsize
        self._frame_bytes = self.frame_shape[0] * self._row_bytes
        self._window_rows = max(1, int(window_bytes) // self._row_bytes)

        target_dir = Path(scratch_dir).resolve() if scratch_dir is not None else Path(tempfile.gettempdir())
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=prefix, suffix=".raw", dir=target_dir)
        self.filepath = Path(name)
        _ACTIVE_SCRATCH_FILES.add(self.filepath)
        try:
            os.ftruncate(fd, self.shape[0] * self._frame_bytes)
        except BaseException:
            os.close(fd)
            self.close()
            raise
        else:
            os.close(fd)

    def __len__(self) -> int:
        return self.shape[0]

    @contextmanager
    def _mapped_window(self, index: int, start: int, end: int, write: bool = False):
        if self.filepath is None:
            raise ValueError("Frame storage is closed.")
        if not 0 <= index < len(self):
            raise IndexError("Frame index out of range.")
        mapped = np.memmap(
            self.filepath, dtype=self.dtype, mode="r+" if write else "r",
            offset=index * self._frame_bytes + start * self._row_bytes,
            shape=(end - start, *self.frame_shape[1:]),
        )
        try:
            yield mapped
            if write:
                mapped.flush()
        finally:
            mapped._mmap.close()

    def write_frame(self, index: int, frame: np.ndarray) -> None:
        """Copy a frame into bounded mappings; no caller-owned data is retained."""
        if frame.shape != self.frame_shape:
            raise ValueError(f"Frame has shape {frame.shape}; expected {self.frame_shape}.")
        for start in range(0, self.frame_shape[0], self._window_rows):
            end = min(start + self._window_rows, self.frame_shape[0])
            with self._mapped_window(index, start, end, write=True) as mapped:
                mapped[:] = frame[start:end]

    def _read_into(self, index: int, start: int, end: int, destination: np.ndarray) -> None:
        for row in range(start, end, self._window_rows):
            stop = min(row + self._window_rows, end)
            with self._mapped_window(index, row, stop) as mapped:
                destination[row - start:stop - start] = mapped

    def read_frame(self, index: int) -> np.ndarray:
        """Return an owned copy of one frame."""
        result = np.empty(self.frame_shape, dtype=self.dtype)
        self._read_into(index, 0, self.frame_shape[0], result)
        return result

    def read_rows(self, start: int, end: int, dtype=None) -> np.ndarray:
        """Return an owned, contiguous (N, rows, W[, C]) chunk."""
        if not 0 <= start < end <= self.frame_shape[0]:
            raise ValueError("Invalid frame row range.")
        result = np.empty((len(self), end - start, *self.frame_shape[1:]), dtype=dtype or self.dtype)
        for index in range(len(self)):
            self._read_into(index, start, end, result[index])
        return result

    def close(self) -> None:
        """Delete scratch storage after all readers have finished."""
        path = self.filepath
        if path is None:
            return
        for attempt in range(5):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                if attempt < 4:
                    time.sleep(0.05)
            else:
                _ACTIVE_SCRATCH_FILES.discard(path)
                self.filepath = None
                return
        # Keep failed removals registered for a later cleanup attempt.
        logger.warning("Could not remove denoise scratch file %s", path)

    def __enter__(self) -> MemmapFrameBuffer:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()


def read_frame_chunk(frames, start: int, end: int, dtype=np.float32, normalize: bool = False) -> np.ndarray:
    """Copy rows from disk storage or existing arrays, optionally scaling integers.

    Floating-point warped pixels retain their interpolation overshoot. Normalize
    each source independently so legacy lists can also contain mixed bit depths.
    """
    if isinstance(frames, MemmapFrameBuffer):
        chunk = frames.read_rows(start, end, dtype=dtype)
        if normalize and np.issubdtype(frames.dtype, np.integer):
            chunk /= np.iinfo(frames.dtype).max
            np.clip(chunk, 0.0, 1.0, out=chunk)
        return chunk
    chunk = np.empty((len(frames), end - start, *frames[0].shape[1:]), dtype=dtype)
    for index, frame in enumerate(frames):
        chunk[index] = frame[start:end]
        if normalize and np.issubdtype(frame.dtype, np.integer):
            chunk[index] /= np.iinfo(frame.dtype).max
            np.clip(chunk[index], 0.0, 1.0, out=chunk[index])
    return chunk
