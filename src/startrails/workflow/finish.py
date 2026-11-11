"""Finish workflow managing source image I/O, layer separation, and export."""

from __future__ import annotations

from pathlib import Path
from collections import OrderedDict
from concurrent.futures import CancelledError
import shutil
from typing import TYPE_CHECKING, Any, Callable, Dict, Final, List, Optional, Sequence, Tuple, Union

import numpy as np

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.file import InputFile, OutputFile
from startrails.lib.finish.composition import (
    blend_denoise,
    compute_denoise_endpoint_signature,
)
from startrails.lib.finish.defaults import (
    INTERMEDIATE_BIT_DEPTH,
    PERCENT_SCALE,
    ROLE_DENOISE_ENDPOINT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    ROLE_UNMASKED_STARLESS,
    SCOPE_SKY_ONLY,
    SCOPE_WHOLE_IMAGE,
    SUPPORTED_CHANNELS,
    FinishSettings,
)
from startrails.lib.finish.graxpert import (
    GRAXPERT_MODEL_RELATIVE_PATH,
    graxpert_model_identity,
)
from startrails.lib.finish.nox import (
    MAX_STRIDE,
    MIN_STRIDE,
    NOX_MODEL_RELATIVE_PATH,
    NoxSession,
    apply_radial_chroma_postfilter,
    nox_model_identity,
    resolve_nox_device,
    validate_separation_stride,
)
from startrails.lib.finish.separation import compute_separation_signature
from startrails.lib.finish.starless_filters import STARLESS_FILTER_VERSION
from startrails.lib.finish.graxpert_runtime import GraXpertSession, resolve_graxpert_device
from startrails.lib.image_io import imread, imwrite
from startrails.lib.project_finish import LAYER_EXPORT_SUFFIXES, FinishProject
from startrails.op.finish.graxpert_denoise import GraXpertDenoise
from startrails.op.finish.recombine import Recombine
from startrails.op.finish.remove_stars import RemoveStars
from startrails.op.finish.separate_stars import SeparateStars
from startrails.op.finish.sharpen_starless import SharpenStarless
from startrails.paths import APPLICATION_DIR
from startrails.lib.signatures import read_file_identity
from startrails.workflow.base import Workflow
from startrails.workflow.masking import SkyMaskingWorkflowMixin

if TYPE_CHECKING:
    from startrails.app import App


# Shared scale for the separation task's phase progress. The view's progress
# updater and enqueue total must use the same value.
SEPARATION_PROGRESS_TOTAL: Final[int] = 100

# Phase spans on that scale (Nox inference dominates runtime).
_NOX_PROGRESS_SPAN = (0, 80)
_POSTFILTER_PROGRESS_SPAN = (80, 5)
_SEPARATION_PROGRESS_SPAN = (85, 15)

# Starless finishing reserves the last unit for publishing, so no inner
# operation can report the whole task complete before sharpening ends.
_STARLESS_PROGRESS_TOTAL: Final[int] = 100
_STARLESS_DENOISE_PROGRESS_SPAN = (0, 90)
_STARLESS_SHARPEN_PROGRESS_SPAN = (90, 9)
_STARLESS_NO_PHASE_PROGRESS = 99

# The interactive blend decodes the full-resolution starless plates on every
# slider adjustment. Retaining the source, separated layers, endpoint, denoised
# and finished plates avoids disk I/O while file identities detect replacement.
_STARLESS_ARRAY_CACHE_MAX_ENTRIES: Final[int] = 6


class _DecodedArrayCache:
    """Bounded cache of read-only decoded arrays keyed by file identity."""

    def __init__(self, max_entries: int = _STARLESS_ARRAY_CACHE_MAX_ENTRIES):
        self._max_entries = max_entries
        self._entries: "OrderedDict[Tuple[str, int, int], np.ndarray]" = OrderedDict()

    @staticmethod
    def _key(path: Path) -> Optional[Tuple[str, int, int]]:
        try:
            identity = read_file_identity(path)
        except OSError:
            return None
        return identity.path, identity.size, identity.mtime_ns

    def get(self, path: Path) -> Optional[np.ndarray]:
        key = self._key(path)
        if key is None:
            return None
        array = self._entries.get(key)
        if array is not None:
            self._entries.move_to_end(key)
        return array

    def put(self, path: Path, array: np.ndarray) -> np.ndarray:
        key = self._key(path)
        if key is not None:
            self._entries[key] = array
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        array.flags.writeable = False
        return array

    def clear(self) -> None:
        self._entries.clear()


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


