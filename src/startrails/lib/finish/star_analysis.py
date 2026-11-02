"""Shared star detection and measurement for Round Stars, Star Glow, and suppression.

All three effects consume this single catalog. Measurements are expressed in
full-resolution image pixels; intensity and flux use the normalized float32 RGB
working representation (`S = max(I - B, 0)` for the star layer).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Final, Optional, Tuple

import cv2
import numpy as np
from scipy.spatial import cKDTree

from startrails.lib.image_io import validate_image_array

# Detector constants are algorithm policy, not user settings. A reduced preview
# must scale pixel units explicitly rather than changing these values.
BACKGROUND_MEDIAN_PX: int = 5  # on a 4x area-downsampled luminance (~20 px window)
BACKGROUND_DOWNSAMPLE: int = 4
NOISE_MAD_SCALE: float = 1.4826
DETECTION_SIGMA: float = 5.0
ABS_THRESHOLD_FLOOR: float = 0.008  # ~524/65535 normalized intensity
MIN_AREA_PX: int = 4
MEASURE_SIGMA_MULT: float = 3.0
FOOTPRINT_SIGMA_MULT: float = 4.0
FOOTPRINT_EXTENT_MULT: float = 1.5
MAX_FOOTPRINT_RADIUS_PX: float = 80.0
SATURATION_LEVEL: float = 0.995
BLEND_DISTANCE_FACTOR: float = 0.7
SECONDARY_PEAK_FRACTION: float = 0.05
SECONDARY_PEAK_NOISE_MULT: float = 3.0
MAX_ELLIPTICITY: float = 0.92
MAX_MEASURE_RADIUS_PX: float = 30.0

_INTERRUPT_INTERVAL: int = 256
_DILATE_KERNEL: Final[np.ndarray] = np.ones((5, 5), dtype=np.uint8)


@dataclass(frozen=True)
class StarCandidate:
    """Measured properties of one detected star candidate."""

    y: float  # Centroid row in full-resolution pixels
    x: float  # Centroid column in full-resolution pixels
    flux: float  # Total integrated flux across the footprint (sum of RGB)
    peak_brightness: float  # Maximum star-layer intensity in the core
    color_ratio: Tuple[float, float, float]  # Normalized RGB flux ratios
    ellipticity: float  # (a - b) / (a + b); 0.0 = circular
    orientation_rad: float  # Major-axis angle in radians, [-pi/2, pi/2]
    footprint_radius_px: float  # Full correction/flux support radius
    is_valid: bool = True  # Passed foreground/border/shape/confidence gates
    is_saturated: bool = False  # Source contains clipped core samples
    is_blended: bool = False  # Overlaps another detection or has multiple peaks
    flux_rgb: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    peak_rgb: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    source_peak_rgb: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    major_sigma_px: float = 0.0
    minor_sigma_px: float = 0.0
    core_radius_px: float = 0.0  # Crowding gate radius (4 sigma major)
    is_border: bool = False
    skip_reason: str = ""

    @property
    def effective_peak(self) -> float:
        """Brightness for selection/suppression, using source for clipped cores."""
        if self.is_saturated and max(self.source_peak_rgb) > 0.0:
            return float(max(self.source_peak_rgb))
        return float(self.peak_brightness)


@dataclass(frozen=True)
class StarAnalysisResult:
    """Authoritative output contract of the shared detection and measurement step."""

    candidates: Tuple[StarCandidate, ...]
    image_shape: Tuple[int, int]
    faint_star_flux_threshold: float = 0.0

    @property
    def valid_stars(self) -> Tuple[StarCandidate, ...]:
        return tuple(s for s in self.candidates if s.is_valid)


def _local_background(luminance: np.ndarray) -> np.ndarray:
    """Robust local background on a 4x-downsampled uint16 median."""
    height, width = luminance.shape
    small = cv2.resize(
        luminance,
        (max(1, width // BACKGROUND_DOWNSAMPLE), max(1, height // BACKGROUND_DOWNSAMPLE)),
        interpolation=cv2.INTER_AREA,
    )
    small = cv2.medianBlur((np.clip(small, 0.0, 1.0) * 65535).astype(np.uint16), BACKGROUND_MEDIAN_PX)
    return cv2.resize(small.astype(np.float32) / 65535.0, (width, height), interpolation=cv2.INTER_LINEAR)


def _noise_sigma(detail: np.ndarray, sky_mask: Optional[np.ndarray]) -> float:
    if sky_mask is not None:
        selected = detail[sky_mask >= 0.5]
        if selected.size > 2_000_000:
            selected = selected[::4]
    else:
        selected = detail.ravel()[::4]
    if selected.size == 0:
        selected = detail.ravel()[::4]
    center = float(np.median(selected))
    sigma = NOISE_MAD_SCALE * float(np.median(np.abs(selected - center)))
    return max(sigma, 1e-6)


def _second_moments(
    weights: np.ndarray, ys: np.ndarray, xs: np.ndarray
) -> Tuple[float, float, float, float, float, float]:
    total = float(weights.sum())
    if total <= 0.0:
        return 0.0, 0.0, 1.0, 1.0, 0.0, 0.0
    if ys.ndim == 1 and xs.ndim == 1:
        w_row = weights.sum(axis=1)
        w_col = weights.sum(axis=0)
        cy = float((w_row * ys).sum() / total)
        cx = float((w_col * xs).sum() / total)
        dy = ys - cy
        dx = xs - cx
        cyy = float((w_row * dy * dy).sum() / total)
        cxx = float((w_col * dx * dx).sum() / total)
        cxy = float((weights * dy[:, None] * dx[None, :]).sum() / total)
    else:
        cy = float((weights * ys).sum() / total)
        cx = float((weights * xs).sum() / total)
        dy = ys - cy
        dx = xs - cx
        cyy = float((weights * dy * dy).sum() / total)
        cxx = float((weights * dx * dx).sum() / total)
        cxy = float((weights * dx * dy).sum() / total)

    diff_half = 0.5 * (cyy - cxx)
    delta = float(np.sqrt(max(0.0, diff_half * diff_half + cxy * cxy)))
    lam_max = max(0.5 * (cyy + cxx) + delta, 1e-6)
    lam_min = max(0.5 * (cyy + cxx) - delta, 1e-6)
    a = float(np.sqrt(lam_max))
    b = float(np.sqrt(lam_min))
    if abs(cxy) > 1e-12:
        major_y = cxy
        major_x = lam_max - cyy
    else:
        if cyy >= cxx:
            major_y, major_x = 1.0, 0.0
        else:
            major_y, major_x = 0.0, 1.0
    theta = float(np.arctan2(major_y, major_x))
    if theta > np.pi / 2:
        theta -= np.pi
    if theta < -np.pi / 2:
        theta += np.pi
    return cy, cx, a, b, (a - b) / (a + b), theta


def _component_extent(seed: np.ndarray, cy: float, cx: float, y0: int, x0: int) -> float:
    ys, xs = np.where(seed)
    if ys.size == 0:
        return 0.0
    return float(np.max(np.hypot(ys + y0 - cy, xs + x0 - cx)))


def _build_candidate(
    stars: np.ndarray,
    source: np.ndarray,
    detail: np.ndarray,
    labels: np.ndarray,
    stats: np.ndarray,
    index: int,
    threshold: float,
    sky_mask: Optional[np.ndarray],
    luminance: Optional[np.ndarray] = None,
) -> Optional[StarCandidate]:
    height, width = detail.shape
    x0 = int(stats[index, cv2.CC_STAT_LEFT])
    y0 = int(stats[index, cv2.CC_STAT_TOP])
    x1 = x0 + int(stats[index, cv2.CC_STAT_WIDTH])
    y1 = y0 + int(stats[index, cv2.CC_STAT_HEIGHT])
    area = int(stats[index, cv2.CC_STAT_AREA])
    if area < MIN_AREA_PX:
        return None

    seed = labels[y0:y1, x0:x1] == index
    seed_weights = np.where(seed, np.maximum(detail[y0:y1, x0:x1], 0.0), 0.0).astype(np.float64)
    ys_seed = np.arange(y0, y1, dtype=np.float64)
    xs_seed = np.arange(x0, x1, dtype=np.float64)
    seed_y, seed_x, a, b, ellipticity, theta = _second_moments(
        seed_weights, ys_seed, xs_seed
    )
    if not all(np.isfinite([seed_y, seed_x, a, b])):
        return None

    cy, cx = seed_y, seed_x
    for _ in range(2):
        radius = min(MAX_MEASURE_RADIUS_PX, max(MEASURE_SIGMA_MULT * max(a, b), 3.0))
        my0 = max(0, int(np.floor(cy - radius)))
        my1 = min(height, int(np.ceil(cy + radius)) + 1)
        mx0 = max(0, int(np.floor(cx - radius)))
        mx1 = min(width, int(np.ceil(cx + radius)) + 1)
        dys = (np.arange(my0, my1, dtype=np.float64) - cy) ** 2
        dxs = (np.arange(mx0, mx1, dtype=np.float64) - cx) ** 2
        inside = (dys[:, None] + dxs[None, :]) <= radius * radius
        weights = np.where(inside, np.maximum(detail[my0:my1, mx0:mx1], 0.0), 0.0).astype(np.float64)
        if weights.sum() <= 0.0:
            break
        cy, cx, a, b, ellipticity, theta = _second_moments(
            weights, np.arange(my0, my1, dtype=np.float64), np.arange(mx0, mx1, dtype=np.float64)
        )

    core_radius = min(MAX_FOOTPRINT_RADIUS_PX, max(FOOTPRINT_SIGMA_MULT * max(a, b), 3.0))
    extent = _component_extent(seed, cy, cx, y0, x0)
    footprint = min(
        MAX_FOOTPRINT_RADIUS_PX,
        max(core_radius, FOOTPRINT_EXTENT_MULT * extent + 2.0),
    )
    iy0 = max(0, int(np.floor(cy - footprint)))
    iy1 = min(height, int(np.ceil(cy + footprint)) + 1)
    ix0 = max(0, int(np.floor(cx - footprint)))
    ix1 = min(width, int(np.ceil(cx + footprint)) + 1)
    dys = (np.arange(iy0, iy1, dtype=np.float64) - cy) ** 2
    dxs = (np.arange(ix0, ix1, dtype=np.float64) - cx) ** 2
    d2 = dys[:, None] + dxs[None, :]
    inside = d2 <= footprint * footprint
    stamp = stars[iy0:iy1, ix0:ix1]
    source_stamp = source[iy0:iy1, ix0:ix1]
    flux_rgb = stamp[inside].sum(axis=0, dtype=np.float64)
    core_inside = d2 <= core_radius * core_radius
    peak_mask = core_inside if np.any(core_inside) else inside
    peak_rgb = stamp[peak_mask].max(axis=0).astype(np.float64)
    source_peak_rgb = source_stamp[peak_mask].max(axis=0).astype(np.float64)
    total_flux = float(flux_rgb.sum())
    color_ratio = tuple(float(v) for v in (flux_rgb / total_flux if total_flux > 0 else np.full(3, 1.0 / 3.0)))

    is_saturated = bool(np.any(source_peak_rgb >= SATURATION_LEVEL))
    is_border = cx - footprint < 0 or cy - footprint < 0 or cx + footprint > width - 1 or cy + footprint > height - 1

    # Resolved companions and unresolved equal-brightness pairs.
    lum_stamp = luminance[iy0:iy1, ix0:ix1] if luminance is not None else stamp.max(axis=2)
    smooth = cv2.GaussianBlur(lum_stamp, (0, 0), 0.7)
    local_max = (smooth == cv2.dilate(smooth, _DILATE_KERNEL)) & core_inside
    if np.any(core_inside):
        secondary_floor = max(
            SECONDARY_PEAK_FRACTION * float(smooth[core_inside].max()), SECONDARY_PEAK_NOISE_MULT * threshold
        )
        local_max &= smooth >= secondary_floor
    is_blended = int(local_max.sum()) > 1

    reason = ""
    if sky_mask is not None:
        my = int(np.clip(round(cy), 0, height - 1))
        mx = int(np.clip(round(cx), 0, width - 1))
        if sky_mask[my, mx] < 0.5:
            reason = "foreground"
    if not reason and is_border:
        reason = "border"
    elif not reason and ellipticity > MAX_ELLIPTICITY:
        reason = "non_stellar_shape"
    elif not reason and footprint >= MAX_FOOTPRINT_RADIUS_PX:
        reason = "too_large"

    return StarCandidate(
        y=float(cy),
        x=float(cx),
        flux=total_flux,
        peak_brightness=float(peak_rgb.max()),
        color_ratio=color_ratio,
        ellipticity=float(ellipticity),
        orientation_rad=float(theta),
        footprint_radius_px=float(footprint),
        is_valid=(reason == ""),
        is_saturated=is_saturated,
        is_blended=bool(is_blended),
        flux_rgb=tuple(float(v) for v in flux_rgb),
        peak_rgb=tuple(float(v) for v in peak_rgb),
        source_peak_rgb=tuple(float(v) for v in source_peak_rgb),
        major_sigma_px=float(a),
        minor_sigma_px=float(b),
        core_radius_px=float(core_radius),
        is_border=is_border,
        skip_reason=reason,
    )


def analyze_stars(
    stars: np.ndarray,
    source: np.ndarray,
    sky_mask: Optional[np.ndarray] = None,
    *,
    should_interrupt: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Optional[StarAnalysisResult]:
    """Detect and measure one shared catalog on a positive float32 star layer.

    `source` is required for true saturation/core-brightness classification.
    Returns None only when interrupted. Both input arrays are read-only.
    """
    validate_image_array(stars)
    validate_image_array(source)
    if stars.shape != source.shape:
        raise ValueError("stars and source must have identical shape.")
    if sky_mask is not None:
        if sky_mask.shape != stars.shape[:2] or sky_mask.dtype != np.float32:
            raise ValueError("sky_mask must be normalized float32 with image dimensions.")
        if not np.isfinite(sky_mask).all() or np.any(sky_mask < 0.0) or np.any(sky_mask > 1.0):
            raise ValueError("sky_mask values must be finite and in [0,1].")

    interrupt = should_interrupt or (lambda: False)
    if interrupt():
        return None
    if progress_callback is not None:
        progress_callback(0, 1, "Analyzing stars...")

    height, width = stars.shape[:2]
    luminance = stars.max(axis=2)
    background = _local_background(luminance)
    detail = luminance - background
    threshold = max(DETECTION_SIGMA * _noise_sigma(detail, sky_mask), ABS_THRESHOLD_FLOOR)
    binary = (detail > threshold).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    candidates: list[StarCandidate] = []
    for index in range(1, count):
        if (index & (_INTERRUPT_INTERVAL - 1)) == 0:
            if interrupt():
                return None
            if progress_callback is not None:
                progress_callback(index, count, f"Analyzing stars: {index:,} / {count:,}")
        if stats[index, cv2.CC_STAT_AREA] < MIN_AREA_PX:
            continue
        candidate = _build_candidate(stars, source, detail, labels, stats, index, threshold, sky_mask, luminance)
        if candidate is not None:
            candidates.append(candidate)

    # Radius-binned KDTree query deblends nearby detections without an all-pairs
    # or monolithic maximum-radius search across the entire dense catalog.
    if len(candidates) > 1:
        if interrupt():
            return None
        if progress_callback is not None:
            progress_callback(count, count, "Analyzing star companions...")
        points = np.array([[s.x, s.y] for s in candidates], dtype=np.float64)
        radii = np.array([s.core_radius_px for s in candidates], dtype=np.float64)
        max_r = float(radii.max())

        bins = [0.0]
        b = 6.0
        while b < max_r:
            bins.append(b)
            b *= 2.0
        bins.append(max_r + 1.0)

        bin_indices = [np.where((radii > bins[k]) & (radii <= bins[k + 1]))[0] for k in range(len(bins) - 1)]
        trees = [cKDTree(points[idx]) if len(idx) > 0 else None for idx in bin_indices]

        blended: set[int] = set()
        for i in range(len(bin_indices)):
            if interrupt():
                return None
            idx_i = bin_indices[i]
            tree_i = trees[i]
            if tree_i is None or len(idx_i) < 2:
                continue
            r_max_i = bins[i + 1]
            pairs_i = tree_i.query_pairs(2.0 * BLEND_DISTANCE_FACTOR * r_max_i, output_type="ndarray")
            if len(pairs_i) > 0:
                pi = idx_i[pairs_i[:, 0]]
                pj = idx_i[pairs_i[:, 1]]
                dists_sq = np.sum((points[pi] - points[pj]) ** 2, axis=1)
                thresh_sq = (BLEND_DISTANCE_FACTOR * (radii[pi] + radii[pj])) ** 2
                mask_b = dists_sq < thresh_sq
                blended.update(pi[mask_b])
                blended.update(pj[mask_b])

        for i in range(len(bin_indices)):
            if interrupt():
                return None
            idx_i = bin_indices[i]
            tree_i = trees[i]
            if tree_i is None or len(idx_i) == 0:
                continue
            for j in range(i + 1, len(bin_indices)):
                idx_j = bin_indices[j]
                tree_j = trees[j]
                if tree_j is None or len(idx_j) == 0:
                    continue
                r_max_ij = BLEND_DISTANCE_FACTOR * (bins[i + 1] + bins[j + 1])
                pairs_ij = tree_i.query_ball_tree(tree_j, r_max_ij)
                for u, neighbors in enumerate(pairs_ij):
                    if neighbors:
                        orig_u = idx_i[u]
                        orig_v = idx_j[neighbors]
                        dists_sq = np.sum((points[orig_u] - points[orig_v]) ** 2, axis=1)
                        thresh_sq = (BLEND_DISTANCE_FACTOR * (radii[orig_u] + radii[orig_v])) ** 2
                        mask_b = dists_sq < thresh_sq
                        if np.any(mask_b):
                            blended.add(orig_u)
                            blended.update(orig_v[mask_b])

        for idx in blended:
            candidates[idx] = _replace_blended(candidates[idx])

    if interrupt():
        return None
    if progress_callback is not None:
        progress_callback(count, count, f"Star analysis complete ({len(candidates):,} stars)")
    return StarAnalysisResult(candidates=tuple(candidates), image_shape=(height, width))


def _replace_blended(candidate: StarCandidate) -> StarCandidate:
    if candidate.is_blended:
        return candidate
    return replace(candidate, is_blended=True)


__all__ = [
    "ABS_THRESHOLD_FLOOR",
    "BACKGROUND_DOWNSAMPLE",
    "BACKGROUND_MEDIAN_PX",
    "BLEND_DISTANCE_FACTOR",
    "DETECTION_SIGMA",
    "FOOTPRINT_SIGMA_MULT",
    "MAX_ELLIPTICITY",
    "MAX_FOOTPRINT_RADIUS_PX",
    "MIN_AREA_PX",
    "SATURATION_LEVEL",
    "StarAnalysisResult",
    "StarCandidate",
    "analyze_stars",
]
