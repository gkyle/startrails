"""Numerical star effects applied to a separated positive star layer.

The single authoritative catalog from ``star_analysis.analyze_stars`` feeds
Round Stars, faint-star suppression and Star Glow. Every effect applies its
delta through the soft sky mask exactly once; unchanged star pixels are never
multiplied by the mask. Global star amount belongs to recombination and is not
read here.
"""

from __future__ import annotations

import inspect
from typing import Callable, Final, Optional, Sequence, Tuple

import cv2
import numpy as np
from scipy.spatial import cKDTree

from startrails.lib.finish.defaults import FinishSettings
from startrails.lib.finish.star_analysis import (
    StarAnalysisResult,
    StarCandidate,
    analyze_stars,
)
from startrails.lib.image_io import validate_image_array

STAR_EFFECT_VERSION: Final[int] = 1

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

# Faint-star suppression brightness mapping. A single smooth weight multiplies
# the whole measured footprint; it is not a per-pixel threshold.
FAINT_PEAK_LOW: Final[float] = 0.02
FAINT_PEAK_HIGH: Final[float] = 0.20

# Star Glow selection and spatial profile.
GLOW_MIN_PEAK: Final[float] = 0.25
GLOW_SIGMA_FRACTION: Final[float] = 1.0 / 3.0
GLOW_CUTOFF_SIGMAS: Final[float] = 3.0

_INTERRUPT_INTERVAL: Final[int] = 64


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
    detections. A nearest-centre bisector does not reliably protect a larger
    neighbour core when the two stars have different radii, so the conservative
    policy is: if this footprint can reach any neighbour core, do not correct
    this candidate. Ownership masking still protects remaining neighbours.
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


def _round_one(
    out: np.ndarray,
    candidate: StarCandidate,
    neighbors: Sequence[Tuple[float, float]],
    sky_mask: np.ndarray,
    amount_fraction: float,
) -> bool:
    """Apply and verify one masked radial circularization. False means rejected."""
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
    delta *= amount_fraction * mask_patch[..., None]
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
    amount_effective = amount_fraction * max(0.0, min(1.0, mean_mask))
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


def _apply_round_stars(
    out: np.ndarray,
    analysis: StarAnalysisResult,
    sky_mask: np.ndarray,
    amount_percent: float,
    interrupt: Callable[[], bool],
) -> Optional[bool]:
    eligible = [c for c in analysis.candidates if _round_eligible(c)]
    if not eligible:
        return True
    blocked = _overlapping_indices(eligible) | _protected_core_blocked(eligible, analysis.candidates)
    accepted = [c for index, c in enumerate(eligible) if index not in blocked]
    if not accepted:
        return True
    points = np.array([[c.x, c.y] for c in analysis.candidates], dtype=np.float64)
    tree = cKDTree(points) if len(points) else None
    catalog_position = {id(candidate): index for index, candidate in enumerate(analysis.candidates)}
    amount_fraction = float(amount_percent) / 100.0
    for index, candidate in enumerate(accepted):
        if (index & (_INTERRUPT_INTERVAL - 1)) == 0 and interrupt():
            return None
        neighbors = []
        if tree is not None:
            neighbor_indices = tree.query_ball_point(
                [candidate.x, candidate.y], r=float(2.0 * candidate.footprint_radius_px)
            )
            center_index = catalog_position[id(candidate)]
            neighbors = [
                (analysis.candidates[idx].x, analysis.candidates[idx].y)
                for idx in neighbor_indices
                if idx != center_index
            ]
        _round_one(out, candidate, neighbors, sky_mask, amount_fraction)
    return True


