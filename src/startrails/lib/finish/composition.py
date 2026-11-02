"""Denoise blending, layer recombination, and inference endpoint cache signatures."""

from __future__ import annotations

from typing import Optional

import numpy as np

from startrails.lib.finish.graxpert import DEFAULT_STRIDE, WINDOW_SIZE
from startrails.lib.signatures import compute_signature

from startrails.lib.finish.defaults import (
    BLEND_ADD,
    BLEND_SCREEN,
    BlendModeType,
    DenoiseScopeType,
    PERCENT_SCALE,
    SCOPE_SKY_ONLY,
    SCOPE_WHOLE_IMAGE,
)

RECOMBINE_CHUNK_ROWS = 512


def blend_denoise(
    base: np.ndarray,
    full_denoised: np.ndarray,
    sky_mask: Optional[np.ndarray],
    strength_percent: float,
    scope: DenoiseScopeType,
) -> np.ndarray:
    """Blend a working RGB region from GraXpert full-strength denoise endpoint with separated starless base.

    Formula:
      a = strength_percent / 100.0
      W = sky_mask for 'sky_only', or 1.0 for 'whole_image'
      B_denoised = base + a * W * (full_denoised - base)
    """
    if base.shape != full_denoised.shape:
        raise ValueError(f"Base shape {base.shape} and full_denoised shape {full_denoised.shape} must match.")
    if not np.isfinite(strength_percent) or not 0 <= strength_percent <= PERCENT_SCALE:
        raise ValueError(f"Denoise strength must be in range [0.0, 100.0], got {strength_percent}")
    if scope not in (SCOPE_SKY_ONLY, SCOPE_WHOLE_IMAGE):
        raise ValueError(f"Unknown scope '{scope}'. Must be one of {(SCOPE_SKY_ONLY, SCOPE_WHOLE_IMAGE)}.")

    if strength_percent == 0.0:
        return base.copy()

    h, w = base.shape[:2]
    a = float(strength_percent) / PERCENT_SCALE

    if scope == SCOPE_WHOLE_IMAGE:
        return base + a * (full_denoised - base)

    if sky_mask is None:
        raise ValueError("Sky-only denoising requires a sky mask.")
    if sky_mask.ndim != 2 or sky_mask.shape != (h, w):
        raise ValueError(f"Sky mask shape {sky_mask.shape} must match image shape {(h, w)}.")

    if sky_mask.dtype != np.float32:
        raise ValueError("Sky mask must be normalized float32.")
    w_weight = sky_mask[..., np.newaxis]
    return base + a * w_weight * (full_denoised - base)


def _blend_star_layer(
    base: np.ndarray,
    stars: np.ndarray,
    amount_percent: float,
    blend_mode: BlendModeType,
    negative_residual: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Blend one amount-scaled star layer onto a base chunk."""
    if amount_percent == 0.0:
        return base.copy()
    amount = float(amount_percent) / PERCENT_SCALE
    if blend_mode == BLEND_ADD:
        blended = base + amount * stars
        if negative_residual is not None:
            blended += amount * negative_residual
        np.clip(blended, 0.0, 1.0, out=blended)
        return blended
    contribution = np.clip(amount * stars, 0.0, 1.0)
    return 1.0 - (1.0 - base) * (1.0 - contribution)


def recombine_layers(
    finished_starless: np.ndarray,
    original_stars: np.ndarray,
    finished_stars: np.ndarray,
    negative_residual: np.ndarray,
    original_stars_amount_percent: float,
    original_stars_blend_mode: BlendModeType,
    finished_stars_amount_percent: float,
    finished_stars_blend_mode: BlendModeType,
    *,
    chunk_rows: int = RECOMBINE_CHUNK_ROWS,
) -> np.ndarray:
    """Recombine finished starless with two independently controlled star layers.

    Endpoint contracts:
      a_o = original_stars_amount_percent / 100.0
      a_f = finished_stars_amount_percent / 100.0
      C1 = blend(F, a_o * S, mode_o)
      C  = blend(C1, a_f * S_fin, mode_f)

    The negative residual follows Finished Stars Add only, as a_f * N. Both
    layers use their own Add/Screen mode. Original defaults are resolved by
    FinishSettings; this function always requires explicit amounts and modes.

    Invariants:
      Both amounts at 0% return finished_starless exactly, in either mode.
      With neutral starless (F=B), unadjusted finished stars (S_fin=S),
      Finished Add 100% and Original 0%, Add reconstructs source I within
      float32 precision.
    """
    expected_shape = finished_starless.shape
    for label, array in (
        ("original_stars", original_stars),
        ("finished_stars", finished_stars),
        ("negative_residual", negative_residual),
    ):
        if array.shape != expected_shape:
            raise ValueError(f"finished_starless and {label} shapes must match.")
    if chunk_rows <= 0:
        raise ValueError("chunk_rows must be positive.")
    for label, amount, mode in (
        ("Original Stars amount", original_stars_amount_percent, original_stars_blend_mode),
        ("Finished Stars amount", finished_stars_amount_percent, finished_stars_blend_mode),
    ):
        if not np.isfinite(amount) or not 0 <= amount <= PERCENT_SCALE:
            raise ValueError(f"{label} must be in range [0.0, 100.0], got {amount}")
        if mode not in (BLEND_ADD, BLEND_SCREEN):
            raise ValueError(f"Unknown blend mode '{mode}'. Must be one of {(BLEND_ADD, BLEND_SCREEN)}.")

    if original_stars_amount_percent == 0.0 and finished_stars_amount_percent == 0.0:
        return finished_starless.copy()

    composite = np.empty_like(finished_starless)
    for start in range(0, expected_shape[0], chunk_rows):
        end = min(start + chunk_rows, expected_shape[0])
        stage = _blend_star_layer(
            finished_starless[start:end],
            original_stars[start:end],
            float(original_stars_amount_percent),
            original_stars_blend_mode,
        )
        stage = _blend_star_layer(
            stage,
            finished_stars[start:end],
            float(finished_stars_amount_percent),
            finished_stars_blend_mode,
            negative_residual=negative_residual[start:end] if finished_stars_blend_mode == BLEND_ADD else None,
        )
        composite[start:end] = stage
    return composite


def compute_denoise_endpoint_signature(separation_signature: str, model_identity: str) -> str:
    """Compute deterministic cache signature for GraXpert full-strength inference endpoint.

    Denoise strength and scope are deliberately EXCLUDED from this endpoint key,
    so interactive adjustments reuse cached inference without rerunning the model.
    """
    return compute_signature(
        {
            "operation": "finish_denoise_endpoint",
            "version": 1,
            "separation": separation_signature,
            "model": model_identity,
            "stride": DEFAULT_STRIDE,
            "tile_size": WINDOW_SIZE,
        }
    )
