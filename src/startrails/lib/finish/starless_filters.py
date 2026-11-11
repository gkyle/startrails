"""Two-scale luminance sharpening for the finished starless sky.

Structure and Detail are fixed spatial scales expressed in full-resolution
pixels. The luminance is decomposed into two bounded high-pass bands:

    detail    = L - Gaussian(L, DETAIL_SIGMA_PX)
    structure = Gaussian(L, DETAIL_SIGMA_PX) - Gaussian(L, STRUCTURE_SIGMA_PX)

Thus Detail covers the finest scales and Structure covers the broader band
without applying the same fine detail twice. Gaussian scales are normalized by
the soft sky mask, G(L*M)/max(G(M), eps), so ground luminance cannot bleed into
the sky estimate across a horizon. A robust high-frequency noise estimate gates
each band with a smooth weight, then a bounded multiplicative luminance gain
applies the result through M. The scalar RGB gain is limited by both local
luminance headroom and the brightest channel, so positive enhancement does not
clip. All spatial filtering runs in row chunks expanded by the Gaussian kernel
radius, so results do not depend on chunk height.
"""

from __future__ import annotations

from typing import Callable, Final, Optional

import numpy as np
from scipy.ndimage import gaussian_filter

from startrails.lib.finish.defaults import PERCENT_SCALE
from startrails.lib.image_io import rgb_luminance, validate_image_array

# Bump when the Structure/Detail algorithm, scales, gating, or cap changes in a
# way that makes previously finished plates no longer reproducible.
STARLESS_FILTER_VERSION: Final[int] = 2

# Fixed full-resolution spatial scales. These are algorithm constants, not
# user-facing options; a reduced-resolution preview must scale them explicitly.
STRUCTURE_SIGMA_PX: Final[float] = 20.0
DETAIL_SIGMA_PX: Final[float] = 1.5

# SciPy's default kernel cut-off. The halo below must cover its full support.
GAUSSIAN_TRUNCATE: Final[float] = 4.0

# Full-strength band gains before noise gating and overshoot limiting.
STRUCTURE_GAIN_AT_FULL: Final[float] = 0.75
DETAIL_GAIN_AT_FULL: Final[float] = 0.5

# Robust noise estimate: MAD of the detail high-pass band over fixed sample
# bands. Fixed bands keep the estimate independent of the processing chunk size.
NOISE_SAMPLE_BAND_ROWS: Final[int] = 256
NOISE_SAMPLE_STRIDE: Final[int] = 8
NOISE_MAD_SCALE: Final[float] = 1.4826
MIN_NOISE_SIGMA: Final[float] = 1e-4
MAX_NOISE_SIGMA: Final[float] = 0.1
NOISE_MASK_SAMPLE_THRESHOLD: Final[float] = 0.5

# Normalized convolution floor for G(L*M)/max(G(M), eps). It matters only where
# the sky mask is essentially zero; output still passes through M.
MASK_NORMALIZATION_EPSILON: Final[float] = 1e-3

# Smooth soft-threshold gate: g = h^2 / (h^2 + t^2). The Structure band is
# already low-passed by the detail scale, so it needs a lower noise multiple.
DETAIL_NOISE_MULTIPLIER: Final[float] = 1.5
STRUCTURE_NOISE_MULTIPLIER: Final[float] = 1.0

# Per-pixel luminance overshoot limit. The headroom term shrinks the cap toward
# black and white so the multiplicative gain stays bounded near both ends.
MAX_LUMINANCE_DELTA: Final[float] = 0.025
LOCAL_HEADROOM_FRACTION: Final[float] = 0.35
LUMINANCE_EPSILON: Final[float] = 1e-6

DEFAULT_CHUNK_ROWS: Final[int] = 512


def _kernel_radius(sigma_px: float) -> int:
    """Return the full Gaussian support radius used by scipy for this sigma."""
    return max(1, int(GAUSSIAN_TRUNCATE * sigma_px + 0.5))


def _normalized_blur(values: np.ndarray, weights: np.ndarray, sigma_px: float) -> np.ndarray:
    """Return normalized mask-weighted Gaussian low-pass G(values*M)/G(M)."""
    numerator = gaussian_filter(values * weights, sigma_px, mode="reflect", truncate=GAUSSIAN_TRUNCATE)
    denominator = gaussian_filter(weights, sigma_px, mode="reflect", truncate=GAUSSIAN_TRUNCATE)
    return numerator / np.maximum(denominator, MASK_NORMALIZATION_EPSILON)


