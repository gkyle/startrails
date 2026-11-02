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

from startrails.lib.finish.star_analysis import StarCandidate
from startrails.lib.finish.star_catalog import RankedStarCatalog
from startrails.lib.image_io import validate_image_array

STAR_EFFECT_VERSION: Final[int] = 2

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


def _build_owner_mask(
    star: StarCandidate,
    neighbors: Sequence[Tuple[float, float]],
    yy: np.ndarray,
    xx: np.ndarray,
) -> np.ndarray:
    own = np.ones(yy.shape, dtype=bool)
    for nx, ny in neighbors:
        if nx == star.x and ny == star.y:
            continue
        d_self = (xx - star.x) ** 2 + (yy - star.y) ** 2
        d_other = (xx - nx) ** 2 + (yy - ny) ** 2
        own &= d_self <= d_other
    return own


def _overlapping_indices(candidates: Sequence[StarCandidate]) -> set[int]:
    """Return indices whose correction footprints overlap another candidate.

    Overlapping corrections are skipped rather than deblended. This guarantees
    that a later accepted correction cannot alter an earlier star's verified
    centroid or footprint flux.
    """
    count = len(candidates)
    if count < 2:
        return set()
    points = np.array([[c.x, c.y] for c in candidates], dtype=np.float64)
    radii = np.array([c.footprint_radius_px for c in candidates], dtype=np.float64)
    tree = cKDTree(points)
    pairs = tree.query_pairs(float(2.0 * max(1.0, radii.max())), output_type="ndarray")
    parents = list(range(count))

    def find(node: int) -> int:
        while parents[node] != node:
            parents[node] = parents[parents[node]]
            node = parents[node]
        return node

    for i, j in pairs:
        if float(np.hypot(*(points[i] - points[j]))) < radii[i] + radii[j]:
            root_i, root_j = find(int(i)), find(int(j))
            if root_i != root_j:
                parents[root_j] = root_i

    component_sizes: dict[int, int] = {}
    for index in range(count):
        root = find(index)
        component_sizes[root] = component_sizes.get(root, 0) + 1
    return {index for index in range(count) if component_sizes[find(index)] > 1}


def _protected_core_blocked(
    candidates: Sequence[StarCandidate],
    all_candidates: Sequence[StarCandidate],
) -> set[int]:
    """Skip candidates whose write footprint intersects a neighbour protected core.

    Protected neighbours include skipped, blended, invalid and saturated
    detections, including excluded ranks. A nearest-centre bisector does not
    reliably protect a larger neighbour core when the two stars have different
    radii, so the conservative policy is: if this footprint can reach any
    neighbour core, do not correct this candidate. Ownership masking still
    protects remaining neighbours.
    """
    if not candidates or not all_candidates:
        return set()
    points = np.array([[c.x, c.y] for c in all_candidates], dtype=np.float64)
    cores = np.array([max(c.core_radius_px, 1.0) for c in all_candidates], dtype=np.float64)
    tree = cKDTree(points)
    max_core = float(cores.max())
    blocked: set[int] = set()
    for index, candidate in enumerate(candidates):
        reach = candidate.footprint_radius_px + max_core
        for other_index in tree.query_ball_point([candidate.x, candidate.y], r=reach):
            if all_candidates[other_index] is candidate:
                continue
            distance = float(np.hypot(candidate.x - points[other_index, 0], candidate.y - points[other_index, 1]))
            if distance < candidate.footprint_radius_px + cores[other_index]:
                blocked.add(index)
                break
    return blocked


def _round_eligible(candidate: StarCandidate) -> bool:
    return (
        candidate.is_valid
        and not candidate.is_blended
        and not candidate.is_saturated
        and not candidate.is_border
        and candidate.ellipticity >= CORRECT_MIN_ELLIPTICITY
        and candidate.peak_brightness >= CORRECT_MIN_PEAK
    )


def _ineligible_reason(candidate: StarCandidate) -> str:
    if not candidate.is_valid:
        return candidate.skip_reason or "invalid"
    if candidate.is_blended:
        return "blended"
    if candidate.is_saturated:
        return "saturated"
    if candidate.is_border:
        return "border"
    if candidate.ellipticity < CORRECT_MIN_ELLIPTICITY:
        return "low_ellipticity"
    if candidate.peak_brightness < CORRECT_MIN_PEAK:
        return "faint"
    return "ineligible"


