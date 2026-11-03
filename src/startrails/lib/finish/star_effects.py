"""Numerical star-effect layers built from the ranked star catalog.

Round Stars is stored once at full strength as a sparse patch delta. Glow is
rendered once as an additive halo layer. Composition scales those layers by the
enabled amounts; it never re-runs analysis, filtering or worker jobs. All
effect deltas are protected by the soft sky mask exactly once.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final, Optional, Sequence, Tuple, Union

import cv2
import numpy as np
from scipy.spatial import cKDTree

from startrails.lib.finish.star_analysis import (
    StarCandidate,
    _local_peak_mask,
    _second_moments,
)
from startrails.lib.finish.star_catalog import RankedStarCatalog
from startrails.lib.image_io import validate_image_array

STAR_EFFECT_VERSION: Final[int] = 4

# Round Stars gates and reconstruction constants. These are policy for the
# isolated-star feature, not user-facing settings.
CORRECT_MIN_ELLIPTICITY: Final[float] = 0.10
CORRECT_MIN_PEAK: Final[float] = 0.02
PEAK_HEADROOM_FACTOR: Final[float] = 1.25
FEATHER_INNER_FRACTION: Final[float] = 0.65
MAX_VERIFY_CENTROID_SHIFT_PX: Final[float] = 0.5
MAX_VERIFY_FLUX_ERROR: Final[float] = 0.01
MAX_VERIFY_COLOR_DRIFT: Final[float] = 0.01
VERIFY_ELLIPTICITY_RATIO_AT_FULL: Final[float] = 0.75
MIN_FEATHER_SCALE: Final[float] = 0.35
MIN_OWNED_CORE_COVERAGE: Final[float] = 0.5
OWNERSHIP_FEATHER_PX: Final[float] = 2.0
TRADITIONAL_GATE_ROUNDS: Final[int] = 8


ROUND_GATE_FRACTIONS: Final[Tuple[float, ...]] = (0.25, 0.5, 0.75, 1.0)

# Star Glow spatial profile and rendering policy.
GLOW_SIGMA_FRACTION: Final[float] = 1.0 / 3.0
GLOW_PYRAMID_RADIUS_PX: Final[float] = 64.0
GLOW_PYRAMID_MIN_SIGMA_PX: Final[float] = 1.5

ROUND_DELTA_FORMAT_VERSION: Final[int] = 2
PERCENT_SCALE: Final[float] = 100.0

_INTERRUPT_INTERVAL: Final[int] = 64

ProgressCallback = Callable[[int, int, str], None]


def _feather_weights(dy: np.ndarray, dx: np.ndarray, radius: float) -> np.ndarray:
    distance = np.hypot(dy, dx)
    inner = FEATHER_INNER_FRACTION * radius
    t = np.clip((distance - inner) / max(radius - inner, 1e-6), 0.0, 1.0)
    smooth = t * t * (3.0 - 2.0 * t)
    return 1.0 - smooth


def _measure_local(stars: np.ndarray, x: float, y: float, radius: float) -> Tuple[float, float, float]:
    """Return (centroid_y, centroid_x, ellipticity) around a known star."""
    height, width = stars.shape[:2]
    iy, ix = int(round(y)), int(round(x))
    y0, y1 = max(0, iy - int(np.ceil(radius))), min(height, iy + int(np.ceil(radius)) + 1)
    x0, x1 = max(0, ix - int(np.ceil(radius))), min(width, ix + int(np.ceil(radius)) + 1)
    luminance = stars[y0:y1, x0:x1].max(axis=2)
    background = float(np.median(luminance))
    weights = np.maximum(luminance - background, 0.0).astype(np.float64)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    total = float(weights.sum())
    if total <= 0.0:
        return y, x, 0.0
    cy = float((weights * yy).sum() / total)
    cx = float((weights * xx).sum() / total)
    dy = yy - cy
    dx = xx - cx
    cyy = float((weights * dy * dy).sum() / total)
    cxx = float((weights * dx * dx).sum() / total)
    cxy = float((weights * dx * dy).sum() / total)
    covariance = np.array([[cyy, cxy], [cxy, cxx]], dtype=np.float64)
    eigenvalues = np.linalg.eigvalsh(covariance)
    a = float(np.sqrt(max(float(eigenvalues[1]), 1e-6)))
    b = float(np.sqrt(max(float(eigenvalues[0]), 1e-6)))
    return cy, cx, (a - b) / (a + b)


def _footprint_flux(stars: np.ndarray, x: float, y: float, radius: float) -> np.ndarray:
    height, width = stars.shape[:2]
    iy, ix = int(round(y)), int(round(x))
    y0, y1 = max(0, iy - int(np.ceil(radius))), min(height, iy + int(np.ceil(radius)) + 1)
    x0, x1 = max(0, ix - int(np.ceil(radius))), min(width, ix + int(np.ceil(radius)) + 1)
    dys = (np.arange(y0, y1, dtype=np.float64) - y) ** 2
    dxs = (np.arange(x0, x1, dtype=np.float64) - x) ** 2
    inside = (dys[:, None] + dxs[None, :]) <= radius * radius
    return stars[y0:y1, x0:x1][inside].sum(axis=0, dtype=np.float64)


@dataclass(frozen=True)
class _Support:
    rank: int
    rect: Tuple[int, int, int, int]
    local_y: np.ndarray
    local_x: np.ndarray
    values: np.ndarray


def _round_gates(candidate: StarCandidate) -> bool:
    return (
        candidate.is_valid
        and not candidate.is_saturated
        and not candidate.is_border
        and candidate.ellipticity >= CORRECT_MIN_ELLIPTICITY
        and candidate.peak_brightness >= CORRECT_MIN_PEAK
    )


def _ineligible_reason(candidate: StarCandidate) -> str:
    if not candidate.is_valid:
        return candidate.skip_reason or "invalid"
    if candidate.is_saturated:
        return "saturated"
    if candidate.is_border:
        return "border"
    if candidate.ellipticity < CORRECT_MIN_ELLIPTICITY:
        return "low_ellipticity"
    if candidate.peak_brightness < CORRECT_MIN_PEAK:
        return "faint"
    return "ineligible"


def _component_peak_counts(
    stars: np.ndarray,
    candidate: StarCandidate,
    rect: Tuple[int, int, int, int],
    threshold: float,
    labels: np.ndarray,
    component_id: int,
) -> Tuple[int, int, int]:
    """Count core local maxima in this component / other components / unknown."""
    y0, x0, y1, x1 = rect
    yy, xx = np.mgrid[y0:y1, x0:x1]
    core = (yy - candidate.y) ** 2 + (xx - candidate.x) ** 2 <= candidate.core_radius_px**2
    luminance = stars[y0:y1, x0:x1].max(axis=2)
    local_max = _local_peak_mask(luminance, core, threshold)
    peak_labels = labels[y0:y1, x0:x1][local_max]
    own = int(np.count_nonzero(peak_labels == component_id))
    other = int(np.count_nonzero((peak_labels > 0) & (peak_labels != component_id)))
    unknown = int(np.count_nonzero(peak_labels == 0))
    return own, other, unknown


def _neighbors(
    candidate: StarCandidate,
    rank: int,
    candidates: Sequence[StarCandidate],
    included_count: int,
    tree: Optional[cKDTree],
    cores: np.ndarray,
    max_core: float,
) -> list[Tuple[StarCandidate, bool]]:
    if tree is None:
        return []
    radius = candidate.footprint_radius_px
    reach = max(2.0 * radius, radius + max_core)
    result = []
    for index in tree.query_ball_point([candidate.x, candidate.y], r=float(reach)):
        if index == rank:
            continue
        distance = float(np.hypot(candidate.x - candidates[index].x, candidate.y - candidates[index].y))
        if distance < 2.0 * radius or distance < radius + cores[index]:
            result.append((candidates[index], index < included_count))
    return result


def _strict_owner_mask(
    candidate: StarCandidate,
    neighbors: Sequence[Tuple[StarCandidate, bool]],
    yy: np.ndarray,
    xx: np.ndarray,
    inclusion_patch: np.ndarray,
) -> np.ndarray:
    own = np.ones(yy.shape, dtype=bool)
    for other, included in neighbors:
        if other.x == candidate.x and other.y == candidate.y:
            continue
        d_self = (xx - candidate.x) ** 2 + (yy - candidate.y) ** 2
        d_other = (xx - other.x) ** 2 + (yy - other.y) ** 2
        own &= d_self < d_other
        if included:
            own &= d_other > max(other.core_radius_px, 1.0) ** 2
    own &= inclusion_patch > 0.0
    return own


def _ownership_feather(
    candidate: StarCandidate,
    neighbors: Sequence[Tuple[StarCandidate, bool]],
    inclusion_mask: np.ndarray,
    rect: Tuple[int, int, int, int],
) -> np.ndarray:
    y0, x0, y1, x1 = rect
    pad = int(np.ceil(OWNERSHIP_FEATHER_PX)) + 1
    height, width = inclusion_mask.shape
    ey0, ey1 = max(0, y0 - pad), min(height, y1 + pad)
    ex0, ex1 = max(0, x0 - pad), min(width, x1 + pad)
    yy, xx = np.mgrid[ey0:ey1, ex0:ex1]
    cell = _strict_owner_mask(
        candidate,
        neighbors,
        yy,
        xx,
        inclusion_mask[ey0:ey1, ex0:ex1],
    )
    distance = cv2.distanceTransform(cell.astype(np.uint8), cv2.DIST_L2, 5)
    t = np.clip(distance / OWNERSHIP_FEATHER_PX, 0.0, 1.0)
    feather = (t * t * (3.0 - 2.0 * t)).astype(np.float64)
    return feather[y0 - ey0 : y0 - ey0 + (y1 - y0), x0 - ex0 : x0 - ex0 + (x1 - x0)]


def _owned_moments_patch(
    window: np.ndarray,
    candidate: StarCandidate,
    own: np.ndarray,
    center_y: float,
    center_x: float,
    y0: int,
    x0: int,
) -> Tuple[float, float, float, float, float]:
    y1 = y0 + window.shape[0]
    x1 = x0 + window.shape[1]
    yy, xx = np.mgrid[y0:y1, x0:x1]
    data = window.astype(np.float64)
    ring = (
        ((yy - center_y) ** 2 + (xx - center_x) ** 2 >= 0.8 * candidate.footprint_radius_px**2)
        & ((yy - center_y) ** 2 + (xx - center_x) ** 2 <= candidate.footprint_radius_px**2)
        & own
    )
    ring_values = data[ring]
    background = np.median(ring_values, axis=0) if ring_values.size else np.zeros(3)
    background = np.maximum(background, 0.0)
    weights = np.maximum(data - background, 0.0).max(axis=2) * own
    if float(weights.sum()) <= 0.0:
        return center_y, center_x, candidate.major_sigma_px, candidate.minor_sigma_px, candidate.ellipticity
    return _second_moments(
        weights,
        np.arange(y0, y1, dtype=np.float64),
        np.arange(x0, x1, dtype=np.float64),
    )[:5]


def _owned_moments(
    image: np.ndarray,
    candidate: StarCandidate,
    own: np.ndarray,
    rect: Tuple[int, int, int, int],
    center_y: float,
    center_x: float,
) -> Tuple[float, float, float, float, float]:
    y0, x0, y1, x1 = rect
    return _owned_moments_patch(
        image[y0:y1, x0:x1],
        candidate,
        own,
        center_y,
        center_x,
        y0,
        x0,
    )


def _owned_flux(
    image: np.ndarray,
    candidate: StarCandidate,
    radius: float,
    own: np.ndarray,
    rect: Tuple[int, int, int, int],
) -> np.ndarray:
    y0, x0, y1, x1 = rect
    yy, xx = np.mgrid[y0:y1, x0:x1]
    selected = ((yy - candidate.y) ** 2 + (xx - candidate.x) ** 2 <= radius * radius) & own
    if not np.any(selected):
        return np.zeros(3)
    return image[y0:y1, x0:x1][selected].sum(axis=0, dtype=np.float64)


def _radial_model(
    stamp: np.ndarray,
    own: np.ndarray,
    dy: np.ndarray,
    dx: np.ndarray,
    distance: np.ndarray,
    radius: float,
    candidate: StarCandidate,
    major_sigma: float,
    minor_sigma: float,
    background: np.ndarray,
) -> np.ndarray:
    signal = np.maximum(stamp - background, 0.0) * own[..., None]

    bin_count = int(np.ceil(radius)) + 1
    bin_index = np.floor(distance).astype(int)
    profile = np.zeros((bin_count, 3), dtype=np.float64)
    counts = np.zeros(bin_count, dtype=np.float64)
    for bin_number in range(bin_count):
        selected = (bin_index == bin_number) & own
        if np.any(selected):
            profile[bin_number] = signal[selected].mean(axis=0)
            counts[bin_number] = float(selected.sum())
    valid_bins = np.where(counts > 0)[0]
    if valid_bins.size < 2:
        return np.zeros_like(stamp)
    for channel in range(3):
        profile[:, channel] = np.interp(
            np.arange(bin_count, dtype=np.float64),
            valid_bins.astype(np.float64),
            profile[valid_bins, channel],
        )
    peak_bin = int(np.argmax(profile.sum(axis=1)))
    for bin_number in range(peak_bin + 1, bin_count):
        profile[bin_number] = np.minimum(profile[bin_number], profile[bin_number - 1])
    profile = np.maximum(profile, 0.0)

    azimuthal_sigma = float(np.sqrt((major_sigma**2 + minor_sigma**2) / 2.0))
    target_sigma = float(np.sqrt(major_sigma * minor_sigma))
    radial_scale = float(np.clip(target_sigma / max(azimuthal_sigma, 1e-6), MIN_FEATHER_SCALE, 1.0))
    peak_limit = min(1.0, max(PEAK_HEADROOM_FACTOR * candidate.peak_brightness, CORRECT_MIN_PEAK))
    radial_scale = max(radial_scale, float(np.sqrt(float(profile.max()) / max(peak_limit, 1e-6))))
    radial_scale = float(np.clip(radial_scale, MIN_FEATHER_SCALE, 1.0))

    sample_radius = np.clip(distance / radial_scale, 0.0, bin_count - 1.0001)
    lower = np.floor(sample_radius).astype(int)
    upper = np.minimum(lower + 1, bin_count - 1)
    fraction = (sample_radius - lower)[..., None]
    model = profile[lower] * (1.0 - fraction) + profile[upper] * fraction
    model = np.maximum(model, 0.0) / (radial_scale * radial_scale)
    return model


def _round_one_owned(
    out: np.ndarray,
    candidate: StarCandidate,
    rank: int,
    neighbors: Sequence[Tuple[StarCandidate, bool]],
    sky_mask: np.ndarray,
    inclusion_mask: np.ndarray,
    remeasure: bool,
    threshold: float,
) -> Tuple[str, Optional[_Support]]:
    height, width = out.shape[:2]
    radius = candidate.footprint_radius_px
    core_radius = candidate.core_radius_px
    rect = _candidate_rect(candidate, (height, width))
    if rect is None:
        return "ineligible:no_patch", None
    iy0, ix0, iy1, ix1 = rect
    stamp = out[iy0:iy1, ix0:ix1].astype(np.float64)
    before_patch = out[iy0:iy1, ix0:ix1].copy()
    yy, xx = np.mgrid[iy0:iy1, ix0:ix1]
    own = _strict_owner_mask(candidate, neighbors, yy, xx, inclusion_mask[iy0:iy1, ix0:ix1])
    own &= (yy - candidate.y) ** 2 + (xx - candidate.x) ** 2 <= radius * radius
    if not np.any(own):
        return "rejected:no_owned_support", None
    ring = (
        ((yy - candidate.y) ** 2 + (xx - candidate.x) ** 2 >= 0.8 * radius**2)
        & ((yy - candidate.y) ** 2 + (xx - candidate.x) ** 2 <= radius**2)
        & own
    )
    ring_values = stamp[ring]
    background = np.median(ring_values, axis=0) if ring_values.size else np.zeros(3)
    background = np.maximum(background, 0.0)
    if remeasure:
        center_y, center_x, major_sigma, minor_sigma, _ = _owned_moments(
            out, candidate, own, rect, candidate.y, candidate.x
        )
    else:
        center_y, center_x = candidate.y, candidate.x
        major_sigma, minor_sigma = candidate.major_sigma_px, candidate.minor_sigma_px
    dy = yy - center_y
    dx = xx - center_x
    distance = np.hypot(dy, dx)
    core_total = distance <= core_radius
    core_inside = core_total & own
    coverage = float(core_inside.sum()) / float(core_total.sum()) if np.any(core_total) else 0.0
    if coverage < MIN_OWNED_CORE_COVERAGE:
        return "blocked:owned_core_coverage", None
    if remeasure:
        luminance = out[iy0:iy1, ix0:ix1].max(axis=2)
        owned_peaks = int(_local_peak_mask(luminance, core_inside, threshold).sum())
        if owned_peaks == 0:
            return "rejected:no_owned_peak", None
        if owned_peaks > 1:
            return "ineligible:multi_peak_owned", None
    model = _radial_model(
        stamp,
        own,
        dy,
        dx,
        distance,
        radius,
        candidate,
        major_sigma,
        minor_sigma,
        background,
    )
    if not np.any(model):
        return "rejected:no_owned_support", None

    weight = _feather_weights(dy, dx, radius)[..., None] * own[..., None]
    weight *= _ownership_feather(candidate, neighbors, inclusion_mask, rect)[..., None]
    delta = weight * (model + background - stamp)
    denominator = float(weight.sum())
    if denominator <= 0.0:
        return "rejected:no_owned_support", None
    delta -= (delta.sum(axis=(0, 1)) / denominator)[None, None, :] * weight
    delta *= sky_mask[iy0:iy1, ix0:ix1, None]
    if not np.any(delta):
        return "rejected:no_owned_support", None

    cy_before, cx_before, _, _, e_before = _owned_moments(out, candidate, own, rect, candidate.y, candidate.x)
    flux_before = _owned_flux(out, candidate, radius, own, rect)
    corrected_patch = np.clip(stamp + delta, 0.0, 1.0).astype(np.float32)
    out[iy0:iy1, ix0:ix1][own] = corrected_patch[own]
    cy_after, cx_after, _, _, e_after = _owned_moments(out, candidate, own, rect, candidate.y, candidate.x)
    flux_after = _owned_flux(out, candidate, radius, own, rect)
    shift = float(np.hypot(cy_after - cy_before, cx_after - cx_before))
    flux_error = float(np.max(np.abs(flux_after - flux_before) / np.maximum(np.abs(flux_before), 1e-9)))
    total_before = float(flux_before.sum())
    total_after = float(flux_after.sum())
    if total_before > 0.0 and total_after > 0.0:
        color_drift = float(
            np.max(
                np.abs(flux_after / total_after - flux_before / total_before)
                / np.maximum(np.abs(flux_before / total_before), 1e-9)
            )
        )
    else:
        color_drift = 0.0
    core_after = (distance <= core_radius) & own
    mean_mask = float(sky_mask[iy0:iy1, ix0:ix1][core_after].mean()) if np.any(core_after) else 0.0
    amount_effective = max(0.0, min(1.0, mean_mask))
    e_limit = max(
        0.10,
        (1.0 - (1.0 - VERIFY_ELLIPTICITY_RATIO_AT_FULL) * amount_effective) * e_before,
    )
    if (
        not np.isfinite(shift)
        or not np.isfinite(flux_error)
        or not np.isfinite(color_drift)
        or shift > MAX_VERIFY_CENTROID_SHIFT_PX
        or flux_error > MAX_VERIFY_FLUX_ERROR
        or color_drift > MAX_VERIFY_COLOR_DRIFT
        or e_after > e_limit
    ):
        out[iy0:iy1, ix0:ix1] = before_patch
        return "rejected:verification", None

    for amount in ROUND_GATE_FRACTIONS:
        partial = before_patch.astype(np.float64)
        partial[own] = np.clip(stamp[own] + amount * delta[own], 0.0, 1.0)
        _, _, _, _, e_intermediate = _owned_moments_patch(partial, candidate, own, candidate.y, candidate.x, iy0, ix0)
        intermediate_amount = amount * amount_effective
        limit = max(
            0.10,
            (1.0 - (1.0 - VERIFY_ELLIPTICITY_RATIO_AT_FULL) * intermediate_amount) * e_before,
        )
        if e_intermediate > limit:
            out[iy0:iy1, ix0:ix1] = before_patch
            return "rejected:amount_verification", None

    difference = out[iy0:iy1, ix0:ix1] - before_patch
    local_y, local_x = np.nonzero(np.any(difference != 0.0, axis=2))
    return (
        "corrected",
        _Support(
            rank=rank,
            rect=rect,
            local_y=local_y.astype(np.int32),
            local_x=local_x.astype(np.int32),
            values=difference[local_y, local_x].astype(np.float32),
        ),
    )


def _validate_image_and_mask(stars: np.ndarray, sky_mask: np.ndarray) -> None:
    validate_image_array(stars)
    if sky_mask.shape != stars.shape[:2] or sky_mask.dtype != np.float32:
        raise ValueError("sky_mask must be normalized float32 with image dimensions.")
    if not np.isfinite(sky_mask).all() or np.any(sky_mask < 0.0) or np.any(sky_mask > 1.0):
        raise ValueError("sky_mask values must be finite and in [0,1].")


def _validate_inclusion_mask(inclusion_mask: np.ndarray, stars: np.ndarray) -> None:
    if inclusion_mask.shape != stars.shape[:2] or inclusion_mask.dtype != np.float32:
        raise ValueError("inclusion_mask must be float32 with image dimensions.")
    if not np.isfinite(inclusion_mask).all() or np.any(inclusion_mask < 0.0) or np.any(inclusion_mask > 1.0):
        raise ValueError("inclusion_mask values must be finite and in [0,1].")


def _candidate_rect(candidate: StarCandidate, shape: Tuple[int, int]) -> Optional[Tuple[int, int, int, int]]:
    height, width = shape
    radius = candidate.footprint_radius_px
    y0 = max(0, int(np.floor(candidate.y - radius)))
    y1 = min(height, int(np.ceil(candidate.y + radius)) + 1)
    x0 = max(0, int(np.floor(candidate.x - radius)))
    x1 = min(width, int(np.ceil(candidate.x + radius)) + 1)
    if y0 >= y1 or x0 >= x1:
        return None
    return y0, x0, y1, x1


@dataclass(frozen=True)
class SparseRoundDelta:
    """Packed actual-support deltas for one full-strength Round Stars pass.

    ``values[offsets[i]:offsets[i+1]]`` are the exact float32
    ``clip(S_inc + correction, 0, 1) - S_inc`` samples for patch ``i``.
    ``local_y``/``local_x`` address those samples inside the bounded region
    ``(y0[i], x0[i], height[i], width[i])``. Only changed pixels are stored, so
    storage is proportional to the accepted correction support rather than to
    a padded rectangle or a merged bounding box. The global write coordinates
    are unique: accepted circular supports do not overlap. ``decision`` records
    the per-rank coverage baseline.
    """

    y0: np.ndarray
    x0: np.ndarray
    height: np.ndarray
    width: np.ndarray
    offsets: np.ndarray
    local_y: np.ndarray
    local_x: np.ndarray
    values: np.ndarray
    image_shape: Tuple[int, int]
    rank: np.ndarray
    decision: np.ndarray

    def __post_init__(self) -> None:
        _validate_round_delta(self)


def _int_vector(name: str, value) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != 1:
        raise ValueError(f"round delta {name} must be one-dimensional.")
    if not np.issubdtype(array.dtype, np.integer):
        raise ValueError(f"round delta {name} must have an integer dtype.")
    return array


def _validate_round_delta(delta: SparseRoundDelta) -> None:
    y0 = _int_vector("y0", delta.y0)
    x0 = _int_vector("x0", delta.x0)
    height = _int_vector("height", delta.height)
    width = _int_vector("width", delta.width)
    offsets = _int_vector("offsets", delta.offsets)
    local_y = _int_vector("local_y", delta.local_y)
    local_x = _int_vector("local_x", delta.local_x)
    rank = _int_vector("rank", delta.rank)

    count = y0.shape[0]
    if not (x0.shape[0] == height.shape[0] == width.shape[0] == count):
        raise ValueError("round delta patch arrays must have equal length.")
    if offsets.shape[0] == 0 or offsets.shape[0] != count + 1:
        raise ValueError("round delta offsets must have one entry per patch plus one.")
    if int(offsets[0]) != 0 or np.any(np.diff(offsets) < 0):
        raise ValueError("round delta offsets must be monotonic and start at zero.")
    support_count = int(offsets[-1])
    if local_y.shape[0] != support_count or local_x.shape[0] != support_count:
        raise ValueError("round delta local coordinates must match the offsets.")
    values = np.asarray(delta.values)
    if values.ndim != 2 or values.shape[1] != 3 or values.shape[0] != support_count:
        raise ValueError("round delta values must have shape (N, 3).")
    if values.dtype != np.float32:
        raise ValueError("round delta values must be float32.")
    if not np.isfinite(values).all():
        raise ValueError("round delta values must be finite.")

    raw_shape = np.asarray(delta.image_shape)
    if raw_shape.ndim != 1 or raw_shape.size != 2 or not np.issubdtype(raw_shape.dtype, np.integer):
        raise ValueError("round delta image_shape must be a two-element integer sequence.")
    image_height, image_width = int(raw_shape[0]), int(raw_shape[1])
    if image_height <= 0 or image_width <= 0:
        raise ValueError("round delta image dimensions must be positive.")

    if count:
        if np.any(y0 < 0) or np.any(x0 < 0):
            raise ValueError("round delta patch origins must be non-negative.")
        if np.any(height <= 0) or np.any(width <= 0):
            raise ValueError("round delta patch sizes must be positive.")
        if np.any(y0 + height > image_height) or np.any(x0 + width > image_width):
            raise ValueError("round delta patch regions must lie inside the image.")
    if support_count:
        counts = np.diff(offsets)
        repeated_height = np.repeat(height, counts)
        repeated_width = np.repeat(width, counts)
        repeated_y0 = np.repeat(y0, counts)
        repeated_x0 = np.repeat(x0, counts)
        if np.any(local_y < 0) or np.any(local_y >= repeated_height):
            raise ValueError("round delta local y indices must be inside their patch.")
        if np.any(local_x < 0) or np.any(local_x >= repeated_width):
            raise ValueError("round delta local x indices must be inside their patch.")
        global_y = repeated_y0.astype(np.int64) + local_y.astype(np.int64)
        global_x = repeated_x0.astype(np.int64) + local_x.astype(np.int64)
        if np.any(global_y < 0) or np.any(global_y >= image_height):
            raise ValueError("round delta support lies outside the image.")
        if np.any(global_x < 0) or np.any(global_x >= image_width):
            raise ValueError("round delta support lies outside the image.")
        keys = global_y * image_width + global_x
        if np.unique(keys).size != keys.size:
            raise ValueError("round delta support pixels must not overlap.")

    decision = np.asarray(delta.decision)
    if decision.ndim != 1 or not np.issubdtype(decision.dtype, np.str_):
        raise ValueError("round delta decisions must be a one-dimensional string array.")
    if decision.shape[0] != rank.shape[0]:
        raise ValueError("round delta rank and decision arrays must have equal length.")
    if np.any(decision == ""):
        raise ValueError("round delta decisions must not be empty.")
    if not np.array_equal(rank, np.arange(rank.shape[0])):
        raise ValueError("round delta ranks must be the full ordered 0..N-1 sequence.")


def save_round_delta(path: Union[str, Path], delta: SparseRoundDelta, *, identity: str) -> Path:
    """Persist a packed round delta as arrays only (never pickle)."""
    if not isinstance(identity, str) or not identity:
        raise ValueError("identity must be a non-empty string.")
    _validate_round_delta(delta)
    destination = Path(path)
    arrays = {
        "format_version": np.asarray(ROUND_DELTA_FORMAT_VERSION, dtype=np.int32),
        "star_effect_version": np.asarray(STAR_EFFECT_VERSION, dtype=np.int32),
        "identity": np.asarray(identity),
        "image_shape": np.asarray(delta.image_shape, dtype=np.int64),
        "y0": np.asarray(delta.y0, dtype=np.int32),
        "x0": np.asarray(delta.x0, dtype=np.int32),
        "height": np.asarray(delta.height, dtype=np.int32),
        "width": np.asarray(delta.width, dtype=np.int32),
        "offsets": np.asarray(delta.offsets, dtype=np.int64),
        "local_y": np.asarray(delta.local_y, dtype=np.int32),
        "local_x": np.asarray(delta.local_x, dtype=np.int32),
        "values": np.asarray(delta.values, dtype=np.float32),
        "rank": np.asarray(delta.rank, dtype=np.int32),
        "decision": np.asarray(delta.decision),
    }
    with destination.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    return destination


def _load_int_vector(data, name: str) -> np.ndarray:
    array = np.asarray(data[name])
    if array.ndim != 1:
        raise ValueError(f"round delta {name} must be one-dimensional.")
    if not np.issubdtype(array.dtype, np.integer):
        raise ValueError(f"round delta {name} must have an integer dtype.")
    return array


def load_round_delta(path: Union[str, Path], *, identity: str) -> SparseRoundDelta:
    """Load a packed round delta, rejecting pickles and malformed raw arrays."""
    required = {
        "format_version",
        "star_effect_version",
        "identity",
        "image_shape",
        "y0",
        "x0",
        "height",
        "width",
        "offsets",
        "local_y",
        "local_x",
        "values",
        "rank",
        "decision",
    }
    with np.load(Path(path), allow_pickle=False) as data:
        missing = required.difference(data.files)
        if missing:
            raise ValueError(f"round delta is missing arrays: {sorted(missing)}")
        raw_version = np.asarray(data["format_version"])
        if raw_version.ndim != 0 or not np.issubdtype(raw_version.dtype, np.integer):
            raise ValueError("round delta format_version must be an integer scalar.")
        if int(raw_version) != ROUND_DELTA_FORMAT_VERSION:
            raise ValueError("unsupported round delta format version.")
        raw_effect_version = np.asarray(data["star_effect_version"])
        if raw_effect_version.ndim != 0 or not np.issubdtype(raw_effect_version.dtype, np.integer):
            raise ValueError("round delta star_effect_version must be an integer scalar.")
        if int(raw_effect_version) != STAR_EFFECT_VERSION:
            raise ValueError("round delta star effect version does not match.")
        raw_identity = np.asarray(data["identity"])
        if raw_identity.ndim != 0 or not np.issubdtype(raw_identity.dtype, np.str_):
            raise ValueError("round delta identity must be a string scalar.")
        if str(raw_identity.item()) != identity:
            raise ValueError("round delta identity does not match this project.")

        raw_shape = np.asarray(data["image_shape"])
        if raw_shape.ndim != 1 or raw_shape.size != 2 or not np.issubdtype(raw_shape.dtype, np.integer):
            raise ValueError("round delta image_shape must be a two-element integer sequence.")
        image_shape = (int(raw_shape[0]), int(raw_shape[1]))

        y0 = _load_int_vector(data, "y0").astype(np.int32)
        x0 = _load_int_vector(data, "x0").astype(np.int32)
        height = _load_int_vector(data, "height").astype(np.int32)
        width = _load_int_vector(data, "width").astype(np.int32)
        offsets = _load_int_vector(data, "offsets").astype(np.int64)
        local_y = _load_int_vector(data, "local_y").astype(np.int32)
        local_x = _load_int_vector(data, "local_x").astype(np.int32)
        values = np.asarray(data["values"])
        if values.dtype != np.float32 or values.ndim != 2 or values.shape[1] != 3:
            raise ValueError("round delta values must be a float32 (N, 3) array.")
        rank = _load_int_vector(data, "rank").astype(np.int32)
        decision = np.asarray(data["decision"])
        if decision.ndim != 1 or not np.issubdtype(decision.dtype, np.str_):
            raise ValueError("round delta decisions must be a one-dimensional string array.")

        delta = SparseRoundDelta(
            y0=y0,
            x0=x0,
            height=height,
            width=width,
            offsets=offsets,
            local_y=local_y,
            local_x=local_x,
            values=values,
            image_shape=image_shape,
            rank=rank,
            decision=decision,
        )
    return delta


def _pack_supports(
    supports: Sequence[_Support],
    decisions: Sequence[str],
    image_shape: Tuple[int, int],
) -> SparseRoundDelta:
    y0_parts: list[np.ndarray] = []
    x0_parts: list[np.ndarray] = []
    height_parts: list[np.ndarray] = []
    width_parts: list[np.ndarray] = []
    local_y_parts: list[np.ndarray] = []
    local_x_parts: list[np.ndarray] = []
    value_parts: list[np.ndarray] = []
    offsets = [0]
    for support in supports:
        if support.local_y.size == 0:
            continue
        y0, x0, y1, x1 = support.rect
        y0_parts.append(np.asarray([y0], np.int32))
        x0_parts.append(np.asarray([x0], np.int32))
        height_parts.append(np.asarray([y1 - y0], np.int32))
        width_parts.append(np.asarray([x1 - x0], np.int32))
        local_y_parts.append(support.local_y)
        local_x_parts.append(support.local_x)
        value_parts.append(support.values)
        offsets.append(offsets[-1] + int(support.local_y.size))

    def joined(parts: list[np.ndarray], dtype) -> np.ndarray:
        return np.concatenate(parts).astype(dtype, copy=False) if parts else np.empty(0, dtype=dtype)

    return SparseRoundDelta(
        y0=joined(y0_parts, np.int32),
        x0=joined(x0_parts, np.int32),
        height=joined(height_parts, np.int32),
        width=joined(width_parts, np.int32),
        offsets=np.asarray(offsets, dtype=np.int64),
        local_y=joined(local_y_parts, np.int32),
        local_x=joined(local_x_parts, np.int32),
        values=(
            np.concatenate(value_parts).astype(np.float32, copy=False)
            if value_parts
            else np.empty((0, 3), dtype=np.float32)
        ),
        image_shape=(int(image_shape[0]), int(image_shape[1])),
        rank=np.arange(len(decisions), dtype=np.int32),
        decision=np.asarray(decisions, dtype=np.str_),
    )


def _assemble_supports(
    base: np.ndarray,
    supports: Sequence[_Support],
    amount: float = 1.0,
) -> np.ndarray:
    out = base.copy()
    for support in supports:
        y0, x0, _, _ = support.rect
        out[y0 + support.local_y, x0 + support.local_x] += amount * support.values
    np.clip(out, 0.0, 1.0, out=out)
    return out


def _victim_reach(candidate: StarCandidate) -> float:
    square_stamp = float(np.sqrt(2.0) * (np.ceil(candidate.core_radius_px) + 1.0))
    return max(candidate.footprint_radius_px, square_stamp)


def _traditional_gate(
    base: np.ndarray,
    candidates: Sequence[StarCandidate],
    supports: Sequence[_Support],
    points: np.ndarray,
    reaches: np.ndarray,
    tree: Optional[cKDTree],
    interrupt: Callable[[], bool],
) -> Optional[set[int]]:
    """Return correction ranks that must be rejected to satisfy the hard gate."""
    active = [support.rank for support in supports]
    if not active or tree is None:
        return set()
    max_reach = float(reaches.max())
    writers_by_victim: dict[int, set[int]] = {rank: {rank} for rank in active}
    victims = set(active)
    for writer in active:
        candidate = candidates[writer]
        reach = float(candidate.footprint_radius_px + max_reach)
        for other in tree.query_ball_point([candidate.x, candidate.y], reach):
            other = int(other)
            if other == writer:
                continue
            if (
                float(np.hypot(candidate.x - points[other, 0], candidate.y - points[other, 1]))
                < candidate.footprint_radius_px + reaches[other]
            ):
                victims.add(other)
                writers_by_victim.setdefault(other, set()).add(writer)

    reject: set[int] = set()
    for amount in ROUND_GATE_FRACTIONS:
        assembled = _assemble_supports(base, supports, amount)
        for index, rank in enumerate(sorted(victims)):
            if (index & (_INTERRUPT_INTERVAL - 1)) == 0 and interrupt():
                return None
            candidate = candidates[rank]
            cy_before, cx_before, _ = _measure_local(base, candidate.x, candidate.y, candidate.core_radius_px)
            cy_after, cx_after, _ = _measure_local(assembled, candidate.x, candidate.y, candidate.core_radius_px)
            flux_before = _footprint_flux(base, candidate.x, candidate.y, candidate.footprint_radius_px)
            flux_after = _footprint_flux(assembled, candidate.x, candidate.y, candidate.footprint_radius_px)
            shift = float(np.hypot(cy_after - cy_before, cx_after - cx_before))
            flux_error = float(np.max(np.abs(flux_after - flux_before) / np.maximum(np.abs(flux_before), 1e-9)))
            total_before = float(flux_before.sum())
            total_after = float(flux_after.sum())
            if total_before > 0.0 and total_after > 0.0:
                colour_error = float(
                    np.max(
                        np.abs(flux_after / total_after - flux_before / total_before)
                        / np.maximum(np.abs(flux_before / total_before), 1e-9)
                    )
                )
            else:
                colour_error = 0.0
            if (
                not np.isfinite(shift)
                or not np.isfinite(flux_error)
                or not np.isfinite(colour_error)
                or shift > MAX_VERIFY_CENTROID_SHIFT_PX
                or flux_error > MAX_VERIFY_FLUX_ERROR
                or colour_error > MAX_VERIFY_COLOR_DRIFT
            ):
                reject.update(writers_by_victim.get(rank, set()))
    return reject


def build_round_delta(
    stars: np.ndarray,
    sky_mask: np.ndarray,
    catalog: RankedStarCatalog,
    *,
    cutoff: Optional[int],
    inclusion_mask: np.ndarray,
    should_interrupt: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Optional[SparseRoundDelta]:
    """Build the full-strength owned-region Round Stars delta.

    Corrections are written only in disjoint owned pixels, then every included
    measured star affected at 25/50/75/100% is gated against the original
    ``S_inc``. Conflicting corrections are rejected deterministically; if the
    bounded gate cannot converge, all remaining corrections are dropped.
    """
    _validate_image_and_mask(stars, sky_mask)
    _validate_inclusion_mask(inclusion_mask, stars)
    interrupt = should_interrupt or (lambda: False)
    if interrupt():
        return None
    candidates = catalog.analysis_for_cutoff(cutoff).candidates
    included_count = catalog.included_count(cutoff)
    points = np.asarray([[c.x, c.y] for c in candidates], dtype=np.float64)
    cores = np.asarray([max(c.core_radius_px, 1.0) for c in candidates], dtype=np.float64)
    max_core = float(cores.max()) if len(cores) else 0.0
    tree = cKDTree(points) if len(points) else None
    included_points = points[:included_count]
    included_reaches = np.asarray(
        [_victim_reach(candidate) for candidate in candidates[:included_count]],
        dtype=np.float64,
    )
    included_tree = cKDTree(included_points) if len(included_points) else None
    decisions = ["excluded"] * len(candidates)
    accepted: list[Tuple[int, StarCandidate, bool]] = []
    for rank in range(included_count):
        if (rank & (_INTERRUPT_INTERVAL - 1)) == 0 and interrupt():
            return None
        candidate = candidates[rank]
        if not _round_gates(candidate):
            decisions[rank] = f"ineligible:{_ineligible_reason(candidate)}"
            continue
        # 10D: an excluded detection never blocks an included correction. Its
        # own label-owned pixels have M == 0 by ownership, so no correction can
        # write there and its thresholded flux stays in read-only Original
        # Stars. Packed support is asserted to have M > 0 below. Excluded ranks
        # still take part in bisector ownership and remain report-only in the
        # neighbour gate. Trade-off: an excluded neighbour's sub-threshold wings
        # inside a corrected star's owned region may be redistributed.
        remeasure = False
        if candidate.is_blended or bool(catalog.intrinsic_blended[rank]):
            rect = _candidate_rect(candidate, stars.shape[:2])
            if rect is None:
                decisions[rank] = "ineligible:no_patch"
                continue
            own_peaks, other_peaks, unknown_peaks = _component_peak_counts(
                stars,
                candidate,
                rect,
                catalog.threshold,
                catalog.labels,
                int(catalog.component_ids[rank]),
            )
            if unknown_peaks:
                decisions[rank] = "ineligible:unattributed_peak"
                continue
            if own_peaks != 1:
                decisions[rank] = "ineligible:multi_peak_component"
                continue
            remeasure = True
        accepted.append((rank, candidate, remeasure))
    accepted.sort(key=lambda item: int(catalog.component_ids[item[0]]))

    base = inclusion_mask[..., None] * stars
    out = base.copy()
    supports: list[_Support] = []
    if progress_callback is not None:
        progress_callback(0, len(accepted), "Rounding included stars...")
    for index, (rank, candidate, remeasure) in enumerate(accepted):
        if (index & (_INTERRUPT_INTERVAL - 1)) == 0 and interrupt():
            return None
        neighbors = _neighbors(candidate, rank, candidates, included_count, tree, cores, max_core)
        status, support = _round_one_owned(
            out,
            candidate,
            rank,
            neighbors,
            sky_mask,
            inclusion_mask,
            remeasure,
            catalog.threshold,
        )
        decisions[rank] = status
        if support is not None:
            supports.append(support)
        if progress_callback is not None and ((index & (_INTERRUPT_INTERVAL - 1)) == 0 or index + 1 == len(accepted)):
            progress_callback(index + 1, len(accepted), f"Rounding stars: {index + 1:,} / {len(accepted):,}")
    if interrupt():
        return None

    for support in supports:
        y0, x0, _, _ = support.rect
        ys = y0 + support.local_y
        xs = x0 + support.local_x
        if np.any(inclusion_mask[ys, xs] <= 0.0):
            raise ValueError("round delta support lies outside the inclusion mask.")
    active = list(supports)
    for _ in range(TRADITIONAL_GATE_ROUNDS):
        if not active or interrupt():
            if interrupt():
                return None
            break
        reject = _traditional_gate(
            base,
            candidates,
            active,
            included_points,
            included_reaches,
            included_tree,
            interrupt,
        )
        if reject is None:
            return None
        if not reject:
            break
        for support in active:
            if support.rank in reject:
                decisions[support.rank] = "rejected:neighbor_quality"
        active = [support for support in active if support.rank not in reject]
    else:
        for support in active:
            decisions[support.rank] = "rejected:neighbor_quality"
        active = []
    if interrupt():
        return None
    return _pack_supports(active, decisions, stars.shape[:2])


def _selected_glow_candidates(
    catalog: RankedStarCatalog, cutoff: Optional[int], glow_star_count: int
) -> list[StarCandidate]:
    if not np.isfinite(glow_star_count) or int(glow_star_count) != glow_star_count or glow_star_count < 0:
        raise ValueError(f"glow_star_count must be a non-negative integer, got {glow_star_count!r}")
    if int(glow_star_count) == 0:
        return []
    included_count = catalog.included_count(cutoff)
    selected: list[StarCandidate] = []
    for candidate in catalog.analysis_for_cutoff(cutoff).candidates[:included_count]:
        if candidate.is_valid and not candidate.is_blended:
            selected.append(candidate)
            if len(selected) >= int(glow_star_count):
                break
    return selected


def _blur_glow_seed(seed: np.ndarray, radius_px: float) -> np.ndarray:
    sigma = max(radius_px * GLOW_SIGMA_FRACTION, 1.0)
    if radius_px < GLOW_PYRAMID_RADIUS_PX:
        return cv2.GaussianBlur(
            seed,
            (0, 0),
            sigmaX=sigma,
            sigmaY=sigma,
            borderType=cv2.BORDER_CONSTANT,
        )
    factor = 1
    while sigma / (factor * 2.0) >= GLOW_PYRAMID_MIN_SIGMA_PX:
        factor *= 2
    levels = int(np.log2(factor))
    height, width = seed.shape[:2]
    # Zero padding makes the pyramid see empty space beyond the frame, matching
    # the direct pass's truncate-and-lose edge behaviour. Pad enough for the
    # low-resolution blur support and to make every pyramid level integral.
    pad = int(np.ceil(3.0 * sigma))
    padded_height = int(np.ceil((height + 2 * pad) / factor) * factor)
    padded_width = int(np.ceil((width + 2 * pad) / factor) * factor)
    pad_y, pad_x = padded_height - height, padded_width - width
    top, left = pad_y // 2, pad_x // 2
    padded = np.pad(seed, ((top, pad_y - top), (left, pad_x - left), (0, 0)), mode="constant")
    small = padded
    for _ in range(levels):
        small = cv2.pyrDown(small)
    small = cv2.GaussianBlur(
        small,
        (0, 0),
        sigmaX=sigma / factor,
        sigmaY=sigma / factor,
        borderType=cv2.BORDER_CONSTANT,
    )
    for _ in range(levels):
        small = cv2.pyrUp(small)
    if small.shape[:2] != padded.shape[:2]:
        small = cv2.resize(small, (padded.shape[1], padded.shape[0]), interpolation=cv2.INTER_LINEAR)
    return small[top : top + height, left : left + width]


def render_glow(
    stars: np.ndarray,
    sky_mask: np.ndarray,
    catalog: RankedStarCatalog,
    *,
    cutoff: Optional[int],
    inclusion_mask: np.ndarray,
    glow_star_count: int,
    radius_px: float,
    should_interrupt: Optional[Callable[[], bool]] = None,
) -> Optional[np.ndarray]:
    """Render the additive Glow layer from the top included non-blended stars."""
    _validate_image_and_mask(stars, sky_mask)
    _validate_inclusion_mask(inclusion_mask, stars)
    if not np.isfinite(radius_px) or radius_px <= 0.0:
        raise ValueError("star_glow_radius_px must be finite and positive.")
    interrupt = should_interrupt or (lambda: False)
    if interrupt():
        return None
    selected = _selected_glow_candidates(catalog, cutoff, glow_star_count)
    glow = np.zeros(stars.shape, dtype=np.float32)
    if not selected:
        return glow

    height, width = stars.shape[:2]
    for index, candidate in enumerate(selected):
        if (index & (_INTERRUPT_INTERVAL - 1)) == 0 and interrupt():
            return None
        radius = candidate.footprint_radius_px
        rect = _candidate_rect(candidate, (height, width))
        if rect is None:
            continue
        y0, x0, y1, x1 = rect
        yy, xx = np.mgrid[y0:y1, x0:x1]
        feather = _feather_weights(yy - candidate.y, xx - candidate.x, radius)[..., None]
        included_patch = stars[y0:y1, x0:x1] * inclusion_mask[y0:y1, x0:x1, None]
        glow[y0:y1, x0:x1] += included_patch * feather
    if interrupt():
        return None
    blurred = _blur_glow_seed(glow, float(radius_px))
    blurred *= sky_mask[..., None]
    return blurred.astype(np.float32, copy=False)


def _validate_amount(label: str, amount: float) -> float:
    if not np.isfinite(amount) or not 0.0 <= amount <= PERCENT_SCALE:
        raise ValueError(f"{label} must be in [0,100], got {amount}")
    return float(amount)


def _apply_sparse_delta(base: np.ndarray, delta: SparseRoundDelta, amount_fraction: float) -> np.ndarray:
    if delta.image_shape != base.shape[:2]:
        raise ValueError("round delta image shape does not match the star layer.")
    # Composition passes its newly allocated, owned included-star buffer.
    out = base
    for index in range(len(delta.y0)):
        start = int(delta.offsets[index])
        end = int(delta.offsets[index + 1])
        if start == end:
            continue
        ys = int(delta.y0[index]) + delta.local_y[start:end]
        xs = int(delta.x0[index]) + delta.local_x[start:end]
        out[ys, xs] += amount_fraction * delta.values[start:end]
    return out


def compose_star_layer(
    stars: np.ndarray,
    catalog: RankedStarCatalog,
    round_delta: Optional[SparseRoundDelta],
    glow: Optional[np.ndarray],
    settings,
    *,
    inclusion_mask: np.ndarray,
    compare: bool = False,
) -> np.ndarray:
    """Compose the finished star layer from stored effect layers.

    ``S_fin = S_inc + round_on*a_r*DeltaRound + glow_on*a_g*Glow``. No analysis,
    detection, filtering or worker work happens here. ``inclusion_mask`` is the
    workflow-owned ``M`` for the current catalog/cutoff.
    """
    validate_image_array(stars)
    _validate_inclusion_mask(inclusion_mask, stars)
    base = inclusion_mask[..., None] * stars
    if compare:
        return base

    round_amount = _validate_amount("round_stars_amount", float(settings.round_stars_amount))
    glow_amount = _validate_amount("star_glow_amount", float(settings.star_glow_amount))
    round_on = bool(settings.round_stars_enabled and round_amount > 0.0)
    glow_on = bool(settings.star_glow_enabled and glow_amount > 0.0)
    if not round_on and not glow_on:
        return base

    out = base
    if round_on:
        if round_delta is None:
            raise ValueError("round_delta is required when Round Stars is enabled.")
        out = _apply_sparse_delta(out, round_delta, round_amount / PERCENT_SCALE)
    if glow_on:
        if glow is None:
            raise ValueError("glow is required when Star Glow is enabled.")
        if glow.shape != out.shape or glow.dtype != np.float32:
            raise ValueError("glow must be a float32 RGB layer with image dimensions.")
        out += (glow_amount / PERCENT_SCALE) * glow
    np.clip(out, 0.0, 1.0, out=out)
    return out.astype(np.float32, copy=False)


__all__ = [
    "GLOW_PYRAMID_RADIUS_PX",
    "SparseRoundDelta",
    "STAR_EFFECT_VERSION",
    "build_round_delta",
    "compose_star_layer",
    "load_round_delta",
    "render_glow",
    "save_round_delta",
]
