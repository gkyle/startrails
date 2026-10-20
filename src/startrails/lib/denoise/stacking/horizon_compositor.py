"""Interactive horizon transition band compositor with real-time blend and denoise tuning."""

from __future__ import annotations
from typing import Callable, Optional
from threading import RLock
from functools import wraps
from inspect import signature
import cv2
import numpy as np

from startrails.lib.denoise.enhancement.horizon_denoiser import HorizonDenoiser


def synchronized_composition(method):
    @wraps(method)
    def evaluate(self, *args, **kwargs):
        with self._composition_lock:
            return method(self, *args, **kwargs)
    return evaluate


class HorizonCompositor:
    """Interactively composites celestial sky stack and landscape ground stack.

    Decomposes the horizon transition zone into distinct gradient parts:
      1. Foreground gradient part (ground stack intersected with gradient mask)
      2. Sky gradient part (sky stack intersected with gradient mask)
      3. Denoised sky part (edge-preserving guided filtered sky stack)

    Evaluates sparse patches for live tuning and reuses them for full-frame
    exports without re-stacking or repeating the guided filter.
    """

    def __init__(
        self,
        sky_stack: np.ndarray,
        ground_stack: np.ndarray,
        gradient_mask: np.ndarray,
        sky_mask: np.ndarray,
        feather_radius: float = 3.0,
        denoise_radius: int = 5,
        denoise_eps: float = 1e-3,
    ):
        self._composition_lock = RLock()
        self.sky_stack = sky_stack.astype(np.float32, copy=False)
        self.ground_stack = ground_stack.astype(np.float32, copy=False)
        self.gradient_mask = np.clip(gradient_mask.astype(np.float32), 0.0, 1.0)
        self.sky_mask = (
            (sky_mask > 0.5).astype(np.float32)
            if sky_mask is not None
            else np.ones(sky_stack.shape[:2], dtype=np.float32)
        )
        self.feather_radius = float(feather_radius)
        self.denoise_radius = int(denoise_radius)
        self.denoise_eps = float(denoise_eps)

        # Compute smoothstep transition weight restricted strictly to the sky region
        t = self.gradient_mask
        self.smoothstep_mask = (t * t * (3.0 - 2.0 * t)) * self.sky_mask
        if self.smoothstep_mask.ndim == 2 and self.sky_stack.ndim == 3:
            self.smoothstep_3d = self.smoothstep_mask[..., None]
        else:
            self.smoothstep_3d = self.smoothstep_mask

        # Precompute feathered boundary mask
        if self.feather_radius > 0:
            ksize = int(self.feather_radius * 4 + 1) | 1
            f_mask = cv2.GaussianBlur(self.sky_mask, (ksize, ksize), self.feather_radius)
        else:
            f_mask = self.sky_mask.copy()

        if f_mask.ndim == 2 and self.sky_stack.ndim == 3:
            self.feathered_mask = f_mask[..., None]
        else:
            self.feathered_mask = f_mask

        # Precompute base composite (full frame without horizon adjustments)
        self.base_composite = np.clip(
            self.feathered_mask * self.sky_stack + (1.0 - self.feathered_mask) * self.ground_stack,
            0.0,
            1.0,
        ).astype(np.float32)

        # Determine vertical active Region of Interest (ROI) for accelerated overlay evaluation
        h, w = self.sky_stack.shape[:2]
        active_rows = np.where(np.any(self.smoothstep_mask > 1e-4, axis=1))[0]
        if len(active_rows) > 0:
            pad = max(32, int(self.denoise_radius * 4 + 1))
            self.roi_y0 = max(0, int(active_rows[0]) - pad)
            self.roi_y1 = min(h, int(active_rows[-1]) + 1 + pad)
        else:
            self.roi_y0 = 0
            self.roi_y1 = h
        self.roi_x0 = 0
        self.roi_x1 = w
        self.roi_rect = (self.roi_x0, self.roi_y0, self.roi_x1 - self.roi_x0, self.roi_y1 - self.roi_y0)

        # Slice out C-contiguous ROI arrays for fast evaluation
        y0, y1 = self.roi_y0, self.roi_y1
        self.roi_sky_stack = np.ascontiguousarray(self.sky_stack[y0:y1])
        self.roi_ground_stack = np.ascontiguousarray(self.ground_stack[y0:y1])
        self.roi_smoothstep_3d = np.ascontiguousarray(self.smoothstep_3d[y0:y1])
        self.roi_feathered_mask = np.ascontiguousarray(self.feathered_mask[y0:y1])

        # Precompute edge-preserving guided filter strictly for the active horizon ROI
        if self.roi_sky_stack.ndim == 3:
            guide_roi = (
                0.299 * self.roi_sky_stack[:, :, 0]
                + 0.587 * self.roi_sky_stack[:, :, 1]
                + 0.114 * self.roi_sky_stack[:, :, 2]
            ).astype(np.float32)
        else:
            guide_roi = self.roi_sky_stack.astype(np.float32)

        self.roi_denoised_sky = HorizonDenoiser.guided_filter(
            guide_roi, self.roi_sky_stack, radius=self.denoise_radius, eps=self.denoise_eps
        )
        self.denoised_sky = None

        # Precompute luminance and chrominance decompositions for independent color/value tuning
        if self.roi_sky_stack.ndim == 3 and self.roi_denoised_sky is not None:
            self.roi_Y_sky = (
                0.299 * self.roi_sky_stack[:, :, 0]
                + 0.587 * self.roi_sky_stack[:, :, 1]
                + 0.114 * self.roi_sky_stack[:, :, 2]
            )[..., None]
            self.roi_Y_den = (
                0.299 * self.roi_denoised_sky[:, :, 0]
                + 0.587 * self.roi_denoised_sky[:, :, 1]
                + 0.114 * self.roi_denoised_sky[:, :, 2]
            )[..., None]
            self.roi_C_sky = self.roi_sky_stack - self.roi_Y_sky
            self.roi_C_den = self.roi_denoised_sky - self.roi_Y_den
        else:
            self.roi_Y_sky = self.roi_sky_stack
            self.roi_Y_den = self.roi_denoised_sky
            self.roi_C_sky = None
            self.roi_C_den = None

        # Cache for Gaussian blurred foreground sky input
        self._cached_blur_radius: float | None = None
        self._blurred_regions: dict[tuple[int, int, int, int], np.ndarray] = {}
        self._cached_patch_key = None
        self._cached_patches = None
        self.preview_rects = self.preview_regions(self.smoothstep_mask, self.roi_rect)
        self._composition_signature = signature(self._composite_region)

    @staticmethod
    def preview_regions(smoothstep_mask, roi_rect, tile_size=128):
        """Tight rectangles around nonzero weights, with a pixel of display-filter context."""
        rx, ry, rw, rh = roi_rect
        rectangles = []
        for y in range(ry, ry + rh, tile_size):
            for x in range(rx, rx + rw, tile_size):
                active = smoothstep_mask[y:min(y + tile_size, ry + rh), x:min(x + tile_size, rx + rw)] > 0
                rows, columns = np.nonzero(active)
                if rows.size:
                    x0, y0 = max(rx, x + int(columns.min()) - 1), max(ry, y + int(rows.min()) - 1)
                    x1 = min(rx + rw, x + int(columns.max()) + 2)
                    y1 = min(ry + rh, y + int(rows.max()) + 2)
                    rectangles.append((x0, y0, x1 - x0, y1 - y0))
        if sum(w * h for _, _, w, h in rectangles) > rw * rh * 0.6:
            # Dense masks gain little from hundreds of separately displayed patches.
            return [roi_rect]
        return rectangles

    @synchronized_composition
    def composite_overlay(self, *args, **kwargs):
        """Evaluate the original full-width ROI, using the shared region evaluator."""
        return self._composite_region(self.roi_rect, *args, **kwargs)

    @synchronized_composition
    def composite_patches(self, **kwargs):
        """Evaluate/cache only active tiles; return None on cancellation, including cache hits."""
        cancel_check = kwargs.get("cancel_check")
        if cancel_check and cancel_check():
            return None
        parameters = self._composition_signature.bind(self.roi_rect, **kwargs)
        parameters.apply_defaults()
        key = tuple((name, value) for name, value in parameters.arguments.items() if name not in ("rect", "cancel_check"))
        if key == self._cached_patch_key:
            return self._cached_patches
        patches = []
        if kwargs.get("enable_corrections", True):
            for rect in self.preview_rects:
                if cancel_check and cancel_check():
                    return None
                pixels, _ = self._composite_region(rect, **kwargs)
                if pixels is None:
                    return None
                patches.append((pixels, rect))
        if cancel_check and cancel_check():
            return None
        self._cached_patch_key, self._cached_patches = key, patches
        return patches

    def _foreground_region(self, rect, radius):
        """Blur with the full kernel halo and the same borders as the original ROI."""
        x, y, w, h = rect
        if self._cached_blur_radius != radius:
            self._blurred_regions.clear()
            self._cached_blur_radius = radius
        if rect not in self._blurred_regions:
            ksize = int(round(radius * 4 + 1)) | 1
            halo = ksize // 2
            rx, ry, rw, rh = self.roi_rect
            x0, y0 = max(rx, x - halo), max(ry, y - halo)
            x1, y1 = min(rx + rw, x + w + halo), min(ry + rh, y + h + halo)
            source = np.ascontiguousarray(self.ground_stack[y0:y1, x0:x1])
            blurred = cv2.GaussianBlur(source, (ksize, ksize), float(radius))
            self._blurred_regions[rect] = np.ascontiguousarray(blurred[y-y0:y-y0+h, x-x0:x-x0+w])
        return self._blurred_regions[rect]

    def _composite_region(
        self,
        rect,
        horizon_blend_percent: float = 60.0,
        horizon_denoise_strength: float = 0.2,
        denoise_enabled: bool = True,
        horizon_blur_radius: float = 2.0,
        enable_corrections: bool = True,
        horizon_color_denoise_strength: Optional[float] = None,
        horizon_value_denoise_strength: Optional[float] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> tuple[Optional[np.ndarray], tuple[int, int, int, int]]:
        """Evaluate composite strictly on the gradient mask region overlay.

        Args:
            horizon_blend_percent: 0.0 to 100.0% unwarped ground blend into sky (default: 60.0).
            horizon_denoise_strength: 0.0 to 2.0 multiplier for guided filter smoothing (default: 0.2).
            denoise_enabled: whether horizon band denoising is activated.
            horizon_blur_radius: Gaussian blur radius in pixels applied to foreground sky input (default: 2.0).
            enable_corrections: whether all horizon gradient adjustments are enabled (default: True).
            horizon_color_denoise_strength: optional multiplier for chrominance denoising (defaults to horizon_denoise_strength).
            horizon_value_denoise_strength: optional multiplier for luminance denoising (defaults to horizon_denoise_strength).
            cancel_check: optional callback returning True if calculation should abort early.

        Returns:
            (roi_clipped, (x0, y0, width, height)): (H_roi, W, 3) float32 array in [0.0, 1.0] (or None if cancelled)
            and bounding rect in image coordinates.
        """
        x, y, w, h = rect
        region = (slice(y - self.roi_y0, y - self.roi_y0 + h), slice(x, x + w))
        roi_sky_stack = self.roi_sky_stack[region]
        roi_ground_stack = self.roi_ground_stack[region]
        roi_smoothstep_3d = self.roi_smoothstep_3d[region]
        roi_feathered_mask = self.roi_feathered_mask[region]
        roi_denoised_sky = self.roi_denoised_sky[region]
        roi_Y_sky = self.roi_Y_sky[region]
        roi_Y_den = self.roi_Y_den[region]
        roi_C_sky = self.roi_C_sky[region] if self.roi_C_sky is not None else None
        roi_C_den = self.roi_C_den[region] if self.roi_C_den is not None else None
        if cancel_check and cancel_check():
            return None, rect

        if not enable_corrections:
            roi_result = roi_feathered_mask * roi_sky_stack + (1.0 - roi_feathered_mask) * roi_ground_stack
            return np.clip(roi_result, 0.0, 1.0).astype(np.float32), rect

        blend_ratio = np.clip(float(horizon_blend_percent) / 100.0, 0.0, 1.0)
        color_str = float(
            horizon_color_denoise_strength
            if horizon_color_denoise_strength is not None
            else horizon_denoise_strength
        )
        value_str = float(
            horizon_value_denoise_strength
            if horizon_value_denoise_strength is not None
            else horizon_denoise_strength
        )

        # 1. Foreground sky input (Gaussian blur applied strictly to foreground input, not stacked sky)
        if horizon_blur_radius > 0.0 and blend_ratio > 0.0:
            fg_sky = self._foreground_region(rect, horizon_blur_radius)
        else:
            fg_sky = roi_ground_stack

        if cancel_check and cancel_check():
            return None, rect

        # 2. Adaptive transition band denoising on tracked sky (independent Color & Value control)
        if denoise_enabled and roi_denoised_sky is not None and max(color_str, value_str) > 0.0:
            if roi_C_sky is not None and roi_C_den is not None:
                wv = np.clip(roi_smoothstep_3d * value_str, 0.0, 1.0)
                wc = np.clip(roi_smoothstep_3d * color_str, 0.0, 1.0)
                y_out = (1.0 - wv) * roi_Y_sky + wv * roi_Y_den
                c_out = (1.0 - wc) * roi_C_sky + wc * roi_C_den
                sky_denoised = y_out + c_out
            else:
                wv = np.clip(roi_smoothstep_3d * value_str, 0.0, 1.0)
                sky_denoised = (1.0 - wv) * roi_sky_stack + wv * roi_denoised_sky
        else:
            sky_denoised = roi_sky_stack

        if cancel_check and cancel_check():
            return None, rect

        # 3. Unwarped horizon sky blend (blends clean foreground into denoised stacked sky)
        if blend_ratio > 0.0:
            w_blend = roi_smoothstep_3d * blend_ratio
            sky_final = (1.0 - w_blend) * sky_denoised + w_blend * fg_sky
        else:
            sky_final = sky_denoised

        if cancel_check and cancel_check():
            return None, rect

        # 4. Final seamless boundary alpha blend with ground stack
        roi_result = roi_feathered_mask * sky_final + (1.0 - roi_feathered_mask) * roi_ground_stack
        return np.clip(roi_result, 0.0, 1.0).astype(np.float32), rect

    @synchronized_composition
    def composite(
        self,
        horizon_blend_percent: float = 60.0,
        horizon_denoise_strength: float = 0.2,
        denoise_enabled: bool = True,
        horizon_blur_radius: float = 2.0,
        enable_corrections: bool = True,
        horizon_color_denoise_strength: Optional[float] = None,
        horizon_value_denoise_strength: Optional[float] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> np.ndarray:
        """Evaluate full composite image given blend, denoise, and blur parameters.

        Args:
            horizon_blend_percent: 0.0 to 100.0% unwarped ground blend into sky.
            horizon_denoise_strength: 0.0 to 2.0 multiplier for guided filter smoothing.
            denoise_enabled: whether horizon band denoising is activated.
            horizon_blur_radius: Gaussian blur radius in pixels (0.0 = disabled).
            enable_corrections: whether all horizon gradient adjustments are enabled.
            horizon_color_denoise_strength: optional multiplier for chrominance denoising.
            horizon_value_denoise_strength: optional multiplier for luminance denoising.

        Returns:
            Fully assembled (H, W, 3) float32 composite image in [0.0, 1.0].
        """
        patches = self.composite_patches(
            horizon_blend_percent=horizon_blend_percent,
            horizon_denoise_strength=horizon_denoise_strength,
            denoise_enabled=denoise_enabled,
            horizon_blur_radius=horizon_blur_radius,
            enable_corrections=enable_corrections,
            horizon_color_denoise_strength=horizon_color_denoise_strength,
            horizon_value_denoise_strength=horizon_value_denoise_strength,
            cancel_check=cancel_check,
        )
        if patches is None or (cancel_check and cancel_check()):
            return None
        result = self.base_composite.copy()
        if enable_corrections:
            color_str = horizon_denoise_strength if horizon_color_denoise_strength is None else horizon_color_denoise_strength
            value_str = horizon_denoise_strength if horizon_value_denoise_strength is None else horizon_value_denoise_strength
            reconstruct_color = denoise_enabled and self.roi_C_sky is not None and max(color_str, value_str) > 0
            blend_ratio = np.clip(float(horizon_blend_percent) / 100.0, 0.0, 1.0)
            # Even at zero weight, the original color reconstruction and blend dtype
            # can change the last float32 bit. Preserve that arithmetic in bounded chunks.
            for offset in range(0, self.roi_y1 - self.roi_y0, 128):
                if cancel_check and cancel_check():
                    return None
                region = slice(offset, min(offset + 128, self.roi_y1 - self.roi_y0))
                sky = self.roi_Y_sky[region] + self.roi_C_sky[region] if reconstruct_color else self.roi_sky_stack[region]
                if blend_ratio > 0:
                    sky = sky.astype(np.result_type(sky.dtype, blend_ratio))
                mask = self.roi_feathered_mask[region]
                background = mask * sky + (1.0 - mask) * self.roi_ground_stack[region]
                y0 = self.roi_y0 + offset
                result[y0:y0 + background.shape[0]] = np.clip(background, 0.0, 1.0).astype(np.float32)
        for pixels, (x, y, w, h) in patches:
            if cancel_check and cancel_check():
                return None
            result[y:y+h, x:x+w] = pixels
        return result
