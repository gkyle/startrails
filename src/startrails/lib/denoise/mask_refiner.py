"""Content-aware sky mask refinement using local color and luminance contrast."""

from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from threading import Event
from typing import Callable, Optional
import cv2
import numpy as np

from startrails.lib.denoise.defaults import DENOISE_DEFAULTS
from startrails.lib.image_io import rgb_luminance

logger = logging.getLogger(__name__)

_DENSE_REFINEMENT_READ_FRACTION = 0.6


class MaskRefiner:
    """Refines rough user-drawn sky masks by snapping boundary edges to natural physical horizons."""

    @staticmethod
    def _refinement_regions(uncertain, fixed_sky, core_sky, guided_radius, blur_window, tile_size=512):
        """Select output tiles; every filter reads a halo beyond these rectangles."""
        active = uncertain.astype(np.uint8)
        guided_halo = 2 * (guided_radius // 2)
        if guided_radius:
            # A guided filter preserves constant masks. Only uncertain values and
            # transitions between known sky/ground can affect nearby outputs.
            boundary = cv2.morphologyEx(
                fixed_sky.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)
            )
            active |= boundary
            kernel = np.ones((2 * guided_halo + 1, 2 * guided_halo + 1), np.uint8)
            active = cv2.dilate(active, kernel)
            active[core_sky] = 0

        h, w = active.shape
        halo = blur_window // 2 + guided_halo
        regions = []
        read_pixels = 0
        for y in range(0, h, tile_size):
            bottom = min(h, y + tile_size)
            run_start = None
            for x in range(0, w, tile_size):
                right = min(w, x + tile_size)
                occupied = np.any(active[y:bottom, x:right])
                if occupied and run_start is None:
                    run_start = x
                if run_start is not None and (not occupied or right == w):
                    end = right if occupied else x
                    dx, dy, width, height = cv2.boundingRect(active[y:bottom, run_start:end])
                    left, top = run_start + dx, y + dy
                    end, lower = left + width, top + height
                    regions.append((left, top, end, lower))
                    read_pixels += (
                        (min(w, end + halo) - max(0, left - halo))
                        * (min(h, lower + halo) - max(0, top - halo))
                    )
                    run_start = None

        # Dense masks are cheaper as one region, using the same filter code.
        if read_pixels >= h * w * _DENSE_REFINEMENT_READ_FRACTION:
            return [(0, 0, w, h)]
        return regions

    @staticmethod
    def _refine_region(channels, sky_weight, ground_weight, core_sky, sky_holes,
                       fallback_colors, blur_window, guided_radius):
        """Evaluate local filters on a region including its dependency halo."""
        sky_safe = np.maximum(cv2.boxFilter(sky_weight, -1, (blur_window, blur_window)), 1e-4)
        ground_safe = np.maximum(cv2.boxFilter(ground_weight, -1, (blur_window, blur_window)), 1e-4)
        sky_distance = np.zeros(core_sky.shape, dtype=np.float32)
        ground_distance = np.zeros(core_sky.shape, dtype=np.float32)
        weighted = np.empty(core_sky.shape, dtype=np.result_type(channels[0].dtype, np.float32))
        for channel, fallbacks in zip(channels, fallback_colors):
            for weights, safe, fallback, distance in (
                (sky_weight, sky_safe, fallbacks[0], sky_distance),
                (ground_weight, ground_safe, fallbacks[1], ground_distance),
            ):
                np.multiply(channel, weights, out=weighted)
                mean = cv2.boxFilter(weighted, -1, (blur_window, blur_window))
                np.divide(mean, safe, out=mean)
                mean[safe <= 1e-4] = fallback
                np.subtract(channel, mean, out=mean)
                np.square(mean, out=mean)
                distance += mean
        np.sqrt(sky_distance, out=sky_distance)
        np.sqrt(ground_distance, out=ground_distance)
        sky_distance += ground_distance
        sky_distance += 1e-6
        probability = np.divide(ground_distance, sky_distance, out=ground_distance)
        refined = np.where(core_sky, 1.0, np.where(sky_holes, 1.0, np.where(ground_weight > 0.5, 0.0, probability)))
        del weighted, mean, sky_safe, ground_safe, sky_distance, ground_distance, probability
        del weights, safe, distance

        if guided_radius:
            guide = channels[-1]
            window = (guided_radius, guided_radius)
            mean_guide = cv2.boxFilter(guide, -1, window)
            mean_mask = cv2.boxFilter(refined, -1, window)
            mean_product = cv2.boxFilter(guide * refined, -1, window)
            covariance = mean_product - mean_guide * mean_mask
            variance = cv2.boxFilter(guide * guide, -1, window) - mean_guide * mean_guide
            slope = covariance / (variance + 1e-3)
            intercept = mean_mask - slope * mean_guide
            filtered = cv2.boxFilter(slope, -1, window) * guide + cv2.boxFilter(intercept, -1, window)
            refined = np.where(core_sky, 1.0, filtered)
        return refined

    @classmethod
    def refine(
        cls,
        image: np.ndarray,
        rough_mask: np.ndarray,
        search_radius: Optional[int] = DENOISE_DEFAULTS.mask_search_radius,
        blur_window: Optional[int] = None,
        edge_alignment: bool = True,
        smooth_radius: float = 2.0,
        erosion_pixels: int = DENOISE_DEFAULTS.mask_erosion_pixels,
        foliage_protection: bool = DENOISE_DEFAULTS.mask_foliage_protection,
        as_bool: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        should_interrupt: Optional[Callable[[], bool]] = None,
    ) -> Optional[np.ndarray]:
        """Refine a rough sky mask to match true physical image boundaries.

        Args:
            image: float32 image array of shape (H, W, 3) or (H, W) in [0.0, 1.0]
            rough_mask: 2D array (H, W) where ~1.0 is Sky and ~0.0 is Ground
            search_radius: pixel radius of the uncertain boundary ribbon (default: adaptive based on image size)
            blur_window: neighborhood window for local color propagation (default: max(31, radius * 4 + 1))
            edge_alignment: whether to lock boundary to physical image gradients via guided filter
            smooth_radius: subpixel anti-aliasing feather radius
            progress_callback: receives (completed, total) regions on the calling thread,
                initially with completed=0 after global preparation.
            should_interrupt: optional cancellation check on the calling thread.

        Returns:
            Refined 2D mask, or None if cancelled.
        """
        if should_interrupt and should_interrupt():
            return None
        h, w = image.shape[:2]
        if rough_mask.shape[:2] != (h, w):
            raise ValueError(f"Mask shape {rough_mask.shape} does not match image shape {image.shape[:2]}")

        bin_m = (rough_mask > 0.5).astype(np.uint8)

        sky_sum = int(np.sum(bin_m))
        total_pixels = h * w
        if sky_sum == 0 or sky_sum == total_pixels:
            if progress_callback:
                progress_callback(0, 0)
            if should_interrupt and should_interrupt():
                return None
            bool_m = bin_m > 0
            if as_bool:
                return bool_m
            return bool_m.astype(np.float32)

        if search_radius is None:
            search_radius = max(20, min(80, int(round(max(h, w) * 0.006))))
        radius = max(3, search_radius)

        if blur_window is None:
            blur_window = max(31, radius * 4 + 1)
        if blur_window % 2 == 0:
            blur_window += 1

        # 1. Define Trimap around rough mask boundary
        scale = max(1, radius // 12)
        if scale > 1:
            sw, sh = w // scale, h // scale
            small_m = cv2.resize(bin_m, (sw, sh), interpolation=cv2.INTER_NEAREST)
            r_small = max(2, radius // scale)
            k_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r_small * 2 + 1, r_small * 2 + 1))
            e_small = cv2.erode(small_m, k_small)
            d_small = cv2.dilate(small_m, k_small)
            def_sky = cv2.resize(e_small, (w, h), interpolation=cv2.INTER_NEAREST).astype(np.float32)
            dilated_m = cv2.resize(d_small, (w, h), interpolation=cv2.INTER_NEAREST).astype(np.float32)
        else:
            k_search = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
            def_sky = cv2.erode(bin_m, k_search).astype(np.float32)
            dilated_m = cv2.dilate(bin_m, k_search).astype(np.float32)

        # 2. Keep guidance channels as views rather than a full RGB+luminance copy.
        if image.ndim == 3 and image.shape[2] == 3:
            lum = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            rgb = image
            channels = (*np.moveaxis(image, -1, 0), lum)
        else:
            lum = image[..., 0] if image.ndim == 3 else image
            rgb = np.broadcast_to(lum[..., None], (h, w, 3))
            channels = (lum,) * 4

        if should_interrupt and should_interrupt():
            return None
        # 3. Fit smooth 2D spatial sky background surface model from core sky
        s_scale = min(8, max(1, min(h, w) // 30))
        s_h, s_w = max(4, h // s_scale), max(4, w // s_scale)
        s_rgb = cv2.resize(rgb, (s_w, s_h))
        s_sky = cv2.resize(def_sky, (s_w, s_h), interpolation=cv2.INTER_NEAREST) > 0.5

        ys, xs = np.where(s_sky)
        if len(xs) >= 6:
            flat_x = np.mgrid[0:s_h, 0:s_w][1].ravel()
            flat_y = np.mgrid[0:s_h, 0:s_w][0].ravel()
            if len(xs) >= 20:
                X = np.column_stack([np.ones_like(xs), xs, ys, xs**2, xs*ys, ys**2, xs**3, (xs**2)*ys, xs*(ys**2), ys**3])
                X_full = np.column_stack([np.ones_like(flat_x), flat_x, flat_y, flat_x**2, flat_x*flat_y, flat_y**2, flat_x**3, (flat_x**2)*flat_y, flat_x*(flat_y**2), flat_y**3])
            else:
                X = np.column_stack([np.ones_like(xs), xs, ys, xs**2, xs*ys, ys**2])
                X_full = np.column_stack([np.ones_like(flat_x), flat_x, flat_y, flat_x**2, flat_x*flat_y, flat_y**2])

            # All color channels share the same design matrix and decomposition.
            coefficients, _, _, _ = np.linalg.lstsq(X, s_rgb[ys, xs], rcond=None)
            pred_rgb = np.empty((h, w, 3), dtype=np.float32)
            for c in range(3):
                pred_c = (X_full @ coefficients[:, c]).reshape(s_h, s_w)
                pred_rgb[..., c] = cv2.resize(pred_c, (w, h))

            # Bound temporary RGB differences without changing per-pixel arithmetic.
            diff_rgb = np.empty((h, w), dtype=np.result_type(image.dtype, np.float32))
            pred_lum = np.empty((h, w), dtype=np.float32)
            for row in range(0, h, 128):
                rows = slice(row, row + 128)
                predicted = pred_rgb[rows]
                diff_rgb[rows] = np.linalg.norm(rgb[rows] - predicted, axis=-1)
                pred_lum[rows] = rgb_luminance(predicted)
            del predicted, pred_rgb, pred_c, X, X_full
            lum_ratio = lum / np.maximum(pred_lum, 1e-4)

            # Porous vegetation / canopy sky gap detection
            dist_from_sky = cv2.distanceTransform((1 - bin_m).astype(np.uint8), cv2.DIST_L2, 5)
            reach = max(int(radius * 2.5), min(100, int(max(h, w) * 0.025)))
            sky_holes = (bin_m == 0) & (dist_from_sky < reach) & (diff_rgb < 0.06) & (lum_ratio > 0.70)

            # Silhouette branches / needles extending into user sky
            dark_in_sky = (bin_m == 1) & ((lum_ratio < 0.45) | (diff_rgb > 0.20))
            del diff_rgb, pred_lum, lum_ratio, dist_from_sky
        else:
            sky_holes = np.zeros((h, w), dtype=bool)
            dark_in_sky = np.zeros((h, w), dtype=bool)

        core_sky = def_sky > 0.5

        def_sky_promoted = np.where(sky_holes, 1.0, np.where(dark_in_sky, 0.0, def_sky))
        def_gnd_promoted = np.where(sky_holes, 0.0, 1.0 - dilated_m)
        del def_sky, dilated_m, dark_in_sky

        if should_interrupt and should_interrupt():
            return None
        # 4. Global fallback colors still include the entire image, including foliage.
        sky_count = max(float(np.sum(def_sky_promoted)), 1.0)
        gnd_count = max(float(np.sum(def_gnd_promoted)), 1.0)
        weighted = np.empty((h, w), dtype=np.result_type(image.dtype, np.float32))
        fallback_colors = []
        for ch in channels:
            np.multiply(ch, def_sky_promoted, out=weighted)
            sky_color = float(np.sum(weighted)) / sky_count
            np.multiply(ch, def_gnd_promoted, out=weighted)
            ground_color = float(np.sum(weighted)) / gnd_count
            fallback_colors.append((sky_color, ground_color))
        del weighted

        # 5. Evaluate color fields and edge alignment only around changeable pixels.
        # Known sky holes also create boundaries, even outside the uncertain ribbon.
        fixed_sky = core_sky | sky_holes
        uncertain = ~fixed_sky & (def_gnd_promoted <= 0.5)
        guided_radius = max(2, min(5, radius // 8)) if edge_alignment else 0
        regions = cls._refinement_regions(uncertain, fixed_sky, core_sky, guided_radius, blur_window)
        if should_interrupt and should_interrupt():
            return None
        if progress_callback:
            progress_callback(0, len(regions))
        if should_interrupt and should_interrupt():
            return None
        refined_dtype = np.result_type(lum.dtype, np.float32) if edge_alignment else np.float32
        refined = fixed_sky.astype(refined_dtype)
        # Color means read half a blur window; guided filtering adds two box
        # filters. Clipping only at physical image edges preserves border rules.
        halo = blur_window // 2 + 2 * (guided_radius // 2)
        stop = Event()

        def process_region(bounds):
            if stop.is_set():
                return
            left, top, right, bottom = bounds
            x0, y0 = max(0, left - halo), max(0, top - halo)
            x1, y1 = min(w, right + halo), min(h, bottom + halo)
            region = np.s_[y0:y1, x0:x1]
            local = cls._refine_region(
                tuple(ch[region] for ch in channels), def_sky_promoted[region],
                def_gnd_promoted[region], core_sky[region], sky_holes[region],
                fallback_colors, blur_window, guided_radius,
            )
            if not stop.is_set():
                # Output rectangles do not overlap; inputs are shared read-only.
                refined[top:bottom, left:right] = local[top - y0:bottom - y0, left - x0:right - x0]

        if len(regions) > 1:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(process_region, region) for region in regions]
                try:
                    for completed, future in enumerate(as_completed(futures), 1):
                        if should_interrupt and should_interrupt():
                            return None
                        future.result()
                        if progress_callback:
                            progress_callback(completed, len(regions))
                        if should_interrupt and should_interrupt():
                            return None
                finally:
                    stop.set()
                    for future in futures:
                        future.cancel()
        elif regions:
            process_region(regions[0])
            if should_interrupt and should_interrupt():
                return None
            if progress_callback:
                progress_callback(1, 1)
        if should_interrupt and should_interrupt():
            return None
        del def_sky_promoted, sky_holes, fixed_sky, uncertain

        # 6. Clean isolated noise speckles
        bin_refined = (refined > 0.5).astype(np.float32)
        k_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        bin_refined = cv2.morphologyEx(bin_refined, cv2.MORPH_CLOSE, k_clean)
        bin_refined = cv2.morphologyEx(bin_refined, cv2.MORPH_OPEN, k_clean)
        refined = np.where(core_sky, 1.0, np.where(def_gnd_promoted > 0.5, 0.0, bin_refined))

        # 7. Smooth subpixel transition along the refined boundary
        if smooth_radius > 0:
            ksize = int(smooth_radius * 4 + 1) | 1
            feathered = cv2.GaussianBlur(refined, (ksize, ksize), smooth_radius)
            trans_band = cv2.boxFilter((bin_refined > 0.5).astype(np.float32), -1, (7, 7))
            feather_mask = (trans_band > 0.01) & (trans_band < 0.99) & ~core_sky
            refined = np.where(feather_mask, feathered, refined)

        # 8. Erode refined mask inward by N pixels to prevent foreground bleed
        if should_interrupt and should_interrupt():
            return None
        if erosion_pixels > 0:
            k_erode = 2 * int(erosion_pixels) + 1
            kernel_erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_erode, k_erode))
            refined = cv2.erode(refined, kernel_erode)

        # 9. Final mask is strictly boolean
        if should_interrupt and should_interrupt():
            return None
        bool_mask = refined > 0.5
        if as_bool:
            return bool_mask
        return bool_mask.astype(np.float32)
