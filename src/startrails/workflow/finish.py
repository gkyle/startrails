"""Finish workflow managing source image I/O, layer separation, and export."""

from __future__ import annotations

from pathlib import Path
from contextlib import nullcontext
from concurrent.futures import CancelledError
import tempfile
from typing import TYPE_CHECKING, Any, Callable, Final, List, Optional, Tuple, Union

import numpy as np

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.file import InputFile, OutputFile
from startrails.lib.finish.composition import blend_denoise, compute_denoise_endpoint_signature
from startrails.lib.finish.defaults import (
    INTERMEDIATE_BIT_DEPTH,
    PERCENT_SCALE,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_FINISHED_STARS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    ROLE_UNMASKED_STARLESS,
    SCOPE_SKY_ONLY,
    SCOPE_WHOLE_IMAGE,
    SUPPORTED_CHANNELS,
)
from startrails.lib.finish.graxpert import graxpert_model_identity
from startrails.lib.finish.separation import compute_separation_signature
from startrails.lib.finish.starnet import MAX_STRIDE, MIN_STRIDE
from startrails.lib.finish.starless_filters import STARLESS_FILTER_VERSION
from startrails.lib.finish.graxpert_runtime import GraXpertSession, resolve_graxpert_runtime_policy
from startrails.lib.image_io import imread, imwrite, normalize_image
from startrails.lib.model_manifest import GRAXPERT_MANIFEST, PlatformNotSupportedError
from startrails.lib.project_finish import FinishProject
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

    def __call__(self, total: int, increment: int, count: int, done: bool, data: Any = None) -> None:
        fraction = min(1.0, count / total) if total > 0 else (1.0 if done else 0.0)
        target = self._start + round(self._size * fraction)
        delta = target - self._reported
        self._reported = target
        # A phase finishing early is not the whole task; only total completion
        # may tell observers that the shared operation is done.
        task_done = bool(done and target >= self._scale)
        self._observer(self._scale, max(0, delta), target, task_done, data)


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
        self.project.set_source_image(path)
        self.save_project()

    def do_replace_source(self, path: Union[str, Path]) -> None:
        """Replace the current source image with a new one and persist project state."""
        self.project.set_source_image(path)
        self.save_project()

    def do_clear_source(self) -> None:
        """Remove the selected source from the project, retaining its files on disk."""
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
        separation_signature = project.separation_signature
        img = imread(composite_artifact, to_rgb=True, as_float=True)

        settings = project.get_settings()
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
        composite_destination: Path,
        transaction: ArtifactTransaction,
        progress_bar: Optional[Any] = None,
        negative_base_path: Optional[Path] = None,
    ) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Recombine the given layers into a staged composite without publishing it.

        The negative correction must come from the original separated plate, not a
        subsequently finished (denoised) starless plate. negative_base_path selects
        that source; omitting it uses starless_path for the Step 7 neutral case.
        """
        project = self.project
        source_arr = imread(project.source_file.path, to_rgb=True, as_float=True)
        starless_arr = imread(starless_path, to_rgb=True, as_float=True)
        stars_arr = imread(stars_path, to_rgb=True, as_float=True)

        if negative_base_path is None or negative_base_path == starless_path:
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
                stars_arr,
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
        """Execute layer recombination and write internal composite artifact.

        progress_bar observes the operation on its native job scale, or on the
        shared separation scale when supplied by do_separate_stars.
        """
        if self.invalidate_if_graxpert_changed() or self.invalidate_if_starless_filter_changed():
            return None
        project = self.project
        revision = project.processing_revision
        separation_signature = project.separation_signature
        if not project.source_is_current():
            return None
        separated_starless_path = project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        stars_path = project.current_artifact_path(ROLE_SEPARATED_STARS)
        if separated_starless_path is None or stars_path is None:
            return None
        # A current finished starless plate supersedes the separated plate for the
        # composite; the signed correction still derives from the separated plate.
        starless_path = project.current_artifact_path(ROLE_FINISHED_STARLESS) or separated_starless_path

        composite_dest = project.artifact_path(ROLE_FINISHED_COMPOSITE, for_write=True)
        try:
            with ArtifactTransaction(self._job_cancel_check(project, revision)) as transaction:
                result = self._recombine_into_transaction(
                    starless_path,
                    stars_path,
                    composite_destination=composite_dest,
                    transaction=transaction,
                    progress_bar=progress_bar,
                    negative_base_path=separated_starless_path,
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


__all__ = ["FinishWorkflow"]
