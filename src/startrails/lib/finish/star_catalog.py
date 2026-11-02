"""Ranked, persisted star catalog for Step 10B star finishing.

Detection and cheap component metrics run once for every connected component.
Only the included ranks receive the full per-candidate measurement used by
Round Stars and Glow; excluded ranks keep conservative cheap centroids and
extents so neighbour protection still sees them. Candidate order is the rank
order (integrated detail flux descending).

Memory note: the catalog persists full-frame int32 connected-component labels
(~96 MB at 24 MP) so it can be extended after reopening without rerunning
connected components. It deliberately does not persist the RGB star/source
images or the background-subtracted detail image; those are regenerated from
the caller's image arrays when a higher cutoff needs new measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import numbers
import os
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple, Union
import zipfile

import cv2
import numpy as np

from startrails.lib.finish.star_analysis import (
    MAX_FOOTPRINT_RADIUS_PX,
    MIN_AREA_PX,
    STAR_ANALYSIS_VERSION,
    StarAnalysisResult,
    StarCandidate,
    _apply_blend_flags,
    _build_candidate,
    _detect_components,
    _local_background,
    _validate_analysis_inputs,
)

STAR_CATALOG_VERSION = 2

# Fraction of the faintest included ranks that fade out with a smoothstep. All
# never fades; a small partial cutoff fades fewer than one rank (i.e. none).
INCLUDED_FADE_FRACTION = 0.10

_FEATHER_INNER_FRACTION = 0.65
_COMPONENT_CHUNK_ROWS = 256
_INTERRUPT_INTERVAL = 256

ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class RankedStarCatalog:
    """Immutable ranked catalog: every detection, measured only when included."""

    analysis: StarAnalysisResult
    cheap_candidates: Tuple[StarCandidate, ...]  # conservative all-component shadows
    measured: np.ndarray  # bool[N], true prefix = fully measured
    scores: np.ndarray  # float64[N], rank score (integrated positive detail)
    labels: np.ndarray  # int32[H,W], connected-component labels
    component_ids: np.ndarray  # int32[N], label id for each rank
    bounds: np.ndarray  # int32[N,4], x, y, width, height
    areas: np.ndarray  # int64[N]
    threshold: float  # detection threshold used for the stored labels
    stats: np.ndarray  # int32[L,5], OpenCV connected-component stats
    intrinsic_blended: np.ndarray  # bool[N], local-peak blend flag only
    uses_sky_mask: bool

    def __post_init__(self) -> None:
        for name in (
            "measured",
            "scores",
            "labels",
            "component_ids",
            "bounds",
            "areas",
            "stats",
            "intrinsic_blended",
        ):
            array = getattr(self, name)
            array.setflags(write=False)

    def included_count(self, cutoff: Optional[int]) -> int:
        """Return the number of included top ranks for a cutoff preset."""
        return _normalise_cutoff(cutoff, len(self.analysis.candidates))

    def cutoff_score(self, cutoff: Optional[int]) -> float:
        """Return the lowest included rank score, or 0.0 when nothing is included."""
        count = self.included_count(cutoff)
        if count <= 0:
            return 0.0
        return float(self.scores[count - 1])

    def analysis_for_cutoff(self, cutoff: Optional[int]) -> StarAnalysisResult:
        """Return the deterministic catalog view consumed by a cutoff.

        Included ranks use their full measurements. Excluded ranks always use
        the same conservative cheap shadows, even after a higher cutoff has
        measured those ranks, so lowering the cutoff cannot inherit different
        neighbour cores, positions or blend flags from edit history. All
        returns the authoritative full-measured ``analysis`` unchanged.
        """
        total = len(self.analysis.candidates)
        count = _normalise_cutoff(cutoff, total)
        if cutoff is None or count >= total:
            return self.analysis
        measured_count = int(np.count_nonzero(self.measured))
        if count > measured_count:
            raise ValueError("cutoff exceeds the catalog's measured ranks; extend the catalog first.")
        if count == measured_count:
            return self.analysis
        intrinsic = self.intrinsic_blended[:count]
        included = tuple(
            replace(candidate, is_blended=bool(intrinsic[index]))
            for index, candidate in enumerate(self.analysis.candidates[:count])
        )
        candidates = included + self.cheap_candidates[count:]
        flagged = _apply_blend_flags(candidates, lambda: False)
        if flagged is None:  # pragma: no cover - the non-interrupting callback cannot interrupt
            raise RuntimeError("Unexpected blend-flag cancellation.")
        return StarAnalysisResult(
            candidates=flagged,
            image_shape=self.analysis.image_shape,
        )


def _normalise_cutoff(cutoff: Optional[int], total: int) -> int:
    if cutoff is None:
        return total
    if isinstance(cutoff, bool) or not isinstance(cutoff, numbers.Integral):
        raise ValueError(f"cutoff must be a non-negative integer or None, got {cutoff!r}")
    value = int(cutoff)
    if value < 0:
        raise ValueError(f"cutoff must be non-negative, got {value}")
    return min(value, total)


def _cheap_component_metrics(
    detail: np.ndarray, labels: np.ndarray, stats: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised area/flux/peak/centroid/extent for every component.

    Frame chunks bound temporary memory. Extents are the maximum component-pixel
    radius from the flux-weighted centroid and are used conservatively for
    excluded detections.
    """
    height, width = detail.shape
    count = int(stats.shape[0])
    flux = np.zeros(count, dtype=np.float64)
    peak = np.zeros(count, dtype=np.float64)
    sum_y = np.zeros(count, dtype=np.float64)
    sum_x = np.zeros(count, dtype=np.float64)
    x_coords = np.arange(width, dtype=np.float64)

    for y0 in range(0, height, _COMPONENT_CHUNK_ROWS):
        y1 = min(height, y0 + _COMPONENT_CHUNK_ROWS)
        lab = labels[y0:y1]
        weights = np.maximum(detail[y0:y1], 0.0).astype(np.float64)
        flat_labels = lab.ravel()
        flat_weights = weights.ravel()
        flux += np.bincount(flat_labels, weights=flat_weights, minlength=count)
        foreground = flat_labels > 0
        if np.any(foreground):
            np.maximum.at(peak, flat_labels[foreground], flat_weights[foreground])
        rows = np.arange(y0, y1, dtype=np.float64)
        sum_y += np.bincount(flat_labels, weights=(weights * rows[:, None]).ravel(), minlength=count)
        sum_x += np.bincount(flat_labels, weights=(weights * x_coords[None, :]).ravel(), minlength=count)

    left = stats[:, cv2.CC_STAT_LEFT]
    top = stats[:, cv2.CC_STAT_TOP]
    box_width = stats[:, cv2.CC_STAT_WIDTH]
    box_height = stats[:, cv2.CC_STAT_HEIGHT]
    bbox_y = top.astype(np.float64) + 0.5 * box_height.astype(np.float64)
    bbox_x = left.astype(np.float64) + 0.5 * box_width.astype(np.float64)
    centroid_y = np.divide(sum_y, flux, out=bbox_y.copy(), where=flux > 0.0)
    centroid_x = np.divide(sum_x, flux, out=bbox_x.copy(), where=flux > 0.0)

    extent_sq = np.zeros(count, dtype=np.float64)
    for y0 in range(0, height, _COMPONENT_CHUNK_ROWS):
        y1 = min(height, y0 + _COMPONENT_CHUNK_ROWS)
        lab = labels[y0:y1]
        fy, fx = np.nonzero(lab)
        if fy.size == 0:
            continue
        component = lab[fy, fx]
        dy = (fy.astype(np.float64) + y0) - centroid_y[component]
        dx = fx.astype(np.float64) - centroid_x[component]
        np.maximum.at(extent_sq, component, dy * dy + dx * dx)

    return flux, peak, centroid_y, centroid_x, np.sqrt(extent_sq)