def _round_one(
    out: np.ndarray,
    candidate: StarCandidate,
    neighbors: Sequence[Tuple[float, float]],
    sky_mask: np.ndarray,
) -> bool:
    """Apply and verify one full-strength masked radial circularization.

    False means rejected; the patch is restored exactly. Correction is computed
    at 100% only; composition scales the stored delta linearly.
    """
    height, width = out.shape[:2]
    radius = candidate.footprint_radius_px
    core_radius = candidate.core_radius_px
    iy0 = max(0, int(np.floor(candidate.y - radius)))
    iy1 = min(height, int(np.ceil(candidate.y + radius)) + 1)
    ix0 = max(0, int(np.floor(candidate.x - radius)))
    ix1 = min(width, int(np.ceil(candidate.x + radius)) + 1)
    if iy0 >= iy1 or ix0 >= ix1:
        return False
    stamp = out[iy0:iy1, ix0:ix1].astype(np.float64)
    before_patch = out[iy0:iy1, ix0:ix1].copy()
    yy, xx = np.mgrid[iy0:iy1, ix0:ix1]
    dy = yy - candidate.y
    dx = xx - candidate.x
    distance = np.hypot(dy, dx)
    own = _build_owner_mask(candidate, neighbors, yy, xx)

    ring = (distance >= 0.8 * radius) & (distance <= radius) & own
    ring_values = stamp[ring]
    background = np.median(ring_values, axis=0) if ring_values.size else np.zeros(3)
    background = np.maximum(background, 0.0)
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
        return False
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

    azimuthal_sigma = float(np.sqrt((candidate.major_sigma_px**2 + candidate.minor_sigma_px**2) / 2.0))
    target_sigma = float(np.sqrt(candidate.major_sigma_px * candidate.minor_sigma_px))
    radial_scale = float(np.clip(target_sigma / max(azimuthal_sigma, 1e-6), MIN_FEATHER_SCALE, 1.0))
    peak_limit = min(1.0, max(PEAK_HEADROOM_FACTOR * candidate.peak_brightness, CORRECT_MIN_PEAK))
    peak_unscaled = float(profile.max())
    radial_scale = max(radial_scale, float(np.sqrt(peak_unscaled / max(peak_limit, 1e-6))))
    radial_scale = float(np.clip(radial_scale, MIN_FEATHER_SCALE, 1.0))

    sample_radius = np.clip(distance / radial_scale, 0.0, bin_count - 1.0001)
    lower = np.floor(sample_radius).astype(int)
    upper = np.minimum(lower + 1, bin_count - 1)
    fraction = (sample_radius - lower)[..., None]
    model = profile[lower] * (1.0 - fraction) + profile[upper] * fraction
    model = np.maximum(model, 0.0) / (radial_scale * radial_scale)

    weight = _feather_weights(dy, dx, radius)[..., None] * own[..., None]
    delta = weight * (model + background - stamp)
    denominator = float(weight.sum())
    if denominator > 0.0:
        delta -= (delta.sum(axis=(0, 1)) / denominator)[None, None, :] * weight

    mask_patch = sky_mask[iy0:iy1, ix0:ix1]
    delta *= mask_patch[..., None]
    if not np.any(delta):
        return False

    cy_before, cx_before, e_before = _measure_local(out, candidate.x, candidate.y, core_radius)
    flux_before = _footprint_flux(out, candidate.x, candidate.y, radius)
    out[iy0:iy1, ix0:ix1] = np.clip(stamp + delta, 0.0, 1.0)
    cy_after, cx_after, e_after = _measure_local(out, candidate.x, candidate.y, core_radius)
    flux_after = _footprint_flux(out, candidate.x, candidate.y, radius)
    shift = float(np.hypot(cy_after - cy_before, cx_after - cx_before))
    flux_error = float(np.max(np.abs(flux_after - flux_before) / np.maximum(np.abs(flux_before), 1e-9)))
    total_before = float(flux_before.sum())
    total_after = float(flux_after.sum())
    if total_before > 0.0 and total_after > 0.0:
        color_before = flux_before / total_before
        color_after = flux_after / total_after
        color_drift = float(np.max(np.abs(color_after - color_before) / np.maximum(np.abs(color_before), 1e-9)))
    else:
        color_drift = 0.0

    core_inside = (distance <= core_radius) & own
    mean_mask = float(mask_patch[core_inside].mean()) if np.any(core_inside) else 0.0
    amount_effective = max(0.0, min(1.0, mean_mask))
    expected_ratio = 1.0 - (1.0 - VERIFY_ELLIPTICITY_RATIO_AT_FULL) * amount_effective
    e_limit = max(0.10, expected_ratio * e_before)
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
        return False
    return True


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


