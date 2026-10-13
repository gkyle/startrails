"""Freeze Ground selective stacking algorithm with seamless boundary blending."""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import os
from typing import Any, List, Optional
import cv2
import numpy as np

from startrails.lib.denoise.enhancement.horizon_denoiser import HorizonDenoiser
from startrails.lib.denoise.io.mask import MaskHandler
from startrails.lib.gpu import (
    free_gpu_memory,
    get_array_module,
    get_optimal_chunk_rows,
)
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor


class FreezeGroundStacker:
    """Combines tracked/aligned sky stacking with stationary landscape ground stacking."""

    @classmethod
    def stack(
        cls,
        aligned_sky_frames: List[np.ndarray],
        sky_coverages: Optional[List[np.ndarray]],
        raw_ground_frames: List[np.ndarray],
        sky_mask: np.ndarray,
        use_multiband_blend: bool = False,
        feather_radius: float = 3.0,
        denoise_horizon_band: bool = False,
        horizon_denoise_radius: int = 7,
        horizon_denoise_eps: float = 2e-3,
        horizon_denoise_strength: float = 0.2,
        horizon_blend_percent: float = 60.0,
        unwarped_blend_percent: Optional[float] = None,
        horizon_blur_radius: float = 2.0,
        enable_horizon_corrections: bool = True,
        horizon_color_denoise_strength: Optional[float] = None,
        horizon_value_denoise_strength: Optional[float] = None,
        stack_method: str = "sigma_clipped",
        sigma_clip_threshold: float = 1.2,
        sigma_clip_iterations: int = 3,
        use_gpu: bool = True,
        max_workers: Optional[int] = None,
        profiler: Optional[Any] = None,
    ) -> np.ndarray:
        """Execute Freeze Ground selective stacking.

        Args:
            aligned_sky_frames: List of frames warped into sky celestial alignment
            sky_coverages: Coverage masks for warped sky frames
            raw_ground_frames: List of stationary un-warped frames
            sky_mask: 2D float32 array (H, W) where 1.0 = Sky and 0.0 = Ground
            use_multiband_blend: Whether to use multi-resolution Laplacian pyramid blending (default False)
            feather_radius: Gaussian blur radius for boundary anti-aliasing (default 3.0)
            denoise_horizon_band: Whether to polish horizon transition band with guided filter
            horizon_denoise_radius: Radius for guided filter
            horizon_denoise_eps: Regularization epsilon for guided filter
            horizon_denoise_strength: Strength multiplier for guided filter (default: 0.2)
            horizon_blend_percent: Maximum percentage of unwarped sky included in blend (0-100%, default: 60.0)
            unwarped_blend_percent: Alias for horizon_blend_percent
            horizon_blur_radius: Gaussian blur radius applied to foreground sky input (default: 2.0)
            enable_horizon_corrections: Whether all horizon gradient adjustments are enabled (default: True)
            horizon_color_denoise_strength: Optional multiplier for chrominance smoothing
            horizon_value_denoise_strength: Optional multiplier for luminance smoothing
            stack_method: Stacking algorithm ('sigma_clipped' or 'mean')
            sigma_clip_threshold: Standard deviations for outlier rejection in sigma-clipped mode
            sigma_clip_iterations: Outlier rejection iterations
            use_gpu: whether to use GPU acceleration if available (default: True)
            max_workers: thread count for CPU fallback
            profiler: optional latency profiler to record stage measurements

        Returns:
            stacked_image: Composite image with razor-sharp stars and razor-sharp ground
        """
        compositor = cls.stack_base_and_prepare_compositor(
            aligned_sky_frames=aligned_sky_frames,
            sky_coverages=sky_coverages,
            raw_ground_frames=raw_ground_frames,
            sky_mask=sky_mask,
            feather_radius=feather_radius,
            horizon_denoise_radius=horizon_denoise_radius,
            horizon_denoise_eps=horizon_denoise_eps,
            stack_method=stack_method,
            sigma_clip_threshold=sigma_clip_threshold,
            sigma_clip_iterations=sigma_clip_iterations,
            use_gpu=use_gpu,
            max_workers=max_workers,
            profiler=profiler,
        )
        blend_pct = unwarped_blend_percent if unwarped_blend_percent is not None else horizon_blend_percent
        if profiler is not None:
            with profiler.measure("4c. Sky-Ground Blending"):
                return compositor.composite(
                    horizon_blend_percent=blend_pct,
                    horizon_denoise_strength=horizon_denoise_strength,
                    denoise_enabled=denoise_horizon_band,
                    horizon_blur_radius=horizon_blur_radius,
                    enable_corrections=enable_horizon_corrections,
                    horizon_color_denoise_strength=horizon_color_denoise_strength,
                    horizon_value_denoise_strength=horizon_value_denoise_strength,
                )
        return compositor.composite(
            horizon_blend_percent=blend_pct,
            horizon_denoise_strength=horizon_denoise_strength,
            denoise_enabled=denoise_horizon_band,
            horizon_blur_radius=horizon_blur_radius,
            enable_corrections=enable_horizon_corrections,
            horizon_color_denoise_strength=horizon_color_denoise_strength,
            horizon_value_denoise_strength=horizon_value_denoise_strength,
        )

    @classmethod
    def stack_base_and_prepare_compositor(
        cls,
        aligned_sky_frames: List[np.ndarray],
        sky_coverages: Optional[List[np.ndarray]],
        raw_ground_frames: List[np.ndarray],
        sky_mask: np.ndarray,
        feather_radius: float = 3.0,
        horizon_denoise_radius: int = 5,
        horizon_denoise_eps: float = 1e-3,
        stack_method: str = "sigma_clipped",
        sigma_clip_threshold: float = 1.2,
        sigma_clip_iterations: int = 3,
        use_gpu: bool = True,
        max_workers: Optional[int] = None,
        profiler: Optional[Any] = None,
    ) -> HorizonCompositor:
        """Stack base sky and ground frames and assemble real-time HorizonCompositor."""
        backend_label = "GPU" if use_gpu else "CPU"

        # 1. Stack sky region (aligned frames)
        if profiler is not None:
            with profiler.measure(f"4a. Sky Region Stacking ({backend_label})"):
                sky_stack = cls.stack_frames(
                    aligned_sky_frames,
                    coverages=sky_coverages,
                    method=stack_method,
                    sigma_threshold=sigma_clip_threshold,
                    iterations=sigma_clip_iterations,
                    use_gpu=use_gpu,
                    max_workers=max_workers,
                )
        else:
            sky_stack = cls.stack_frames(
                aligned_sky_frames,
                coverages=sky_coverages,
                method=stack_method,
                sigma_threshold=sigma_clip_threshold,
                iterations=sigma_clip_iterations,
                use_gpu=use_gpu,
                max_workers=max_workers,
            )

        # 2. Stack ground region (stationary un-warped frames)
        if profiler is not None:
            with profiler.measure(f"4b. Ground Region Stacking ({backend_label})"):
                ground_stack = cls.stack_frames(
                    raw_ground_frames,
                    coverages=None,
                    method=stack_method,
                    sigma_threshold=sigma_clip_threshold,
                    iterations=sigma_clip_iterations,
                    use_gpu=use_gpu,
                    max_workers=max_workers,
                )
        else:
            ground_stack = cls.stack_frames(
                raw_ground_frames,
                coverages=None,
                method=stack_method,
                sigma_threshold=sigma_clip_threshold,
                iterations=sigma_clip_iterations,
                use_gpu=use_gpu,
                max_workers=max_workers,
            )


        # Ensure any pixel with 0 sky coverage falls back to ground stack
        if sky_coverages is not None and len(sky_coverages) > 0:
            total_sky_cov = np.sum(sky_coverages, axis=0)
            if sky_stack.ndim == 3:
                sky_stack = np.where(total_sky_cov[..., None] > 0, sky_stack, ground_stack)
            else:
                sky_stack = np.where(total_sky_cov > 0, sky_stack, ground_stack)

        # Compute gradient mask from frame coverages
        if sky_coverages is not None and len(sky_coverages) > 0 and sky_mask is not None:
            edge_mask = MaskHandler.compute_gradient_mask(sky_coverages, sky_mask=sky_mask)
        else:
            h, w = sky_stack.shape[:2]
            edge_mask = np.zeros((h, w), dtype=np.float32)

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
    def _pyramid_blend(
        cls,
        img_sky: np.ndarray,
        img_ground: np.ndarray,
        mask: np.ndarray,
        levels: Optional[int] = None,
    ) -> np.ndarray:
        """Laplacian pyramid multi-band blending to eliminate seam halos along horizon."""
        h, w = img_sky.shape[:2]
        if levels is None:
            min_dim = min(h, w)
            levels = max(1, min(5, int(np.floor(np.log2(min_dim))) - 3))

        # Pad image to multiples of 2^levels
        pad_h = ((1 << levels) - (h % (1 << levels))) % (1 << levels)
        pad_w = ((1 << levels) - (w % (1 << levels))) % (1 << levels)

        if pad_h > 0 or pad_w > 0:
            img_sky = cv2.copyMakeBorder(img_sky, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT)
            img_ground = cv2.copyMakeBorder(img_ground, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT)
            mask = cv2.copyMakeBorder(mask, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT)

        if mask.ndim == 2 and img_sky.ndim == 3:
            mask = mask[..., None]

        # Build Gaussian pyramid for mask
        mask_pyr = [mask.astype(np.float32)]
        for _ in range(levels):
            mask_pyr.append(cv2.pyrDown(mask_pyr[-1]))

        # Build Laplacian pyramids for sky and ground
        def _get_laplacian_pyramid(img: np.ndarray):
            gp = [img.astype(np.float32)]
            for _ in range(levels):
                gp.append(cv2.pyrDown(gp[-1]))

            lp = [gp[levels]]
            for i in range(levels, 0, -1):
                size = (gp[i - 1].shape[1], gp[i - 1].shape[0])
                expanded = cv2.pyrUp(gp[i], dstsize=size)
                laplacian = gp[i - 1] - expanded
                lp.append(laplacian)
            return lp

        sky_lp = _get_laplacian_pyramid(img_sky)
        ground_lp = _get_laplacian_pyramid(img_ground)

        # Combine pyramids using mask pyramid
        blended_lp = []
        blended_lp.append(
            mask_pyr[levels] * sky_lp[0] + (1.0 - mask_pyr[levels]) * ground_lp[0]
        )

        for i in range(1, levels + 1):
            mask_level = mask_pyr[levels - i]
            blended_lp.append(
                mask_level * sky_lp[i] + (1.0 - mask_level) * ground_lp[i]
            )

        # Reconstruct from Laplacian pyramid
        reconstructed = blended_lp[0]
        for i in range(1, levels + 1):
            size = (blended_lp[i].shape[1], blended_lp[i].shape[0])
            reconstructed = cv2.pyrUp(reconstructed, dstsize=size) + blended_lp[i]

        # Crop back to original dimensions
        if pad_h > 0 or pad_w > 0:
            reconstructed = reconstructed[:h, :w]

        return np.clip(reconstructed, 0.0, 1.0).astype(np.float32)

    @classmethod
    def stack_frames(
        cls,
        frames: List[np.ndarray],
        coverages: Optional[List[np.ndarray]] = None,
        chunk_rows: Optional[int] = None,
        method: str = "sigma_clipped",
        sigma_threshold: float = 1.2,
        iterations: int = 3,
        use_gpu: bool = True,
        max_workers: Optional[int] = None,
    ) -> np.ndarray:
        """Stack a list of image frames using weighted/masked average or sigma-clipped mean.

        Args:
            frames: list of N float32 arrays of shape (H, W, C) or (H, W)
            coverages: optional list of N boolean or float masks (H, W) where True/weight > 0 = valid pixel
            chunk_rows: rows to process at a time (default: auto-computed based on memory)
            method: stacking algorithm ('sigma_clipped' or 'mean')
            sigma_threshold: standard deviation multiplier for outlier rejection (default: 1.2)
            iterations: sigma-clipping iterations (default: 3)
            use_gpu: whether to use CuPy GPU acceleration if available (default: True)
            max_workers: thread count for CPU fallback (default: min(16, cpu_count))

        Returns:
            stacked_image: float32 array of shape (H, W, C) or (H, W)
        """
        n_frames = len(frames)
        if n_frames == 0:
            raise ValueError("No frames to stack.")
        if n_frames == 1:
            return frames[0].copy()

        h, w = frames[0].shape[:2]
        is_rgb = (frames[0].ndim == 3)
        channels = frames[0].shape[2] if is_rgb else 1

        out_shape = (h, w, channels) if is_rgb else (h, w)
        stacked = np.zeros(out_shape, dtype=np.float32)

        xp, is_gpu = get_array_module(use_gpu=use_gpu)

        # Determine optimal chunk rows
        if chunk_rows is None:
            chunk_rows = get_optimal_chunk_rows(
                height=h,
                width=w,
                num_frames=n_frames,
                channels=channels,
                use_gpu=is_gpu,
                default_cpu_rows=256,
            )

        is_soft_weights = (
            coverages is not None
            and len(coverages) > 0
            and coverages[0].dtype != bool
            and np.issubdtype(coverages[0].dtype, np.floating)
        )

        # -------------------------------------------------------------
        # Path A: GPU Acceleration (CuPy)
        # -------------------------------------------------------------
        if is_gpu:
            try:
                for y_start in range(0, h, chunk_rows):
                    y_end = min(y_start + chunk_rows, h)

                    if is_rgb:
                        chunk_stack = xp.array([f[y_start:y_end, :, :] for f in frames], dtype=xp.float32)
                    else:
                        chunk_stack = xp.array([f[y_start:y_end, :] for f in frames], dtype=xp.float32)

                    if coverages is not None:
                        if is_soft_weights:
                            weight_stack = xp.array([c[y_start:y_end, :] for c in coverages], dtype=xp.float32)
                            if is_rgb:
                                weight_stack = xp.repeat(weight_stack[..., None], channels, axis=-1)
                            mask_stack = weight_stack > 1e-4
                        else:
                            weight_stack = None
                            mask_stack = xp.array([c[y_start:y_end, :] for c in coverages], dtype=bool)
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
            finally:
                free_gpu_memory()

        # -------------------------------------------------------------
        # Path B: Multithreaded CPU Fallback (NumPy)
        # -------------------------------------------------------------
        else:
            workers = max_workers or min(16, max(1, (os.cpu_count() or 1)))

            chunks = []
            for y_start in range(0, h, chunk_rows):
                y_end = min(y_start + chunk_rows, h)
                if is_rgb:
                    c_stack = np.array([f[y_start:y_end, :, :] for f in frames], dtype=np.float32)
                else:
                    c_stack = np.array([f[y_start:y_end, :] for f in frames], dtype=np.float32)

                if coverages is not None:
                    if is_soft_weights:
                        c_weights = np.array([c[y_start:y_end, :] for c in coverages], dtype=np.float32)
                        if is_rgb:
                            c_weights = np.repeat(c_weights[..., None], channels, axis=-1)
                        c_mask = c_weights > 1e-4
                    else:
                        c_weights = None
                        c_mask = np.array([c[y_start:y_end, :] for c in coverages], dtype=bool)
                        if is_rgb:
                            c_mask = np.repeat(c_mask[..., None], channels, axis=-1)
                else:
                    c_weights = None
                    c_mask = np.ones_like(c_stack, dtype=bool)

                chunks.append((y_start, y_end, c_stack, c_mask, c_weights))

            def _process_chunk_task(item):
                y_s, y_e, data, mask, w_arr = item
                if method == "sigma_clipped":
                    res = cls._sigma_clipped_chunk(
                        data,
                        mask,
                        weights=w_arr,
                        sigma_threshold=sigma_threshold,
                        iterations=iterations,
                        xp=np,
                    )
                else:
                    res = cls._average_chunk(
                        data,
                        mask,
                        weights=w_arr,
                        xp=np,
                    )
                return y_s, y_e, res

            if len(chunks) > 1 and workers > 1:
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    for y_s, y_e, chunk_res in executor.map(_process_chunk_task, chunks):
                        if is_rgb:
                            stacked[y_s:y_e, :, :] = chunk_res
                        else:
                            stacked[y_s:y_e, :] = chunk_res
            else:
                for item in chunks:
                    y_s, y_e, chunk_res = _process_chunk_task(item)
                    if is_rgb:
                        stacked[y_s:y_e, :, :] = chunk_res
                    else:
                        stacked[y_s:y_e, :] = chunk_res

        return stacked

    @staticmethod
    def _sigma_clipped_chunk(
        data: Any,
        valid_mask: Any,
        weights: Optional[Any] = None,
        sigma_threshold: float = 1.2,
        iterations: int = 3,
        xp: Any = np,
    ) -> Any:
        """Perform iterative sigma-clipping outlier rejection and accumulation on chunk data."""
        n_frames = data.shape[0]
        if n_frames < 3:
            return FreezeGroundStacker._average_chunk(data, valid_mask, weights=weights, xp=xp)

        curr_mask = valid_mask.copy()
        for _ in range(max(1, iterations)):
            counts = xp.maximum(xp.sum(curr_mask, axis=0), 1)
            if weights is not None:
                w = xp.where(curr_mask, weights, 0.0)
                w_sum = xp.maximum(xp.sum(w, axis=0), 1e-8)
                mean = xp.sum(w * data, axis=0) / w_sum
                diff = xp.where(curr_mask, data - mean[None, ...], 0.0)
                var = xp.sum(w * diff * diff, axis=0) / w_sum
            else:
                sum_d = xp.sum(xp.where(curr_mask, data, 0.0), axis=0)
                mean = sum_d / counts
                diff = xp.where(curr_mask, data - mean[None, ...], 0.0)
                var = xp.sum(diff * diff, axis=0) / counts

            std = xp.maximum(xp.sqrt(xp.maximum(var, 0.0)), 1e-6)
            abs_diff = xp.abs(data - mean[None, ...])
            is_outlier = abs_diff > (sigma_threshold * std[None, ...])

            # Safety fallback: preserve at least 2 valid frames at every coordinate
            remaining_counts = xp.sum(curr_mask & ~is_outlier, axis=0)
            safe_outlier = is_outlier & (remaining_counts[None, ...] >= 2)

            if not bool(xp.any(safe_outlier)):
                break

            curr_mask = curr_mask & ~safe_outlier

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

