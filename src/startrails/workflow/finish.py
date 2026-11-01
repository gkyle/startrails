"""Finish workflow managing source image I/O, layer separation, and export."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union

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
from startrails.lib.image_io import imread, imwrite
from startrails.lib.project_finish import FinishProject
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


__all__ = ["FinishWorkflow"]
