"""Finish workflow managing source image I/O, layer separation, and export."""

from __future__ import annotations

from pathlib import Path
from contextlib import nullcontext
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple, Union

import numpy as np

from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.file import InputFile, OutputFile
from startrails.lib.finish.defaults import (
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_FINISHED_STARS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
)
from startrails.lib.finish.starnet import DEFAULT_STRIDE as STARNET_DEFAULT_STRIDE
from startrails.lib.finish.graxpert_runtime import GraXpertSession, resolve_graxpert_runtime_policy
from startrails.lib.image_io import imread, imwrite
from startrails.lib.model_manifest import GRAXPERT_MANIFEST, PlatformNotSupportedError
from startrails.lib.project_finish import FinishProject
from startrails.lib.signatures import verify_file_integrity
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
from startrails.op.finish.run_starnet import RunStarNet
from startrails.paths import APPLICATION_DIR
from startrails.workflow.base import Workflow
from startrails.workflow.masking import SkyMaskingWorkflowMixin

if TYPE_CHECKING:
    from startrails.app import App


class FinishWorkflow(Workflow, SkyMaskingWorkflowMixin):
    """Workflow controller managing Finish mode project state, operations, and exports."""

    mode_name: str = "finish"

    def __init__(self, app: App):
        super().__init__(app)

    @property
    def project(self) -> FinishProject:
        """The active FinishProject managed by this workflow."""
        return self.app.project

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
            (ROLE_DENOISED_STARLESS, "Denoised"),
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

    def save_mask(self, mask: np.ndarray) -> Path:
        """Validate source geometry, persist canonical sky mask, and invalidate downstream results."""
        if not self.project.source_is_current():
            raise ValueError("Source image is not current or unavailable.")
        dims = self.project.get_source_dimensions()
        if dims is None:
            raise ValueError("No valid source image loaded.")
        if mask.ndim != 2:
            raise ValueError("Sky mask must be a 2D array.")
        if mask.shape != dims:
            raise ValueError(f"Mask dimensions {mask.shape} do not match source dimensions {dims}.")
        if not np.isfinite(mask).all():
            raise ValueError("Sky mask must contain finite values.")
        canonical_path = self.project.artifact_path(ROLE_SKY_MASK, for_write=True)
        written = MaskHandler.save_mask(mask, canonical_path)
        self.project.record_artifact(ROLE_SKY_MASK, written)
        self.project.invalidate_results()
        self.save_project()
        return written

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
        """Export full-resolution result using source-matching depth and format."""
        if not self.project.source_file or not self.project.source_file.path:
            raise ValueError("No source image imported to export.")

        source_path = Path(self.project.source_file.path)
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        if not self.project.source_is_current():
            raise ValueError("Source image changed; import it again before exporting.")
        depth = self.project.source_bit_depth
        if depth not in (8, 16):
            raise ValueError("Source bit depth is unknown; import the source again before exporting.")
        target_path = Path(output_path) if output_path is not None else self.project.get_default_export_path()
        self.project.validate_export_path(target_path)
        if target_path.resolve() == source_path.resolve():
            raise ValueError("Export must not overwrite the original source image.")

        composite_artifact = self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        image_path = composite_artifact if composite_artifact is not None else source_path
        img = imread(image_path, to_rgb=True, as_float=True)

        settings = self.project.get_settings()
        target_path = Path(target_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        written = imwrite(
            target_path,
            img,
            convertBGR=True,
            bit_depth=depth,
            quality=settings.jpeg_quality,
            optimize=settings.jpeg_optimize,
            compression=settings.tiff_deflate_compression,
        )
        self.project.record_export(written)
        self.save_project()
        return written

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
        model_ready = verify_file_integrity(model_path, GRAXPERT_MANIFEST.sha256, GRAXPERT_MANIFEST.size_bytes)
        return {
            "policy": policy,
            "setup_error": setup_error,
            "model_ready": model_ready,
            "model_path": str(model_path),
        }

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
        record_starnet_installation(
            self.app.state,
            installation,
            managed=managed,
            terms_accepted=terms_accepted,
        )
        self.app.saveAppState()

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

    def do_run_starnet(
        self,
        input_image_path: Union[str, Path],
        output_starless_path: Union[str, Path],
        *,
        output_stars_path: Optional[Union[str, Path]] = None,
        stride: int = STARNET_DEFAULT_STRIDE,
        disable_highlights: bool = False,
        upsample: bool = False,
    ) -> Optional[Tuple[Path, Optional[Path]]]:
        """Execute StarNet subprocess using the active verified installation."""
        managed = self.app.state.get("starnet", {}).get("managed", False)
        lock = starnet_installation_lock(get_starnet_storage_dir()) if managed else nullcontext()
        with lock:
            status = self.get_starnet_status()
            if not status["configured"]:
                raise RuntimeError("StarNet is not configured or terms have not been accepted.")
            op = self._new_operation(RunStarNet)
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

    def do_denoise_starless(
        self,
        image: np.ndarray,
        *,
        strength: float = 1.0,
        sky_mask: Optional[np.ndarray] = None,
        sky_only: bool = True,
        output_path: Optional[Union[str, Path]] = None,
        bit_depth: int = 16,
    ) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Execute GraXpert AI denoising on starless plate using the resolved runtime policy."""
        op = self._new_operation(GraXpertDenoise)
        self.app.activeOperation = op
        try:
            if op.shouldInterrupt():
                return None
            session = None
            if strength > 0:
                policy = resolve_graxpert_runtime_policy()
                session = GraXpertSession(provider=policy["provider"])
            return op.denoise(
                image,
                strength=strength,
                sky_mask=sky_mask,
                sky_only=sky_only,
                session=session,
                output_path=output_path,
                bit_depth=bit_depth,
                settings=self.project.get_settings(),
            )
        finally:
            if self.app.activeOperation is op:
                self.app.activeOperation = self._session_operation


__all__ = ["FinishWorkflow"]
