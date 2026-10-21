"""Temporary frame storage with bounded buffered file I/O."""

from __future__ import annotations

import atexit
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
    """Disk-backed frames using bounded transfers and independent reader handles.

    The historical class name is retained for callers. No file pages are mapped
    into the process. Transfers and dtype conversions use at most window_bytes
    (or one image row); reads return owned arrays. Writers sync once per frame
    to bound dirty-data accumulation. Decoded images, returned chunks and the
    operating system's file cache have separate memory costs.
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

    def _check_index(self, index: int) -> None:
        if self.filepath is None:
            raise ValueError("Frame storage is closed.")
        if not 0 <= index < len(self):
            raise IndexError("Frame index out of range.")

    @staticmethod
    def _read_exact(stream, array: np.ndarray) -> None:
        remaining = memoryview(array).cast("B")
        while remaining:
            count = stream.readinto(remaining)
            if not count:
                raise OSError("Unexpected end of frame storage.")
            remaining = remaining[count:]

    def write_frame(self, index: int, frame: np.ndarray) -> None:
        """Write bounded windows without retaining caller-owned data."""
        self._check_index(index)
        if frame.shape != self.frame_shape:
            raise ValueError(f"Frame has shape {frame.shape}; expected {self.frame_shape}.")
        with open(self.filepath, "r+b", buffering=0) as stream:
            stream.seek(index * self._frame_bytes)
            for start in range(0, self.frame_shape[0], self._window_rows):
                end = min(start + self._window_rows, self.frame_shape[0])
                window = np.ascontiguousarray(frame[start:end], dtype=self.dtype)
                remaining = memoryview(window).cast("B")
                while remaining:
                    count = stream.write(remaining)
                    if not count:
                        raise OSError("Could not write frame storage.")
                    remaining = remaining[count:]
            os.fsync(stream.fileno())

    def _read_into(self, stream, index: int, start: int, end: int, destination: np.ndarray) -> None:
        stream.seek(index * self._frame_bytes + start * self._row_bytes)
        for row in range(start, end, self._window_rows):
            stop = min(row + self._window_rows, end)
            target = destination[row - start:stop - start]
            if target.dtype == self.dtype:
                self._read_exact(stream, target)
            else:
                window = np.empty(target.shape, dtype=self.dtype)
                self._read_exact(stream, window)
                target[:] = window

    def read_frame(self, index: int) -> np.ndarray:
        """Return an owned copy of one frame."""
        self._check_index(index)
        result = np.empty(self.frame_shape, dtype=self.dtype)
        with open(self.filepath, "rb", buffering=0) as stream:
            self._read_into(stream, index, 0, self.frame_shape[0], result)
        return result

    def read_rows(self, start: int, end: int, dtype=None) -> np.ndarray:
        """Return an owned, contiguous (N, rows, W[, C]) chunk."""
        if not 0 <= start < end <= self.frame_shape[0]:
            raise ValueError("Invalid frame row range.")
        self._check_index(0)
        result = np.empty((len(self), end - start, *self.frame_shape[1:]), dtype=dtype or self.dtype)
        with open(self.filepath, "rb", buffering=0) as stream:
            for index in range(len(self)):
                self._read_into(stream, index, start, end, result[index])
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
