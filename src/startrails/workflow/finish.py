"""Finish workflow managing source image I/O, layer separation, and export."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from contextlib import nullcontext
from concurrent.futures import CancelledError
import logging
import tempfile
from typing import TYPE_CHECKING, Any, Callable, Final, List, Literal, Optional, Tuple, Union

import cv2
import numpy as np

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.file import InputFile, OutputFile
from startrails.lib.finish.composition import (
    blend_denoise,
    compute_denoise_endpoint_signature,
    recombine_layers,
)
from startrails.lib.finish.defaults import (
    CATALOG_SETTING_NAMES,
    COMPOSITION_ONLY_SETTING_NAMES,
    GLOW_SETTING_NAMES,
    INTERMEDIATE_BIT_DEPTH,
    PERCENT_SCALE,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_FINISHED_STARS,
    ROLE_ROUND_DELTA,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    ROLE_STAR_CATALOG,
    ROLE_UNMASKED_STARLESS,
    SCOPE_SKY_ONLY,
    SCOPE_WHOLE_IMAGE,
    SUPPORTED_CHANNELS,
    FinishSettings,
)
from startrails.lib.finish.graxpert import graxpert_model_identity
from startrails.lib.finish.separation import compute_separation_signature
from startrails.lib.finish.star_analysis import STAR_ANALYSIS_VERSION
from startrails.lib.finish.star_catalog import (
    STAR_CATALOG_VERSION,
    RankedStarCatalog,
    build_catalog,
    extend_catalog,
    included_mask,
    load_catalog,
    save_catalog,
)
from startrails.lib.finish.star_effects import (
    STAR_EFFECT_VERSION,
    SparseRoundDelta,
    build_round_delta,
    compose_star_layer,
    load_round_delta,
    render_glow,
    save_round_delta,
)
from startrails.lib.finish.starnet import MAX_STRIDE, MIN_STRIDE
from startrails.lib.finish.starless_filters import STARLESS_FILTER_VERSION
from startrails.lib.finish.graxpert_runtime import GraXpertSession, resolve_graxpert_runtime_policy
from startrails.lib.image_io import imread, imwrite, normalize_image
from startrails.lib.model_manifest import GRAXPERT_MANIFEST, PlatformNotSupportedError
from startrails.lib.project_finish import FinishProject
from startrails.lib.signatures import compute_signature, read_file_identity
from startrails.lib.starnet_setup import (
    STARNET_TERMS_REVISION,
    STARNET_TERMS_SHA256,
    starnet_terms_accepted,
    starnet_installation_lock,
    get_starnet_storage_dir,
    StarNetSetupError,
    detect_platform_target,
    managed_starnet_setup_notice,
    StarNetInstallation,
    get_active_starnet_installation,
    install_starnet_managed,
    record_starnet_installation,
    repair_starnet_installation,
)
from startrails.op.finish.finish_stars import FinishStars
from startrails.op.finish.graxpert_denoise import GraXpertDenoise
from startrails.op.finish.recombine import Recombine
from startrails.op.finish.run_starnet import RunStarNet
from startrails.op.finish.separate_stars import SeparateStars
from startrails.op.finish.sharpen_starless import SharpenStarless
from startrails.paths import APPLICATION_DIR
from startrails.workflow.base import Workflow
from startrails.workflow.masking import SkyMaskingWorkflowMixin

if TYPE_CHECKING:
    from startrails.app import App

logger = logging.getLogger(__name__)


# Shared scale for the separation task's phase progress. The view's progress
# updater and enqueue total must use the same value.
SEPARATION_PROGRESS_TOTAL: Final[int] = 100

# Phase spans on that scale (StarNet inference dominates runtime).
_STARNET_PROGRESS_SPAN = (0, 80)
_SEPARATION_PROGRESS_SPAN = (80, 17)
_RECOMBINE_PROGRESS_SPAN = (97, 3)

# Starless finishing reserves the last unit for publishing, so no inner
# operation can report the whole task complete before sharpening ends.
_STARLESS_PROGRESS_TOTAL: Final[int] = 100
_STARLESS_DENOISE_PROGRESS_SPAN = (0, 90)
_STARLESS_SHARPEN_PROGRESS_SPAN = (90, 9)
_STARLESS_NO_PHASE_PROGRESS = 99

# Star finishing also reserves the last unit for TIFF publication, so the inner
# effect operation cannot report the task complete before its result is recorded.
_STAR_FINISH_PROGRESS_TOTAL: Final[int] = 100
_STAR_FINISH_PROGRESS_SPAN = (0, 99)

# Work required when a star setting changes. Composition-only edits never run a
# worker job; Glow geometry edits reuse the catalog and Round delta.
StarRefreshAction = Literal["none", "composition", "glow", "effects"]
STAR_PREVIEW_LAYERS: Final[Tuple[str, ...]] = (
    "composite",
    "finished_stars",
    "original_stars",
    "excluded_stars",
)
# Full-frame interactive previews use a reduced cached endpoint so a 66 MP
# composition never allocates full-resolution RGB buffers on the GUI thread.
STAR_PREVIEW_MAX_DIMENSION: Final[int] = 1600

_STAR_SETTING_NAMES: Final[Tuple[str, ...]] = (
    CATALOG_SETTING_NAMES + GLOW_SETTING_NAMES + COMPOSITION_ONLY_SETTING_NAMES
)


@dataclass(frozen=True)
class StarFinishState:
    """In-memory star layers required to compose or preview the finished stars."""

    catalog: RankedStarCatalog
    inclusion_mask: np.ndarray
    round_delta: Optional[SparseRoundDelta]
    glow: Optional[np.ndarray]
    cutoff: Optional[int]
    glow_star_count: int
    glow_radius_px: float
    identity: str


@dataclass(frozen=True)
class _ReducedStarPreview:
    """Composition-only preview endpoint at a bounded resolution."""

    key: Tuple[Any, ...]
    stars: np.ndarray
    included_stars: np.ndarray
    round_component: np.ndarray
    glow: np.ndarray
    finished_starless: Optional[np.ndarray]
    negative_residual: Optional[np.ndarray]
    full_shape: Tuple[int, int]


class _PhaseProgress:
    """Map one operation's job counts onto a span of a shared progress scale.

    Each phase runs its own Observable with an independent total; this adapter
    reports every phase's absolute fraction onto ``scale`` so the task overlay
    sees one monotonic scale.
    """

    def __init__(
        self,
        observer: Callable[..., None],
        span: Tuple[int, int],
        scale: int = SEPARATION_PROGRESS_TOTAL,
    ):
        self._observer = observer
        self._start, self._size = span
        self._scale = scale
        self._reported = self._start

    @property
    def reported(self) -> int:
        """Absolute count already reported on the shared scale."""
        return self._reported

    def __call__(self, total: int, increment: int, count: int, done: bool, data: Any = None) -> None:
        sub = 0.0
        if isinstance(data, dict):
            sub = float(data.get("sub_fraction", 0.0))
        fraction = min(1.0, (count + max(0.0, min(0.99, sub))) / total) if total > 0 else (1.0 if done else 0.0)
        target = self._start + round(self._size * fraction)
        delta = target - self._reported
        if delta > 0:
            self._reported = target
        # A phase finishing early is not the whole task; only total completion
        # may tell observers that the shared operation is done.
        task_done = bool(done and target >= self._scale)
        self._observer(self._scale, max(0, delta), self._reported, task_done, data)


def _starnet_identity(platform_id: str, version: str, build: str, backend_id: str, package_sha256: str) -> str:
    return ":".join((platform_id, version, build, backend_id, package_sha256))


def _starnet_model_identity(status: dict) -> Optional[str]:
    if not status.get("configured"):
        return None
    return _starnet_identity(
        str(status["platform_id"]),
        str(status["version"]),
        str(status["build"]),
        str(status["backend_id"]),
        str(status["package_sha256"]),
    )


class FinishWorkflow(Workflow, SkyMaskingWorkflowMixin):
    """Workflow controller managing Finish mode project state, operations, and exports."""

    mode_name: str = "finish"

    def __init__(self, app: App):
        super().__init__(app)
        self._project = app.project
        self._graxpert_session: Optional[GraXpertSession] = None
        self._graxpert_session_key: Optional[Tuple[str, str]] = None
        self._catalog_cache: Optional[RankedStarCatalog] = None
        self._catalog_key: Optional[str] = None
        self._catalog_dirty: bool = False
        self._round_delta_cache: Optional[SparseRoundDelta] = None
        self._round_delta_key: Optional[str] = None
        self._round_delta_dirty: bool = False
        self._glow_cache: Optional[np.ndarray] = None
        self._glow_key: Optional[str] = None
        self._inclusion_mask_cache: Optional[np.ndarray] = None
        self._inclusion_mask_key: Optional[Tuple[str, Optional[int]]] = None
        self._reduced_preview: Optional[_ReducedStarPreview] = None
        # Interactive previews reuse decoded layers. Each entry is keyed by file
        # metadata so an externally replaced artifact is reloaded, never served
        # from a stale cache.
        self._image_cache: dict[Path, Tuple[Tuple[int, int, int], np.ndarray]] = {}
        self._mask_cache: Optional[np.ndarray] = None
        self._mask_cache_key: Optional[Tuple[str, int, int, int]] = None
        self._negative_cache: Optional[np.ndarray] = None
        self._negative_cache_key: Optional[Tuple[Any, Any]] = None

    def _clear_image_caches(self) -> None:
        """Drop decoded images and arrays derived from them."""
        self._image_cache.clear()
        self._mask_cache = None
        self._mask_cache_key = None
        self._negative_cache = None
        self._negative_cache_key = None
        self._reduced_preview = None

    def _clear_star_caches(self) -> None:
        """Drop in-memory catalog/effect layers after an ownership change."""
        self._catalog_cache = None
        self._catalog_key = None
        self._catalog_dirty = False
        self._round_delta_cache = None
        self._round_delta_key = None
        self._round_delta_dirty = False
        self._glow_cache = None
        self._glow_key = None
        self._inclusion_mask_cache = None
        self._inclusion_mask_key = None
        self._clear_image_caches()

    @staticmethod
    def _file_cache_key(path: Path) -> Tuple[int, int, int]:
        identity = read_file_identity(path)
        return identity.size, identity.mtime_ns, identity.ctime_ns

    def _cached_imread(self, path: Union[str, Path]) -> np.ndarray:
        """Decode a normalized RGB image once per file identity."""
        resolved = Path(path).resolve()
        key = self._file_cache_key(resolved)
        cached = self._image_cache.get(resolved)
        if cached is not None and cached[0] == key:
            return cached[1]
        image = imread(resolved, to_rgb=True, as_float=True)
        # A project has a small fixed set of layers; this only guards against
        # accumulating old separation paths across repeated re-runs.
        if len(self._image_cache) >= 8:
            self._image_cache.pop(next(iter(self._image_cache)))
        self._image_cache[resolved] = (key, image)
        return image

    def _current_mask_cached(self) -> Optional[np.ndarray]:
        """Load and cache the current canonical mask for interactive previews."""
        project = self.project
        if not project.source_is_current():
            return None
        mask_path = project.current_artifact_path(ROLE_SKY_MASK)
        if mask_path is None or not mask_path.is_file():
            return None
        identity = read_file_identity(mask_path)
        key = (str(mask_path), identity.size, identity.mtime_ns, identity.ctime_ns)
        if self._mask_cache is not None and self._mask_cache_key == key:
            return self._mask_cache
        dims = project.get_source_dimensions()
        mask = MaskHandler.load_mask(mask_path)
        if dims is None or mask.shape != dims:
            return None
        self._mask_cache = mask
        self._mask_cache_key = key
        return mask

    @staticmethod
    def _downsample_rgb(array: np.ndarray) -> np.ndarray:
        height, width = array.shape[:2]
        scale = min(1.0, STAR_PREVIEW_MAX_DIMENSION / float(max(height, width)))
        if scale >= 1.0:
            return array
        return cv2.resize(
            array,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        ).astype(np.float32, copy=False)

    def _preview_base_paths(self) -> Tuple[Optional[Path], Optional[Path]]:
        project = self.project
        separated = project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        finished = project.current_artifact_path(ROLE_FINISHED_STARLESS) or separated
        return finished, separated

    def _artifact_stamp(self, path: Optional[Path]) -> Optional[Tuple[int, int, int]]:
        if path is None:
            return None
        try:
            return self._file_cache_key(path)
        except OSError:
            return None

    def _expected_preview_key(self, settings: FinishSettings) -> Optional[Tuple[Any, ...]]:
        """Identify the cached preview endpoint without decoding any image."""
        project = self.project
        if project.current_artifact_path(ROLE_SEPARATED_STARS) is None:
            return None
        context = self._catalog_identity_context()
        if context is None:
            return None
        catalog_identity, _, _ = context
        base_path, separated_starless_path = self._preview_base_paths()
        return (
            f"{catalog_identity}|cutoff={settings.star_count_cutoff}",
            settings.glow_star_count,
            float(settings.star_glow_radius_px),
            STAR_EFFECT_VERSION,
            self._artifact_stamp(base_path),
            self._artifact_stamp(separated_starless_path),
        )

    @staticmethod
    def _state_matches_settings(state: StarFinishState, settings: FinishSettings) -> bool:
        return (
            state.cutoff == settings.star_count_cutoff
            and state.glow_star_count == settings.glow_star_count
            and state.glow_radius_px == float(settings.star_glow_radius_px)
        )

    def _build_reduced_preview(
        self,
        state: StarFinishState,
        stars: np.ndarray,
    ) -> Optional[_ReducedStarPreview]:
        """Build the bounded composition endpoint once, never on a toggle."""
        project = self.project
        revision = project.processing_revision
        settings = project.get_settings()
        if self._request_is_stale(project, revision) or not self._state_matches_settings(state, settings):
            return None
        key = self._expected_preview_key(settings)
        if key is None:
            return None
        stars_small = self._downsample_rgb(stars)
        # Reduce the actual S_inc product, not M and S independently: reduction
        # and multiplication do not commute at feathered footprint edges.
        included_full = (state.inclusion_mask[..., None] * stars).astype(np.float32, copy=False)
        included_small = self._downsample_rgb(included_full)
        del included_full

        round_component = np.zeros_like(included_small)
        if state.round_delta is not None:
            round_settings = replace(
                settings,
                round_stars_enabled=True,
                round_stars_amount=100.0,
                star_glow_enabled=False,
                star_glow_amount=0.0,
            )
            rounded_full = compose_star_layer(
                stars,
                state.catalog,
                state.round_delta,
                None,
                round_settings,
                inclusion_mask=state.inclusion_mask,
            )
            round_component = (self._downsample_rgb(rounded_full) - included_small).astype(np.float32, copy=False)
            del rounded_full

        glow_small = self._downsample_rgb(state.glow) if state.glow is not None else np.zeros_like(stars_small)
        base_path, separated_starless_path = self._preview_base_paths()
        finished_starless: Optional[np.ndarray] = None
        negative: Optional[np.ndarray] = None
        if base_path is not None and separated_starless_path is not None:
            finished_starless = self._downsample_rgb(self._cached_imread(base_path))
            negative = self._downsample_rgb(
                self._cached_negative_residual(self.project.source_file.path, separated_starless_path)
            )

        current_settings = project.get_settings()
        if (
            self._request_is_stale(project, revision)
            or not self._state_matches_settings(state, current_settings)
            or self._expected_preview_key(current_settings) != key
        ):
            return None
        preview = _ReducedStarPreview(
            key=key,
            stars=stars_small,
            included_stars=included_small,
            round_component=round_component,
            glow=glow_small,
            finished_starless=finished_starless,
            negative_residual=negative,
            full_shape=(int(stars.shape[0]), int(stars.shape[1])),
        )
        self._reduced_preview = preview
        return preview

    def prepare_star_endpoints(
        self,
        *,
        progress_bar: Optional[Any] = None,
        should_interrupt: Optional[Callable[[], bool]] = None,
    ) -> Optional[StarFinishState]:
        """Ensure persisted catalog/Round/Glow endpoints and a bounded preview cache.

        This is the background preparation boundary used after separation, on
        reopen, and for explicit effect/Glow rebuilds. Rendering never performs
        analysis or disk decoding on its own.
        """
        project = self.project
        revision = project.processing_revision
        settings = project.get_settings()
        inputs = self._star_inputs()
        if inputs is None:
            return None
        _, stars, _, _, _, _ = inputs
        state = self.get_star_finish_state(should_interrupt=should_interrupt, _inputs=inputs)
        if (
            state is None
            or self._request_is_stale(project, revision)
            or not self._state_matches_settings(state, settings)
        ):
            return None

        # A cache hit is not persistence truth: a prior cancellation, failed
        # transaction or corrupt artifact can leave updated blobs only in memory.
        if self._catalog_dirty or self._round_delta_dirty:
            if self.do_finish_stars(progress_bar=progress_bar) is None:
                return None
            project = self.project
            revision = project.processing_revision
            settings = project.get_settings()
            inputs = self._star_inputs()
            if inputs is None:
                return None
            _, stars, _, _, _, _ = inputs
            state = self.get_star_finish_state(should_interrupt=should_interrupt, _inputs=inputs)
            if (
                state is None
                or self._request_is_stale(project, revision)
                or not self._state_matches_settings(state, settings)
            ):
                return None

        current_settings = project.get_settings()
        if self._request_is_stale(project, revision) or not self._state_matches_settings(state, current_settings):
            return None
        key = self._expected_preview_key(current_settings)
        if self._reduced_preview is None or self._reduced_preview.key != key:
            if self._build_reduced_preview(state, stars) is None:
                return None
        if self._request_is_stale(project, revision) or not self._state_matches_settings(state, project.get_settings()):
            return None
        return state

    def get_star_preview_status(self) -> str:
        """Return ``ready``, ``cold``, ``stale`` or ``unavailable`` for the preview."""
        project = self.project
        if project.current_artifact_path(ROLE_SEPARATED_STARS) is None:
            return "unavailable"
        if not project.source_is_current():
            return "stale"
        settings = project.get_settings()
        if self._expected_preview_key(settings) is None:
            return "unavailable"
        if self._reduced_preview is None:
            return "cold"
        return "ready" if self._reduced_preview.key == self._expected_preview_key(settings) else "stale"

    def _compose_reduced_preview(
        self,
        layer: str,
        settings: FinishSettings,
        *,
        compare: bool,
    ) -> Optional[np.ndarray]:
        preview = self._reduced_preview
        if preview is None:
            return None
        included = preview.included_stars
        if layer == "original_stars":
            return preview.stars
        if layer == "excluded_stars":
            return preview.stars - included
        if layer == "finished_stars":
            if compare:
                return included.copy()
            finished = included.copy()
            round_amount = float(settings.round_stars_amount) / PERCENT_SCALE
            glow_amount = float(settings.star_glow_amount) / PERCENT_SCALE
            if settings.round_stars_enabled and round_amount > 0.0:
                finished += np.float32(round_amount) * preview.round_component
            if settings.star_glow_enabled and glow_amount > 0.0:
                finished += np.float32(glow_amount) * preview.glow
            np.clip(finished, 0.0, 1.0, out=finished)
            return finished
        if preview.finished_starless is None or preview.negative_residual is None:
            return None
        finished = self._compose_reduced_preview("finished_stars", settings, compare=False)
        if finished is None:
            return None
        return recombine_layers(
            preview.finished_starless,
            preview.stars,
            finished,
            preview.negative_residual,
            settings.original_stars_amount,
            settings.original_stars_blend_mode,
            settings.star_amount,
            settings.blend_mode,
        )

    def _region_from_reduced(
        self,
        preview: np.ndarray,
        region: Tuple[int, int, int, int],
    ) -> np.ndarray:
        cached = self._reduced_preview
        if cached is None:
            return preview
        full_h, full_w = cached.full_shape
        y0, y1, x0, x1 = region
        if y0 < 0 or x0 < 0 or y1 > full_h or x1 > full_w or y0 >= y1 or x0 >= x1:
            raise ValueError(f"Invalid preview region {region!r} for shape {(full_h, full_w)}.")
        small_h, small_w = preview.shape[:2]
        sx = small_w / float(full_w)
        sy = small_h / float(full_h)
        sx0 = max(0, min(small_w - 1, int(np.floor(x0 * sx))))
        sx1 = max(sx0 + 1, min(small_w, int(np.ceil(x1 * sx))))
        sy0 = max(0, min(small_h - 1, int(np.floor(y0 * sy))))
        sy1 = max(sy0 + 1, min(small_h, int(np.ceil(y1 * sy))))
        cropped = preview[sy0:sy1, sx0:sx1]
        target_w = x1 - x0
        target_h = y1 - y0
        bound = max(target_h, target_w)
        if bound > STAR_PREVIEW_MAX_DIMENSION:
            shrink = STAR_PREVIEW_MAX_DIMENSION / float(bound)
            target_h = max(1, int(round(target_h * shrink)))
            target_w = max(1, int(round(target_w * shrink)))
        if cropped.shape[0] != target_h or cropped.shape[1] != target_w:
            cropped = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        return cropped.astype(np.float32, copy=False)

    def _cached_negative_residual(
        self,
        source_path: Union[str, Path],
        separated_starless_path: Union[str, Path],
    ) -> np.ndarray:
        """Compute ``min(I - B, 0)`` once per source/separated-starless identity."""
        source_id = read_file_identity(Path(source_path).resolve())
        starless_id = read_file_identity(Path(separated_starless_path).resolve())
        key = (
            (source_id.size, source_id.mtime_ns, source_id.ctime_ns),
            (starless_id.size, starless_id.mtime_ns, starless_id.ctime_ns),
        )
        if self._negative_cache is not None and self._negative_cache_key == key:
            return self._negative_cache
        source = self._cached_imread(source_path)
        separated_starless = self._cached_imread(separated_starless_path)
        negative = np.subtract(source, separated_starless)
        np.minimum(negative, 0.0, out=negative)
        self._negative_cache = negative
        self._negative_cache_key = key
        return negative

    @property
    def project(self) -> FinishProject:
        """The active FinishProject managed by this workflow."""
        return self._project

    def save_project(self) -> None:
        """Do not let a stale workflow persist a project that replaced it."""
        if self._project is self.app.project:
            super().save_project()

    def invalidate_if_starnet_changed(self) -> bool:
        """Invalidate separation when its saved inputs no longer match current project state."""
        status = self.get_starnet_status()
        current_identity = _starnet_model_identity(status)
        project = self.project
        if project.separation_signature is None:
            return False
        mask_record = project.artifact_manifest.get(ROLE_SKY_MASK)
        if (
            mask_record is None
            or not project.source_file
            or not project.source_is_current()
            or project.current_artifact_path(ROLE_SKY_MASK) is None
        ):
            expected_signature = None
        else:
            if current_identity is None:
                return False
            options = project.separation_options
            if options is None:
                # A saved signature without its producing options cannot be
                # revalidated; treat it as an invalid cache rather than guessing.
                expected_signature = None
            else:
                expected_signature = compute_separation_signature(
                    source_id=project.source_file.sourceId,
                    mask_id=str(mask_record.get("file", "")),
                    model_identity=current_identity,
                    stride=int(options["stride"]),
                    upsample=bool(options["upsample"]),
                    linear=bool(options["linear"]),
                    highlights_protection=bool(options["highlights_protection"]),
                    mask_feather_radius_px=project.mask_feather_radius_px,
                )
        if expected_signature == project.separation_signature and project.separation_model_identity == current_identity:
            return False
        self._clear_star_caches()
        self.project.invalidate_results()
        self.save_project()
        return True

    def getInputFileList(self) -> List[InputFile]:  # noqa: N802 - standard host shell interface
        """Return list containing the single imported source image, if present."""
        src = getattr(self.project, "source_file", None)
        return [src] if src is not None else []

    def get_output_file_list(self) -> List[OutputFile]:
        """Return published output images whose source, revision and file are current."""
        outputs: List[OutputFile] = []
        artifact_roles = (
            (ROLE_SEPARATED_STARLESS, "Starless"),
            (ROLE_SEPARATED_STARS, "Stars"),
            (ROLE_FINISHED_STARLESS, "Finished Starless"),
            (ROLE_FINISHED_STARS, "Finished Stars"),
            (ROLE_FINISHED_COMPOSITE, "Composite"),
        )
        for role, label in artifact_roles:
            p = self.project.current_artifact_path(role)
            if p is not None:
                outputs.append(OutputFile(basename=p.name, path=str(p), operation=label))

        final_p = self.project.current_export_path()
        if final_p is not None and not any(o.path == str(final_p) for o in outputs):
            outputs.append(OutputFile(basename=final_p.name, path=str(final_p), operation="Export"))

        return outputs

    def getOutputFileList(self) -> List[OutputFile]:  # noqa: N802 - compatibility alias
        return self.get_output_file_list()

    def do_import_source(self, path: Union[str, Path]) -> None:
        """Import a new source image and persist project state."""
        self._clear_star_caches()
        self.project.set_source_image(path)
        self.save_project()

    def do_replace_source(self, path: Union[str, Path]) -> None:
        """Replace the current source image with a new one and persist project state."""
        self._clear_star_caches()
        self.project.set_source_image(path)
        self.save_project()

    def do_clear_source(self) -> None:
        """Remove the selected source from the project, retaining its files on disk."""
        self._clear_star_caches()
        self.project.clear_source_image()
        self.save_project()

    def save_mask(self, mask: np.ndarray) -> Path:
        """Validate source geometry, persist canonical sky mask, and invalidate downstream results."""
        project = self.project
        revision = project.processing_revision
        if not project.source_is_current():
            raise ValueError("Source image is not current or unavailable.")
        dims = project.get_source_dimensions()
        if dims is None:
            raise ValueError("No valid source image loaded.")
        if mask.ndim != 2:
            raise ValueError("Sky mask must be a 2D array.")
        if mask.shape != dims:
            raise ValueError(f"Mask dimensions {mask.shape} do not match source dimensions {dims}.")
        if not np.isfinite(mask).all():
            raise ValueError("Sky mask must contain finite values.")
        canonical_path = project.artifact_path(ROLE_SKY_MASK, for_write=True)
        try:
            with ArtifactTransaction(self._job_cancel_check(project, revision)) as transaction:
                staged_path = transaction.stage(canonical_path)
                written = MaskHandler.save_mask(mask, staged_path)
                if written != staged_path:
                    raise OSError("Mask staging path changed unexpectedly; mask was not published.")
                if not project.publish_mask(
                    canonical_path,
                    expected_revision=revision,
                    transaction=transaction,
                ):
                    raise ValueError("Project changed while saving the sky mask; retry the mask edit.")
        except CancelledError:
            raise ValueError("Project changed while saving the sky mask; retry the mask edit.") from None
        self._clear_star_caches()
        self.save_project()
        return canonical_path

    def get_current_mask(self) -> Optional[np.ndarray]:
        """Load published canonical sky mask after verifying freshness and source geometry."""
        if not self.project.source_is_current():
            return None
        mask_path = self.project.current_artifact_path(ROLE_SKY_MASK)
        if mask_path is None or not mask_path.is_file():
            return None
        dims = self.project.get_source_dimensions()
        mask = MaskHandler.load_mask(mask_path)
        if dims is None or mask.shape != dims:
            return None
        return mask

    def do_clear_mask(self) -> Path:
        """Create and publish an all-zeros mask matching source dimensions."""
        dims = self.project.get_source_dimensions()
        if dims is None:
            raise ValueError("No valid source image loaded.")
        mask = np.zeros(dims, dtype=np.float32)
        return self.save_mask(mask)

    def do_all_sky_mask(self) -> Path:
        """Create and publish an all-ones (all sky) mask matching source dimensions."""
        dims = self.project.get_source_dimensions()
        if dims is None:
            raise ValueError("No valid source image loaded.")
        mask = np.ones(dims, dtype=np.float32)
        return self.save_mask(mask)

    def do_export_composite(
        self,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Export the current recombined composite using source-matching depth and format."""
        self.invalidate_if_graxpert_changed()
        self.invalidate_if_starless_filter_changed()
        self.invalidate_if_star_effects_changed()
        project = self.project
        revision = project.processing_revision
        if not project.source_file or not project.source_file.path:
            raise ValueError("No source image imported to export.")

        source_path = Path(project.source_file.path)
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        if not project.source_is_current():
            raise ValueError("Source image changed; import it again before exporting.")
        depth = project.source_bit_depth
        if depth not in (8, 16):
            raise ValueError("Source bit depth is unknown; import the source again before exporting.")
        target_path = Path(output_path) if output_path is not None else project.get_default_export_path()
        project.validate_export_path(target_path)

        composite_artifact = project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        if composite_artifact is None:
            raise ValueError("No current composite result to export; separate stars and recombine first.")
        settings = project.get_settings()
        separation_signature = project.separation_signature
        img = imread(composite_artifact, to_rgb=True, as_float=True)

        target_path = Path(target_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        expected_export = {
            "expected_revision": revision,
            "expected_separation_signature": separation_signature,
        }
        try:
            with ArtifactTransaction(self._job_cancel_check(project, revision)) as transaction:
                staged_path = transaction.stage(target_path)
                written = imwrite(
                    staged_path,
                    img,
                    convertBGR=True,
                    bit_depth=depth,
                    quality=settings.jpeg_quality,
                    optimize=settings.jpeg_optimize,
                    compression=settings.tiff_deflate_compression,
                )
                if written != staged_path:
                    raise OSError("Export staging path changed unexpectedly; output was not published.")
                if not project.record_export_if_current(
                    target_path,
                    transaction=transaction,
                    **expected_export,
                ):
                    raise ValueError("Project changed while saving; the export was not recorded as current.")
        except CancelledError:
            raise ValueError("Export was cancelled; no output was published.") from None
        self.save_project()
        return target_path

    # -------------------------------------------------------------------------
    # Dependency Lifecycle & Operational Adapters (StarNet & GraXpert)
    # -------------------------------------------------------------------------

    def get_starnet_status(self) -> dict:
        """Return the current installation, configuration, and terms status for StarNet."""
        state = self.app.state
        record = state.get("starnet", {})
        if not isinstance(record, dict):
            record = {}
        terms_accepted = starnet_terms_accepted(state)
        installation = get_active_starnet_installation(state)

        try:
            setup_notice = managed_starnet_setup_notice(detect_platform_target())
        except PlatformNotSupportedError as error:
            setup_notice = str(error)
        return {
            "setup_notice": setup_notice,
            "configured": installation is not None and terms_accepted,
            "installation": installation,
            "managed": record.get("managed", False),
            "executable": str(installation.executable) if installation else record.get("executable"),
            "version": installation.package.version if installation else record.get("version"),
            "build": installation.package.build if installation else record.get("build"),
            "backend_id": installation.package.backend_id if installation else record.get("backend_id"),
            "platform_id": installation.package.platform_id if installation else None,
            "package_sha256": installation.package.archive_sha256 if installation else None,
            "terms_accepted": terms_accepted,
            "terms_revision": record.get("terms_revision"),
        }

    def get_graxpert_status(self) -> dict:
        """Return the current runtime execution policy and model file readiness for GraXpert."""
        try:
            policy = resolve_graxpert_runtime_policy()
            setup_error = None
        except (RuntimeError, ValueError, OSError) as error:
            policy = None
            setup_error = str(error)
        model_path = APPLICATION_DIR / "models" / GRAXPERT_MANIFEST.relative_path
        # Status is refreshed often; setup/repair already verified the model hash.
        # A cheap presence/size check avoids rehashing the ~478 MB weights here.
        try:
            model_ready = model_path.is_file() and model_path.stat().st_size == GRAXPERT_MANIFEST.size_bytes
        except OSError:
            model_ready = False
        provider = policy.get("provider") if policy is not None else None
        device = policy.get("device") if policy is not None else None
        session = self._graxpert_session
        # A session created for a previous policy lane no longer describes the
        # configured runtime, so do not present its execution state as current.
        session_matches_policy = (
            session is not None and provider is not None and session.configured_provider == provider
        )
        return {
            "configured": policy is not None and model_ready,
            # Configured provider comes from the setup-owned policy; execution
            # fields report what the last session actually used, including a CPU retry.
            "provider": provider,
            "device": device,
            "execution_provider": session.execution_provider if session_matches_policy else None,
            "fallback_reason": session.fallback_reason if session_matches_policy else None,
            "policy": policy,
            "setup_error": setup_error,
            "model_ready": model_ready,
            "model_path": str(model_path),
        }

    def invalidate_if_graxpert_changed(self) -> bool:
        """Invalidate denoise outputs when the pinned GraXpert model identity changed."""
        project = self.project
        if project.denoise_signature is None:
            return False
        if project.denoise_model_identity == graxpert_model_identity():
            return False
        project.invalidate_denoise_descendants()
        self.save_project()
        return True

    def invalidate_if_starless_filter_changed(self) -> bool:
        """Invalidate finished plates built by a different sharpening algorithm version.

        The cached full-strength denoise endpoint is unaffected, so structure/detail
        can be recomputed from the same endpoint after upgrading the filter.
        """
        project = self.project
        record = project.artifact_manifest.get(ROLE_FINISHED_STARLESS)
        if record is None:
            return False
        saved_version = record.get("options", {}).get("starless_filter_version")
        if saved_version == STARLESS_FILTER_VERSION:
            return False
        project.invalidate_starless_filter_descendants()
        self.save_project()
        return True

    def invalidate_if_star_effects_changed(self) -> bool:
        """Invalidate layers produced by older analysis/effect versions.

        An analysis-version change invalidates the catalog and every layer derived
        from it. An effect-version change keeps the catalog but rebuilds Round,
        Glow and compositions. Separation, denoise and finished-starless results
        are unaffected either way.
        """
        project = self.project
        catalog_record = project.artifact_manifest.get(ROLE_STAR_CATALOG)
        if catalog_record is not None:
            options = catalog_record.get("options", {})
            if (
                options.get("analysis_version") != STAR_ANALYSIS_VERSION
                or options.get("catalog_version") != STAR_CATALOG_VERSION
            ):
                self._clear_star_caches()
                project.invalidate_star_effects_descendants()
                self.save_project()
                return True

        changed = False
        round_record = project.artifact_manifest.get(ROLE_ROUND_DELTA)
        if round_record is not None:
            if round_record.get("options", {}).get("star_effect_version") != STAR_EFFECT_VERSION:
                changed = True
        # A finished-stars TIFF is derived output, but a record produced by an
        # older effect algorithm still identifies stale on-disk layers.
        finished_record = project.artifact_manifest.get(ROLE_FINISHED_STARS)
        if finished_record is not None:
            if finished_record.get("options", {}).get("star_effect_version") != STAR_EFFECT_VERSION:
                changed = True
        if changed:
            self._clear_star_caches()
            project.invalidate_star_effect_layers()
            self.save_project()
        return changed

    @staticmethod
    def _star_effects_enabled(settings: FinishSettings) -> bool:
        """Return whether an enabled effect has a non-zero amount.

        A toggle left on at 0% is neutral and must not require an effect layer.
        """
        return bool(
            (settings.round_stars_enabled and settings.round_stars_amount > 0)
            or (settings.star_glow_enabled and settings.star_glow_amount > 0)
        )

    @classmethod
    def _star_effects_required(cls, settings: FinishSettings) -> bool:
        """Return whether effects can change the recombined output."""
        return settings.star_amount > 0 and cls._star_effects_enabled(settings)

    @staticmethod
    def star_refresh_action(previous: FinishSettings, current: FinishSettings) -> StarRefreshAction:
        """Classify the work needed for a star-settings change.

        Composition-only controls never require a worker job. Glow geometry
        changes only the rendered Glow component. The cutoff may need incremental
        catalog measurements plus Round/Glow rebuilds.
        """
        changed = {name for name in _STAR_SETTING_NAMES if getattr(previous, name) != getattr(current, name)}
        if not changed:
            return "none"
        if changed & set(CATALOG_SETTING_NAMES):
            return "effects"
        if changed & set(GLOW_SETTING_NAMES):
            return "glow"
        if changed & set(COMPOSITION_ONLY_SETTING_NAMES):
            return "composition"
        return "none"

    def _graxpert_session_for(self, policy: dict) -> GraXpertSession:
        """Reuse one verified inference session for the resolved provider policy.

        The setup result is authoritative; processing must not re-probe providers or
        rediscover capabilities. A cached session also avoids reloading the model on
        every interactive strength/scope request.
        """
        provider = str(policy["provider"])
        key = (provider, graxpert_model_identity())
        session = self._graxpert_session
        if session is not None and self._graxpert_session_key == key:
            return session
        session = GraXpertSession(provider=provider)
        self._graxpert_session = session
        self._graxpert_session_key = key
        return session

    def accept_starnet_terms(self) -> None:
        """Record affirmative terms acceptance in application state."""
        record = self.app.state.setdefault("starnet", {})
        record["terms_accepted"] = True
        record["terms_revision"] = STARNET_TERMS_REVISION
        record["terms_sha256"] = STARNET_TERMS_SHA256
        self.app.saveAppState()

    def set_starnet_installation(
        self,
        installation: StarNetInstallation,
        *,
        managed: bool,
        terms_accepted: bool,
    ) -> None:
        """Persist verified StarNet installation in application state."""
        project = self.project
        new_identity = _starnet_identity(
            installation.package.platform_id,
            installation.package.version,
            installation.package.build,
            installation.package.backend_id,
            installation.package.archive_sha256,
        )
        old_identity = _starnet_model_identity(self.get_starnet_status())
        if old_identity is None:
            # The recorded installation may be offline; the project still knows
            # the identity that produced its current layers.
            old_identity = project.separation_model_identity
        invalidated_results = False
        if (project.separation_signature is not None or old_identity is not None) and old_identity != new_identity:
            project.invalidate_results()
            invalidated_results = True
        record_starnet_installation(
            self.app.state,
            installation,
            managed=managed,
            terms_accepted=terms_accepted,
        )
        self.app.saveAppState()
        if invalidated_results:
            self.save_project()

    def do_install_starnet_managed(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> StarNetInstallation:
        """Download, validate, probe, and atomically install managed StarNet."""
        if not starnet_terms_accepted(self.app.state):
            raise StarNetSetupError("Accept the current StarNet terms before installation.")
        installation = install_starnet_managed(
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        self.set_starnet_installation(installation, managed=True, terms_accepted=True)
        return installation

    def do_repair_starnet(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> StarNetInstallation:
        """Repair or re-probe the active StarNet installation."""
        state = dict(self.app.state)
        installation = repair_starnet_installation(
            state,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        return installation

    def _job_cancel_check(self, project: FinishProject, revision: int) -> Callable[[], bool]:
        """Return a cancellation guard bound to this job's project, revision, and session."""

        def cancelled() -> bool:
            if project is not self.app.project or revision != project.processing_revision:
                return True
            if not project.source_is_current():
                return True
            session = self._session_operation
            return bool(session is not None and session.shouldInterrupt())

        return cancelled

    # -------------------------------------------------------------------------
    # Ranked catalog and composable star layers
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_star_cutoff(cutoff: Optional[int]) -> None:
        if cutoff is None:
            return
        if type(cutoff) is not int or cutoff < 0:
            raise ValueError(f"star_count_cutoff must be a non-negative integer or None, got {cutoff!r}")

    @staticmethod
    def _validate_glow_count(count: int) -> None:
        if type(count) is not int or count < 0:
            raise ValueError(f"glow_star_count must be a non-negative integer, got {count!r}")

    @staticmethod
    def _catalog_identity(separation_signature: str, source_id: str, mask_file: str) -> str:
        return compute_signature(
            {
                "operation": "finish_star_catalog",
                "catalog_version": STAR_CATALOG_VERSION,
                "analysis_version": STAR_ANALYSIS_VERSION,
                "separation": separation_signature,
                "source": source_id,
                "mask": mask_file,
            }
        )

    @staticmethod
    def _round_identity(catalog_identity: str, cutoff: Optional[int]) -> str:
        return compute_signature(
            {
                "operation": "finish_round_delta",
                "effect_version": STAR_EFFECT_VERSION,
                "catalog": catalog_identity,
                "cutoff": cutoff,
            }
        )

    @staticmethod
    def _glow_cache_key(catalog_identity: str, cutoff: Optional[int], count: int, radius_px: float) -> str:
        return f"{catalog_identity}|cutoff={cutoff}|count={count}|radius={radius_px:g}|effect={STAR_EFFECT_VERSION}"

    def _catalog_identity_context(self) -> Optional[Tuple[str, str, str]]:
        """Return catalog identity/source/mask metadata without decoding images."""
        project = self.project
        if project.separation_signature is None or project.source_file is None or not project.source_is_current():
            return None
        mask_record = project.artifact_manifest.get(ROLE_SKY_MASK, {})
        mask_file = str(mask_record.get("file", ""))
        source_id = project.source_file.sourceId
        identity = self._catalog_identity(project.separation_signature, source_id, mask_file)
        return identity, source_id, mask_file

    def _star_inputs(self) -> Optional[Tuple[Path, np.ndarray, np.ndarray, str, str, str]]:
        """Load current separated stars and mask for catalog/effect work."""
        project = self.project
        stars_path = project.current_artifact_path(ROLE_SEPARATED_STARS)
        if stars_path is None:
            return None
        context = self._catalog_identity_context()
        if context is None:
            return None
        catalog_identity, source_id, mask_file = context
        mask = self._current_mask_cached()
        if mask is None:
            return None
        stars = self._cached_imread(stars_path)
        return stars_path, stars, mask, catalog_identity, source_id, mask_file

    def _read_catalog_source(self) -> np.ndarray:
        project = self.project
        if project.source_file is None or not project.source_file.path:
            raise ValueError("Source image is unavailable.")
        return self._cached_imread(project.source_file.path)

    def _catalog_is_measured(self, catalog: RankedStarCatalog, cutoff: Optional[int]) -> bool:
        total = len(catalog.analysis.candidates)
        needed = total if cutoff is None else min(cutoff, total)
        return int(np.count_nonzero(catalog.measured)) >= needed

    def _catalog_persisted_current(self, identity: str) -> bool:
        project = self.project
        if project.current_artifact_path(ROLE_STAR_CATALOG) is None:
            return False
        record = project.artifact_manifest.get(ROLE_STAR_CATALOG, {})
        options = record.get("options", {})
        return (
            options.get("catalog_identity") == identity
            and options.get("analysis_version") == STAR_ANALYSIS_VERSION
            and options.get("catalog_version") == STAR_CATALOG_VERSION
        )

    def _round_delta_persisted_current(self, identity: str, cutoff: Optional[int]) -> bool:
        project = self.project
        if project.current_artifact_path(ROLE_ROUND_DELTA) is None:
            return False
        options = project.artifact_manifest.get(ROLE_ROUND_DELTA, {}).get("options", {})
        return (
            options.get("round_identity") == identity
            and options.get("cutoff") == cutoff
            and options.get("star_effect_version") == STAR_EFFECT_VERSION
        )

    def _load_persisted_catalog(self, identity: str) -> Optional[RankedStarCatalog]:
        project = self.project
        path = project.current_artifact_path(ROLE_STAR_CATALOG)
        if path is None:
            return None
        record = project.artifact_manifest.get(ROLE_STAR_CATALOG, {})
        options = record.get("options", {})
        if (
            options.get("catalog_identity") != identity
            or options.get("analysis_version") != STAR_ANALYSIS_VERSION
            or options.get("catalog_version") != STAR_CATALOG_VERSION
        ):
            return None
        try:
            return load_catalog(path, identity=identity)
        except (OSError, ValueError):
            # Missing or corrupt caches are stale, never partially consumed.
            return None

    def _ensure_catalog(
        self,
        stars: np.ndarray,
        mask: np.ndarray,
        *,
        cutoff: Optional[int],
        identity: str,
        should_interrupt: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[..., None]] = None,
    ) -> Tuple[Optional[RankedStarCatalog], bool]:
        """Load or build the catalog, extending measurements when the cutoff rose."""
        self._validate_star_cutoff(cutoff)
        if self._catalog_cache is not None and self._catalog_key == identity:
            if self._catalog_is_measured(self._catalog_cache, cutoff):
                dirty = self._catalog_dirty or not self._catalog_persisted_current(identity)
                self._catalog_dirty = dirty
                return self._catalog_cache, dirty
        else:
            persisted = self._load_persisted_catalog(identity)
            if persisted is not None:
                self._catalog_cache = persisted
                self._catalog_key = identity
                self._catalog_dirty = False
                if self._catalog_is_measured(persisted, cutoff):
                    return persisted, False

        source = self._read_catalog_source()
        if self._catalog_cache is not None and self._catalog_key == identity:
            catalog = extend_catalog(
                self._catalog_cache,
                stars,
                source,
                mask,
                cutoff=cutoff,
                should_interrupt=should_interrupt,
                progress_callback=progress_callback,
            )
        else:
            catalog = build_catalog(
                stars,
                source,
                mask,
                cutoff=cutoff,
                should_interrupt=should_interrupt,
                progress_callback=progress_callback,
            )
        if catalog is None:
            return None, False
        self._catalog_cache = catalog
        self._catalog_key = identity
        self._catalog_dirty = True
        return catalog, True

    def _ensure_inclusion_mask(
        self,
        catalog: RankedStarCatalog,
        *,
        cutoff: Optional[int],
        catalog_identity: str,
    ) -> np.ndarray:
        """Return the feathered included-star mask M, built once per catalog/cutoff."""
        key = (catalog_identity, cutoff)
        if self._inclusion_mask_cache is not None and self._inclusion_mask_key == key:
            return self._inclusion_mask_cache
        mask = included_mask(catalog, cutoff=cutoff)
        self._inclusion_mask_cache = mask
        self._inclusion_mask_key = key
        return mask

    def _ensure_round_delta(
        self,
        stars: np.ndarray,
        mask: np.ndarray,
        catalog: RankedStarCatalog,
        *,
        cutoff: Optional[int],
        identity: str,
        inclusion_mask: np.ndarray,
        should_interrupt: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[..., None]] = None,
    ) -> Tuple[Optional[SparseRoundDelta], bool]:
        """Load or build the full-strength Round Stars delta, independent of toggles."""
        if self._round_delta_cache is not None and self._round_delta_key == identity:
            dirty = self._round_delta_dirty or not self._round_delta_persisted_current(identity, cutoff)
            self._round_delta_dirty = dirty
            return self._round_delta_cache, dirty

        project = self.project
        path = project.current_artifact_path(ROLE_ROUND_DELTA)
        if path is not None:
            record = project.artifact_manifest.get(ROLE_ROUND_DELTA, {})
            options = record.get("options", {})
            if options.get("round_identity") == identity and options.get("cutoff") == cutoff:
                try:
                    delta = load_round_delta(path, identity=identity)
                except (OSError, ValueError):
                    delta = None
                if delta is not None:
                    self._round_delta_cache = delta
                    self._round_delta_key = identity
                    self._round_delta_dirty = False
                    return delta, False

        delta = build_round_delta(
            stars,
            mask,
            catalog,
            cutoff=cutoff,
            inclusion_mask=inclusion_mask,
            should_interrupt=should_interrupt,
            progress_callback=progress_callback,
        )
        if delta is None:
            return None, False
        self._round_delta_cache = delta
        self._round_delta_key = identity
        self._round_delta_dirty = True
        return delta, True

    def _ensure_glow(
        self,
        stars: np.ndarray,
        mask: np.ndarray,
        catalog: RankedStarCatalog,
        *,
        cutoff: Optional[int],
        inclusion_mask: np.ndarray,
        count: int,
        radius_px: float,
        catalog_identity: str,
        should_interrupt: Optional[Callable[[], bool]] = None,
    ) -> Optional[np.ndarray]:
        """Render the Glow component in memory; it is never persisted."""
        self._validate_glow_count(count)
        key = self._glow_cache_key(catalog_identity, cutoff, count, float(radius_px))
        if self._glow_cache is not None and self._glow_key == key:
            return self._glow_cache
        glow = render_glow(
            stars,
            mask,
            catalog,
            cutoff=cutoff,
            inclusion_mask=inclusion_mask,
            glow_star_count=count,
            radius_px=float(radius_px),
            should_interrupt=should_interrupt,
        )
        if glow is None:
            return None
        self._glow_cache = glow
        self._glow_key = key
        return glow

    def get_star_finish_state(
        self,
        *,
        ensure_round: bool = True,
        ensure_glow: bool = True,
        should_interrupt: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[..., None]] = None,
        _inputs: Optional[Tuple[Path, np.ndarray, np.ndarray, str, str, str]] = None,
    ) -> Optional[StarFinishState]:
        """Return current catalog/effect layers, loading caches instead of re-analysis.

        Both endpoints are built even when their toggles are off so later toggles
        and amount changes are composition-only. Returns None when inputs are not
        ready, interrupted or the project changed underneath the request.
        """
        project = self.project
        revision = project.processing_revision
        inputs = _inputs if _inputs is not None else self._star_inputs()
        if inputs is None:
            return None
        _, stars, mask, catalog_identity, _, _ = inputs
        settings = project.get_settings()
        cutoff = settings.star_count_cutoff
        self._validate_star_cutoff(cutoff)

        catalog, _ = self._ensure_catalog(
            stars,
            mask,
            cutoff=cutoff,
            identity=catalog_identity,
            should_interrupt=should_interrupt,
            progress_callback=progress_callback,
        )
        if catalog is None or self._request_is_stale(project, revision):
            return None
        inclusion_mask = self._ensure_inclusion_mask(
            catalog,
            cutoff=cutoff,
            catalog_identity=catalog_identity,
        )

        round_delta: Optional[SparseRoundDelta] = None
        if ensure_round:
            round_identity = self._round_identity(catalog_identity, cutoff)
            round_delta, _ = self._ensure_round_delta(
                stars,
                mask,
                catalog,
                cutoff=cutoff,
                identity=round_identity,
                inclusion_mask=inclusion_mask,
                should_interrupt=should_interrupt,
                progress_callback=progress_callback,
            )
            if round_delta is None or self._request_is_stale(project, revision):
                return None

        glow: Optional[np.ndarray] = None
        if ensure_glow:
            glow = self._ensure_glow(
                stars,
                mask,
                catalog,
                cutoff=cutoff,
                inclusion_mask=inclusion_mask,
                count=settings.glow_star_count,
                radius_px=settings.star_glow_radius_px,
                catalog_identity=catalog_identity,
                should_interrupt=should_interrupt,
            )
            if glow is None or self._request_is_stale(project, revision):
                return None

        return StarFinishState(
            catalog=catalog,
            inclusion_mask=inclusion_mask,
            round_delta=round_delta,
            glow=glow,
            cutoff=cutoff,
            glow_star_count=settings.glow_star_count,
            glow_radius_px=float(settings.star_glow_radius_px),
            identity=f"{catalog_identity}|cutoff={cutoff}",
        )

    def get_star_catalog_summary(self) -> Optional[dict]:
        """Return counts from the prepared catalog cache without disk/analysis work."""
        project = self.project
        context = self._catalog_identity_context()
        if context is None or project.current_artifact_path(ROLE_SEPARATED_STARS) is None:
            return None
        catalog_identity, _, _ = context
        if self._catalog_cache is None or self._catalog_key != catalog_identity:
            return None
        settings = project.get_settings()
        cutoff = settings.star_count_cutoff
        self._validate_star_cutoff(cutoff)
        catalog = self._catalog_cache
        return {
            "total_count": len(catalog.analysis.candidates),
            "included_count": catalog.included_count(cutoff),
            "cutoff_score": catalog.cutoff_score(cutoff),
        }

    def _request_is_stale(self, project: FinishProject, revision: int) -> bool:
        return (
            project is not self.app.project
            or revision != project.processing_revision
            or not project.source_is_current()
        )

    def render_star_preview(
        self,
        layer: str = "composite",
        *,
        region: Optional[Tuple[int, int, int, int]] = None,
        compare: bool = False,
        should_interrupt: Optional[Callable[[], bool]] = None,
    ) -> Optional[np.ndarray]:
        """Return a display-ready star preview without publishing or worker jobs.

        ``layer`` is ``composite``, ``finished_stars``, ``original_stars`` or
        ``excluded_stars``. ``region`` is a full-resolution ``(y0, y1, x0, x1)``
        crop. ``compare`` returns ``S_inc`` without effects for finished stars.

        Full-frame output is a reduced composition endpoint. Region output is a
        reduced-endpoint crop upscaled to the requested size for Finished/Composite
        layers; Original/Excluded use the exact cached full-resolution crop when
        those arrays are still warm. It is not a true full-resolution 100% render
        for Finished/Composite until a bounded full-res region compositor exists.
        """
        if layer not in STAR_PREVIEW_LAYERS:
            raise ValueError(f"Unknown star preview layer '{layer}'.")
        project = self.project
        if not project.source_is_current():
            return None
        settings = project.get_settings()
        self._validate_star_cutoff(settings.star_count_cutoff)
        expected = self._expected_preview_key(settings)
        if expected is None or self._reduced_preview is None or self._reduced_preview.key != expected:
            # Cold/stale: the background preparation task owns all disk, mask,
            # Round and Glow work. A toggle must never trigger it from the GUI.
            return None
        if should_interrupt is not None and should_interrupt():
            return None
        if region is not None and layer in ("original_stars", "excluded_stars"):
            exact = self._exact_cached_star_crop(layer, region, settings)
            if exact is not None:
                return exact
        composed = self._compose_reduced_preview(layer, settings, compare=compare)
        if composed is None:
            return None
        if region is not None:
            composed = self._region_from_reduced(composed, region)
        return np.ascontiguousarray(composed, dtype=np.float32)

    def _exact_cached_star_crop(
        self,
        layer: str,
        region: Tuple[int, int, int, int],
        settings: FinishSettings,
    ) -> Optional[np.ndarray]:
        """Return an exact cached full-resolution Original/Excluded crop if warm."""
        project = self.project
        stars_path = project.current_artifact_path(ROLE_SEPARATED_STARS)
        if stars_path is None:
            return None
        cached = self._image_cache.get(stars_path)
        if cached is None or cached[0] != self._file_cache_key(stars_path):
            return None
        stars = cached[1]
        y0, y1, x0, x1 = region
        if y0 < 0 or x0 < 0 or y1 > stars.shape[0] or x1 > stars.shape[1] or y0 >= y1 or x0 >= x1:
            raise ValueError(f"Invalid preview region {region!r} for shape {stars.shape[:2]}.")
        stars_crop = stars[y0:y1, x0:x1]
        if layer == "original_stars":
            return np.ascontiguousarray(stars_crop, dtype=np.float32)
        context = self._catalog_identity_context()
        if context is None:
            return None
        catalog_identity, _, _ = context
        if self._inclusion_mask_cache is None or self._inclusion_mask_key != (
            catalog_identity,
            settings.star_count_cutoff,
        ):
            return None
        mask_crop = self._inclusion_mask_cache[y0:y1, x0:x1]
        return np.ascontiguousarray(
            stars_crop - mask_crop[..., None] * stars_crop,
            dtype=np.float32,
        )

    @staticmethod
    def _validate_starnet_stride(stride: int) -> None:
        """Enforce the StarNet CLI stride contract before any cache lookup."""
        if type(stride) is not int or stride < MIN_STRIDE or stride > MAX_STRIDE or stride % 2 != 0:
            raise ValueError(f"Stride must be an even integer between {MIN_STRIDE} and {MAX_STRIDE}, got {stride}")

    @staticmethod
    def _validate_model_output(path: Path, dimensions: Tuple[int, int]) -> None:
        """Reject a corrupt StarNet result before it is cached or normalized."""
        model = imread(path, to_rgb=True, as_float=False)
        if model.dtype not in (np.uint8, np.uint16):
            raise ValueError(f"StarNet output must be uint8 or uint16, got {model.dtype}.")
        if model.ndim != 3 or model.shape[2] != SUPPORTED_CHANNELS or model.shape[:2] != dimensions:
            raise ValueError(f"StarNet output shape {model.shape} does not match source dimensions {dimensions}.")
        if not np.isfinite(model).all():
            raise ValueError("StarNet output contains non-finite values.")

    def _recombine_into_transaction(
        self,
        starless_path: Path,
        stars_path: Path,
        *,
        negative_base_path: Path,
        composite_destination: Path,
        transaction: ArtifactTransaction,
        progress_bar: Optional[Any] = None,
        finished_stars: Optional[np.ndarray] = None,
    ) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Recombine the given layers into a staged composite without publishing it.

        The negative correction always derives from the separated starless plate
        passed as negative_base_path, never from a subsequently finished plate.
        starless_path controls the visible base; in the Step 7 neutral case both
        paths are the same separated plate. ``finished_stars`` is composed from
        catalog layers by the caller; before star effects exist it is the original
        separated star layer, matching the neutral Step 7 composite.
        """
        project = self.project
        source_arr = imread(project.source_file.path, to_rgb=True, as_float=True)
        starless_arr = imread(starless_path, to_rgb=True, as_float=True)
        original_stars_arr = imread(stars_path, to_rgb=True, as_float=True)
        finished_stars_arr = original_stars_arr if finished_stars is None else finished_stars

        if negative_base_path == starless_path:
            negative_base_arr = starless_arr
        else:
            negative_base_arr = imread(negative_base_path, to_rgb=True, as_float=True)

        neg_residual = source_arr
        np.subtract(neg_residual, negative_base_arr, out=neg_residual)
        np.minimum(neg_residual, 0, out=neg_residual)
        if negative_base_arr is not starless_arr:
            del negative_base_arr

        op = self._new_operation(Recombine)
        if progress_bar is not None:
            op.addObserver(progress_bar)
        self.app.activeOperation = op
        try:
            result = op.recombine(
                starless_arr,
                original_stars_arr,
                finished_stars_arr,
                neg_residual,
                project.get_settings(),
                bit_depth=INTERMEDIATE_BIT_DEPTH,
                output_path=composite_destination,
                artifacts=transaction,
            )
        finally:
            if self.app.activeOperation is op:
                self.app.activeOperation = self._session_operation
            if progress_bar is not None:
                op.removeObserver(progress_bar)

        if result is None or op.shouldInterrupt():
            return None
        return result

    def do_run_starnet(
        self,
        input_image_path: Union[str, Path],
        output_starless_path: Union[str, Path],
        *,
        output_stars_path: Optional[Union[str, Path]] = None,
        stride: int,
        disable_highlights: bool = False,
        upsample: bool = False,
        progress_bar: Optional[Any] = None,
    ) -> Optional[Tuple[Path, Optional[Path]]]:
        """Execute StarNet subprocess using the active verified installation."""
        self._validate_starnet_stride(stride)
        managed = self.app.state.get("starnet", {}).get("managed", False)
        lock = starnet_installation_lock(get_starnet_storage_dir()) if managed else nullcontext()
        with lock:
            status = self.get_starnet_status()
            if not status["configured"]:
                raise RuntimeError("StarNet is not configured or terms have not been accepted.")
            op = self._new_operation(RunStarNet)
            if progress_bar is not None:
                op.addObserver(progress_bar)
            self.app.activeOperation = op
            try:
                return op.run(
                    status["executable"],
                    input_image_path,
                    output_starless_path,
                    output_stars_path=output_stars_path,
                    stride=stride,
                    disable_highlights=disable_highlights,
                    upsample=upsample,
                )
            finally:
                if self.app.activeOperation is op:
                    self.app.activeOperation = self._session_operation
                if progress_bar is not None:
                    op.removeObserver(progress_bar)

    def do_separate_stars(
        self,
        *,
        stride: Optional[int] = None,
        disable_highlights: bool = False,
        upsample: bool = False,
        chunk_rows: int = 512,
        progress_bar: Optional[Any] = None,
    ) -> Optional[Tuple[OutputFile, OutputFile]]:
        """Separate stars from sky background using StarNet and sky protection mask.

        progress_bar, when given, receives each phase's progress mapped onto the
        shared SEPARATION_PROGRESS_TOTAL scale.
        """
        project = self.project
        stride = project.starnet_stride if stride is None else stride
        self._validate_starnet_stride(stride)
        project_revision = project.processing_revision
        if not project.source_is_current():
            raise ValueError("Source image is not current or unavailable.")
        dims = project.get_source_dimensions()
        min_dim = 256 if upsample else 512
        if dims is None or dims[0] < min_dim or dims[1] < min_dim:
            actual_dims = f"{dims[1]}x{dims[0]}" if dims else "0x0"
            raise ValueError(
                f"Image dimensions ({actual_dims}) are below StarNet minimum supported dimensions ({min_dim}x{min_dim})."
            )

        mask = self.get_current_mask()
        if mask is None:
            raise ValueError("A sky mask is required to separate stars.")
        feather_radius_px = project.mask_feather_radius_px
        mask = MaskHandler.feather_mask(mask, feather_radius_px)

        source_id = project.source_file.sourceId
        mask_record = project.artifact_manifest.get(ROLE_SKY_MASK, {})
        mask_id = str(mask_record.get("file", ""))

        starnet_status = self.get_starnet_status()
        if not starnet_status.get("configured", False):
            raise RuntimeError("StarNet2 is not configured or terms have not been accepted.")
        model_identity = _starnet_model_identity(starnet_status)
        if model_identity is None:
            raise RuntimeError(
                "StarNet2 package identity is unavailable; repair the installation before separating stars."
            )

        source_path = Path(project.source_file.path)
        unmasked_options = {
            "stride": stride,
            "disable_highlights": disable_highlights,
            "upsample": upsample,
            "version": starnet_status.get("version"),
            "build": starnet_status.get("build"),
            "backend_id": starnet_status.get("backend_id"),
            "platform_id": starnet_status.get("platform_id"),
            "package_sha256": starnet_status.get("package_sha256"),
        }
        separation_options = {
            "stride": stride,
            "upsample": upsample,
            "linear": False,
            "highlights_protection": not disable_highlights,
            "mask_feather_radius_px": feather_radius_px,
        }

        unmasked_path = project.current_artifact_path(ROLE_UNMASKED_STARLESS, options=unmasked_options)
        if unmasked_path is None or not unmasked_path.is_file():
            starnet_progress = (
                _PhaseProgress(progress_bar, _STARNET_PROGRESS_SPAN) if progress_bar is not None else None
            )
            unmasked_dest = project.artifact_path(ROLE_UNMASKED_STARLESS, for_write=True)
            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_input = Path(tmp_dir) / "starnet_input.tif"
                    source_int = imread(source_path, to_rgb=True, as_float=False)
                    imwrite(tmp_input, source_int, convertBGR=True, bit_depth=project.source_bit_depth)
                    del source_int
                    with ArtifactTransaction(self._job_cancel_check(project, project_revision)) as transaction:
                        staged_unmasked = transaction.stage(unmasked_dest)
                        run_res = self.do_run_starnet(
                            tmp_input,
                            staged_unmasked,
                            stride=stride,
                            disable_highlights=disable_highlights,
                            upsample=upsample,
                            progress_bar=starnet_progress,
                        )
                        if run_res is None:
                            return None
                        self._validate_model_output(staged_unmasked, dims)
                        if not project.record_artifact(
                            ROLE_UNMASKED_STARLESS,
                            unmasked_dest,
                            options=unmasked_options,
                            expected_revision=project_revision,
                            transaction=transaction,
                        ):
                            return None
                self.save_project()
            except CancelledError:
                return None
            unmasked_path = unmasked_dest
        elif progress_bar is not None:
            star_net_span = _STARNET_PROGRESS_SPAN[1]
            progress_bar(
                SEPARATION_PROGRESS_TOTAL,
                star_net_span,
                star_net_span,
                False,
                {"desc": "Using cached StarNet separation..."},
            )

        source_float = imread(source_path, to_rgb=True, as_float=True)
        model_float = imread(unmasked_path, to_rgb=True, as_float=True)

        starless_dest = project.artifact_path(ROLE_SEPARATED_STARLESS, for_write=True)
        stars_dest = project.artifact_path(ROLE_SEPARATED_STARS, for_write=True)
        composite_dest = project.artifact_path(ROLE_FINISHED_COMPOSITE, for_write=True)

        op = self._new_operation(SeparateStars)
        separation_progress = (
            _PhaseProgress(progress_bar, _SEPARATION_PROGRESS_SPAN) if progress_bar is not None else None
        )
        if separation_progress is not None:
            op.addObserver(separation_progress)
        self.app.activeOperation = op
        try:
            try:
                with ArtifactTransaction(self._job_cancel_check(project, project_revision)) as transaction:
                    staged_starless = transaction.stage(starless_dest)
                    staged_stars = transaction.stage(stars_dest)
                    sep_result = op.separate(
                        source_float,
                        model_float,
                        mask,
                        starless_path=staged_starless,
                        stars_path=staged_stars,
                        chunk_rows=chunk_rows,
                        settings=project.get_settings(),
                    )
                    if (
                        sep_result is None
                        or op.shouldInterrupt()
                        or project is not self.app.project
                        or project_revision != project.processing_revision
                        or not project.source_is_current()
                    ):
                        # A cancel, mask save or project switch landing after the
                        # operation stage makes these results stale; never publish them.
                        return None

                    # Release the separation working arrays before allocating the
                    # composite buffers; the staged files are the authoritative inputs.
                    source_float = model_float = mask = None

                    # Build the initial composite from the staged layers before
                    # any new separated layer or metadata becomes visible.
                    recombine_progress = (
                        _PhaseProgress(progress_bar, _RECOMBINE_PROGRESS_SPAN) if progress_bar is not None else None
                    )
                    composite_result = self._recombine_into_transaction(
                        staged_starless,
                        staged_stars,
                        negative_base_path=staged_starless,
                        composite_destination=composite_dest,
                        transaction=transaction,
                        progress_bar=recombine_progress,
                    )
                    if composite_result is None:
                        return None

                    separation_signature = compute_separation_signature(
                        source_id=source_id,
                        mask_id=mask_id,
                        model_identity=model_identity,
                        **separation_options,
                    )
                    if not project.publish_separation(
                        starless_dest,
                        stars_dest,
                        signature=separation_signature,
                        model_identity=model_identity,
                        expected_revision=project_revision,
                        composite_path=composite_dest,
                        options=separation_options,
                        transaction=transaction,
                    ):
                        return None
                    self._clear_star_caches()
                    self.save_project()
            except CancelledError:
                return None
        finally:
            if self.app.activeOperation is op:
                self.app.activeOperation = self._session_operation
            if separation_progress is not None:
                op.removeObserver(separation_progress)
            del source_float, model_float, mask

        return (
            OutputFile(basename=starless_dest.name, path=str(starless_dest), operation="Starless"),
            OutputFile(basename=stars_dest.name, path=str(stars_dest), operation="Stars"),
        )

    def do_finish_stars(self, progress_bar: Optional[Any] = None) -> Optional[OutputFile]:
        """Build/reuse catalog layers and publish the derived finished-stars TIFF.

        Effect work is incremental: an unchanged catalog and Round/Glow layers are
        reused, raising the cutoff extends measurements only, and a Glow geometry
        change renders only Glow. Publication is atomic with the project record;
        cancellation or a stale project leaves the previous result untouched.
        """
        self.invalidate_if_star_effects_changed()
        project = self.project
        revision = project.processing_revision
        if not project.source_is_current():
            raise ValueError("Source image is not current or unavailable.")
        inputs = self._star_inputs()
        if inputs is None:
            if project.current_artifact_path(ROLE_SEPARATED_STARS) is None or project.separation_signature is None:
                raise ValueError("Separate stars before finishing the stars layer.")
            raise ValueError("A current sky mask is required to finish stars.")
        _, stars, mask, catalog_identity, source_id, mask_file = inputs
        separation_signature = project.separation_signature
        if separation_signature is None:
            raise ValueError("Separate stars before finishing the stars layer.")
        settings = project.get_settings()
        cutoff = settings.star_count_cutoff
        self._validate_star_cutoff(cutoff)
        self._validate_glow_count(settings.glow_star_count)
        round_identity = self._round_identity(catalog_identity, cutoff)
        finished_dest = project.artifact_path(ROLE_FINISHED_STARS, for_write=True)
        catalog_dest = project.artifact_path(ROLE_STAR_CATALOG, for_write=True)
        round_dest = project.artifact_path(ROLE_ROUND_DELTA, for_write=True)

        phase_progress = (
            _PhaseProgress(
                progress_bar,
                _STAR_FINISH_PROGRESS_SPAN,
                scale=_STAR_FINISH_PROGRESS_TOTAL,
            )
            if progress_bar is not None
            else None
        )

        def emit(unit: int, description: str, sub_fraction: float = 0.0) -> None:
            if phase_progress is not None:
                phase_progress(4, 0, unit, False, {"desc": description, "sub_fraction": sub_fraction})

        def catalog_progress(current: int, total: int, description: str) -> None:
            emit(0, description, current / total if total > 0 else 0.0)

        def round_progress(current: int, total: int, description: str) -> None:
            emit(1, description, current / total if total > 0 else 0.0)

        op = self._new_operation(FinishStars)
        self.app.activeOperation = op
        try:
            try:
                with ArtifactTransaction(self._job_cancel_check(project, revision)) as transaction:
                    catalog, catalog_dirty = self._ensure_catalog(
                        stars,
                        mask,
                        cutoff=cutoff,
                        identity=catalog_identity,
                        should_interrupt=op.shouldInterrupt,
                        progress_callback=catalog_progress,
                    )
                    if catalog is None or op.shouldInterrupt():
                        return None
                    inclusion_mask = self._ensure_inclusion_mask(
                        catalog,
                        cutoff=cutoff,
                        catalog_identity=catalog_identity,
                    )
                    emit(1, "Star catalog ready")

                    round_delta, round_dirty = self._ensure_round_delta(
                        stars,
                        mask,
                        catalog,
                        cutoff=cutoff,
                        identity=round_identity,
                        inclusion_mask=inclusion_mask,
                        should_interrupt=op.shouldInterrupt,
                        progress_callback=round_progress,
                    )
                    if round_delta is None or op.shouldInterrupt():
                        return None
                    emit(2, "Round Stars layer ready")

                    glow = self._ensure_glow(
                        stars,
                        mask,
                        catalog,
                        cutoff=cutoff,
                        inclusion_mask=inclusion_mask,
                        count=settings.glow_star_count,
                        radius_px=settings.star_glow_radius_px,
                        catalog_identity=catalog_identity,
                        should_interrupt=op.shouldInterrupt,
                    )
                    if glow is None or op.shouldInterrupt():
                        return None
                    emit(3, "Applying star glow...")

                    catalog_path = project.current_artifact_path(ROLE_STAR_CATALOG)
                    if catalog_dirty or catalog_path is None:
                        staged_catalog = transaction.stage(catalog_dest)
                        save_catalog(staged_catalog, catalog, identity=catalog_identity)
                        catalog_path = catalog_dest
                    round_path = project.current_artifact_path(ROLE_ROUND_DELTA)
                    if round_dirty or round_path is None:
                        staged_round = transaction.stage(round_dest)
                        save_round_delta(staged_round, round_delta, identity=round_identity)
                        round_path = round_dest

                    finished_path = op.finish(
                        stars,
                        settings,
                        catalog=catalog,
                        inclusion_mask=inclusion_mask,
                        round_delta=round_delta,
                        glow=glow,
                        output_path=finished_dest,
                        artifacts=transaction,
                    )
                    if finished_path is None or op.shouldInterrupt() or self._request_is_stale(project, revision):
                        return None
                    if not project.publish_star_effects(
                        catalog_path=catalog_path,
                        round_delta_path=round_path,
                        finished_stars_path=finished_path,
                        separation_signature=separation_signature,
                        expected_revision=revision,
                        catalog_identity=catalog_identity,
                        round_identity=round_identity,
                        star_effect_version=STAR_EFFECT_VERSION,
                        settings=settings,
                        catalog_options={
                            "analysis_version": STAR_ANALYSIS_VERSION,
                            "catalog_version": STAR_CATALOG_VERSION,
                            "source_id": source_id,
                            "mask_file": mask_file,
                            "cutoff": cutoff,
                        },
                        round_options={"cutoff": cutoff},
                        transaction=transaction,
                    ):
                        return None
                    self._catalog_dirty = False
                    self._round_delta_dirty = False
                    self.save_project()
                    try:
                        self._build_reduced_preview(
                            StarFinishState(
                                catalog=catalog,
                                inclusion_mask=inclusion_mask,
                                round_delta=round_delta,
                                glow=glow,
                                cutoff=cutoff,
                                glow_star_count=settings.glow_star_count,
                                glow_radius_px=float(settings.star_glow_radius_px),
                                identity=f"{catalog_identity}|cutoff={cutoff}",
                            ),
                            stars,
                        )
                    except Exception as error:  # preview cache must not invalidate published effects
                        logger.warning("Could not build reduced star preview: %s", error)
                        self._reduced_preview = None
            except CancelledError:
                return None
        finally:
            if self.app.activeOperation is op:
                self.app.activeOperation = self._session_operation
            del stars, mask

        if progress_bar is not None:
            # Publication is complete; only now may the shared task report done.
            final_increment = _STAR_FINISH_PROGRESS_TOTAL - (phase_progress.reported if phase_progress else 0)
            if final_increment > 0:
                progress_bar(
                    _STAR_FINISH_PROGRESS_TOTAL,
                    final_increment,
                    _STAR_FINISH_PROGRESS_TOTAL,
                    True,
                    {"desc": "Star finishing complete."},
                )

        return OutputFile(
            basename=finished_dest.name,
            path=str(finished_dest),
            operation="Finished Stars",
        )

    def do_recombine(self, *, progress_bar: Optional[Any] = None) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Execute layer recombination and write internal composite artifact.

        progress_bar observes the operation on its native job scale, or on the
        shared separation scale when supplied by do_separate_stars.
        """
        if any(
            (
                self.invalidate_if_graxpert_changed(),
                self.invalidate_if_starless_filter_changed(),
                self.invalidate_if_star_effects_changed(),
            )
        ):
            return None
        project = self.project
        if not project.source_is_current():
            return None
        if project.current_artifact_path(ROLE_SEPARATED_STARS) is None:
            return None
        inputs = self._star_inputs()
        if inputs is None:
            return None
        _, stars, _, _, _, _ = inputs
        state = self.get_star_finish_state(_inputs=inputs)
        if state is None:
            return None
        if self._catalog_dirty or self._round_delta_dirty:
            # Persist repaired or newly extended endpoints even when stale
            # artifact records still exist, so reopening skips analysis.
            if self.do_finish_stars(progress_bar=progress_bar) is None:
                return None
            project = self.project
            inputs = self._star_inputs()
            if inputs is None:
                return None
            _, stars, _, _, _, _ = inputs
            state = self.get_star_finish_state(_inputs=inputs)
            if state is None:
                return None
        revision = project.processing_revision
        separation_signature = project.separation_signature
        separated_starless_path = project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        separated_stars_path = project.current_artifact_path(ROLE_SEPARATED_STARS)
        if separated_starless_path is None or separated_stars_path is None:
            return None
        settings = project.get_settings()
        finished_stars = compose_star_layer(
            stars,
            state.catalog,
            state.round_delta,
            state.glow,
            settings,
            inclusion_mask=state.inclusion_mask,
        )
        # A current finished starless plate supersedes the separated plate for the
        # composite; the signed correction always derives from the separated plate.
        starless_path = project.current_artifact_path(ROLE_FINISHED_STARLESS) or separated_starless_path

        composite_dest = project.artifact_path(ROLE_FINISHED_COMPOSITE, for_write=True)
        try:
            with ArtifactTransaction(self._job_cancel_check(project, revision)) as transaction:
                result = self._recombine_into_transaction(
                    starless_path,
                    separated_stars_path,
                    composite_destination=composite_dest,
                    transaction=transaction,
                    progress_bar=progress_bar,
                    negative_base_path=separated_starless_path,
                    finished_stars=finished_stars,
                )
                if result is None:
                    # Stale after a concurrent invalidation; keep the last valid composite.
                    return None
                if not project.record_artifact(
                    ROLE_FINISHED_COMPOSITE,
                    composite_dest,
                    options={"separation_signature": separation_signature},
                    expected_revision=revision,
                    expected_separation_signature=separation_signature,
                    transaction=transaction,
                ):
                    return None
                self.save_project()
                try:
                    self._build_reduced_preview(state, stars)
                except Exception as error:  # preview cache must not invalidate the composite
                    logger.warning("Could not refresh reduced star preview: %s", error)
                    self._reduced_preview = None
        except CancelledError:
            return None
        return result

    def do_denoise_starless(self, progress_bar: Optional[Any] = None) -> Optional[OutputFile]:
        """Finish the separated starless plate with the current denoise and sharpen settings.

        A full-strength GraXpert endpoint is computed once per separation/model
        identity and cached. Strength, scope, Structure and Detail then reuse that
        endpoint, so their controls never rerun inference. Each run starts from the
        separated plate plus the cached endpoint, applies the denoise blend, then
        applies the bounded two-scale enhancement. Zero amounts remain exact identity.
        """
        self.invalidate_if_starless_filter_changed()
        self.invalidate_if_graxpert_changed()
        project = self.project
        revision = project.processing_revision
        if not project.source_is_current():
            raise ValueError("Source image is not current or unavailable.")
        separated_path = project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        separation_signature = project.separation_signature
        if separated_path is None or separation_signature is None:
            raise ValueError("Separate stars before finishing the starless layer.")

        settings = project.get_settings()
        strength = settings.denoise_strength
        scope = settings.denoise_scope
        structure = settings.structure_amount
        detail = settings.detail_amount
        if not np.isfinite(strength) or not 0 <= strength <= PERCENT_SCALE:
            raise ValueError(f"Denoise strength must be in range [0.0, 100.0], got {strength}")
        if scope not in (SCOPE_SKY_ONLY, SCOPE_WHOLE_IMAGE):
            raise ValueError(f"Unknown denoise scope '{scope}'.")
        self._validate_sharpen_amounts(structure, detail)

        mask: Optional[np.ndarray] = None
        if (scope == SCOPE_SKY_ONLY and strength > 0) or structure > 0 or detail > 0:
            mask = self.get_current_mask()
            if mask is None:
                raise ValueError("Sky-only finishing requires a current sky mask.")

        model_identity = graxpert_model_identity()
        endpoint_signature = compute_denoise_endpoint_signature(separation_signature, model_identity)
        endpoint_options = {
            "separation_signature": separation_signature,
            "denoise_signature": endpoint_signature,
        }
        endpoint_path = project.current_artifact_path(ROLE_DENOISED_STARLESS, options=endpoint_options)
        finished_dest = project.artifact_path(ROLE_FINISHED_STARLESS, for_write=True)
        will_sharpen = structure > 0 or detail > 0

        base = imread(separated_path, to_rgb=True, as_float=True)
        denoised: Optional[np.ndarray] = None
        endpoint_dest: Optional[Path] = None
        op: Optional[GraXpertDenoise] = None
        try:
            try:
                with ArtifactTransaction(self._job_cancel_check(project, revision)) as transaction:
                    if strength > 0 and endpoint_path is None:
                        policy = resolve_graxpert_runtime_policy()
                        session = self._graxpert_session_for(policy)
                        endpoint_dest = project.artifact_path(ROLE_DENOISED_STARLESS, for_write=True)
                        op = self._new_operation(GraXpertDenoise)
                        inference_progress = (
                            _PhaseProgress(
                                progress_bar,
                                _STARLESS_DENOISE_PROGRESS_SPAN if will_sharpen else (0, _STARLESS_NO_PHASE_PROGRESS),
                                scale=_STARLESS_PROGRESS_TOTAL,
                            )
                            if progress_bar is not None
                            else None
                        )
                        if inference_progress is not None:
                            op.addObserver(inference_progress)
                        self.app.activeOperation = op
                        try:
                            inference = op.denoise(
                                base,
                                session=session,
                                settings=settings,
                                bit_depth=INTERMEDIATE_BIT_DEPTH,
                                output_path=endpoint_dest,
                                artifacts=transaction,
                            )
                        finally:
                            if self.app.activeOperation is op:
                                self.app.activeOperation = self._session_operation
                            if inference_progress is not None:
                                op.removeObserver(inference_progress)
                        if inference is None or op.shouldInterrupt():
                            return None
                        denoised = inference[0]
                    elif strength > 0:
                        assert endpoint_path is not None
                        denoised = imread(endpoint_path, to_rgb=True, as_float=True)
                        if progress_bar is not None:
                            cached_progress = 90 if will_sharpen else _STARLESS_NO_PHASE_PROGRESS
                            progress_bar(
                                _STARLESS_PROGRESS_TOTAL,
                                cached_progress,
                                cached_progress,
                                False,
                                {"desc": "Using cached denoise endpoint."},
                            )

                    if strength == 0:
                        finished = base
                    else:
                        assert denoised is not None
                        finished = blend_denoise(base, denoised, mask, strength, scope)

                    if will_sharpen:
                        assert mask is not None
                        sharpen_op = self._new_operation(SharpenStarless)
                        sharpen_progress = (
                            _PhaseProgress(
                                progress_bar,
                                _STARLESS_SHARPEN_PROGRESS_SPAN if strength > 0 else (0, _STARLESS_NO_PHASE_PROGRESS),
                                scale=_STARLESS_PROGRESS_TOTAL,
                            )
                            if progress_bar is not None
                            else None
                        )
                        if sharpen_progress is not None:
                            sharpen_op.addObserver(sharpen_progress)
                        self.app.activeOperation = sharpen_op
                        try:
                            sharpened = sharpen_op.sharpen(
                                finished,
                                mask,
                                structure_amount=structure,
                                detail_amount=detail,
                            )
                        finally:
                            if self.app.activeOperation is sharpen_op:
                                self.app.activeOperation = self._session_operation
                            if sharpen_progress is not None:
                                sharpen_op.removeObserver(sharpen_progress)
                        if sharpened is None:
                            return None
                        finished = sharpened

                    staged_finished = transaction.stage(finished_dest)
                    written = imwrite(
                        staged_finished,
                        finished,
                        convertBGR=True,
                        bit_depth=INTERMEDIATE_BIT_DEPTH,
                        quality=settings.jpeg_quality,
                        optimize=settings.jpeg_optimize,
                        compression=settings.tiff_deflate_compression,
                    )
                    if written != staged_finished:
                        written.unlink(missing_ok=True)
                        raise OSError("Finished starless staging path changed unexpectedly; nothing was published.")
                    if not project.publish_denoise_results(
                        finished_dest,
                        separation_signature=separation_signature,
                        expected_revision=revision,
                        strength=strength,
                        scope=scope,
                        structure_amount=structure,
                        detail_amount=detail,
                        starless_filter_version=STARLESS_FILTER_VERSION,
                        endpoint_path=endpoint_dest,
                        endpoint_signature=endpoint_signature,
                        model_identity=model_identity,
                        transaction=transaction,
                    ):
                        return None
                    self.save_project()
            except CancelledError:
                return None
        finally:
            del base, denoised

        if progress_bar is not None:
            has_progress = strength > 0 or will_sharpen
            progress_bar(
                _STARLESS_PROGRESS_TOTAL,
                1 if has_progress else _STARLESS_PROGRESS_TOTAL,
                _STARLESS_PROGRESS_TOTAL,
                True,
                {"desc": "Starless finishing complete."},
            )
        return OutputFile(
            basename=finished_dest.name,
            path=str(finished_dest),
            operation="Finished Starless",
        )

    @staticmethod
    def _validate_sharpen_amounts(structure: float, detail: float) -> None:
        """Validate persisted Structure/Detail values before any expensive work."""
        for label, amount in (("Structure", structure), ("Detail", detail)):
            if not np.isfinite(amount) or not 0 <= amount <= PERCENT_SCALE:
                raise ValueError(f"{label} amount must be in range [0.0, 100.0], got {amount}")


__all__ = ["FinishWorkflow", "STAR_PREVIEW_LAYERS", "StarFinishState", "StarRefreshAction"]