def _cheap_candidates(
    stars_shape: Tuple[int, int],
    component_ids: np.ndarray,
    flux: np.ndarray,
    peak: np.ndarray,
    centroid_y: np.ndarray,
    centroid_x: np.ndarray,
    extent: np.ndarray,
) -> list[StarCandidate]:
    height, width = stars_shape
    core = np.minimum(MAX_FOOTPRINT_RADIUS_PX, np.maximum(3.0, 4.0 * extent))
    footprint = np.minimum(MAX_FOOTPRINT_RADIUS_PX, np.maximum(core, 1.5 * extent + 2.0))
    border = (
        (centroid_x - footprint < 0.0)
        | (centroid_y - footprint < 0.0)
        | (centroid_x + footprint > width - 1)
        | (centroid_y + footprint > height - 1)
    )
    candidates: list[StarCandidate] = []
    for component in component_ids:
        candidates.append(
            StarCandidate(
                y=float(centroid_y[component]),
                x=float(centroid_x[component]),
                flux=float(flux[component]),
                peak_brightness=float(peak[component]),
                color_ratio=(1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
                ellipticity=0.0,
                orientation_rad=0.0,
                footprint_radius_px=float(footprint[component]),
                is_valid=False,
                is_saturated=False,
                is_blended=False,
                flux_rgb=(0.0, 0.0, 0.0),
                peak_rgb=(0.0, 0.0, 0.0),
                source_peak_rgb=(0.0, 0.0, 0.0),
                major_sigma_px=0.0,
                minor_sigma_px=0.0,
                core_radius_px=float(core[component]),
                is_border=bool(border[component]),
                skip_reason="excluded",
            )
        )
    return candidates


def _rank_components(
    stats: np.ndarray,
    flux: np.ndarray,
    peak: np.ndarray,
    centroid_y: np.ndarray,
    centroid_x: np.ndarray,
) -> np.ndarray:
    component_ids = np.arange(1, stats.shape[0], dtype=np.int32)
    component_ids = component_ids[stats[component_ids, cv2.CC_STAT_AREA] >= MIN_AREA_PX]
    scores = flux[component_ids]
    peaks = peak[component_ids]
    ys = centroid_y[component_ids]
    xs = centroid_x[component_ids]
    order = np.lexsort((xs, ys, -peaks, -scores))
    return component_ids[order]


def _build_initial_catalog(
    detected,
    *,
    sky_mask: Optional[np.ndarray],
) -> RankedStarCatalog:
    flux, peak, centroid_y, centroid_x, extent = _cheap_component_metrics(
        detected.detail, detected.labels, detected.stats
    )
    component_ids = _rank_components(detected.stats, flux, peak, centroid_y, centroid_x)
    candidates = _cheap_candidates(
        detected.detail.shape,
        component_ids,
        flux,
        peak,
        centroid_y,
        centroid_x,
        extent,
    )
    count = len(candidates)
    stats = detected.stats.astype(np.int32, copy=False)
    return RankedStarCatalog(
        analysis=StarAnalysisResult(candidates=tuple(candidates), image_shape=detected.detail.shape),
        cheap_candidates=tuple(candidates),
        measured=np.zeros(count, dtype=bool),
        scores=np.asarray(flux[component_ids], dtype=np.float64),
        labels=detected.labels.astype(np.int32, copy=False),
        component_ids=component_ids.astype(np.int32, copy=False),
        bounds=stats[component_ids][:, :4].astype(np.int32, copy=True),
        areas=stats[component_ids, cv2.CC_STAT_AREA].astype(np.int64, copy=True),
        threshold=float(detected.threshold),
        stats=stats,
        intrinsic_blended=np.zeros(count, dtype=bool),
        uses_sky_mask=sky_mask is not None,
    )


def _measure_ranks(
    catalog: RankedStarCatalog,
    stars: np.ndarray,
    source: np.ndarray,
    sky_mask: Optional[np.ndarray],
    detail: np.ndarray,
    luminance: np.ndarray,
    *,
    target: int,
    interrupt: Callable[[], bool],
    progress_callback: Optional[ProgressCallback],
) -> Optional[RankedStarCatalog]:
    measured_count = int(np.count_nonzero(catalog.measured))
    if target <= measured_count and measured_count > 0:
        return catalog

    candidates = list(catalog.analysis.candidates)
    measured = catalog.measured.copy()
    intrinsic = catalog.intrinsic_blended.copy()
    for rank in range(measured_count, target):
        if (rank & (_INTERRUPT_INTERVAL - 1)) == 0:
            if interrupt():
                return None
            if progress_callback is not None:
                progress_callback(rank, target, f"Measuring stars: {rank:,} / {target:,}")
        component = int(catalog.component_ids[rank])
        candidate = _build_candidate(
            stars,
            source,
            detail,
            catalog.labels,
            catalog.stats,
            component,
            catalog.threshold,
            sky_mask,
            luminance,
        )
        if candidate is None:
            # Keep the cheap candidate for protection but record why it could
            # not be fully measured.
            candidates[rank] = replace(candidates[rank], skip_reason="measurement_failed")
        else:
            candidates[rank] = candidate
            intrinsic[rank] = candidate.is_blended
        measured[rank] = True

    # Restore local-peak flags before recomputing neighbour flags globally so a
    # higher cutoff never leaves stale blend state behind.
    restored = tuple(
        replace(candidate, is_blended=bool(intrinsic[index])) for index, candidate in enumerate(candidates)
    )
    flagged = _apply_blend_flags(restored, interrupt)
    if flagged is None:
        return None

    return RankedStarCatalog(
        analysis=StarAnalysisResult(
            candidates=flagged,
            image_shape=catalog.analysis.image_shape,
        ),
        cheap_candidates=catalog.cheap_candidates,
        measured=measured,
        scores=catalog.scores,
        labels=catalog.labels,
        component_ids=catalog.component_ids,
        bounds=catalog.bounds,
        areas=catalog.areas,
        threshold=catalog.threshold,
        stats=catalog.stats,
        intrinsic_blended=intrinsic,
        uses_sky_mask=catalog.uses_sky_mask,
    )


def build_catalog(
    stars: np.ndarray,
    source: np.ndarray,
    sky_mask: Optional[np.ndarray] = None,
    *,
    cutoff: Optional[int] = None,
    should_interrupt: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Optional[RankedStarCatalog]:
    """Detect, rank and measure a catalog. Returns None only when interrupted."""
    _validate_analysis_inputs(stars, source, sky_mask)
    interrupt = should_interrupt or (lambda: False)
    if interrupt():
        return None
    if progress_callback is not None:
        progress_callback(0, 1, "Analyzing stars...")

    detected = _detect_components(stars, sky_mask)
    if interrupt():
        return None
    catalog = _build_initial_catalog(detected, sky_mask=sky_mask)
    if interrupt():
        return None
    target = _normalise_cutoff(cutoff, len(catalog.analysis.candidates))
    measured = _measure_ranks(
        catalog,
        stars,
        source,
        sky_mask,
        detected.detail,
        detected.luminance,
        target=target,
        interrupt=interrupt,
        progress_callback=progress_callback,
    )
    if measured is None:
        return None
    if progress_callback is not None:
        total = len(measured.analysis.candidates)
        progress_callback(total, total, f"Star analysis complete ({total:,} stars)")
    return measured


def _detail_for_catalog(catalog: RankedStarCatalog, stars: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    luminance = stars.max(axis=2)
    detail = luminance - _local_background(luminance)
    binary = detail > catalog.threshold
    if not np.array_equal(binary, catalog.labels > 0):
        raise ValueError("stars do not match the catalog's stored detection labels.")
    return detail, luminance


def measure_catalog(
    catalog: RankedStarCatalog,
    stars: np.ndarray,
    source: np.ndarray,
    sky_mask: Optional[np.ndarray] = None,
    *,
    cutoff: Optional[int],
    should_interrupt: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Optional[RankedStarCatalog]:
    """Full-measure newly included ranks without rerunning connected components."""
    _validate_analysis_inputs(stars, source, sky_mask)
    if stars.shape[:2] != catalog.analysis.image_shape:
        raise ValueError("stars shape does not match the catalog image.")
    if (sky_mask is not None) != catalog.uses_sky_mask:
        raise ValueError("sky_mask presence must match the catalog that was built.")
    target = _normalise_cutoff(cutoff, len(catalog.analysis.candidates))
    if target <= int(np.count_nonzero(catalog.measured)):
        return catalog
    interrupt = should_interrupt or (lambda: False)
    if interrupt():
        return None
    detail, luminance = _detail_for_catalog(catalog, stars)
    return _measure_ranks(
        catalog,
        stars,
        source,
        sky_mask,
        detail,
        luminance,
        target=target,
        interrupt=interrupt,
        progress_callback=progress_callback,
    )


def extend_catalog(
    catalog: RankedStarCatalog,
    stars: np.ndarray,
    source: np.ndarray,
    sky_mask: Optional[np.ndarray] = None,
    *,
    cutoff: Optional[int],
    should_interrupt: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Optional[RankedStarCatalog]:
    """Raise a catalog's cutoff, measuring only the newly included ranks."""
    return measure_catalog(
        catalog,
        stars,
        source,
        sky_mask,
        cutoff=cutoff,
        should_interrupt=should_interrupt,
        progress_callback=progress_callback,
    )


def _smoothstep(values: np.ndarray) -> np.ndarray:
    return values * values * (3.0 - 2.0 * values)


def _included_rank_weights(count: int) -> np.ndarray:
    weights = np.ones(count, dtype=np.float32)
    fade_count = int(count * INCLUDED_FADE_FRACTION)
    if fade_count <= 0:
        return weights
    start = count - fade_count
    t = np.arange(1, fade_count + 1, dtype=np.float64) / float(fade_count)
    weights[start:] = (1.0 - _smoothstep(t)).astype(np.float32)
    return weights


def included_mask(catalog: RankedStarCatalog, *, cutoff: Optional[int]) -> np.ndarray:
    """Return the feathered included-star ownership mask `M` as float32[H,W].

    All (or any numeric cutoff at/above the detection count) is exact ones.
    Partial cutoffs assign ownership by nearest detection label, fade the last
    ``INCLUDED_FADE_FRACTION`` ranks, and leave excluded detections at zero.
    """
    total = len(catalog.analysis.candidates)
    count = _normalise_cutoff(cutoff, total)
    height, width = catalog.analysis.image_shape
    if cutoff is None or count >= total:
        return np.ones((height, width), dtype=np.float32)
    if count <= 0:
        return np.zeros((height, width), dtype=np.float32)

    component_count = catalog.stats.shape[0]
    label_weights = np.zeros(component_count, dtype=np.float32)
    label_weights[catalog.component_ids[:count]] = _included_rank_weights(count)

    candidates = catalog.analysis_for_cutoff(cutoff).candidates
    component_y = np.zeros(component_count, dtype=np.float64)
    component_x = np.zeros(component_count, dtype=np.float64)
    component_radius = np.zeros(component_count, dtype=np.float64)
    ids = catalog.component_ids
    component_y[ids] = np.asarray([candidate.y for candidate in candidates], dtype=np.float64)
    component_x[ids] = np.asarray([candidate.x for candidate in candidates], dtype=np.float64)
    component_radius[ids] = np.asarray([candidate.footprint_radius_px for candidate in candidates], dtype=np.float64)

    foreground = catalog.labels > 0
    if not np.any(foreground):
        return np.zeros((height, width), dtype=np.float32)
    if not np.any(~foreground):
        owner_labels = catalog.labels
    else:
        # Nearest connected component in one vectorised OpenCV pass. The label
        # ids returned by DIST_LABEL_CCOMP are mapped back to our CC labels.
        inverse = (~foreground).astype(np.uint8)
        _, distance_labels = cv2.distanceTransformWithLabels(
            inverse,
            cv2.DIST_L2,
            5,
            labelType=cv2.DIST_LABEL_CCOMP,
        )
        max_distance_label = int(distance_labels.max())
        distance_to_component = np.zeros(max_distance_label + 1, dtype=np.int32)
        np.maximum.at(
            distance_to_component,
            distance_labels[foreground],
            catalog.labels[foreground],
        )
        owner_labels = distance_to_component[distance_labels]

    mask = np.empty((height, width), dtype=np.float32)
    x_coords = np.arange(width, dtype=np.float64)
    for y0 in range(0, height, _COMPONENT_CHUNK_ROWS):
        y1 = min(height, y0 + _COMPONENT_CHUNK_ROWS)
        owner = owner_labels[y0:y1]
        owner_weight = label_weights[owner]
        chunk = np.zeros((y1 - y0, width), dtype=np.float32)
        active = owner_weight > 0.0
        if np.any(active):
            radius = component_radius[owner]
            inner = _FEATHER_INNER_FRACTION * radius
            dy = np.arange(y0, y1, dtype=np.float64)[:, None] - component_y[owner]
            dx = x_coords[None, :] - component_x[owner]
            distance = np.hypot(dy, dx)
            t = np.clip(
                (distance - inner) / np.maximum(radius - inner, 1e-6),
                0.0,
                1.0,
            )
            feather = 1.0 - _smoothstep(t)
            chunk = np.where(active, owner_weight * feather, 0.0).astype(np.float32)
        mask[y0:y1] = chunk
    return mask


def _candidate_arrays(candidates: Tuple[StarCandidate, ...], prefix: str) -> Dict[str, np.ndarray]:
    count = len(candidates)

    def scalar(name: str, dtype: np.dtype) -> np.ndarray:
        return np.asarray([getattr(candidate, name) for candidate in candidates], dtype=dtype)

    def vectors(name: str) -> np.ndarray:
        if count == 0:
            return np.zeros((0, 3), dtype=np.float64)
        return np.asarray([getattr(candidate, name) for candidate in candidates], dtype=np.float64)

    def key(name: str) -> str:
        return f"{prefix}_{name}"

    return {
        key("y"): scalar("y", np.float64),
        key("x"): scalar("x", np.float64),
        key("flux"): scalar("flux", np.float64),
        key("peak_brightness"): scalar("peak_brightness", np.float64),
        key("color_ratio"): vectors("color_ratio"),
        key("ellipticity"): scalar("ellipticity", np.float64),
        key("orientation_rad"): scalar("orientation_rad", np.float64),
        key("footprint_radius_px"): scalar("footprint_radius_px", np.float64),
        key("is_valid"): scalar("is_valid", bool),
        key("is_saturated"): scalar("is_saturated", bool),
        key("is_blended"): scalar("is_blended", bool),
        key("flux_rgb"): vectors("flux_rgb"),
        key("peak_rgb"): vectors("peak_rgb"),
        key("source_peak_rgb"): vectors("source_peak_rgb"),
        key("major_sigma_px"): scalar("major_sigma_px", np.float64),
        key("minor_sigma_px"): scalar("minor_sigma_px", np.float64),
        key("core_radius_px"): scalar("core_radius_px", np.float64),
        key("is_border"): scalar("is_border", bool),
        key("skip_reason"): np.asarray([candidate.skip_reason for candidate in candidates], dtype=np.str_),
    }


def _catalog_arrays(catalog: RankedStarCatalog) -> Dict[str, np.ndarray]:
    arrays = {
        "image_shape": np.asarray(catalog.analysis.image_shape, dtype=np.int64),
        "measured": np.asarray(catalog.measured, dtype=bool),
        "scores": np.asarray(catalog.scores, dtype=np.float64),
        "labels": np.asarray(catalog.labels, dtype=np.int32),
        "component_ids": np.asarray(catalog.component_ids, dtype=np.int32),
        "bounds": np.asarray(catalog.bounds, dtype=np.int32),
        "areas": np.asarray(catalog.areas, dtype=np.int64),
        "threshold": np.asarray(catalog.threshold, dtype=np.float64),
        "stats": np.asarray(catalog.stats, dtype=np.int32),
        "intrinsic_blended": np.asarray(catalog.intrinsic_blended, dtype=bool),
        "uses_sky_mask": np.asarray(catalog.uses_sky_mask, dtype=bool),
    }
    arrays.update(_candidate_arrays(catalog.analysis.candidates, "candidate"))
    arrays.update(_candidate_arrays(catalog.cheap_candidates, "cheap"))
    return arrays


def save_catalog(path: Union[str, Path], catalog: RankedStarCatalog, *, identity: str) -> None:
    """Persist catalog arrays atomically as an allow_pickle=False-ready npz."""
    if not isinstance(identity, str) or not identity:
        raise ValueError("identity must be a non-empty string.")
    target = Path(path)
    temporary = target.with_name(target.name + ".tmp")
    arrays = _catalog_arrays(catalog)
    try:
        with open(temporary, "wb") as handle:
            np.savez_compressed(
                handle,
                star_catalog_version=np.asarray(STAR_CATALOG_VERSION, dtype=np.int64),
                star_analysis_version=np.asarray(STAR_ANALYSIS_VERSION, dtype=np.int64),
                identity=np.asarray(identity),
                **arrays,
            )
        os.replace(temporary, target)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _expect_dtype(name: str, array: np.ndarray, kinds: str) -> None:
    _require(
        array.dtype.kind in kinds,
        f"{name} must have dtype kind {kinds}, got {array.dtype}.",
    )


def _array_with_shape(
    archive: Dict[str, np.ndarray],
    name: str,
    shape: Tuple[int, ...],
    kinds: str,
) -> np.ndarray:
    _require(name in archive, f"Catalog is missing '{name}'.")
    array = archive[name]
    _require(array.shape == shape, f"{name} has shape {array.shape}, expected {shape}.")
    _expect_dtype(name, array, kinds)
    return array


def _read_scalar(archive: Dict[str, np.ndarray], name: str, kinds: str) -> np.ndarray:
    return _array_with_shape(archive, name, (), kinds)


def _float_array(
    archive: Dict[str, np.ndarray],
    name: str,
    shape: Tuple[int, ...],
    *,
    nonnegative: bool = False,
) -> np.ndarray:
    array = _array_with_shape(archive, name, shape, "f")
    _require(np.isfinite(array).all(), f"{name} contains non-finite values.")
    if nonnegative:
        _require(np.all(array >= 0.0), f"{name} must be non-negative.")
    return np.asarray(array, dtype=np.float64)


def _bool_array(archive: Dict[str, np.ndarray], name: str, shape: Tuple[int, ...]) -> np.ndarray:
    return np.asarray(_array_with_shape(archive, name, shape, "b"), dtype=bool)


def _integer_array(archive: Dict[str, np.ndarray], name: str, shape: Tuple[int, ...]) -> np.ndarray:
    array = _array_with_shape(archive, name, shape, "iu")
    _require(np.all(array >= 0), f"{name} must be non-negative.")
    _require(
        int(array.max(initial=0)) <= np.iinfo(np.int32).max,
        f"{name} contains an index outside the int32 range.",
    )
    return np.asarray(array, dtype=np.int64)


def _float_scalar(archive: Dict[str, np.ndarray], name: str) -> float:
    value = float(_read_scalar(archive, name, "f"))
    _require(np.isfinite(value), f"{name} must be finite.")
    return value


def _bool_scalar(archive: Dict[str, np.ndarray], name: str) -> bool:
    return bool(_read_scalar(archive, name, "b").item())


def _read_candidates(
    archive: Dict[str, np.ndarray],
    prefix: str,
    count: int,
    height: int,
    width: int,
) -> Tuple[StarCandidate, ...]:
    def key(name: str) -> str:
        return f"{prefix}_{name}"

    y = _float_array(archive, key("y"), (count,))
    x = _float_array(archive, key("x"), (count,))
    _require(
        np.all(y >= -1e-6) and np.all(y <= height - 1 + 1e-6),
        f"{key('y')} must lie within the image.",
    )
    _require(
        np.all(x >= -1e-6) and np.all(x <= width - 1 + 1e-6),
        f"{key('x')} must lie within the image.",
    )
    flux = _float_array(archive, key("flux"), (count,), nonnegative=True)
    peak = _float_array(archive, key("peak_brightness"), (count,), nonnegative=True)
    color_ratio = _float_array(archive, key("color_ratio"), (count, 3))
    ellipticity = _float_array(archive, key("ellipticity"), (count,))
    _require(np.all((ellipticity >= 0.0) & (ellipticity <= 1.0)), f"{key('ellipticity')} must be in [0, 1].")
    orientation = _float_array(archive, key("orientation_rad"), (count,))
    footprint = _float_array(archive, key("footprint_radius_px"), (count,), nonnegative=True)
    major_sigma = _float_array(archive, key("major_sigma_px"), (count,), nonnegative=True)
    minor_sigma = _float_array(archive, key("minor_sigma_px"), (count,), nonnegative=True)
    core_radius = _float_array(archive, key("core_radius_px"), (count,), nonnegative=True)
    is_valid = _bool_array(archive, key("is_valid"), (count,))
    is_saturated = _bool_array(archive, key("is_saturated"), (count,))
    is_blended = _bool_array(archive, key("is_blended"), (count,))
    flux_rgb = _float_array(archive, key("flux_rgb"), (count, 3), nonnegative=True)
    peak_rgb = _float_array(archive, key("peak_rgb"), (count, 3), nonnegative=True)
    source_peak_rgb = _float_array(archive, key("source_peak_rgb"), (count, 3), nonnegative=True)
    is_border = _bool_array(archive, key("is_border"), (count,))
    skip_reasons = _array_with_shape(archive, key("skip_reason"), (count,), "U")

    return tuple(
        StarCandidate(
            y=float(y[index]),
            x=float(x[index]),
            flux=float(flux[index]),
            peak_brightness=float(peak[index]),
            color_ratio=tuple(float(value) for value in color_ratio[index]),
            ellipticity=float(ellipticity[index]),
            orientation_rad=float(orientation[index]),
            footprint_radius_px=float(footprint[index]),
            is_valid=bool(is_valid[index]),
            is_saturated=bool(is_saturated[index]),
            is_blended=bool(is_blended[index]),
            flux_rgb=tuple(float(value) for value in flux_rgb[index]),
            peak_rgb=tuple(float(value) for value in peak_rgb[index]),
            source_peak_rgb=tuple(float(value) for value in source_peak_rgb[index]),
            major_sigma_px=float(major_sigma[index]),
            minor_sigma_px=float(minor_sigma[index]),
            core_radius_px=float(core_radius[index]),
            is_border=bool(is_border[index]),
            skip_reason=str(skip_reasons[index]),
        )
        for index in range(count)
    )


def load_catalog(path: Union[str, Path], *, identity: str) -> RankedStarCatalog:
    """Load and strictly validate a catalog written by :func:`save_catalog`."""
    if not isinstance(identity, str) or not identity:
        raise ValueError("identity must be a non-empty string.")
    try:
        with np.load(path, allow_pickle=False) as archive:
            arrays = {name: archive[name] for name in archive.files}
    except OSError:
        raise
    except (KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Invalid star catalog: {exc}") from exc

    catalog_version = _read_scalar(arrays, "star_catalog_version", "iu")
    _require(int(catalog_version) == STAR_CATALOG_VERSION, "Unsupported star catalog version.")
    analysis_version = _read_scalar(arrays, "star_analysis_version", "iu")
    _require(int(analysis_version) == STAR_ANALYSIS_VERSION, "Unsupported star analysis version.")
    stored_identity = _read_scalar(arrays, "identity", "U")
    _require(str(stored_identity.item()) == identity, "Star catalog identity mismatch.")

    shape = _array_with_shape(arrays, "image_shape", (2,), "iu")
    height, width = int(shape[0]), int(shape[1])
    _require(height > 0 and width > 0, "Image dimensions must be positive.")

    required = (
        "measured",
        "scores",
        "labels",
        "component_ids",
        "bounds",
        "areas",
        "intrinsic_blended",
        "stats",
    )
    for name in required:
        _require(name in arrays, f"Catalog is missing '{name}'.")

    measured_array = arrays["measured"]
    _require(measured_array.ndim == 1, "measured must be one-dimensional.")
    _expect_dtype("measured", measured_array, "b")
    measured = np.asarray(measured_array, dtype=bool)
    count = measured.size

    scores = _float_array(arrays, "scores", (count,), nonnegative=True)
    _require(np.all(scores[:-1] >= scores[1:]), "scores must be in descending rank order.")

    stats_raw = arrays["stats"]
    _require(stats_raw.ndim == 2 and stats_raw.shape[1] == 5, "stats must have shape (L, 5).")
    stats = _integer_array(arrays, "stats", stats_raw.shape)
    _require(stats.shape[0] >= 1, "stats must include the background component.")
    _require(np.all(stats[:, cv2.CC_STAT_LEFT] + stats[:, cv2.CC_STAT_WIDTH] <= width), "stats exceed image width.")
    _require(np.all(stats[:, cv2.CC_STAT_TOP] + stats[:, cv2.CC_STAT_HEIGHT] <= height), "stats exceed image height.")
    _require(np.all(stats[:, cv2.CC_STAT_AREA] <= width * height), "stats area exceeds image size.")

    labels = _integer_array(arrays, "labels", (height, width))
    label_count = int(labels.max(initial=0)) + 1
    _require(label_count <= stats.shape[0], "labels reference an unknown component.")

    component_ids = _integer_array(arrays, "component_ids", (count,))
    if count:
        _require(np.all(component_ids >= 1), "component_ids must be positive.")
        _require(np.all(component_ids < stats.shape[0]), "component_ids reference an unknown component.")
        _require(np.unique(component_ids).size == count, "component_ids must be unique.")
    bounds = _integer_array(arrays, "bounds", (count, 4))
    if count:
        _require(np.all(bounds[:, 0] + bounds[:, 2] <= width), "bounds exceed image width.")
        _require(np.all(bounds[:, 1] + bounds[:, 3] <= height), "bounds exceed image height.")
        _require(np.array_equal(bounds, stats[component_ids][:, :4]), "bounds disagree with stats.")
    areas = _integer_array(arrays, "areas", (count,))
    if count:
        _require(
            np.array_equal(areas, stats[component_ids, cv2.CC_STAT_AREA]),
            "areas disagree with stats.",
        )
    intrinsic = _bool_array(arrays, "intrinsic_blended", (count,))

    measured_count = int(np.count_nonzero(measured))
    _require(np.all(measured[:measured_count]), "measured must be a true prefix.")
    _require(not np.any(measured[measured_count:]), "measured must be a true prefix.")

    candidates = _read_candidates(arrays, "candidate", count, height, width)
    cheap_candidates = _read_candidates(arrays, "cheap", count, height, width)
    _require(
        not any(candidate.is_valid for candidate in cheap_candidates),
        "cheap shadow candidates must not be valid.",
    )
    _require(
        not any(candidate.is_blended for candidate in cheap_candidates),
        "cheap shadow candidates must not carry blend flags.",
    )

    _require(
        not any(candidate.is_valid for candidate, measured_flag in zip(candidates, measured) if not measured_flag),
        "unmeasured candidates must not be valid.",
    )
    _require(
        not np.any(intrinsic[~measured]),
        "unmeasured candidates must not carry intrinsic blend flags.",
    )

    threshold = _float_scalar(arrays, "threshold")
    _require(threshold > 0.0, "threshold must be positive.")
    uses_sky_mask = _bool_scalar(arrays, "uses_sky_mask")

    return RankedStarCatalog(
        analysis=StarAnalysisResult(candidates=candidates, image_shape=(height, width)),
        cheap_candidates=cheap_candidates,
        measured=measured,
        scores=scores,
        labels=np.asarray(labels, dtype=np.int32),
        component_ids=np.asarray(component_ids, dtype=np.int32),
        bounds=np.asarray(bounds, dtype=np.int32),
        areas=areas,
        threshold=threshold,
        stats=np.asarray(stats, dtype=np.int32),
        intrinsic_blended=intrinsic,
        uses_sky_mask=uses_sky_mask,
    )


__all__ = [
    "INCLUDED_FADE_FRACTION",
    "RankedStarCatalog",
    "STAR_CATALOG_VERSION",
    "build_catalog",
    "extend_catalog",
    "included_mask",
    "load_catalog",
    "measure_catalog",
    "save_catalog",
]
