"""Denoise blending, layer recombination, and inference endpoint cache signatures."""

from __future__ import annotations

import numpy as np

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
    sky_mask: np.ndarray,
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

    if sky_mask.ndim != 2 or sky_mask.shape != (h, w):
        raise ValueError(f"Sky mask shape {sky_mask.shape} must match image shape {(h, w)}.")

    if sky_mask.dtype != np.float32:
        raise ValueError("Sky mask must be normalized float32.")
    w_weight = sky_mask[..., np.newaxis]
    return base + a * w_weight * (full_denoised - base)


def recombine_layers(
    finished_starless: np.ndarray,
    finished_stars: np.ndarray,
    negative_residual: np.ndarray,
    star_amount_percent: float,
    blend_mode: BlendModeType,
    *,
    chunk_rows: int = RECOMBINE_CHUNK_ROWS,
) -> np.ndarray:
    """Recombine a working RGB region of finished starless and star layers.

    Endpoint contracts:
      a_s = star_amount_percent / 100.0
      S_f = a_s * finished_stars
      Add:    C = clip(finished_starless + S_f + a_s * negative_residual, 0.0, 1.0)
      Screen: C = 1.0 - (1.0 - finished_starless) * (1.0 - clip(S_f, 0.0, 1.0))

    Invariants:
      At star_amount_percent == 0.0, both modes return finished_starless exactly.
      With neutral starless (F=B), unadjusted stars (S_e=S), and star_amount=100%,
      Add reconstructs original source I within float32 precision.
    """
    if finished_starless.shape != finished_stars.shape:
        raise ValueError("finished_starless and finished_stars shapes must match.")
    if finished_starless.shape != negative_residual.shape:
        raise ValueError("finished_starless and negative_residual shapes must match.")
    if chunk_rows <= 0:
        raise ValueError("chunk_rows must be positive.")
    if not np.isfinite(star_amount_percent) or not 0 <= star_amount_percent <= PERCENT_SCALE:
        raise ValueError(f"Star amount must be in range [0.0, 100.0], got {star_amount_percent}")
    if blend_mode not in (BLEND_ADD, BLEND_SCREEN):
        raise ValueError(f"Unknown blend mode '{blend_mode}'. Must be one of {(BLEND_ADD, BLEND_SCREEN)}.")

    composite = np.clip(finished_starless, 0.0, 1.0)
    if star_amount_percent == 0.0:
        return composite

    a_s = float(star_amount_percent) / PERCENT_SCALE
    for start in range(0, finished_starless.shape[0], chunk_rows):
        end = min(start + chunk_rows, finished_starless.shape[0])
        finished = composite[start:end]
        stars = finished_stars[start:end]
        if blend_mode == BLEND_ADD:
            star_delta = a_s * stars
            star_delta += a_s * negative_residual[start:end]
            np.add(finished, star_delta, out=finished)
            np.clip(finished, 0.0, 1.0, out=finished)
        else:
            star_contribution = np.clip(a_s * stars, 0.0, 1.0)
            np.subtract(1.0, finished, out=finished)
            np.subtract(1.0, star_contribution, out=star_contribution)
            np.multiply(finished, star_contribution, out=finished)
            np.subtract(1.0, finished, out=finished)
    return composite


def compute_denoise_endpoint_signature(
    separation_signature: str,
    model_identity: str,
    *,
    stride: int,
    tile_size: int,
) -> str:
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
            "stride": stride,
            "tile_size": tile_size,
        }
    )
