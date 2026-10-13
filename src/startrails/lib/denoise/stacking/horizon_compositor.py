"""Interactive horizon transition band compositor with real-time blend and denoise tuning."""

from __future__ import annotations
from typing import Callable, Optional
import cv2
import numpy as np

from startrails.lib.denoise.enhancement.horizon_denoiser import HorizonDenoiser


class HorizonCompositor:
    """Interactively composites celestial sky stack and landscape ground stack.

    Decomposes the horizon transition zone into distinct gradient parts:
      1. Foreground gradient part (ground stack intersected with gradient mask)
      2. Sky gradient part (sky stack intersected with gradient mask)
      3. Denoised sky part (edge-preserving guided filtered sky stack)

    Enables real-time (<15ms) parameter tuning of horizon unwarped blending and
    adaptive transition band denoising without re-stacking or re-filtering.
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
        self.sky_stack = sky_stack.astype(np.float32)
        self.ground_stack = ground_stack.astype(np.float32)
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

        # -----------------------------------------------------------------
        # Horizon gradient parts (intersected with gradient mask)
        # -----------------------------------------------------------------
        # 1) Based on foreground stack:
        self.part_foreground = self.ground_stack * self.smoothstep_3d
        # 2) Based on sky stack:
        self.part_sky = self.sky_stack * self.smoothstep_3d

        # Precompute edge-preserving guided filter for sky stack
        if self.sky_stack.ndim == 3:
            guide = (
                0.299 * self.sky_stack[:, :, 0]
                + 0.587 * self.sky_stack[:, :, 1]
                + 0.114 * self.sky_stack[:, :, 2]
            ).astype(np.float32)
        else:
            guide = self.sky_stack.astype(np.float32)

        self.denoised_sky = HorizonDenoiser.guided_filter(
            guide, self.sky_stack, radius=self.denoise_radius, eps=self.denoise_eps
        )
        self.part_denoised = self.denoised_sky * self.smoothstep_3d

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
            pad = 32  # margin for Gaussian blur / filtering without border truncation
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
        self.roi_denoised_sky = (
            np.ascontiguousarray(self.denoised_sky[y0:y1]) if self.denoised_sky is not None else None
        )

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
        self._cached_blurred_fg: np.ndarray | None = None

    def composite_overlay(
        self,
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
        if cancel_check and cancel_check():
            return None, self.roi_rect

        if not enable_corrections:
            roi_result = self.roi_feathered_mask * self.roi_sky_stack + (1.0 - self.roi_feathered_mask) * self.roi_ground_stack
            return np.clip(roi_result, 0.0, 1.0).astype(np.float32), self.roi_rect

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
        if horizon_blur_radius > 0.0:
            if self._cached_blur_radius == horizon_blur_radius and self._cached_blurred_fg is not None:
                fg_sky = self._cached_blurred_fg
            else:
                if cancel_check and cancel_check():
                    return None, self.roi_rect
                ksize = int(round(horizon_blur_radius * 4 + 1)) | 1
                fg_sky = cv2.GaussianBlur(self.roi_ground_stack, (ksize, ksize), float(horizon_blur_radius))
                self._cached_blur_radius = horizon_blur_radius
                self._cached_blurred_fg = fg_sky
        else:
            fg_sky = self.roi_ground_stack

        if cancel_check and cancel_check():
            return None, self.roi_rect

        # 2. Adaptive transition band denoising on tracked sky (independent Color & Value control)
        if denoise_enabled and self.roi_denoised_sky is not None and max(color_str, value_str) > 0.0:
            if self.roi_C_sky is not None and self.roi_C_den is not None:
                wv = np.clip(self.roi_smoothstep_3d * value_str, 0.0, 1.0)
                wc = np.clip(self.roi_smoothstep_3d * color_str, 0.0, 1.0)
                y_out = (1.0 - wv) * self.roi_Y_sky + wv * self.roi_Y_den
                c_out = (1.0 - wc) * self.roi_C_sky + wc * self.roi_C_den
                sky_denoised = y_out + c_out
            else:
                wv = np.clip(self.roi_smoothstep_3d * value_str, 0.0, 1.0)
                sky_denoised = (1.0 - wv) * self.roi_sky_stack + wv * self.roi_denoised_sky
        else:
            sky_denoised = self.roi_sky_stack

        if cancel_check and cancel_check():
            return None, self.roi_rect

        # 3. Unwarped horizon sky blend (blends clean foreground into denoised stacked sky)
        if blend_ratio > 0.0:
            w_blend = self.roi_smoothstep_3d * blend_ratio
            sky_final = (1.0 - w_blend) * sky_denoised + w_blend * fg_sky
        else:
            sky_final = sky_denoised

        if cancel_check and cancel_check():
            return None, self.roi_rect

        # 4. Final seamless boundary alpha blend with ground stack
        roi_result = self.roi_feathered_mask * sky_final + (1.0 - self.roi_feathered_mask) * self.roi_ground_stack
        return np.clip(roi_result, 0.0, 1.0).astype(np.float32), self.roi_rect

    def composite(
        self,
        horizon_blend_percent: float = 60.0,
        horizon_denoise_strength: float = 0.2,
        denoise_enabled: bool = True,
        horizon_blur_radius: float = 2.0,
        enable_corrections: bool = True,
        horizon_color_denoise_strength: Optional[float] = None,
        horizon_value_denoise_strength: Optional[float] = None,
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
        roi_result, (rx, ry, rw, rh) = self.composite_overlay(
            horizon_blend_percent=horizon_blend_percent,
            horizon_denoise_strength=horizon_denoise_strength,
            denoise_enabled=denoise_enabled,
            horizon_blur_radius=horizon_blur_radius,
            enable_corrections=enable_corrections,
            horizon_color_denoise_strength=horizon_color_denoise_strength,
            horizon_value_denoise_strength=horizon_value_denoise_strength,
        )
        result = self.base_composite.copy()
        result[ry : ry + rh, rx : rx + rw] = roi_result
        return np.clip(result, 0.0, 1.0).astype(np.float32)