def _faint_weight(peak: float) -> float:
    t = (float(peak) - FAINT_PEAK_LOW) / (FAINT_PEAK_HIGH - FAINT_PEAK_LOW)
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _apply_faint_suppression(
    out: np.ndarray,
    analysis: StarAnalysisResult,
    sky_mask: np.ndarray,
    amount_percent: float,
    interrupt: Callable[[], bool],
) -> Optional[bool]:
    eligible = [c for c in analysis.candidates if c.is_valid and not c.is_blended and not c.is_border]
    if not eligible:
        return True
    blocked = _overlapping_indices(eligible) | _protected_core_blocked(eligible, analysis.candidates)
    accepted = [c for index, c in enumerate(eligible) if index not in blocked]
    if not accepted:
        return True
    points = np.array([[c.x, c.y] for c in analysis.candidates], dtype=np.float64)
    tree = cKDTree(points) if len(points) else None
    catalog_position = {id(candidate): index for index, candidate in enumerate(analysis.candidates)}
    amount = float(amount_percent) / 100.0
    height, width = out.shape[:2]
    for index, candidate in enumerate(accepted):
        if (index & (_INTERRUPT_INTERVAL - 1)) == 0 and interrupt():
            return None
        weight = _faint_weight(candidate.effective_peak)
        scale = 1.0 - amount * (1.0 - weight)
        if abs(scale - 1.0) <= 1e-12:
            continue
        radius = candidate.footprint_radius_px
        iy0 = max(0, int(np.floor(candidate.y - radius)))
        iy1 = min(height, int(np.ceil(candidate.y + radius)) + 1)
        ix0 = max(0, int(np.floor(candidate.x - radius)))
        ix1 = min(width, int(np.ceil(candidate.x + radius)) + 1)
        if iy0 >= iy1 or ix0 >= ix1:
            continue
        yy, xx = np.mgrid[iy0:iy1, ix0:ix1]
        dy = yy - candidate.y
        dx = xx - candidate.x
        own = np.ones(yy.shape, dtype=bool)
        if tree is not None:
            center_index = catalog_position[id(candidate)]
            neighbors = [
                (analysis.candidates[other_index].x, analysis.candidates[other_index].y)
                for other_index in tree.query_ball_point([candidate.x, candidate.y], r=float(2.0 * radius))
                if other_index != center_index
            ]
            own = _build_owner_mask(candidate, neighbors, yy, xx)
        feather = _feather_weights(dy, dx, radius)[..., None]
        patch = out[iy0:iy1, ix0:ix1]
        delta = patch * (scale - 1.0) * feather * own[..., None]
        delta *= sky_mask[iy0:iy1, ix0:ix1][..., None]
        out[iy0:iy1, ix0:ix1] = np.clip(patch + delta, 0.0, 1.0)
    return True