def _pack_round_delta(
    base: np.ndarray,
    corrected: np.ndarray,
    regions: Sequence[Tuple[Tuple[int, int, int, int], StarCandidate]],
    rank: np.ndarray,
    decision: np.ndarray,
) -> SparseRoundDelta:
    y0_parts: list[np.ndarray] = []
    x0_parts: list[np.ndarray] = []
    height_parts: list[np.ndarray] = []
    width_parts: list[np.ndarray] = []
    local_y_parts: list[np.ndarray] = []
    local_x_parts: list[np.ndarray] = []
    value_parts: list[np.ndarray] = []
    offsets = [0]
    for (py0, px0, py1, px1), candidate in regions:
        difference = corrected[py0:py1, px0:px1] - base[py0:py1, px0:px1]
        yy, xx = np.mgrid[py0:py1, px0:px1]
        inside = (yy - candidate.y) ** 2 + (xx - candidate.x) ** 2 <= candidate.footprint_radius_px**2
        # Bounding rectangles can overlap diagonally even though accepted
        # circular correction supports do not. Clip each extraction to its own
        # candidate support so a neighbouring correction is never copied twice.
        support = np.any(difference != 0.0, axis=2) & inside
        if not np.any(support):
            continue
        local_y, local_x = np.nonzero(support)
        y0_parts.append(np.asarray([py0], dtype=np.int32))
        x0_parts.append(np.asarray([px0], dtype=np.int32))
        height_parts.append(np.asarray([py1 - py0], dtype=np.int32))
        width_parts.append(np.asarray([px1 - px0], dtype=np.int32))
        local_y_parts.append(local_y.astype(np.int32))
        local_x_parts.append(local_x.astype(np.int32))
        value_parts.append(difference[local_y, local_x].astype(np.float32))
        offsets.append(offsets[-1] + int(local_y.shape[0]))

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
        image_shape=(int(base.shape[0]), int(base.shape[1])),
        rank=np.asarray(rank, dtype=np.int32),
        decision=np.asarray(decision, dtype=np.str_),
    )


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
    """Build the full-strength Round Stars delta for included ranked stars.

    ``inclusion_mask`` is the workflow-owned ``M`` for this catalog and cutoff.
    All detections, including excluded ranks, protect their neighbour cores.
    The conservative Step 10 gates and verification tolerances are unchanged.
    """
    _validate_image_and_mask(stars, sky_mask)
    _validate_inclusion_mask(inclusion_mask, stars)
    interrupt = should_interrupt or (lambda: False)
    if interrupt():
        return None
    candidates = catalog.analysis_for_cutoff(cutoff).candidates
    included_count = catalog.included_count(cutoff)
    eligible = [
        (rank, candidate) for rank, candidate in enumerate(candidates[:included_count]) if _round_eligible(candidate)
    ]

    blocked_overlap = _overlapping_indices([candidate for _, candidate in eligible])
    blocked_core = _protected_core_blocked([candidate for _, candidate in eligible], candidates)
    accepted = [
        (rank, candidate)
        for position, (rank, candidate) in enumerate(eligible)
        if position not in blocked_overlap and position not in blocked_core
    ]
    # Ranking selects the budget, not the correction order. Preserve Step 10's
    # component order: square measurement windows can see a neighbouring support
    # even when the protected circular supports are disjoint.
    accepted.sort(key=lambda item: int(catalog.component_ids[item[0]]))

    decisions = ["excluded"] * len(candidates)
    eligible_positions = {rank: position for position, (rank, _) in enumerate(eligible)}
    for rank, candidate in enumerate(candidates):
        if rank >= included_count:
            decisions[rank] = "excluded"
        elif rank not in eligible_positions:
            decisions[rank] = f"ineligible:{_ineligible_reason(candidate)}"
    for position, (rank, _) in enumerate(eligible):
        reasons = []
        if position in blocked_overlap:
            reasons.append("overlap")
        if position in blocked_core:
            reasons.append("neighbor_core")
        if reasons:
            decisions[rank] = "blocked:" + ",".join(reasons)

    base = inclusion_mask[..., None] * stars
    corrected = base.copy()
    if not accepted:
        return _pack_round_delta(
            base,
            corrected,
            [],
            np.arange(len(candidates), dtype=np.int32),
            np.asarray(decisions),
        )

    all_points = np.array([[c.x, c.y] for c in candidates], dtype=np.float64)
    tree = cKDTree(all_points) if len(all_points) else None
    catalog_position = {id(candidate): index for index, candidate in enumerate(candidates)}
    accepted_regions: list[Tuple[Tuple[int, int, int, int], StarCandidate]] = []

    if progress_callback is not None:
        progress_callback(0, len(accepted), "Rounding included stars...")
    for index, (rank, candidate) in enumerate(accepted):
        if (index & (_INTERRUPT_INTERVAL - 1)) == 0 and interrupt():
            return None
        neighbors = []
        if tree is not None:
            neighbor_indices = tree.query_ball_point(
                [candidate.x, candidate.y], r=float(2.0 * candidate.footprint_radius_px)
            )
            center_index = catalog_position[id(candidate)]
            neighbors = [
                (candidates[other_index].x, candidates[other_index].y)
                for other_index in neighbor_indices
                if other_index != center_index
            ]
        corrected_before = _candidate_rect(candidate, base.shape[:2])
        if corrected_before is None:
            decisions[rank] = "ineligible:no_patch"
            continue
        if _round_one(corrected, candidate, neighbors, sky_mask):
            decisions[rank] = "corrected"
            accepted_regions.append((corrected_before, candidate))
        else:
            decisions[rank] = "rejected:verification"
        if progress_callback is not None and ((index & (_INTERRUPT_INTERVAL - 1)) == 0 or index + 1 == len(accepted)):
            progress_callback(index + 1, len(accepted), f"Rounding stars: {index + 1:,} / {len(accepted):,}")
    if interrupt():
        return None
    return _pack_round_delta(
        base,
        corrected,
        accepted_regions,
        np.arange(len(candidates), dtype=np.int32),
        np.asarray(decisions),
    )


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
