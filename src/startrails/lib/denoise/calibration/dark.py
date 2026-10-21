"""Calibration support code: dark frame integration and subtraction."""

from __future__ import annotations
from concurrent.futures import CancelledError
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Callable, Optional, Sequence
from zipfile import BadZipFile
import numpy as np

from startrails.lib.gpu import free_gpu_memory, get_array_module
from startrails.lib.image_io import imread, normalize_image
from startrails.lib.denoise.stacking.memmap_buffer import MemmapFrameBuffer, read_frame_chunk

logger = logging.getLogger(__name__)


class DarkCalibrator:
    """Handles dark frame integration and subtraction."""

    @classmethod
    def compute_master_dark_from_paths(
        cls,
        paths: Sequence[Path | str],
        use_gpu: bool = True,
        scratch_dir: Optional[Path | str] = None,
        should_interrupt: Optional[Callable[[], bool]] = None,
        cache_dir: Optional[Path | str] = None,
    ) -> np.ndarray:
        """Reuse a persistent master or integrate one decoded dark at a time.

        The uncompressed cache preserves normalized float32 values exactly. It
        holds only one master per project and is atomically replaced after a
        successful calculation. Cache failures never prevent calibration.
        """
        if not paths:
            raise ValueError("No dark frames provided.")
        cls._check_cancelled(should_interrupt)
        cache_path = Path(cache_dir) / "master_dark.npz" if cache_dir is not None else None
        signature = cls._cache_signature(paths) if cache_path is not None else None
        if cache_path is not None:
            try:
                with np.load(cache_path, allow_pickle=False) as cached:
                    if cached["signature"].item() == signature:
                        master = cached["master"]
                        if master.dtype == np.float32 and master.ndim in (2, 3) and all(master.shape):
                            cls._check_cancelled(should_interrupt)
                            logger.info("Reusing master dark: %s", cache_path)
                            return master
            except FileNotFoundError:
                pass
            except (OSError, ValueError, TypeError, KeyError, EOFError, BadZipFile):
                logger.warning("Cannot read master dark cache %s; rebuilding", cache_path)

        master = cls._integrate_paths(paths, use_gpu, scratch_dir, should_interrupt)
        cls._check_cancelled(should_interrupt)
        if cache_path is not None and cls._cache_signature(paths) == signature:
            temporary = None
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=cache_path.parent, prefix="master_dark_", suffix=".tmp", delete=False) as stream:
                    temporary = Path(stream.name)
                    np.savez(stream, signature=signature, master=master)
                    stream.flush()
                    os.fsync(stream.fileno())
                cls._check_cancelled(should_interrupt)
                temporary.replace(cache_path)
            except OSError:
                logger.warning("Cannot save master dark cache %s", cache_path, exc_info=True)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return master

    @staticmethod
    def _cache_signature(paths: Sequence[Path | str]) -> str:
        # Bump the version when decoding, normalization, or integration changes.
        sources = []
        for path in paths:
            resolved = Path(path).resolve()
            stat = resolved.stat()
            sources.append((str(resolved), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        payload = {"version": 1, "sources": sorted(sources)}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @classmethod
    def _integrate_paths(cls, paths, use_gpu, scratch_dir, should_interrupt):
        first = imread(paths[0], to_rgb=True, as_float=False)
        if len(paths) == 1:
            cls._check_cancelled(should_interrupt)
            return normalize_image(first)
        shape = first.shape
        with MemmapFrameBuffer((len(paths), *shape), np.float32, scratch_dir, prefix="st_dark_") as buffer:
            buffer.write_frame(0, normalize_image(first))
            del first
            for index, path in enumerate(paths[1:], start=1):
                cls._check_cancelled(should_interrupt)
                frame = imread(path, to_rgb=True, as_float=False)
                if frame.shape != shape:
                    raise ValueError(f"Dark frame {path} has shape {frame.shape}; expected {shape}.")
                buffer.write_frame(index, normalize_image(frame))
                del frame
            return cls.compute_master_dark(buffer, use_gpu=use_gpu, should_interrupt=should_interrupt)

    @staticmethod
    def _check_cancelled(should_interrupt):
        if should_interrupt and should_interrupt():
            raise CancelledError("Dark calibration cancelled")

    @classmethod
    def compute_master_dark(
        cls,
        darks: Sequence[np.ndarray] | np.ndarray | MemmapFrameBuffer,
        use_gpu: bool = True,
        chunk_rows: int = 1024,
        should_interrupt: Optional[Callable[[], bool]] = None,
    ) -> np.ndarray:
        """Compute a normalized float32 median, preserving fractional dark values."""
        if len(darks) == 0:
            raise ValueError("No dark frames provided.")
        cls._check_cancelled(should_interrupt)
        if len(darks) == 1:
            first = darks.read_frame(0) if isinstance(darks, MemmapFrameBuffer) else darks[0]
            return normalize_image(first)

        frame_shape = darks.frame_shape if isinstance(darks, MemmapFrameBuffer) else darks[0].shape
        h, w = frame_shape[:2]
        out = np.zeros(frame_shape, dtype=np.float32)
        xp, is_gpu = get_array_module(use_gpu=use_gpu)
        channels = frame_shape[2] if len(frame_shape) == 3 else 1
        # Leave room for the input, median workspace and any GPU upload buffer.
        bytes_per_row = len(darks) * w * channels * np.dtype(np.float32).itemsize * 3
        chunk_rows = max(1, min(chunk_rows, (64 * 1024**2) // bytes_per_row))

        def read_chunk(start, end):
            cls._check_cancelled(should_interrupt)
            chunk = read_frame_chunk(darks, start, end, normalize=True)
            np.clip(chunk, 0.0, 1.0, out=chunk)
            return chunk

        if is_gpu:
            try:
                for y in range(0, h, chunk_rows):
                    cls._check_cancelled(should_interrupt)
                    y_end = min(y + chunk_rows, h)
                    chunk_gpu = xp.asarray(read_chunk(y, y_end))
                    res_gpu = xp.median(chunk_gpu, axis=0)
                    out[y:y_end] = xp.asnumpy(res_gpu)
                    del chunk_gpu, res_gpu
                cls._check_cancelled(should_interrupt)
                return out
            finally:
                free_gpu_memory()

        # Serial chunks prevent CPU count from multiplying peak median memory.
        for start in range(0, h, chunk_rows):
            cls._check_cancelled(should_interrupt)
            end = min(start + chunk_rows, h)
            chunk = read_chunk(start, end)
            out[start:end] = np.median(chunk, axis=0, overwrite_input=True)
            del chunk

        cls._check_cancelled(should_interrupt)
        return out

    @staticmethod
    def subtract_dark(light: np.ndarray, master_dark: np.ndarray, in_place: bool = False) -> np.ndarray:
        """Subtract on a normalized scale, without quantizing calibrated pixels.

        Integer inputs are converted to float32 even when in_place is requested.
        Floating masters are already normalized by compute_master_dark.
        """
        dark = master_dark if np.issubdtype(master_dark.dtype, np.floating) else normalize_image(master_dark)
        if in_place and light.dtype in (np.float32, np.float64):
            result = np.clip(light, 0.0, 1.0, out=light)
        else:
            result = normalize_image(light)
        np.subtract(result, dark, out=result)
        np.maximum(result, 0.0, out=result)
        return result
