"""Horizon transition band denoising using gradient-weighted Guided Filter."""

from __future__ import annotations
from typing import Optional
import cv2
import numpy as np


class HorizonDenoiser:
    """Adaptive edge-preserving noise reduction for under-sampled sky horizon transition bands."""

    @classmethod
    def guided_filter(
        cls,
        guide: np.ndarray,
        src: np.ndarray,
        radius: int = 5,
        eps: float = 1e-3,
        prefilter_guide: bool = True,
        guide_bilateral_d: int = 5,
        guide_bilateral_sigma_color: float = 0.08,
        guide_bilateral_sigma_space: float = 3.0,
    ) -> np.ndarray:
        """Apply Guided Filter for edge-preserving smoothing."""
        ksize = (2 * int(radius) + 1, 2 * int(radius) + 1)

        def _filter_2d(p: np.ndarray, I: np.ndarray) -> np.ndarray:
            mean_I = cv2.boxFilter(I, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)
            mean_p = cv2.boxFilter(p, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)
            mean_Ip = cv2.boxFilter(I * p, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)
            cov_Ip = mean_Ip - mean_I * mean_p

            mean_II = cv2.boxFilter(I * I, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)
            var_I = mean_II - mean_I * mean_I

            a = cov_Ip / (var_I + eps)
            b = mean_p - a * mean_I

            mean_a = cv2.boxFilter(a, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)
            mean_b = cv2.boxFilter(b, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)

            q = mean_a * I + mean_b
            return np.clip(q, 0.0, 1.0).astype(np.float32)

        guide_f32 = guide.astype(np.float32)
        if prefilter_guide and guide_bilateral_d > 0:
            guide_f32 = cv2.bilateralFilter(
                guide_f32,
                d=int(guide_bilateral_d),
                sigmaColor=float(guide_bilateral_sigma_color),
                sigmaSpace=float(guide_bilateral_sigma_space),
            )

        if src.ndim == 2:
            return _filter_2d(src.astype(np.float32), guide_f32)
        elif src.ndim == 3:
            out = np.zeros_like(src, dtype=np.float32)
            for c in range(src.shape[2]):
                out[:, :, c] = _filter_2d(src[:, :, c].astype(np.float32), guide_f32)
            return out
        else:
            raise ValueError(f"Unsupported array ndim: {src.ndim}")

    @classmethod
    def denoise_transition_band(
        cls,
        sky_image: np.ndarray,
        gradient_mask: np.ndarray,
        sky_mask: Optional[np.ndarray] = None,
        radius: int = 5,
        eps: float = 1e-3,
        strength: float = 1.0,
        color_strength: Optional[float] = None,
        value_strength: Optional[float] = None,
    ) -> np.ndarray:
        """Selectively denoise the under-sampled horizon transition band weighted by the gradient mask."""
        color_str = float(color_strength if color_strength is not None else strength)
        value_str = float(value_strength if value_strength is not None else strength)

        if max(color_str, value_str) <= 0.0:
            return sky_image.copy()

        # 1. Compute luminance guide
        if sky_image.ndim == 3:
            guide = (
                0.299 * sky_image[:, :, 0]
                + 0.587 * sky_image[:, :, 1]
                + 0.114 * sky_image[:, :, 2]
            ).astype(np.float32)
        else:
            guide = sky_image.astype(np.float32)

        # 2. Compute edge-preserving filtered image
        denoised = cls.guided_filter(guide, sky_image, radius=radius, eps=eps)

        # 3. Calculate continuous blend weight based on edge deficit
        t = np.clip(gradient_mask.astype(np.float32), 0.0, 1.0)
        w_base = t * t * (3.0 - 2.0 * t)

        if sky_mask is not None:
            sky_region = (sky_mask > 0.5).astype(np.float32)
            w_base = w_base * sky_region

        if sky_image.ndim == 3:
            w_val = np.clip(w_base * value_str, 0.0, 1.0)[..., None]
            w_col = np.clip(w_base * color_str, 0.0, 1.0)[..., None]

            guide_3d = guide[..., None]
            den_guide = (
                0.299 * denoised[:, :, 0]
                + 0.587 * denoised[:, :, 1]
                + 0.114 * denoised[:, :, 2]
            )[..., None]

            c_sky = sky_image - guide_3d
            c_den = denoised - den_guide

            y_out = (1.0 - w_val) * guide_3d + w_val * den_guide
            c_out = (1.0 - w_col) * c_sky + w_col * c_den
            return np.clip(y_out + c_out, 0.0, 1.0).astype(np.float32)
        else:
            w_val = np.clip(w_base * value_str, 0.0, 1.0)
            return np.clip((1.0 - w_val) * sky_image + w_val * denoised, 0.0, 1.0).astype(np.float32)
