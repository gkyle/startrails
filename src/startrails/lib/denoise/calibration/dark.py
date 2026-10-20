"""Calibration support code: dark frame integration and subtraction."""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import os
from typing import List, Optional
import numpy as np

from startrails.lib.gpu import free_gpu_memory, get_array_module


class DarkCalibrator:
    """Handles dark frame integration and subtraction."""

    @classmethod
    def compute_master_dark(
        cls,
        darks: List[np.ndarray],
        use_gpu: bool = True,
        chunk_rows: int = 1024,
    ) -> np.ndarray:
        """Compute master dark frame using median combination with GPU or multithreaded CPU."""
        if not darks:
            raise ValueError("No dark frames provided.")
        if len(darks) == 1:
            return darks[0].copy()

        h, w = darks[0].shape[:2]
        target_dtype = darks[0].dtype
        out = np.zeros_like(darks[0], dtype=target_dtype)
        xp, is_gpu = get_array_module(use_gpu=use_gpu)

        if is_gpu:
            try:
                for y in range(0, h, chunk_rows):
                    y_end = min(y + chunk_rows, h)
                    chunk_gpu = xp.array([d[y:y_end] for d in darks], dtype=xp.float32)
                    res_gpu = xp.median(chunk_gpu, axis=0)
                    if np.issubdtype(target_dtype, np.integer):
                        max_val = np.iinfo(target_dtype).max
                        res_gpu = xp.clip(res_gpu + 0.5, 0, max_val).astype(getattr(xp, target_dtype.name))
                    out[y:y_end] = xp.asnumpy(res_gpu)
                    del chunk_gpu, res_gpu
                return out
            finally:
                free_gpu_memory()

        chunks = [(y, min(y + chunk_rows, h)) for y in range(0, h, chunk_rows)]
        workers = min(16, os.cpu_count() or 4)

        def _process_chunk(y_range):
            y_s, y_e = y_range
            st = np.stack([d[y_s:y_e] for d in darks], axis=0)
            res = np.median(st, axis=0)
            if np.issubdtype(target_dtype, np.integer):
                max_val = np.iinfo(target_dtype).max
                res = np.clip(res + 0.5, 0, max_val).astype(target_dtype)
            else:
                res = res.astype(target_dtype)
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
        """Subtract master dark frame from light frame."""
        import cv2
        if light.dtype == master_dark.dtype and light.dtype in (np.uint8, np.uint16):
            if in_place:
                cv2.subtract(light, master_dark, dst=light)
                return light
            return cv2.subtract(light, master_dark)
        if in_place and light.dtype in (np.float32, np.float64):
            np.subtract(light, master_dark, out=light)
            np.maximum(light, 0.0, out=light)
            return light
        res = np.maximum(light.astype(np.float32) - master_dark.astype(np.float32), 0.0)
        if np.issubdtype(light.dtype, np.integer):
            res = np.clip(res + 0.5, 0, np.iinfo(light.dtype).max)
        return res.astype(light.dtype)
