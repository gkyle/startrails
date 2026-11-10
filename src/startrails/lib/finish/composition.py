"""Denoise blending, layer recombination, and inference endpoint cache signatures."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from startrails.lib.finish.graxpert import DEFAULT_STRIDE, WINDOW_SIZE
from startrails.lib.image_io import rgb_luminance
from startrails.lib.signatures import compute_signature

from startrails.lib.finish.defaults import (
    BLEND_ADD,
    BLEND_SCREEN,
    BlendModeType,
    DEFAULT_STAR_THRESHOLD_PERCENT,
    DenoiseScopeType,
    PERCENT_SCALE,
    SCOPE_SKY_ONLY,
    SCOPE_WHOLE_IMAGE,
)

RECOMBINE_CHUNK_ROWS = 512

# Coupled geodesic star-threshold constants. Surviving star cores (luminance > t)
# seed a smooth [0, 1] weight that propagates downhill along the Gaussian-smoothed
# star envelope B so each remaining bright star retains its outer radiance/halo
# without leaking across dark sky or climbing into neighboring weak stars.
STAR_THRESHOLD_RAMP_WIDTH = 0.05
STAR_ENVELOPE_SIGMA_PX = 1.5
STAR_ENVELOPE_KERNEL_SIZE = 13
STAR_SUPPORT_DILATE_PX = 3
STAR_SUPPORT_FLOOR = 1e-5
STAR_HALO_DILATE_SIZE_PX = 5
STAR_HALO_PROPAGATION_STEPS = 12
STAR_ENVELOPE_EPSILON = 1e-6
STAR_THRESHOLD_HALO_ROWS = (
    (STAR_SUPPORT_DILATE_PX // 2)
    + (STAR_ENVELOPE_KERNEL_SIZE // 2)
    + (STAR_HALO_DILATE_SIZE_PX // 2) * (1 + STAR_HALO_PROPAGATION_STEPS)
)

_SUPPORT_KERNEL = cv2.getStructuringElement(cv2.MORPH_RECT, (STAR_SUPPORT_DILATE_PX, STAR_SUPPORT_DILATE_PX))
_HALO_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (STAR_HALO_DILATE_SIZE_PX, STAR_HALO_DILATE_SIZE_PX))


def _compute_star_threshold_weights(stars_band: np.ndarray, threshold: float) -> np.ndarray:
    """Return a [0, 1] retention mask preserving full halos around stars above threshold.

    At each geodesic step from pixel p to neighbor q:
      - Weight cannot increase downhill:    W(q) <= W(p)
      - Intensity cannot increase uphill:   W(q) * B(q) <= W(p) * B(p)
    Hence monotonic star halos inherit their core's full weight W(p), while
    propagation across a saddle into a fainter neighbor is capped at the saddle
    intensity and blocked across empty sky outside the 3x3 star support.
    """
    luma = rgb_luminance(stars_band)
    envelope = cv2.GaussianBlur(
        luma,
        (STAR_ENVELOPE_KERNEL_SIZE, STAR_ENVELOPE_KERNEL_SIZE),
        sigmaX=STAR_ENVELOPE_SIGMA_PX,
        sigmaY=STAR_ENVELOPE_SIGMA_PX,
        borderType=cv2.BORDER_REFLECT,
    )
    peak_luma = np.maximum(luma, envelope)
    ramp = np.clip(
        (peak_luma - np.float32(threshold)) * np.float32(1.0 / STAR_THRESHOLD_RAMP_WIDTH),
        0.0,
        1.0,
    )
    if not np.any(ramp > 0.0):
        return np.zeros_like(luma)

    support = cv2.dilate(luma, _SUPPORT_KERNEL) > np.float32(STAR_SUPPORT_FLOOR)
    envelope = np.where(support, envelope, np.float32(0.0))
    weights = ramp * ramp * (np.float32(3.0) - np.float32(2.0) * ramp)
    weights = np.where(support, cv2.dilate(weights, _HALO_KERNEL), np.float32(0.0))

    inv_envelope = np.zeros_like(envelope)
    np.divide(1.0, envelope, out=inv_envelope, where=envelope > STAR_ENVELOPE_EPSILON)
    weighted_envelope = np.empty_like(weights)
    dilated_weights = np.empty_like(weights)
    dilated_intensity = np.empty_like(weights)
    for _ in range(STAR_HALO_PROPAGATION_STEPS):
        np.multiply(weights, envelope, out=weighted_envelope)
        cv2.dilate(weights, _HALO_KERNEL, dst=dilated_weights)
        cv2.dilate(weighted_envelope, _HALO_KERNEL, dst=dilated_intensity)
        np.multiply(dilated_intensity, inv_envelope, out=dilated_intensity)
        np.minimum(dilated_weights, dilated_intensity, out=dilated_weights)
        np.maximum(weights, dilated_weights, out=weights)
    return weights


def blend_denoise(
    base: np.ndarray,
    full_denoised: np.ndarray,
    sky_mask: Optional[np.ndarray],
    strength_percent: float,
    scope: DenoiseScopeType,
    *,
    chunk_rows: int = RECOMBINE_CHUNK_ROWS,
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
    if chunk_rows <= 0:
        raise ValueError("chunk_rows must be positive.")

    if strength_percent == 0.0:
        return base.copy()

    h, w = base.shape[:2]
    if scope == SCOPE_SKY_ONLY:
        if sky_mask is None:
            raise ValueError("Sky-only denoising requires a sky mask.")
        if sky_mask.ndim != 2 or sky_mask.shape != (h, w):
            raise ValueError(f"Sky mask shape {sky_mask.shape} must match image shape {(h, w)}.")
        if sky_mask.dtype != np.float32:
            raise ValueError("Sky mask must be normalized float32.")

    a = np.float32(float(strength_percent) / PERCENT_SCALE)
    blended = np.empty_like(base, dtype=np.float32)
    for start in range(0, h, chunk_rows):
        end = min(start + chunk_rows, h)
        chunk = blended[start:end]
        np.subtract(full_denoised[start:end], base[start:end], out=chunk)
        chunk *= a
        if scope == SCOPE_SKY_ONLY:
            chunk *= sky_mask[start:end, :, np.newaxis]
        chunk += base[start:end]
    return blended


def recombine_layers(
    finished_starless: np.ndarray,
    stars: np.ndarray,
    negative_residual: np.ndarray,
    star_amount_percent: float,
    blend_mode: BlendModeType,
    star_threshold_percent: float = DEFAULT_STAR_THRESHOLD_PERCENT,
    *,
    chunk_rows: int = RECOMBINE_CHUNK_ROWS,
) -> np.ndarray:
    """Recombine finished starless with the separated positive star layer.

    Endpoint contract:
      a = star_amount_percent / 100.0
      t = star_threshold_percent / 100.0
      W_t = geodesic star-retention weights in [0, 1] seeded where star peak > t
            (1 everywhere when t == 0; 0 everywhere when t == 1)
      S_t = W_t * stars
      Add:    C = clip(F + a * S_t + a * N, 0, 1)
      Screen: C = 1 - (1 - F) * (1 - clip(a * S_t, 0, 1))

    The negative residual N follows Add only, scaled by star amount as part of
    the original separation residual. Screen uses the positive layer and does
    not promise to reconstruct the source. ``FinishSettings`` resolves the
    amount, threshold, and mode; callers inside the workflow always pass
    explicit values.

    Invariants:
      At 0% star amount the result is finished_starless exactly, in either mode.
      With neutral starless (F=B) and 0% threshold, 100% Add reconstructs source
      I within float32 precision.
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
    if not np.isfinite(star_threshold_percent) or not 0 <= star_threshold_percent <= PERCENT_SCALE:
        raise ValueError(f"Star Threshold must be in range [0.0, 100.0], got {star_threshold_percent}")
    if blend_mode not in (BLEND_ADD, BLEND_SCREEN):
        raise ValueError(f"Unknown blend mode '{blend_mode}'. Must be one of {(BLEND_ADD, BLEND_SCREEN)}.")

    if star_amount_percent == 0.0:
        return finished_starless.copy()

    height = expected_shape[0]
    amount = float(star_amount_percent) / PERCENT_SCALE
    threshold = float(star_threshold_percent) / PERCENT_SCALE
    composite = np.empty_like(finished_starless)
    for start in range(0, height, chunk_rows):
        end = min(start + chunk_rows, height)
        base = finished_starless[start:end]
        stars_chunk = stars[start:end]
        if star_threshold_percent >= PERCENT_SCALE:
            filtered_stars: np.ndarray | float = 0.0
        elif star_threshold_percent > 0.0:
            lo = max(0, start - STAR_THRESHOLD_HALO_ROWS)
            hi = min(height, end + STAR_THRESHOLD_HALO_ROWS)
            band_weights = _compute_star_threshold_weights(stars[lo:hi], threshold)
            central_weights = band_weights[start - lo : start - lo + (end - start)]
            filtered_stars = stars_chunk * central_weights[..., np.newaxis]
        else:
            filtered_stars = stars_chunk

        if blend_mode == BLEND_ADD:
            stage = base + amount * filtered_stars + amount * negative_residual[start:end]
            np.clip(stage, 0.0, 1.0, out=stage)
        else:
            contribution = np.clip(amount * filtered_stars, 0.0, 1.0)
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
