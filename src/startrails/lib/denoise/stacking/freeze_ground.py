"""Freeze Ground selective stacking algorithm with seamless boundary blending."""

from __future__ import annotations
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import nullcontext
import os
from pathlib import Path
from typing import Any, Callable, List, Optional
import numpy as np

from startrails.lib.denoise.alignment.warper import ImageWarper
from startrails.lib.denoise.enhancement.horizon_denoiser import HorizonDenoiser
from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.denoise.stacking.disk_buffer import DiskFrameBuffer, read_frame_chunk
from startrails.lib.gpu import (
    free_gpu_memory,
    get_array_module,
    get_optimal_chunk_rows,
)
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor
from startrails.lib.image_io import imread, normalize_image
from startrails.lib.profiler import PipelineProfiler
from startrails.lib.project_denoise import DenoiseProject

_CPU_STACK_BYTES_PER_ROW = 48
_GPU_STACK_BYTES_PER_ROW = 96
_MIN_SIGMA_CLIP_FRAMES = 3

ProgressData = dict[str, Any]
ProgressCallback = Callable[[int, Optional[ProgressData]], None]
CancelCheck = Callable[[], bool]


class FreezeGroundStacker:
    """Combines tracked/aligned sky stacking with stationary landscape ground stacking."""

    @classmethod
    def _stack_region(
        cls,
        frames: List[np.ndarray] | np.ndarray | DiskFrameBuffer,
        coverages: Optional[List[np.ndarray] | np.ndarray | DiskFrameBuffer],
        *,
        stage_name: str,
        stage_key: str,
        total_frames: int,
        backend_label: str,
        method: str,
        sigma_threshold: float,
        iterations: int,
        use_gpu: bool,
        max_workers: Optional[int],
        profiler: Optional[PipelineProfiler],
        progress_callback: Optional[ProgressCallback],
        should_interrupt: Optional[CancelCheck],
    ) -> Optional[np.ndarray]:
        def report(increment: int, data: Optional[ProgressData] = None) -> None:
            if progress_callback is None:
                return
            progress_data: ProgressData = {"stage": stage_key, "total": total_frames}
            if data:
                progress_data.update(data)
            progress_callback(increment, progress_data)

        measurement = (
            profiler.measure(f"{stage_name} ({backend_label})")
            if profiler is not None
            else nullcontext()
        )
        with measurement:
            return cls.stack_frames(
                frames,
                coverages=coverages,
                method=method,
                sigma_threshold=sigma_threshold,
                iterations=iterations,
                use_gpu=use_gpu,
                max_workers=max_workers,
                progress_callback=report,
                should_interrupt=should_interrupt,
            )

    @staticmethod
    def _prepare_compositor(
        sky_stack: np.ndarray,
        ground_stack: np.ndarray,
        coverage_counts: Optional[np.ndarray],
        coverage_frame_count: int,
        sky_mask: Optional[np.ndarray],
        *,
        feather_radius: float,
        horizon_denoise_radius: int,
        horizon_denoise_eps: float,
    ) -> HorizonCompositor:
        if coverage_counts is not None:
            if sky_stack.ndim == 3:
                sky_stack = np.where(coverage_counts[..., None] > 0, sky_stack, ground_stack)
            else:
                sky_stack = np.where(coverage_counts > 0, sky_stack, ground_stack)
            edge_mask = MaskHandler.compute_gradient_mask_from_counts(
                coverage_counts,
                n_frames=float(coverage_frame_count),
                sky_mask=sky_mask,
            )
        else:
            edge_mask = np.zeros(sky_stack.shape[:2], dtype=np.float32)

        return HorizonCompositor(
            sky_stack=sky_stack,
            ground_stack=ground_stack,
            gradient_mask=edge_mask,
            sky_mask=sky_mask,
            feather_radius=feather_radius,
            denoise_radius=horizon_denoise_radius,
            denoise_eps=horizon_denoise_eps,
        )

    @classmethod
    def stack_base_and_prepare_compositor(
        cls,
        aligned_sky_frames: Optional[List[np.ndarray]] = None,
        sky_coverages: Optional[List[np.ndarray]] = None,
        raw_ground_frames: Optional[List[np.ndarray]] = None,
        sky_mask: Optional[np.ndarray] = None,
        *,
        feather_radius: float,
        horizon_denoise_radius: int,
        horizon_denoise_eps: float,
        stack_method: str,
        sigma_clip_threshold: float,
        sigma_clip_iterations: int,
        use_gpu: bool,
        max_workers: Optional[int],
        profiler: Optional[PipelineProfiler] = None,
        progress_callback: Optional[ProgressCallback] = None,
        should_interrupt: Optional[CancelCheck] = None,
        config: Optional[DenoiseProject] = None,
        scratch_dir: Optional[Path | str] = None,
        calibrate_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    ) -> Optional[HorizonCompositor]:
        """Stack base sky and ground frames and assemble real-time HorizonCompositor.

        Supports both pre-loaded frame lists (legacy/test path) and on-demand disk-backed
        staging via DiskFrameBuffer when config is provided.
        """
        backend_label = "GPU" if use_gpu else "CPU"

        # -----------------------------------------------------------------
        # Branch A: Disk-backed on-demand staging (never more than 1 file in RAM)
        # -----------------------------------------------------------------
        if (aligned_sky_frames is None or len(aligned_sky_frames) == 0) and config is not None:
            star_images = config.star_images
            n_stars = len(star_images)
            if n_stars == 0:
                raise ValueError("No star images provided in configuration.")

            from startrails.op.denoise.align_stars import AlignStars
            base_path = AlignStars.get_base_image_path(config)
            if calibrate_fn is None:
                calibrate_fn = AlignStars.prepare_calibrator(
                    config, should_interrupt=should_interrupt, scratch_dir=scratch_dir,
                )

            sample = imread(base_path, to_rgb=True, as_float=False)
            h, w = sample.shape[:2]
            is_rgb = (sample.ndim == 3)
            channels = sample.shape[2] if is_rgb else 1
            buf_shape = (n_stars, h, w, channels) if is_rgb else (n_stars, h, w)
            del sample

            if sky_mask is None and (
                config.mask_path or config.mask_array is not None
            ):
                sky_mask = MaskHandler.create_mask(
                    shape=(h, w),
                    mask_path=config.mask_path,
                    mask_array=config.mask_array,
                )

            if scratch_dir is None:
                if config.output_path:
                    scratch_dir = Path(config.output_path).resolve().parent
                elif config.sky_stack_path:
                    scratch_dir = Path(config.sky_stack_path).resolve().parent

            # 1. Sky Staging & Stacking
            is_tapered = bool(config.taper_mask_edges and config.mask_taper_pixels > 0)
            cov_dtype = np.float32 if is_tapered else bool
            total_sky_cov = np.zeros((h, w), dtype=np.float32)

            with DiskFrameBuffer(buf_shape, dtype=np.float32, scratch_dir=scratch_dir, prefix="st_sky_") as sky_buf, \
                 DiskFrameBuffer((n_stars, h, w), dtype=cov_dtype, scratch_dir=scratch_dir, prefix="st_cov_") as cov_buf:
                for idx, p in enumerate(star_images):
                    if should_interrupt and should_interrupt():
                        return None
                    p_resolved = Path(p).resolve()
                    frame_raw = imread(p_resolved, to_rgb=True, as_float=False)
                    frame_cal = calibrate_fn(frame_raw)
                    del frame_raw
                    frame_float = normalize_image(frame_cal)
                    del frame_cal

                    matrix = config.homographies.get(p_resolved)
                    if matrix is None and p_resolved == base_path:
                        matrix = np.eye(2, 3, dtype=np.float32)

                    if matrix is None:
                        warped = frame_float.copy()
                        coverage = np.zeros((h, w), dtype=bool)
                    else:
                        warped, in_bounds = ImageWarper.warp(frame_float, matrix, (h, w))
                        if sky_mask is not None:
                            warped_mask = ImageWarper.warp_mask(
                                sky_mask.astype(np.float32), matrix, (h, w)
                            )
                            coverage = in_bounds & (warped_mask > 0.5)
                        else:
                            coverage = in_bounds

                    if is_tapered:
                        coverage = ImageWarper.compute_tapered_mask(
                            coverage, taper_radius=float(config.mask_taper_pixels)
                        )

                    sky_buf.write_frame(idx, warped)
                    cov_buf.write_frame(idx, coverage)
                    total_sky_cov += coverage.astype(np.float32)
                    del frame_float, warped, coverage

                    if progress_callback is not None:
                        progress_callback(1, {"stage": "sky_warp", "index": idx + 1, "total": n_stars, "filename": Path(p).name, "desc": f"Warping sky frame {idx + 1}/{n_stars}: {Path(p).name}"})

                sky_stack = cls._stack_region(
                    sky_buf,
                    cov_buf,
                    stage_name="4a. Sky Region Stacking",
                    stage_key="sky",
                    total_frames=n_stars,
                    backend_label=backend_label,
                    method=stack_method,
                    sigma_threshold=sigma_clip_threshold,
                    iterations=sigma_clip_iterations,
                    use_gpu=use_gpu,
                    max_workers=max_workers,
                    profiler=profiler,
                    progress_callback=progress_callback,
                    should_interrupt=should_interrupt,
                )

            if sky_stack is None or (should_interrupt and should_interrupt()):
                return None

            # 2. Ground Staging & Stacking
            # A common normalized scale preserves mixed input bit depths and
            # fractional calibrated values without quantizing to the base dtype.
            with DiskFrameBuffer(buf_shape, dtype=np.float32, scratch_dir=scratch_dir, prefix="st_ground_") as ground_buf:
                for idx, p in enumerate(star_images):
                    if should_interrupt and should_interrupt():
                        return None
                    p_resolved = Path(p).resolve()
                    frame_raw = imread(p_resolved, to_rgb=True, as_float=False)
                    frame_cal = calibrate_fn(frame_raw)
                    del frame_raw
                    ground_buf.write_frame(idx, normalize_image(frame_cal))
                    del frame_cal

                    if progress_callback is not None:
                        progress_callback(1, {"stage": "ground_load", "index": idx + 1, "total": n_stars, "filename": Path(p).name, "desc": f"Reading ground frame {idx + 1}/{n_stars}: {Path(p).name}"})

                ground_stack = cls._stack_region(
                    ground_buf,
                    None,
                    stage_name="4b. Ground Region Stacking",
                    stage_key="ground",
                    total_frames=n_stars,
                    backend_label=backend_label,
                    method=stack_method,
                    sigma_threshold=sigma_clip_threshold,
                    iterations=sigma_clip_iterations,
                    use_gpu=use_gpu,
                    max_workers=max_workers,
                    profiler=profiler,
                    progress_callback=progress_callback,
                    should_interrupt=should_interrupt,
                )

            if ground_stack is None or (should_interrupt and should_interrupt()):
                return None

            return cls._prepare_compositor(
                sky_stack,
                ground_stack,
                total_sky_cov,
                n_stars,
                sky_mask,
                feather_radius=feather_radius,
                horizon_denoise_radius=horizon_denoise_radius,
                horizon_denoise_eps=horizon_denoise_eps,
            )

        # -----------------------------------------------------------------
        # Branch B: In-memory pre-loaded lists (legacy/test path)
        # -----------------------------------------------------------------
        sky_frames = aligned_sky_frames or []
        n_sky = len(sky_frames)
        sky_stack = cls._stack_region(
            sky_frames,
            sky_coverages,
            stage_name="4a. Sky Region Stacking",
            stage_key="sky",
            total_frames=n_sky,
            backend_label=backend_label,
            method=stack_method,
            sigma_threshold=sigma_clip_threshold,
            iterations=sigma_clip_iterations,
            use_gpu=use_gpu,
            max_workers=max_workers,
            profiler=profiler,
            progress_callback=progress_callback,
            should_interrupt=should_interrupt,
        )

        if sky_stack is None or (should_interrupt and should_interrupt()):
            return None

        # Immediately release aligned sky frames to reclaim gigabytes of memory
        sky_frames.clear()

        ground_frames = raw_ground_frames or []
        n_ground = len(ground_frames)
        ground_stack = cls._stack_region(
            ground_frames,
            None,
            stage_name="4b. Ground Region Stacking",
            stage_key="ground",
            total_frames=n_ground,
            backend_label=backend_label,
            method=stack_method,
            sigma_threshold=sigma_clip_threshold,
            iterations=sigma_clip_iterations,
            use_gpu=use_gpu,
            max_workers=max_workers,
            profiler=profiler,
            progress_callback=progress_callback,
            should_interrupt=should_interrupt,
        )

        if ground_stack is None or (should_interrupt and should_interrupt()):
            return None

        # Immediately release raw ground frames to reclaim gigabytes of memory
        ground_frames.clear()

        coverage_counts = (
            np.sum(sky_coverages, axis=0)
            if sky_coverages is not None and len(sky_coverages) > 0
            else None
        )
        coverage_frame_count = len(sky_coverages) if sky_coverages is not None else 0
        if sky_coverages is not None:
            sky_coverages.clear()

        return cls._prepare_compositor(
            sky_stack,
            ground_stack,
            coverage_counts,
            coverage_frame_count,
            sky_mask,
            feather_radius=feather_radius,
            horizon_denoise_radius=horizon_denoise_radius,
            horizon_denoise_eps=horizon_denoise_eps,
        )

    @classmethod
    def stack_frames(
        cls,
        frames: List[np.ndarray] | np.ndarray | DiskFrameBuffer,
        coverages: Optional[List[np.ndarray] | np.ndarray | DiskFrameBuffer] = None,
        chunk_rows: Optional[int] = None,
        *,
        method: str,
        sigma_threshold: float,
        iterations: int,
        use_gpu: bool,
        max_workers: Optional[int],
        progress_callback: Optional[ProgressCallback] = None,
        should_interrupt: Optional[CancelCheck] = None,
        memory_budget_bytes: int = 256 * 1024**2,
    ) -> Optional[np.ndarray]:
        """Stack a list of image frames using weighted/masked average or sigma-clipped mean.

        Args:
            frames: disk-backed storage or N arrays of shape (H, W, C) or (H, W)
            coverages: optional list of N boolean or float masks (H, W) where True/weight > 0 = valid pixel
            chunk_rows: rows to process at a time (default: auto-computed based on memory)
            method: stacking algorithm ('sigma_clipped' or 'mean')
            sigma_threshold: standard deviation multiplier for outlier rejection
            iterations: sigma-clipping iterations
            use_gpu: whether to use CuPy GPU acceleration if available
            max_workers: CPU threads; None selects up to 4, bounded by the scratch budget
            progress_callback: optional callback receiving (increment, data_dict) per frame
            should_interrupt: optional callable returning True if cancelled
            memory_budget_bytes: estimated scratch budget across active workers;
                excludes full-frame outputs and has a minimum of one row per worker

        Returns:
            stacked_image: float32 array of shape (H, W, C) or (H, W) or None if interrupted
        """
        if method not in ("sigma_clipped", "mean"):
            raise ValueError(f"Unsupported stacking method: {method}")
        n_frames = len(frames)
        if n_frames == 0:
            raise ValueError("No frames to stack.")
        if n_frames == 1:
            if progress_callback is not None:
                progress_callback(1, {"frame_idx": 1, "total_frames": 1})
            f0 = frames.read_frame(0) if isinstance(frames, DiskFrameBuffer) else frames[0]
            if np.issubdtype(f0.dtype, np.integer):
                return normalize_image(f0)
            return f0.copy() if f0.dtype == np.float32 else f0.astype(np.float32)

        frame_shape = frames.frame_shape if isinstance(frames, DiskFrameBuffer) else frames[0].shape
        h, w = frame_shape[:2]
        is_rgb = len(frame_shape) == 3
        channels = frame_shape[2] if is_rgb else 1

        out_shape = (h, w, channels) if is_rgb else (h, w)
        stacked = np.zeros(out_shape, dtype=np.float32)

        xp, is_gpu = get_array_module(use_gpu=use_gpu)
        workers = max_workers or min(4, max(1, (os.cpu_count() or 1)))
        if memory_budget_bytes <= 0:
            raise ValueError("memory_budget_bytes must be positive.")

        # Determine optimal chunk rows and ensure at least n_frames chunks for granular progress
        if chunk_rows is None:
            chunk_rows = get_optimal_chunk_rows(
                height=h,
                width=w,
                num_frames=n_frames,
                channels=channels,
                use_gpu=is_gpu,
                default_cpu_rows=256,
            )
            if not is_gpu:
                # Small input tiles keep sigma-clipping workspaces cache-friendly.
                tile_rows = max(1, (4 * 1024**2) // (n_frames * w * channels * 4))
                chunk_rows = min(chunk_rows, tile_rows)
        if n_frames > 1 and chunk_rows > max(1, h // n_frames):
            chunk_rows = max(1, h // n_frames)
        # CPU sigma clipping reuses its float64 differences and broadcasts weights.
        # Bound scratch across workers even when callers request large chunks.
        bytes_per_row = n_frames * w * channels * (
            _GPU_STACK_BYTES_PER_ROW if is_gpu else _CPU_STACK_BYTES_PER_ROW
        )
        max_in_flight = 1 if is_gpu else max(1, min(workers, memory_budget_bytes // bytes_per_row))
        budget_rows = max(1, memory_budget_bytes // (max_in_flight * bytes_per_row))
        chunk_rows = max(1, min(chunk_rows, budget_rows))

        if coverages is not None:
            if hasattr(coverages, "dtype"):
                is_soft_weights = (coverages.dtype != bool) and np.issubdtype(coverages.dtype, np.floating)
            elif len(coverages) > 0:
                is_soft_weights = (coverages[0].dtype != bool) and np.issubdtype(coverages[0].dtype, np.floating)
            else:
                is_soft_weights = False
        else:
            is_soft_weights = False

        progress_state = {"reported": 0}

        def _emit_frame_progress(completed_count: int, total_count: int):
            if progress_callback is None or total_count <= 0:
                return
            target = min(n_frames, int(completed_count * n_frames / total_count))
            cur = progress_state["reported"]
            if target > cur:
                for step in range(cur + 1, target + 1):
                    progress_callback(1, {"frame_idx": step, "total_frames": n_frames})
                progress_state["reported"] = target

        # -------------------------------------------------------------
        # Path A: GPU Acceleration (CuPy)
        # -------------------------------------------------------------
        if is_gpu:
            try:
                y_starts = list(range(0, h, chunk_rows))
                total_chunks = len(y_starts)
                chunk_idx = 0
                for y_start in y_starts:
                    if should_interrupt and should_interrupt():
                        return None
                    y_end = min(y_start + chunk_rows, h)

                    raw_chunk = read_frame_chunk(frames, y_start, y_end, normalize=True)
                    chunk_stack = xp.asarray(raw_chunk)
                    del raw_chunk

                    if coverages is not None:
                        if is_soft_weights:
                            raw_cov = read_frame_chunk(coverages, y_start, y_end)
                            weight_stack = xp.asarray(raw_cov)
                            del raw_cov
                            if is_rgb:
                                weight_stack = xp.repeat(weight_stack[..., None], channels, axis=-1)
                            mask_stack = weight_stack > 1e-4
                        else:
                            weight_stack = None
                            raw_cov = read_frame_chunk(coverages, y_start, y_end, dtype=bool)
                            mask_stack = xp.asarray(raw_cov)
                            del raw_cov
                            if is_rgb:
                                mask_stack = xp.repeat(mask_stack[..., None], channels, axis=-1)
                    else:
                        weight_stack = None
                        mask_stack = xp.ones_like(chunk_stack, dtype=bool)

                    if method == "sigma_clipped":
                        chunk_result = cls._sigma_clipped_chunk(
                            chunk_stack,
                            mask_stack,
                            weights=weight_stack,
                            sigma_threshold=sigma_threshold,
                            iterations=iterations,
                            xp=xp,
                        )
                    else:
                        chunk_result = cls._average_chunk(
                            chunk_stack,
                            mask_stack,
                            weights=weight_stack,
                            xp=xp,
                        )

                    if is_rgb:
                        stacked[y_start:y_end, :, :] = xp.asnumpy(chunk_result)
                    else:
                        stacked[y_start:y_end, :] = xp.asnumpy(chunk_result)

                    del chunk_stack, mask_stack, chunk_result
                    if weight_stack is not None:
                        del weight_stack
                    chunk_idx += 1
                    _emit_frame_progress(chunk_idx, total_chunks)
            finally:
                free_gpu_memory()

        # -------------------------------------------------------------
        # Path B: Multithreaded CPU Fallback (NumPy)
        # -------------------------------------------------------------
        else:
            chunk_ranges = iter(
                (y_start, min(y_start + chunk_rows, h))
                for y_start in range(0, h, chunk_rows)
            )

            def _process_chunk_task(row_range):
                y_s, y_e = row_range
                data = read_frame_chunk(frames, y_s, y_e, normalize=True)

                if coverages is not None:
                    if is_soft_weights:
                        weights = read_frame_chunk(coverages, y_s, y_e)
                        if is_rgb:
                            weights = weights[..., None]
                        mask = weights > 1e-4
                    else:
                        weights = None
                        mask = read_frame_chunk(coverages, y_s, y_e, dtype=bool)
                        if is_rgb:
                            mask = mask[..., None]
                else:
                    weights = None
                    mask = np.ones_like(data, dtype=bool)
                if method == "sigma_clipped":
                    res = cls._sigma_clipped_chunk(
                        data,
                        mask,
                        weights=weights,
                        sigma_threshold=sigma_threshold,
                        iterations=iterations,
                        xp=np,
                    )
                else:
                    res = cls._average_chunk(
                        data,
                        mask,
                        weights=weights,
                        xp=np,
                    )
                return y_s, y_e, res

            total_chunks = (h + chunk_rows - 1) // chunk_rows
            chunk_idx = 0
            if total_chunks > 1 and max_in_flight > 1:
                with ThreadPoolExecutor(max_workers=max_in_flight) as executor:
                    pending = set()
                    for _ in range(max_in_flight):
                        row_range = next(chunk_ranges, None)
                        if row_range is not None:
                            pending.add(executor.submit(_process_chunk_task, row_range))

                    while pending:
                        completed, pending = wait(pending, return_when=FIRST_COMPLETED)
                        for future in completed:
                            if should_interrupt and should_interrupt():
                                return None
                            y_s, y_e, chunk_res = future.result()
                            if is_rgb:
                                stacked[y_s:y_e, :, :] = chunk_res
                            else:
                                stacked[y_s:y_e, :] = chunk_res
                            chunk_idx += 1
                            _emit_frame_progress(chunk_idx, total_chunks)

                            row_range = next(chunk_ranges, None)
                            if row_range is not None:
                                pending.add(executor.submit(_process_chunk_task, row_range))
            else:
                for row_range in chunk_ranges:
                    if should_interrupt and should_interrupt():
                        return None
                    y_s, y_e, chunk_res = _process_chunk_task(row_range)
                    if is_rgb:
                        stacked[y_s:y_e, :, :] = chunk_res
                    else:
                        stacked[y_s:y_e, :] = chunk_res
                    chunk_idx += 1
                    _emit_frame_progress(chunk_idx, total_chunks)

        if progress_callback is not None:
            cur = progress_state["reported"]
            if cur < n_frames:
                for step in range(cur + 1, n_frames + 1):
                    progress_callback(1, {"frame_idx": step, "total_frames": n_frames})
                progress_state["reported"] = n_frames

        return stacked

    @staticmethod
    def _sigma_clipped_chunk(
        data: Any,
        valid_mask: Any,
        weights: Optional[Any] = None,
        *,
        sigma_threshold: float,
        iterations: int,
        xp: Any = np,
    ) -> Any:
        """Perform iterative sigma-clipping outlier rejection and accumulation on chunk data."""
        n_frames = data.shape[0]
        if n_frames < _MIN_SIGMA_CLIP_FRAMES or (xp is np and not np.any(valid_mask)):
            # Empty coverage cannot reject any samples; retain the average's
            # handling of nonfinite values without running a clipping iteration.
            return FreezeGroundStacker._average_chunk(data, valid_mask, weights=weights, xp=xp)

        curr_mask = np.broadcast_to(valid_mask, data.shape).copy() if xp is np else valid_mask.copy()
        for _ in range(max(1, iterations)):
            if weights is not None:
                w = xp.where(curr_mask, weights, 0.0)
                w_sum = xp.maximum(xp.sum(w, axis=0), 1e-8)
                mean = xp.sum(w * data, axis=0) / w_sum
            else:
                counts = xp.maximum(xp.sum(curr_mask, axis=0), 1)
                sum_d = xp.sum(xp.where(curr_mask, data, 0.0), axis=0)
                mean = sum_d / counts

            if xp is np:
                diff = np.where(curr_mask, data - mean[None, ...], 0.0)
                if weights is not None:
                    # Preserve the original (w * diff) * diff evaluation order.
                    # w is no longer needed after its sum and mean were computed.
                    work = w if w.dtype == diff.dtype else np.empty_like(diff)
                    np.multiply(w, diff, out=work)
                    np.multiply(work, diff, out=work)
                    var = np.sum(work, axis=0) / w_sum
                    del work
                else:
                    np.square(diff, out=diff)
                    var = np.sum(diff, axis=0) / counts
            else:
                diff = xp.where(curr_mask, data - mean[None, ...], 0.0)
                if weights is not None:
                    var = xp.sum(w * diff * diff, axis=0) / w_sum
                else:
                    var = xp.sum(diff * diff, axis=0) / counts

            std = xp.maximum(xp.sqrt(xp.maximum(var, 0.0)), 1e-6)
            if xp is np:
                np.subtract(data, mean[None, ...], out=diff)
                np.abs(diff, out=diff)
                is_outlier = diff > (sigma_threshold * std[None, ...])
            else:
                abs_diff = xp.abs(data - mean[None, ...])
                is_outlier = abs_diff > (sigma_threshold * std[None, ...])

            # Safety fallback: preserve at least 2 valid frames at every coordinate
            remaining_counts = xp.sum(curr_mask & ~is_outlier, axis=0)
            safe_outlier = is_outlier & (remaining_counts[None, ...] >= 2)

            if not bool(xp.any(safe_outlier)):
                break

            curr_mask &= ~safe_outlier

        # Final average on surviving frames
        if weights is not None:
            active_weights = xp.where(curr_mask, weights, 0.0)
            sum_w = xp.sum(active_weights, axis=0)
            safe_sum_w = xp.maximum(sum_w, 1e-8)
            final = xp.sum(active_weights * data, axis=0) / safe_sum_w
        else:
            counts = xp.maximum(xp.sum(curr_mask, axis=0), 1)
            final = xp.sum(xp.where(curr_mask, data, 0.0), axis=0) / counts

        return final.astype(xp.float32)

    @staticmethod
    def _average_chunk(
        data: Any,
        valid_mask: Any,
        weights: Optional[Any] = None,
        xp: Any = np,
    ) -> Any:
        """Perform weighted/masked average accumulation on a 4D (N, H, W, C) or 3D (N, H, W) data block using xp."""
        if weights is not None:
            active_weights = xp.where(valid_mask, weights, 0.0)
            sum_w = xp.sum(active_weights, axis=0)
            safe_sum_w = xp.maximum(sum_w, 1e-8)
            final_mean = xp.sum(active_weights * data, axis=0) / safe_sum_w
        else:
            counts = xp.maximum(xp.sum(valid_mask, axis=0), 1)
            final_mean = xp.sum(xp.where(valid_mask, data, 0.0), axis=0) / counts

        return final_mean.astype(xp.float32)
