"""Content-aware sky mask refinement using local color and luminance contrast."""

from __future__ import annotations
import logging
from typing import Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class MaskRefiner:
    """Refines rough user-drawn sky masks by snapping boundary edges to natural physical horizons."""

    @classmethod
    def refine(
        cls,
        image: np.ndarray,
        rough_mask: np.ndarray,
        search_radius: Optional[int] = None,
        blur_window: Optional[int] = None,
        edge_alignment: bool = True,
        smooth_radius: float = 2.0,
        erosion_pixels: int = 0,
        foliage_protection: bool = True,
        as_bool: bool = False,
        **kwargs,
    ) -> np.ndarray:
        """Refine a rough sky mask to match true physical image boundaries.

        Args:
            image: float32 image array of shape (H, W, 3) or (H, W) in [0.0, 1.0]
            rough_mask: 2D array (H, W) where ~1.0 is Sky and ~0.0 is Ground
            search_radius: pixel radius of the uncertain boundary ribbon (default: adaptive based on image size)
            blur_window: neighborhood window for local color propagation (default: max(31, radius * 4 + 1))
            edge_alignment: whether to lock boundary to physical image gradients via guided filter (default: True)
            smooth_radius: subpixel anti-aliasing feather radius (default: 2.0)

        Returns:
            refined_mask: 2D float32 array (H, W) in [0.0, 1.0] snapped to natural horizons
        """
        h, w = image.shape[:2]
        if rough_mask.shape[:2] != (h, w):
            raise ValueError(f"Mask shape {rough_mask.shape} does not match image shape {image.shape[:2]}")

        bin_m = (rough_mask > 0.5).astype(np.uint8)

        sky_sum = int(np.sum(bin_m))
        total_pixels = h * w
        if sky_sum == 0 or sky_sum == total_pixels:
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

        # 2. RGB + Luminance guidance stack
        if image.ndim == 3 and image.shape[2] == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)[..., None]
            features = np.concatenate([image, gray], axis=-1)
        elif image.ndim == 3:
            features = np.repeat(image[..., :1], 4, axis=-1)
        else:
            features = np.repeat(image[..., None], 4, axis=-1)

        lum = features[..., 3]
        rgb = features[..., :3]

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

            pred_rgb = np.zeros((h, w, 3), dtype=np.float32)
            for c in range(3):
                coeffs_c, _, _, _ = np.linalg.lstsq(X, s_rgb[ys, xs, c], rcond=None)
                pred_c = (X_full @ coeffs_c).reshape(s_h, s_w)
                pred_rgb[..., c] = cv2.resize(pred_c, (w, h))

            diff_rgb = np.linalg.norm(rgb - pred_rgb, axis=-1)
            pred_lum = 0.299 * pred_rgb[..., 0] + 0.587 * pred_rgb[..., 1] + 0.114 * pred_rgb[..., 2]
            lum_ratio = lum / np.maximum(pred_lum, 1e-4)

            # Porous vegetation / canopy sky gap detection
            dist_from_sky = cv2.distanceTransform((1 - bin_m).astype(np.uint8), cv2.DIST_L2, 5)
            reach = max(int(radius * 2.5), min(100, int(max(h, w) * 0.025)))
            sky_holes = (bin_m == 0) & (dist_from_sky < reach) & (diff_rgb < 0.06) & (lum_ratio > 0.70)

            # Silhouette branches / needles extending into user sky
            dark_in_sky = (bin_m == 1) & ((lum_ratio < 0.45) | (diff_rgb > 0.20))
        else:
            sky_holes = np.zeros((h, w), dtype=bool)
            dark_in_sky = np.zeros((h, w), dtype=bool)

        core_sky = def_sky > 0.5

        def_sky_promoted = np.where(sky_holes, 1.0, np.where(dark_in_sky, 0.0, def_sky))
        def_gnd_promoted = np.where(sky_holes, 0.0, 1.0 - dilated_m)

        # 4. Estimate local sky and ground color fields
        safe_sky_weight = np.maximum(cv2.boxFilter(def_sky_promoted, -1, (blur_window, blur_window)), 1e-4)
        safe_gnd_weight = np.maximum(cv2.boxFilter(def_gnd_promoted, -1, (blur_window, blur_window)), 1e-4)

        sky_count = max(float(np.sum(def_sky_promoted)), 1.0)
        gnd_count = max(float(np.sum(def_gnd_promoted)), 1.0)

        dist_sky_sq = np.zeros((h, w), dtype=np.float32)
        dist_gnd_sq = np.zeros((h, w), dtype=np.float32)

        for c in range(features.shape[2]):
            ch = features[:, :, c]
            sky_sum = cv2.boxFilter(ch * def_sky_promoted, -1, (blur_window, blur_window))
            gnd_sum = cv2.boxFilter(ch * def_gnd_promoted, -1, (blur_window, blur_window))
            sky_c_mean = np.where(safe_sky_weight > 1e-4, sky_sum / safe_sky_weight, float(np.sum(ch * def_sky_promoted)) / sky_count)
            gnd_c_mean = np.where(safe_gnd_weight > 1e-4, gnd_sum / safe_gnd_weight, float(np.sum(ch * def_gnd_promoted)) / gnd_count)
            dist_sky_sq += (ch - sky_c_mean) ** 2
            dist_gnd_sq += (ch - gnd_c_mean) ** 2

        p_sky = np.sqrt(dist_gnd_sq) / (np.sqrt(dist_sky_sq) + np.sqrt(dist_gnd_sq) + 1e-6)
        refined = np.where(core_sky, 1.0, np.where(sky_holes, 1.0, np.where(def_gnd_promoted > 0.5, 0.0, p_sky)))

        # 5. Edge-preserving Guided Filter for crisp subpixel branch & horizon alignment
        if edge_alignment:
            guide = lum
            r = max(2, min(5, radius // 8))
            eps = 1e-3
            mean_I = cv2.boxFilter(guide, -1, (r, r))
            mean_p = cv2.boxFilter(refined, -1, (r, r))
            mean_Ip = cv2.boxFilter(guide * refined, -1, (r, r))
            cov_Ip = mean_Ip - mean_I * mean_p
            var_I = cv2.boxFilter(guide * guide, -1, (r, r)) - mean_I * mean_I
            a = cov_Ip / (var_I + eps)
            b = mean_p - a * mean_I
            filtered = cv2.boxFilter(a, -1, (r, r)) * guide + cv2.boxFilter(b, -1, (r, r))
            refined = np.where(core_sky, 1.0, filtered)

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
        if erosion_pixels > 0:
            k_erode = 2 * int(erosion_pixels) + 1
            kernel_erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_erode, k_erode))
            refined = cv2.erode(refined, kernel_erode)

        # 9. Final mask is strictly boolean
        bool_mask = refined > 0.5
        if as_bool:
            return bool_mask
        return bool_mask.astype(np.float32)
