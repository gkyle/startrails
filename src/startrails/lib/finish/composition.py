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


def recombine_layers(
    finished_starless: np.ndarray,
    stars: np.ndarray,
    negative_residual: np.ndarray,
    star_amount_percent: float,
    blend_mode: BlendModeType,
    *,
    chunk_rows: int = RECOMBINE_CHUNK_ROWS,
) -> np.ndarray:
    """Recombine finished starless with the separated positive star layer.

    Endpoint contract:
      a = star_amount_percent / 100.0
      Add:    C = clip(F + a * S + a * N, 0, 1)
      Screen: C = 1 - (1 - F) * (1 - clip(a * S, 0, 1))

    The negative residual N follows Add only, scaled by star amount as part of
    the original separation residual. Screen uses the positive layer and does
    not promise to reconstruct the source. ``FinishSettings`` resolves the
    amount and mode; this function always requires explicit values.

    Invariants:
      At 0% the result is finished_starless exactly, in either mode.
      With neutral starless (F=B), 100% Add reconstructs source I within
      float32 precision.
    """
    expected_shape = finished_starless.shape
    for label, array in (
        ("stars", stars),
        ("negative_residual", negative_residual),
    ):
        if array.shape != expected_shape:
            raise ValueError(f"finished_starless and {label} shapes must match.")
    if chunk_rows <= 0:
        raise ValueError("chunk_rows must be positive.")
    if not np.isfinite(star_amount_percent) or not 0 <= star_amount_percent <= PERCENT_SCALE:
        raise ValueError(f"Stars Amount must be in range [0.0, 100.0], got {star_amount_percent}")
    if blend_mode not in (BLEND_ADD, BLEND_SCREEN):
        raise ValueError(f"Unknown blend mode '{blend_mode}'. Must be one of {(BLEND_ADD, BLEND_SCREEN)}.")

    if star_amount_percent == 0.0:
        return finished_starless.copy()

    amount = float(star_amount_percent) / PERCENT_SCALE
    composite = np.empty_like(finished_starless)
    for start in range(0, expected_shape[0], chunk_rows):
        end = min(start + chunk_rows, expected_shape[0])
        base = finished_starless[start:end]
        if blend_mode == BLEND_ADD:
            stage = base + amount * stars[start:end] + amount * negative_residual[start:end]
            np.clip(stage, 0.0, 1.0, out=stage)
        else:
            contribution = np.clip(amount * stars[start:end], 0.0, 1.0)
            stage = 1.0 - (1.0 - base) * (1.0 - contribution)
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