def _smooth_gate(band: np.ndarray, threshold: float) -> np.ndarray:
    """Return a smooth [0,1] noise gate for a high-pass band."""
    squared = np.square(band)
    return squared / (squared + threshold * threshold)


def _estimate_noise_sigma(
    image: np.ndarray,
    sky_mask: np.ndarray,
    *,
    should_interrupt: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    progress_offset: int = 0,
    progress_total: int = 0,
) -> Optional[float]:
    """Estimate sky luminance noise from the detail high-pass band with a robust MAD.

    Sample bands are fixed in image coordinates, so the result does not change
    with the caller's processing chunk height. Only sky-weighted samples inform
    the estimate, preventing foreground texture from raising the noise gate.
    Returns None when interrupted.
    """
    height = image.shape[0]
    halo = _kernel_radius(DETAIL_SIGMA_PX)
    samples: list[np.ndarray] = []
    band_starts = range(0, height, NOISE_SAMPLE_BAND_ROWS)
    for done, start in enumerate(band_starts, start=1):
        if should_interrupt is not None and should_interrupt():
            return None
        end = min(start + NOISE_SAMPLE_BAND_ROWS, height)
        lo, hi = max(0, start - halo), min(height, end + halo)
        luminance = rgb_luminance(image[lo:hi])
        weight = sky_mask[lo:hi]
        detail = luminance - _normalized_blur(luminance, weight, DETAIL_SIGMA_PX)
        central = np.s_[start - lo : start - lo + (end - start)]
        central_detail = detail[central][::NOISE_SAMPLE_STRIDE, ::NOISE_SAMPLE_STRIDE]
        central_mask = weight[central][::NOISE_SAMPLE_STRIDE, ::NOISE_SAMPLE_STRIDE]
        selected = central_detail[central_mask >= NOISE_MASK_SAMPLE_THRESHOLD]
        samples.append(selected.ravel())
        if progress_callback is not None:
            progress_callback(progress_offset + done, progress_total, "Analyzing starless noise...")

    values = np.concatenate(samples)
    if values.size == 0:
        return MIN_NOISE_SIGMA
    center = float(np.median(values))
    sigma = NOISE_MAD_SCALE * float(np.median(np.abs(values - center)))
    return float(np.clip(sigma, MIN_NOISE_SIGMA, MAX_NOISE_SIGMA))


def _validate_amounts(structure_amount: float, detail_amount: float) -> None:
    for label, amount in (("Structure", structure_amount), ("Detail", detail_amount)):
        if not np.isfinite(amount) or not 0 <= amount <= PERCENT_SCALE:
            raise ValueError(f"{label} amount must be in range [0.0, 100.0], got {amount}")


