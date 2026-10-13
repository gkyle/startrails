"""Flat field calibration."""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import os
from typing import List, Optional
import numpy as np

from startrails.lib.gpu import free_gpu_memory, get_array_module


class FlatCalibrator:
    """Handles flat field integration and division."""

    @classmethod
    def compute_master_flat(
        cls,
        flats: List[np.ndarray],
        master_dark: Optional[np.ndarray] = None,
        use_gpu: bool = True,
        chunk_rows: int = 1024,
    ) -> np.ndarray:
        """Compute master flat frame from list of flat exposures with GPU or multithreading."""
        if not flats:
            raise ValueError("No flat frames provided.")

        h, w = flats[0].shape[:2]
        out = np.zeros_like(flats[0], dtype=np.float32)
        xp, is_gpu = get_array_module(use_gpu=use_gpu)

        if is_gpu:
            try:
                for y in range(0, h, chunk_rows):
                    y_end = min(y + chunk_rows, h)
                    if master_dark is not None:
                        md_chunk = xp.array(master_dark[y:y_end], dtype=xp.float32)
                        chunks = [xp.maximum(xp.array(f[y:y_end], dtype=xp.float32) - md_chunk, 0.0) for f in flats]
                    else:
                        chunks = [xp.array(f[y:y_end], dtype=xp.float32) for f in flats]
                    chunk_gpu = xp.array(chunks, dtype=xp.float32)
                    res_gpu = xp.median(chunk_gpu, axis=0)
                    out[y:y_end] = xp.asnumpy(res_gpu)
                    del chunk_gpu, res_gpu, chunks
            finally:
                free_gpu_memory()
        else:
            chunks = [(y, min(y + chunk_rows, h)) for y in range(0, h, chunk_rows)]
            workers = min(16, os.cpu_count() or 4)

            def _process_chunk(y_range):
                y_s, y_e = y_range
                if master_dark is not None:
                    md_chunk = master_dark[y_s:y_e]
                    c_flats = [np.maximum(f[y_s:y_e] - md_chunk, 0.0) for f in flats]
                else:
                    c_flats = [f[y_s:y_e] for f in flats]
                st = np.stack(c_flats, axis=0)
                return y_s, y_e, np.median(st, axis=0).astype(np.float32)

            if len(chunks) > 1 and workers > 1:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for y_s, y_e, res in pool.map(_process_chunk, chunks):
                        out[y_s:y_e] = res
            else:
                for y_range in chunks:
                    y_s, y_e, res = _process_chunk(y_range)
                    out[y_s:y_e] = res

        sample = out[:: max(1, h // 100), :: max(1, w // 100)]
        norm_val = float(np.median(sample))
        if norm_val > 1e-6:
            out /= norm_val
        return np.maximum(out, 1e-5)

    @staticmethod
    def apply_flat(light: np.ndarray, master_flat: np.ndarray) -> np.ndarray:
        """Apply flat field correction (divide light by normalized flat)."""
        safe_flat = np.maximum(master_flat, 1e-5)
        calibrated = light / safe_flat
        return np.clip(calibrated, 0.0, 1.0).astype(np.float32)