class FinishWorkflow(Workflow, SkyMaskingWorkflowMixin):
    """Workflow controller managing Finish mode project state, operations, and exports."""

    mode_name: str = "finish"

    def __init__(self, app: App):
        super().__init__(app)
        self._project = app.project
        self._nox_session: Optional[NoxSession] = None
        self._nox_session_key: Optional[str] = None
        self._graxpert_session: Optional[GraXpertSession] = None
        self._graxpert_session_key: Optional[str] = None
        self._starless_arrays = _DecodedArrayCache()

    @property
    def project(self) -> FinishProject:
        """The active FinishProject managed by this workflow."""
        return self._project

    def _clear_starless_array_cache(self) -> None:
        """Drop decoded plates whenever a producing separation/denoise job changes."""
        self._starless_arrays.clear()

    def _load_starless_array(self, path: Path) -> np.ndarray:
        """Return a read-only decoded plate, reusing the cached array when unchanged."""
        cached = self._starless_arrays.get(path)
        if cached is not None:
            return cached
        return self._starless_arrays.put(path, imread(path, to_rgb=True, as_float=True))

    @staticmethod
    def _uses_finished_starless_plate(settings: FinishSettings) -> bool:
        """Return True when post-denoise sharpening is active on top of denoising."""
        return bool(settings.enable_starless_denoise and settings.enable_starless_sharpen)

    def active_starless_role(self, settings: Optional[FinishSettings] = None) -> str:
        """Return the stored starless role selected by the current toggles.

        Sharpening is post-denoise only: when denoise is disabled, both preview
        and recombine fall back to the separated starless plate regardless of
        the remembered post-denoise sharpen preference.
        """
        settings = self.project.get_settings() if settings is None else settings
        if not settings.enable_starless_denoise:
            return ROLE_SEPARATED_STARLESS
        if settings.enable_starless_sharpen:
            return ROLE_FINISHED_STARLESS
        return ROLE_DENOISED_STARLESS

    def _starless_plate_path(self, settings: FinishSettings, separated_starless_path: Path) -> Path:
        """Resolve the best current plate for the toggles, falling back safely."""
        project = self.project
        if not settings.enable_starless_denoise:
            return separated_starless_path
        if settings.enable_starless_sharpen:
            finished = project.current_artifact_path(ROLE_FINISHED_STARLESS)
            if finished is not None:
                return finished
        denoised = project.current_artifact_path(ROLE_DENOISED_STARLESS)
        if denoised is not None:
            return denoised
        return separated_starless_path

    def _resolved_starless_role(self, settings: FinishSettings, separated_starless_path: Path) -> str:
        """Identify which stored role backs the plate selected by the toggles."""
        plate = self._starless_plate_path(settings, separated_starless_path)
        project = self.project
        if plate == project.current_artifact_path(ROLE_FINISHED_STARLESS):
            return ROLE_FINISHED_STARLESS
        if plate == project.current_artifact_path(ROLE_DENOISED_STARLESS):
            return ROLE_DENOISED_STARLESS
        return ROLE_SEPARATED_STARLESS

    def save_project(self) -> None:
        """Do not let a stale workflow persist a project that replaced it."""
        if self._project is self.app.project:
            super().save_project()

    def invalidate_if_separation_changed(self) -> bool:
        """Invalidate separation when its saved inputs no longer match current project state."""
        status = self.get_star_removal_status()
        current_identity = nox_model_identity() if status.get("configured") else None
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
            if options is None or "stride" not in options or "chroma_postfilter" not in options:
                # A saved signature without its producing options cannot be
                # revalidated; treat it as an invalid cache rather than guessing.
                expected_signature = None
            else:
                try:
                    expected_signature = compute_separation_signature(
                        source_id=project.source_file.sourceId,
                        mask_id=str(mask_record.get("file", "")),
                        model_identity=current_identity,
                        stride=int(options["stride"]),
                        chroma_postfilter=bool(options["chroma_postfilter"]),
                        mask_feather_radius_px=project.mask_feather_radius_px,
                    )
                except (TypeError, ValueError):
                    expected_signature = None
        if expected_signature == project.separation_signature and project.separation_model_identity == current_identity:
            return False
        self._clear_starless_array_cache()
        self.project.invalidate_results()
        self.save_project()
        return True

    invalidate_if_nox_changed = invalidate_if_separation_changed

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
            (ROLE_DENOISED_STARLESS, "Denoised Starless"),
            (ROLE_FINISHED_STARLESS, "Finished Starless"),
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
        self._clear_starless_array_cache()
        self.project.set_source_image(path)
        self.save_project()

    def do_replace_source(self, path: Union[str, Path]) -> None:
        """Replace the current source image with a new one and persist project state."""
        self._clear_starless_array_cache()
        self.project.set_source_image(path)
        self.save_project()

    def do_clear_source(self) -> None:
        """Remove the selected source from the project, retaining its files on disk."""
        self._clear_starless_array_cache()
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
        self._clear_starless_array_cache()
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
        record_options = project.artifact_manifest.get(ROLE_FINISHED_COMPOSITE, {}).get("options", {})
        if "star_amount" in record_options and (
            record_options.get("star_amount") != settings.star_amount
            or ("star_threshold" in record_options and record_options.get("star_threshold") != settings.star_threshold)
            or record_options.get("blend_mode") != settings.blend_mode
            or record_options.get("enable_starless_denoise") != settings.enable_starless_denoise
            or record_options.get("enable_starless_sharpen") != settings.enable_starless_sharpen
        ):
            # Never export a composite encoded from previous star settings or
            # built from a different starless plate after toggling a stage.
            raise ValueError("Composite does not match the current star settings; recombine before exporting.")
        if "starless_role" in record_options:
            separated_starless_path = project.current_artifact_path(ROLE_SEPARATED_STARLESS)
            if separated_starless_path is None or record_options["starless_role"] != self._resolved_starless_role(
                settings, separated_starless_path
            ):
                raise ValueError("Composite does not match the current starless layer; recombine before exporting.")
            if project.current_artifact_path(record_options["starless_role"]) is None:
                raise ValueError("Composite starless layer is no longer current; recombine before exporting.")
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

    def _validate_layer_export_source(self) -> tuple[FinishProject, int, int]:
        """Validate the shared source prerequisites for layer exports."""
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
        return project, revision, depth

    @staticmethod
    def _validate_layer_export_options(
        role: str,
        record_options: Dict[str, Any],
        settings: FinishSettings,
    ) -> None:
        """Reject a stored layer that was built from different visible settings."""
        if role == ROLE_DENOISED_STARLESS:
            expected = {
                "denoise_strength": settings.denoise_strength,
                "denoise_scope": settings.denoise_scope,
            }
            message = "Denoised starless layer does not match the current denoise settings; rebuild it."
        elif role == ROLE_FINISHED_STARLESS:
            expected = {
                "denoise_strength": settings.denoise_strength,
                "denoise_scope": settings.denoise_scope,
                "structure_amount": settings.structure_amount,
                "detail_amount": settings.detail_amount,
            }
            message = "Finished starless layer does not match the current starless settings; rebuild it."
        else:
            return
        if any(key in record_options and record_options.get(key) != value for key, value in expected.items()):
            raise ValueError(message)

    def do_export_layer(
        self,
        role: str,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Export one current layer at full resolution using source-matching format and depth."""
        if role == ROLE_FINISHED_COMPOSITE:
            return self.do_export_composite(output_path=output_path)
        if role not in LAYER_EXPORT_SUFFIXES:
            raise ValueError(f"Unsupported layer export role: {role}")
        self.invalidate_if_graxpert_changed()
        self.invalidate_if_starless_filter_changed()
        project, revision, depth = self._validate_layer_export_source()
        separation_signature = project.separation_signature
        settings = project.get_settings()
        target_path = (
            Path(output_path).resolve() if output_path is not None else project.get_default_layer_export_path(role)
        )
        project.validate_export_path(target_path)
        artifact_path = project.current_artifact_path(role)
        if artifact_path is None:
            raise ValueError(f"No current '{role}' layer to export.")
        record_options = project.artifact_manifest.get(role, {}).get("options", {})
        self._validate_layer_export_options(role, record_options, settings)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        img = self._load_starless_array(artifact_path)

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
                if not project.commit_layer_export(
                    transaction,
                    expected_revision=revision,
                    expected_separation_signature=separation_signature,
                ):
                    raise ValueError("Project changed while saving; the layer export was not published.")
        except CancelledError:
            raise ValueError("Layer export was cancelled; no output was published.") from None
        self.save_project()
        return target_path

    def do_export_layers(
        self,
        output_dir: Optional[Union[str, Path]] = None,
        *,
        roles: Optional[Sequence[str]] = None,
        progress_bar: Optional[Any] = None,
    ) -> Dict[str, Path]:
        """Export the active separated/finished layers to one directory atomically."""
        self.invalidate_if_graxpert_changed()
        self.invalidate_if_starless_filter_changed()
        project, revision, depth = self._validate_layer_export_source()
        separation_signature = project.separation_signature
        if (
            project.current_artifact_path(ROLE_SEPARATED_STARLESS) is None
            or project.current_artifact_path(ROLE_SEPARATED_STARS) is None
        ):
            raise ValueError("Separate stars before exporting layers.")

        settings = project.get_settings()
        base_dir = Path(output_dir).resolve() if output_dir is not None else project.get_output_dir()
        if roles is None:
            selected_roles: List[str] = [ROLE_SEPARATED_STARLESS, ROLE_SEPARATED_STARS]
            if settings.enable_starless_denoise and project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None:
                selected_roles.append(ROLE_DENOISED_STARLESS)
            if (
                self._uses_finished_starless_plate(settings)
                and project.current_artifact_path(ROLE_FINISHED_STARLESS) is not None
            ):
                selected_roles.append(ROLE_FINISHED_STARLESS)
        else:
            selected_roles = list(roles)

        exports: Dict[str, tuple[Path, Path]] = {}
        for role in selected_roles:
            if role not in LAYER_EXPORT_SUFFIXES:
                raise ValueError(f"Unsupported layer export role: {role}")
            artifact_path = project.current_artifact_path(role)
            if artifact_path is None:
                raise ValueError(f"No current '{role}' layer to export.")
            record_options = project.artifact_manifest.get(role, {}).get("options", {})
            self._validate_layer_export_options(role, record_options, settings)
            destination = project.get_default_layer_export_path(role, base_dir)
            project.validate_export_path(destination)
            exports[role] = (artifact_path, destination)

        total = len(exports)
        results: Dict[str, Path] = {}
        try:
            with ArtifactTransaction(self._job_cancel_check(project, revision)) as transaction:
                for index, (role, (artifact_path, destination)) in enumerate(exports.items(), start=1):
                    img = self._load_starless_array(artifact_path)
                    staged_path = transaction.stage(destination)
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
                    results[role] = destination
                    if progress_bar is not None:
                        progress_bar(
                            total,
                            1,
                            index,
                            index == total,
                            {"desc": f"Exported {LAYER_EXPORT_SUFFIXES[role].lstrip('_')} layer."},
                        )
                if not project.commit_layer_export(
                    transaction,
                    expected_revision=revision,
                    expected_separation_signature=separation_signature,
                ):
                    raise ValueError("Project changed while saving; layer exports were not published.")
        except CancelledError:
            raise ValueError("Layer exports were cancelled; no outputs were published.") from None
        self.save_project()
        return results

    # -------------------------------------------------------------------------
    # Dependency Lifecycle & Operational Adapters (Nox & GraXpert)
    # -------------------------------------------------------------------------

    def get_star_removal_status(self) -> dict:
        """Return runtime device selection and model readiness for Nox star removal."""
        model_path = APPLICATION_DIR / "models" / NOX_MODEL_RELATIVE_PATH
        try:
            model_ready = model_path.is_file()
            setup_error = None if model_ready else f"Star removal model not found: {model_path}"
        except OSError as error:
            model_ready = False
            setup_error = str(error)
        try:
            device = str(resolve_nox_device())
        except (RuntimeError, OSError, ValueError) as error:
            device = "cpu"
            if setup_error is None:
                setup_error = str(error)
        session = self._nox_session
        return {
            "configured": model_ready,
            "model_ready": model_ready,
            "model_path": str(model_path),
            "device": device,
            "execution_device": session.execution_device if session is not None else None,
            "fallback_reason": session.fallback_reason if session is not None else None,
            "setup_error": setup_error,
        }

    def get_graxpert_status(self) -> dict:
        """Return runtime device selection and model readiness for GraXpert denoising."""
        model_path = APPLICATION_DIR / "models" / GRAXPERT_MODEL_RELATIVE_PATH
        try:
            model_ready = model_path.is_file()
            setup_error = None if model_ready else f"GraXpert model not found: {model_path}"
        except OSError as error:
            model_ready = False
            setup_error = str(error)
        try:
            device = str(resolve_graxpert_device())
        except (RuntimeError, OSError, ValueError) as error:
            device = "cpu"
            if setup_error is None:
                setup_error = str(error)
        session = self._graxpert_session
        session_matches_device = session is not None and str(session.configured_device) == device
        return {
            "configured": model_ready,
            "model_ready": model_ready,
            "model_path": str(model_path),
            "device": device,
            "execution_device": session.execution_device if session_matches_device else None,
            "fallback_reason": session.fallback_reason if session_matches_device else None,
            "setup_error": setup_error,
        }

    def invalidate_if_graxpert_changed(self) -> bool:
        """Invalidate denoise outputs when the pinned GraXpert model identity changed."""
        project = self.project
        if project.denoise_signature is None:
            return False
        if project.denoise_model_identity == graxpert_model_identity():
            return False
        self._clear_starless_array_cache()
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

    def _nox_session_for(self) -> NoxSession:
        """Reuse one loaded Nox inference session for the pinned model identity."""
        key = nox_model_identity()
        session = self._nox_session
        if session is not None and self._nox_session_key == key:
            return session
        session = NoxSession()
        self._nox_session = session
        self._nox_session_key = key
        return session

    def _graxpert_session_for(self) -> GraXpertSession:
        """Reuse one loaded GraXpert inference session for the pinned model identity."""
        key = graxpert_model_identity()
        session = self._graxpert_session
        if session is not None and self._graxpert_session_key == key:
            return session
        session = GraXpertSession()
        self._graxpert_session = session
        self._graxpert_session_key = key
        return session

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

    @staticmethod
    def _validate_model_output(model: np.ndarray, dimensions: Tuple[int, int]) -> None:
        """Reject a corrupt star removal result before downstream separation."""
        if model.ndim != 3 or model.shape[2] != SUPPORTED_CHANNELS or model.shape[:2] != dimensions:
            raise ValueError(f"Star removal output shape {model.shape} does not match source dimensions {dimensions}.")
        if not np.isfinite(model).all():
            raise ValueError("Star removal output contains non-finite values.")

    def _recombine_into_transaction(
        self,
        starless_path: Path,
        stars_path: Path,
        *,
        negative_base_path: Path,
        composite_destination: Path,
        transaction: ArtifactTransaction,
        settings: FinishSettings,
        progress_bar: Optional[Any] = None,
    ) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Recombine the given layers into a staged composite without publishing it.

        The signed negative correction always derives from the separated starless
        plate passed as negative_base_path, never from a subsequently finished
        plate. starless_path controls the visible base and is the same separated
        plate when no starless finishing has run. ``settings`` is the caller's
        snapshot taken before the job starts, so mid-flight project edits cannot
        change the recombination contract.
        """
        project = self.project
        source_arr = self._load_starless_array(Path(project.source_file.path))
        starless_arr = self._load_starless_array(starless_path)
        stars_arr = self._load_starless_array(stars_path)

        if negative_base_path == starless_path:
            negative_base_arr = starless_arr
        else:
            negative_base_arr = self._load_starless_array(negative_base_path)

        # Cached plates are read-only; derive the signed correction into a new
        # array instead of mutating the source buffer in place.
        neg_residual = np.minimum(source_arr - negative_base_arr, 0.0).astype(np.float32, copy=False)

        op = self._new_operation(Recombine)
        if progress_bar is not None:
            op.addObserver(progress_bar)
        self.app.activeOperation = op
        try:
            result = op.recombine(
                starless_arr,
                stars_arr,
                neg_residual,
                settings,
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

    def do_separate_stars(
        self,
        *,
        stride: Optional[int] = None,
        chroma_postfilter: Optional[bool] = None,
        chunk_rows: int = 512,
        progress_bar: Optional[Any] = None,
    ) -> Optional[Tuple[OutputFile, OutputFile]]:
        """Separate stars from sky background using Nox and sky protection mask.

        progress_bar, when given, receives each phase's progress mapped onto the
        shared SEPARATION_PROGRESS_TOTAL scale.
        """
        project = self.project
        stride = project.nox_stride if stride is None else stride
        validate_separation_stride(stride)
        chroma_postfilter = project.chroma_postfilter if chroma_postfilter is None else chroma_postfilter
        if type(chroma_postfilter) is not bool:
            raise ValueError(f"chroma_postfilter must be a bool, got {chroma_postfilter!r}")
        project_revision = project.processing_revision
        if not project.source_is_current():
            raise ValueError("Source image is not current or unavailable.")
        settings = project.get_settings()
        dims = project.get_source_dimensions()
        if dims is None or dims[0] <= 0 or dims[1] <= 0:
            actual_dims = f"{dims[1]}x{dims[0]}" if dims else "0x0"
            raise ValueError(f"Source image dimensions ({actual_dims}) are invalid for star separation.")

        mask = self.get_current_mask()
        if mask is None:
            raise ValueError("A sky mask is required to separate stars.")
        feather_radius_px = project.mask_feather_radius_px
        mask = MaskHandler.feather_mask(mask, feather_radius_px)

        source_id = project.source_file.sourceId
        mask_record = project.artifact_manifest.get(ROLE_SKY_MASK, {})
        mask_id = str(mask_record.get("file", ""))

        star_removal_status = self.get_star_removal_status()
        if not star_removal_status.get("configured", False):
            raise RuntimeError(
                star_removal_status.get("setup_error")
                or f"Star removal model is not available at {star_removal_status.get('model_path')}."
            )
        model_identity = nox_model_identity()

        source_path = Path(project.source_file.path)
        if progress_bar is not None:
            progress_bar(SEPARATION_PROGRESS_TOTAL, 0, 0, False, {"desc": "Loading source image..."})
        source_float = imread(source_path, to_rgb=True, as_float=True)
        unmasked_options = {
            "stride": stride,
            "model_identity": model_identity,
        }
        separation_options = {
            "stride": stride,
            "chroma_postfilter": chroma_postfilter,
            "mask_feather_radius_px": feather_radius_px,
        }

        unmasked_path = project.current_artifact_path(ROLE_UNMASKED_STARLESS, options=unmasked_options)
        raw_model_float: Optional[np.ndarray] = None
        if unmasked_path is None or not unmasked_path.is_file():
            nox_progress = _PhaseProgress(progress_bar, _NOX_PROGRESS_SPAN) if progress_bar is not None else None
            unmasked_dest = project.artifact_path(ROLE_UNMASKED_STARLESS, for_write=True)
            if progress_bar is not None and self._nox_session is None:
                progress_bar(SEPARATION_PROGRESS_TOTAL, 0, 0, False, {"desc": "Loading star removal model..."})
            session = self._nox_session_for()
            if progress_bar is not None:
                progress_bar(SEPARATION_PROGRESS_TOTAL, 0, 0, False, {"desc": "Removing stars..."})
            remove_op = self._new_operation(RemoveStars)
            if nox_progress is not None:
                remove_op.addObserver(nox_progress)
            self.app.activeOperation = remove_op
            try:
                try:
                    with ArtifactTransaction(self._job_cancel_check(project, project_revision)) as transaction:
                        remove_res = remove_op.remove_stars(
                            source_float,
                            session=session,
                            stride=stride,
                            settings=settings,
                            bit_depth=INTERMEDIATE_BIT_DEPTH,
                            output_path=unmasked_dest,
                            artifacts=transaction,
                        )
                        if (
                            remove_res is None
                            or remove_op.shouldInterrupt()
                            or project is not self.app.project
                            or project_revision != project.processing_revision
                            or not project.source_is_current()
                        ):
                            return None
                        raw_model_float = remove_res[0]
                        self._validate_model_output(raw_model_float, dims)
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
            finally:
                if self.app.activeOperation is remove_op:
                    self.app.activeOperation = self._session_operation
                if nox_progress is not None:
                    remove_op.removeObserver(nox_progress)
            unmasked_path = unmasked_dest
        elif progress_bar is not None:
            nox_span = _NOX_PROGRESS_SPAN[1]
            progress_bar(
                SEPARATION_PROGRESS_TOTAL,
                nox_span,
                nox_span,
                False,
                {"desc": "Using cached starless removal..."},
            )

        if raw_model_float is not None:
            model_float = raw_model_float
            raw_model_float = None
        else:
            if progress_bar is not None:
                progress_bar(
                    SEPARATION_PROGRESS_TOTAL,
                    0,
                    _NOX_PROGRESS_SPAN[1],
                    False,
                    {"desc": "Loading cached starless image..."},
                )
            model_float = imread(unmasked_path, to_rgb=True, as_float=True)

        if chroma_postfilter:
            postfilter_progress = (
                _PhaseProgress(progress_bar, _POSTFILTER_PROGRESS_SPAN) if progress_bar is not None else None
            )
            try:
                model_float, _ = apply_radial_chroma_postfilter(
                    source_float,
                    model_float,
                    progress_bar=postfilter_progress,
                    should_interrupt=self._job_cancel_check(project, project_revision),
                )
            except CancelledError:
                return None
        elif progress_bar is not None:
            postfilter_span = _POSTFILTER_PROGRESS_SPAN[1]
            progress_bar(
                SEPARATION_PROGRESS_TOTAL,
                postfilter_span,
                _SEPARATION_PROGRESS_SPAN[0],
                False,
                {"desc": "Preparing separated layers..."},
            )

        starless_dest = project.artifact_path(ROLE_SEPARATED_STARLESS, for_write=True)
        stars_dest = project.artifact_path(ROLE_SEPARATED_STARS, for_write=True)

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
                        settings=settings,
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

                    source_float = model_float = mask = None

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
                        options=separation_options,
                        transaction=transaction,
                    ):
                        return None
                    # New separated plates invalidate the cached endpoint and
                    # with it every decoded array this workflow retained.
                    self._clear_starless_array_cache()
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

    def do_recombine(self, *, progress_bar: Optional[Any] = None) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Recombine the single star layer with the current starless base.

        This is the worker boundary for interactive amount/mode updates and for
        full-resolution saving. It reads the separated positive stars and the
        current starless base, derives the signed correction from the separated
        starless plate, and publishes the composite transactionally using a
        snapshot of the current settings. Cancellation or a stale revision leaves
        the previous composite untouched.
        """
        if any(
            (
                self.invalidate_if_graxpert_changed(),
                self.invalidate_if_starless_filter_changed(),
            )
        ):
            return None
        project = self.project
        if not project.source_is_current():
            return None
        revision = project.processing_revision
        separation_signature = project.separation_signature
        separated_starless_path = project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        separated_stars_path = project.current_artifact_path(ROLE_SEPARATED_STARS)
        if separated_starless_path is None or separated_stars_path is None:
            return None
        settings = project.get_settings()

        # Refresh a missing starless plate from cached separation/endpoint data
        # before recombining. GraXpert inference is only reached when no
        # endpoint exists; changed sliders rebuild from the cached endpoint.
        will_sharpen = settings.structure_amount > 0.0 or settings.detail_amount > 0.0
        has_endpoint = project.current_artifact_path(ROLE_DENOISE_ENDPOINT) is not None
        has_denoised = project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None
        has_finished = project.current_artifact_path(ROLE_FINISHED_STARLESS) is not None
        needs_denoise = (
            settings.enable_starless_denoise
            and not has_denoised
            and (
                has_endpoint or (settings.denoise_strength == 0.0 and will_sharpen and settings.enable_starless_sharpen)
            )
            and self.get_current_mask() is not None
        )
        needs_sharpen = (
            self._uses_finished_starless_plate(settings)
            and will_sharpen
            and not has_finished
            and (has_denoised or has_endpoint or settings.denoise_strength == 0.0)
            and self.get_current_mask() is not None
        )
        if needs_denoise or needs_sharpen:
            if self.do_denoise_starless() is None:
                return None
            revision = project.processing_revision
            separation_signature = project.separation_signature
            settings = project.get_settings()
            separated_starless_path = project.current_artifact_path(ROLE_SEPARATED_STARLESS)
            separated_stars_path = project.current_artifact_path(ROLE_SEPARATED_STARS)
            if separated_starless_path is None or separated_stars_path is None:
                return None

        # The starless toggles select the stored plate used as the visible base;
        # the signed correction always derives from the separated plate.
        starless_path = self._starless_plate_path(settings, separated_starless_path)
        starless_role = self._resolved_starless_role(settings, separated_starless_path)

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
                    settings=settings,
                )
                if result is None:
                    # Stale after a concurrent invalidation; keep the last valid composite.
                    return None
                if not project.record_artifact(
                    ROLE_FINISHED_COMPOSITE,
                    composite_dest,
                    options={
                        "separation_signature": separation_signature,
                        "starless_role": starless_role,
                        "enable_starless_denoise": settings.enable_starless_denoise,
                        "enable_starless_sharpen": settings.enable_starless_sharpen,
                        "star_amount": settings.star_amount,
                        "star_threshold": settings.star_threshold,
                        "blend_mode": settings.blend_mode,
                    },
                    expected_revision=revision,
                    expected_separation_signature=separation_signature,
                    transaction=transaction,
                ):
                    return None
                self.save_project()
        except CancelledError:
            return None
        return result

    def do_denoise_starless(self, progress_bar: Optional[Any] = None) -> Optional[OutputFile]:
        """Apply denoise and sharpening independently to the separated starless plate.

        The internal full-strength GraXpert endpoint is computed once per
        separation/model identity. The user-blended denoised plate is rebuilt only
        when its settings or endpoint change, and the sharpened plate is rebuilt
        only when its inputs or amounts change. Either stored output can be reused
        while the other is refreshed, so Structure/Detail edits never re-blend and
        denoise edits never re-sharpen an untouched finished plate.
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
        denoise_enabled = bool(settings.enable_starless_denoise)
        scope = settings.denoise_scope
        structure = settings.structure_amount
        detail = settings.detail_amount
        will_sharpen = structure > 0 or detail > 0
        publish_finished = self._uses_finished_starless_plate(settings) or (denoise_enabled and will_sharpen)
        if not np.isfinite(strength) or not 0 <= strength <= PERCENT_SCALE:
            raise ValueError(f"Denoise strength must be in range [0.0, 100.0], got {strength}")
        if scope not in (SCOPE_SKY_ONLY, SCOPE_WHOLE_IMAGE):
            raise ValueError(f"Unknown denoise scope '{scope}'.")
        self._validate_sharpen_amounts(structure, detail)

        model_identity = graxpert_model_identity()
        endpoint_signature = compute_denoise_endpoint_signature(separation_signature, model_identity)
        endpoint_options = {
            "separation_signature": separation_signature,
            "denoise_signature": endpoint_signature,
        }
        denoised_options = {
            **endpoint_options,
            "denoise_strength": float(strength),
            "denoise_scope": scope,
        }
        finished_options = {
            **denoised_options,
            "structure_amount": float(structure),
            "detail_amount": float(detail),
            "starless_filter_version": STARLESS_FILTER_VERSION,
        }
        endpoint_path = (
            project.current_artifact_path(ROLE_DENOISE_ENDPOINT, options=endpoint_options)
            if denoise_enabled
            else None
        )
        denoised_path = (
            project.current_artifact_path(ROLE_DENOISED_STARLESS, options=denoised_options)
            if denoise_enabled
            else None
        )
        finished_path = (
            project.current_artifact_path(ROLE_FINISHED_STARLESS, options=finished_options)
            if publish_finished
            else None
        )

        denoised_dest = project.artifact_path(ROLE_DENOISED_STARLESS, for_write=True)
        finished_dest = project.artifact_path(ROLE_FINISHED_STARLESS, for_write=True)
        need_denoised = denoise_enabled and denoised_path is None
        need_finished = publish_finished and finished_path is None
        need_endpoint = need_denoised and strength > 0 and endpoint_path is None

        def active_output() -> OutputFile:
            active_role = self.active_starless_role(settings)
            if active_role == ROLE_FINISHED_STARLESS:
                path = project.current_artifact_path(ROLE_FINISHED_STARLESS) or finished_dest
                return OutputFile(basename=path.name, path=str(path), operation="Finished Starless")
            if active_role == ROLE_DENOISED_STARLESS:
                path = project.current_artifact_path(ROLE_DENOISED_STARLESS) or denoised_dest
                return OutputFile(basename=path.name, path=str(path), operation="Denoised Starless")
            return OutputFile(basename=separated_path.name, path=str(separated_path), operation="Starless")

        def report_complete() -> None:
            if progress_bar is None:
                return
            has_progress = denoise_enabled and (strength > 0 or will_sharpen)
            progress_bar(
                _STARLESS_PROGRESS_TOTAL,
                1 if has_progress else _STARLESS_PROGRESS_TOTAL,
                _STARLESS_PROGRESS_TOTAL,
                True,
                {"desc": "Starless finishing complete."},
            )

        cancel_check = self._job_cancel_check(project, revision)
        if cancel_check():
            return None

        if not need_denoised and not need_finished and not need_endpoint:
            report_complete()
            return active_output()

        mask: Optional[np.ndarray] = None
        if (scope == SCOPE_SKY_ONLY and need_denoised and strength > 0) or (will_sharpen and need_finished):
            mask = self.get_current_mask()
            if mask is None:
                raise ValueError("Sky-only finishing requires a current sky mask.")

        base: Optional[np.ndarray] = None
        denoised_arr: Optional[np.ndarray] = None
        endpoint_arr: Optional[np.ndarray] = None
        endpoint_dest: Optional[Path] = None
        op: Optional[GraXpertDenoise] = None
        try:
            try:
                with ArtifactTransaction(self._job_cancel_check(project, revision)) as transaction:

                    def stage_plate(destination: Path, array: np.ndarray) -> Path:
                        staged = transaction.stage(destination)
                        # Internal intermediate TIFFs skip deflate compression so
                        # interactive strength/amount updates write quickly; user
                        # exports apply settings.tiff_deflate_compression.
                        written = imwrite(
                            staged,
                            array,
                            convertBGR=True,
                            bit_depth=INTERMEDIATE_BIT_DEPTH,
                            compression=False,
                        )
                        if written != staged:
                            written.unlink(missing_ok=True)
                            raise OSError("Starless staging path changed unexpectedly; nothing was published.")
                        return staged

                    staged_denoised: Optional[Path] = None
                    if need_denoised:
                        base = self._load_starless_array(separated_path)
                        if strength == 0:
                            denoised_arr = base
                        elif need_endpoint:
                            session = self._graxpert_session_for()
                            endpoint_dest = project.artifact_path(ROLE_DENOISE_ENDPOINT, for_write=True)
                            op = self._new_operation(GraXpertDenoise)
                            inference_progress = (
                                _PhaseProgress(
                                    progress_bar,
                                    _STARLESS_DENOISE_PROGRESS_SPAN
                                    if will_sharpen
                                    else (0, _STARLESS_NO_PHASE_PROGRESS),
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
                            endpoint_arr = inference[0]
                            denoised_arr = blend_denoise(base, endpoint_arr, mask, strength, scope)
                        else:
                            assert endpoint_path is not None
                            endpoint_arr = self._load_starless_array(endpoint_path)
                            if progress_bar is not None:
                                cached_progress = 90 if will_sharpen else _STARLESS_NO_PHASE_PROGRESS
                                progress_bar(
                                    _STARLESS_PROGRESS_TOTAL,
                                    cached_progress,
                                    cached_progress,
                                    False,
                                    {"desc": "Applying denoise strength..."},
                                )
                            denoised_arr = blend_denoise(base, endpoint_arr, mask, strength, scope)
                        staged_denoised = stage_plate(denoised_dest, denoised_arr)
                    elif need_finished:
                        if denoise_enabled:
                            assert denoised_path is not None
                            denoised_arr = self._load_starless_array(denoised_path)
                            if progress_bar is not None and will_sharpen:
                                progress_bar(
                                    _STARLESS_PROGRESS_TOTAL,
                                    90,
                                    90,
                                    False,
                                    {"desc": "Using cached denoised starless."},
                                )
                        else:
                            denoised_arr = self._load_starless_array(separated_path)

                    if need_finished:
                        assert denoised_arr is not None
                        if will_sharpen:
                            assert mask is not None
                            sharpen_op = self._new_operation(SharpenStarless)
                            sharpen_progress = (
                                _PhaseProgress(
                                    progress_bar,
                                    _STARLESS_SHARPEN_PROGRESS_SPAN
                                    if (denoise_enabled and strength > 0)
                                    else (0, _STARLESS_NO_PHASE_PROGRESS),
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
                                    denoised_arr,
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
                            stage_plate(finished_dest, sharpened)
                        else:
                            copy_source = staged_denoised if staged_denoised is not None else denoised_path
                            if copy_source is not None and copy_source.is_file():
                                shutil.copyfile(copy_source, transaction.stage(finished_dest))
                            else:
                                stage_plate(finished_dest, denoised_arr)

                    if not project.publish_denoise_results(
                        denoised_dest if need_denoised else None,
                        separation_signature=separation_signature,
                        expected_revision=revision,
                        strength=strength,
                        scope=scope,
                        structure_amount=structure,
                        detail_amount=detail,
                        starless_filter_version=STARLESS_FILTER_VERSION,
                        finished_starless_path=finished_dest if need_finished else None,
                        endpoint_path=endpoint_dest,
                        endpoint_signature=endpoint_signature,
                        model_identity=model_identity,
                        transaction=transaction,
                    ):
                        return None
                    if need_denoised and denoised_arr is not None:
                        self._starless_arrays.put(denoised_dest, denoised_arr)
                    if endpoint_dest is not None and endpoint_arr is not None:
                        # The freshly computed endpoint is already decoded; cache
                        # it so the next blend skips reading it back.
                        self._starless_arrays.put(endpoint_dest, endpoint_arr)
                    self.save_project()
            except CancelledError:
                return None
        finally:
            del base, denoised_arr, endpoint_arr

        report_complete()
        return active_output()

    @staticmethod
    def _validate_sharpen_amounts(structure: float, detail: float) -> None:
        """Validate persisted Structure/Detail values before any expensive work."""
        for label, amount in (("Structure", structure), ("Detail", detail)):
            if not np.isfinite(amount) or not 0 <= amount <= PERCENT_SCALE:
                raise ValueError(f"{label} amount must be in range [0.0, 100.0], got {amount}")


__all__ = ["FinishWorkflow"]