def sharpen_starless(
    image: np.ndarray,
    sky_mask: np.ndarray,
    structure_amount: float,
    detail_amount: float,
    *,
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
    should_interrupt: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Optional[np.ndarray]:
    """Enhance sky luminance with Structure and Detail high-pass bands.

    Args:
        image: Normalized float32 RGB plate after denoising.
        sky_mask: Normalized float32 sky weight with the image's spatial shape.
            Enhancement is applied to the masked delta; zero mask leaves pixels
            exactly unchanged.
        structure_amount: Broad-scale amount as a percentage.
        detail_amount: Fine-scale amount as a percentage.
        chunk_rows: Central rows processed per bounded working region.
        should_interrupt: Optional cancellation probe checked between chunks.
        progress_callback: Optional ``(done, total, description)`` reporter.

    Returns:
        A new normalized float32 RGB array, or None if interrupted. Both zero
        amounts return an exact copy of the input image.
    """
    validate_image_array(image)
    if chunk_rows <= 0:
        raise ValueError("chunk_rows must be positive.")
    _validate_amounts(structure_amount, detail_amount)
    if sky_mask.dtype != np.float32 or sky_mask.shape != image.shape[:2]:
        raise ValueError("Sky mask must be normalized float32 with image dimensions.")
    if not np.isfinite(sky_mask).all() or np.any(sky_mask < 0) or np.any(sky_mask > 1):
        raise ValueError("Sky mask values must be finite and in [0,1].")

    if structure_amount == 0.0 and detail_amount == 0.0:
        return image.copy()

    height = image.shape[0]
    chunk_total = (height + chunk_rows - 1) // chunk_rows
    noise_bands = (height + NOISE_SAMPLE_BAND_ROWS - 1) // NOISE_SAMPLE_BAND_ROWS
    progress_total = noise_bands + chunk_total

    sigma = _estimate_noise_sigma(
        image,
        sky_mask,
        should_interrupt=should_interrupt,
        progress_callback=progress_callback,
        progress_offset=0,
        progress_total=progress_total,
    )
    if sigma is None:
        return None

    structure_gain = float(structure_amount) / PERCENT_SCALE * STRUCTURE_GAIN_AT_FULL
    detail_gain = float(detail_amount) / PERCENT_SCALE * DETAIL_GAIN_AT_FULL
    structure_threshold = max(sigma * STRUCTURE_NOISE_MULTIPLIER, MIN_NOISE_SIGMA)
    detail_threshold = max(sigma * DETAIL_NOISE_MULTIPLIER, MIN_NOISE_SIGMA)

    halo = max(_kernel_radius(STRUCTURE_SIGMA_PX), _kernel_radius(DETAIL_SIGMA_PX))
    result = np.empty_like(image)
    for index, start in enumerate(range(0, height, chunk_rows)):
        if should_interrupt is not None and should_interrupt():
            return None
        end = min(start + chunk_rows, height)
        lo, hi = max(0, start - halo), min(height, end + halo)
        rgb = image[lo:hi]
        weight = sky_mask[lo:hi]
        luminance = rgb_luminance(rgb)

        # Two-scale decomposition: Structure is the band between the fine and
        # broad scales, Detail is everything finer than the detail scale. Adding
        # both recovers the broad high-pass L - Gaussian(L, structure) while
        # keeping the two controls independent. Mask-normalized scales prevent
        # ground luminance from bleeding into the sky near a horizon.
        detail_scale = _normalized_blur(luminance, weight, DETAIL_SIGMA_PX)
        broad_scale = _normalized_blur(luminance, weight, STRUCTURE_SIGMA_PX)
        structure_band = detail_scale - broad_scale
        detail_band = luminance - detail_scale
        delta = structure_gain * structure_band * _smooth_gate(structure_band, structure_threshold)
        delta += detail_gain * detail_band * _smooth_gate(detail_band, detail_threshold)

        cap = np.minimum(MAX_LUMINANCE_DELTA, LOCAL_HEADROOM_FRACTION * np.minimum(luminance, 1.0 - luminance))
        np.clip(delta, -cap, cap, out=delta)

        # Multiplicative luminance gain preserves channel ratios. At zero
        # luminance the cap is zero; keeping gain 1 avoids a division there.
        gain = np.ones_like(luminance)
        np.divide(luminance + delta, luminance, out=gain, where=luminance > LUMINANCE_EPSILON)

        # Positive gain must not drive the brightest channel past white. This
        # is a scalar limit, so channel ratios remain intact while it is active.
        channel_limit = np.ones_like(luminance)
        max_channel = np.max(rgb, axis=2)
        np.divide(1.0, max_channel, out=channel_limit, where=max_channel > LUMINANCE_EPSILON)
        np.minimum(gain, channel_limit, out=gain)

        sharpened = rgb * gain[..., np.newaxis]
        np.clip(sharpened, 0.0, 1.0, out=sharpened)

        central = slice(start - lo, start - lo + (end - start))
        np.add(
            rgb[central],
            weight[central, :, np.newaxis] * (sharpened[central] - rgb[central]),
            out=result[start:end],
        )
        if progress_callback is not None:
            progress_callback(noise_bands + index + 1, progress_total, "Enhancing starless structure...")

    return result


__all__ = [
    "DEFAULT_CHUNK_ROWS",
    "DETAIL_SIGMA_PX",
    "MAX_LUMINANCE_DELTA",
    "STARLESS_FILTER_VERSION",
    "STRUCTURE_SIGMA_PX",
    "sharpen_starless",
]
