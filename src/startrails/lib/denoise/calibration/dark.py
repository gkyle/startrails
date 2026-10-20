"""Calibration support code: dark frame integration and subtraction."""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import os
from typing import List, Optional
import numpy as np

from startrails.lib.gpu import free_gpu_memory, get_array_module
from startrails.lib.image_io import normalize_image


class DarkCalibrator:
    """Handles dark frame integration and subtraction."""

    @classmethod
    def compute_master_dark(
        cls,
        darks: List[np.ndarray],
        use_gpu: bool = True,
        chunk_rows: int = 1024,
    ) -> np.ndarray:
        """Compute a normalized float32 median, preserving fractional dark values."""
        if not darks:
            raise ValueError("No dark frames provided.")
        if len(darks) == 1:
            return normalize_image(darks[0])

        h, w = darks[0].shape[:2]
        out = np.zeros_like(darks[0], dtype=np.float32)
        xp, is_gpu = get_array_module(use_gpu=use_gpu)

        if is_gpu:
            try:
                for y in range(0, h, chunk_rows):
                    y_end = min(y + chunk_rows, h)
                    chunk_gpu = xp.asarray(np.stack([normalize_image(d[y:y_end]) for d in darks]))
                    res_gpu = xp.median(chunk_gpu, axis=0)
                    out[y:y_end] = xp.asnumpy(res_gpu)
                    del chunk_gpu, res_gpu
                return out
            finally:
                free_gpu_memory()

        chunks = [(y, min(y + chunk_rows, h)) for y in range(0, h, chunk_rows)]
        workers = min(16, os.cpu_count() or 4)

        def _process_chunk(y_range):
            y_s, y_e = y_range
            st = np.stack([normalize_image(d[y_s:y_e]) for d in darks], axis=0)
            res = np.median(st, axis=0).astype(np.float32)
            return y_s, y_e, res

        if len(chunks) > 1 and workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for y_s, y_e, res in pool.map(_process_chunk, chunks):
                    out[y_s:y_e] = res
        else:
            for y_range in chunks:
                y_s, y_e, res = _process_chunk(y_range)
                out[y_s:y_e] = res

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
