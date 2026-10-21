"""Horizon transition band denoising using gradient-weighted Guided Filter."""

from __future__ import annotations
from typing import Optional
import cv2
import numpy as np

from startrails.lib.denoise.defaults import DENOISE_DEFAULTS


class HorizonDenoiser:
    """Adaptive edge-preserving noise reduction for under-sampled sky horizon transition bands."""

    @classmethod
    def guided_filter(
        cls,
        guide: np.ndarray,
        src: np.ndarray,
        radius: int = DENOISE_DEFAULTS.horizon_denoise_radius,
        eps: float = DENOISE_DEFAULTS.horizon_denoise_eps,
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