def _apply_glow(
    out: np.ndarray,
    analysis: StarAnalysisResult,
    sky_mask: np.ndarray,
    amount_percent: float,
    radius_px: float,
    interrupt: Callable[[], bool],
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Optional[bool]:
    selected = [c for c in analysis.candidates if c.is_valid and not c.is_blended and c.effective_peak >= GLOW_MIN_PEAK]
    if not selected:
        return True
    if not np.isfinite(radius_px) or radius_px <= 0.0:
        raise ValueError("star_glow_radius_px must be finite and positive.")

    amount = float(amount_percent) / 100.0
    sigma = max(radius_px * GLOW_SIGMA_FRACTION, 1.0)
    support = int(np.ceil(GLOW_CUTOFF_SIGMAS * sigma))
    height, width = out.shape[:2]

    # Snapshot the current corrected/suppressed flux before adding any halo.
    # Using mutable `out` inside the halo loop would feed earlier halos into
    # later colour normalization and make the result order-dependent.
    snapshots = [
        (candidate, _footprint_flux(out, candidate.x, candidate.y, candidate.footprint_radius_px))
        for candidate in selected
    ]
    num_glow = len(snapshots)
    two_sigma_sq = 2.0 * sigma * sigma

    for index, (candidate, current_flux) in enumerate(snapshots):
        if (index & (_INTERRUPT_INTERVAL - 1)) == 0:
            if interrupt():
                return None
            if progress_callback is not None:
                progress_callback(index, num_glow, f"Adding star glow: {index:,} / {num_glow:,}")
        if float(current_flux.sum()) <= 0.0:
            continue
        # Full discrete kernel support, before clipping to the frame. At a frame
        # edge the omitted tail is intentionally lost (truncate-and-lose); it is
        # never redistributed into the visible patch. Glow is artistic added
        # flux, so its frame-boundary flux is not a preservation invariant.
        full_y0 = int(np.floor(candidate.y - support))
        full_y1 = int(np.ceil(candidate.y + support)) + 1
        full_x0 = int(np.floor(candidate.x - support))
        full_x1 = int(np.ceil(candidate.x + support)) + 1

        y_coords = np.arange(full_y0, full_y1, dtype=np.float64)
        x_coords = np.arange(full_x0, full_x1, dtype=np.float64)
        ky_full = np.exp(-((y_coords - candidate.y) ** 2) / two_sigma_sq)
        kx_full = np.exp(-((x_coords - candidate.x) ** 2) / two_sigma_sq)
        full_normalization = float(ky_full.sum() * kx_full.sum())
        if full_normalization <= 0.0:
            continue
        iy0 = max(0, full_y0)
        iy1 = min(height, full_y1)
        ix0 = max(0, full_x0)
        ix1 = min(width, full_x1)
        if iy0 >= iy1 or ix0 >= ix1:
            continue
        ky = ky_full[(iy0 - full_y0):(iy1 - full_y0)]
        kx = kx_full[(ix0 - full_x0):(ix1 - full_x0)]
        gaussian = ky[:, None] * kx[None, :]
        halo = gaussian[..., None] * (amount * current_flux / full_normalization)[None, None, :]
        halo *= sky_mask[iy0:iy1, ix0:ix1][..., None]
        patch = out[iy0:iy1, ix0:ix1]
        out[iy0:iy1, ix0:ix1] = np.clip(patch + halo, 0.0, 1.0)
    return True


def apply_star_effects(
    stars: np.ndarray,
    sky_mask: np.ndarray,
    settings: FinishSettings,
    *,
    source: np.ndarray,
    analysis: Optional[StarAnalysisResult] = None,
    analysis_callback: Optional[Callable[[StarAnalysisResult], None]] = None,
    should_interrupt: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[..., None]] = None,
) -> Optional[np.ndarray]:
    """Apply the enabled star effects and return the finished positive star layer.

    ``source`` is required: true saturation and clipped-core brightness cannot
    be recovered from ``S = I - B``. The global ``settings.star_amount`` is not
    read; recombination owns global amount and the negative residual.
    """
    validate_image_array(stars)
    validate_image_array(source)
    if stars.shape != source.shape:
        raise ValueError("stars and source must have identical shape.")
    if sky_mask.shape != stars.shape[:2] or sky_mask.dtype != np.float32:
        raise ValueError("sky_mask must be normalized float32 with image dimensions.")
    if not np.isfinite(sky_mask).all() or np.any(sky_mask < 0.0) or np.any(sky_mask > 1.0):
        raise ValueError("sky_mask values must be finite and in [0,1].")

    round_amount = float(settings.round_stars_amount)
    suppression_amount = float(settings.faint_star_amount)
    glow_amount = float(settings.star_glow_amount)
    for label, amount in (
        ("round_stars_amount", round_amount),
        ("faint_star_amount", suppression_amount),
        ("star_glow_amount", glow_amount),
    ):
        if not np.isfinite(amount) or not 0.0 <= amount <= 100.0:
            raise ValueError(f"{label} must be in [0,100], got {amount}")

    round_on = bool(settings.round_stars_enabled and round_amount > 0.0)
    suppression_on = bool(settings.faint_star_suppression and suppression_amount > 0.0)
    glow_on = bool(settings.star_glow_enabled and glow_amount > 0.0)
    enabled_count = int(round_on) + int(suppression_on) + int(glow_on)
    if enabled_count == 0:
        return stars.copy()

    interrupt = should_interrupt or (lambda: False)
    total = 1 + enabled_count
    done = 0

    takes_extra = False
    if progress_callback is not None:
        try:
            sig = inspect.signature(progress_callback)
            params = list(sig.parameters.values())
            takes_extra = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params) or len(params) >= 4
        except Exception:
            takes_extra = False

    def emit_progress(step_done: int, description: str, sub_fraction: Optional[float] = None) -> None:
        if progress_callback is not None:
            if takes_extra and sub_fraction is not None:
                progress_callback(step_done, total, description, {"sub_fraction": sub_fraction})
            else:
                progress_callback(step_done, total, description)

    if analysis is None:
        emit_progress(0, "Analyzing stars...")

        def on_analysis_progress(cur: int, tot: int, desc: str) -> None:
            frac = cur / tot if tot > 0 else 0.0
            emit_progress(0, desc, sub_fraction=frac * 0.95)

        analysis = analyze_stars(
            stars,
            source,
            sky_mask,
            should_interrupt=interrupt,
            progress_callback=on_analysis_progress,
        )
        if analysis is None or interrupt():
            return None
        if analysis_callback is not None:
            analysis_callback(analysis)
    else:
        emit_progress(0, f"Using analyzed stars ({len(analysis.candidates):,} detections)")
        if interrupt():
            return None

    out = stars.copy()
    done = 1
    emit_progress(done, "Star analysis complete")
    if round_on:
        result = _apply_round_stars(out, analysis, sky_mask, round_amount, interrupt)
        if result is None or interrupt():
            return None
        done += 1
        emit_progress(done, "Rounding stars...")
    if suppression_on:
        result = _apply_faint_suppression(out, analysis, sky_mask, suppression_amount, interrupt)
        if result is None or interrupt():
            return None
        done += 1
        emit_progress(done, "Suppressing faint stars...")
    if glow_on:
        def on_glow_progress(cur: int, tot: int, desc: str) -> None:
            frac = cur / tot if tot > 0 else 0.0
            emit_progress(done, desc, sub_fraction=frac)

        result = _apply_glow(
            out,
            analysis,
            sky_mask,
            glow_amount,
            float(settings.star_glow_radius_px),
            interrupt,
            progress_callback=on_glow_progress,
        )
        if result is None or interrupt():
            return None
        done += 1
        emit_progress(done, "Adding star glow...")
    np.clip(out, 0.0, 1.0, out=out)
    return out


__all__ = ["STAR_EFFECT_VERSION", "apply_star_effects"]
