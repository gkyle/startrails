"""Denoise workflow implementation managing astrophotography denoising operations."""

from __future__ import annotations
import os
from contextlib import contextmanager
from threading import Event
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import numpy as np

from startrails.op.denoise.base import DenoiseOperation
from startrails.lib.file import DenoiseInputFile, OutputFile
from startrails.lib.project_denoise import DenoiseProject
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor
from startrails.op.denoise.detect_sky import DetectSky
from startrails.op.denoise.refine_mask import RefineMask
from startrails.op.denoise.align_stars import AlignStars, AlignResult
from startrails.op.denoise.stack_denoise import StackDenoise
from startrails.op.denoise.compose_horizon import ComposeHorizon
from startrails.op.denoise.pipeline import DenoisePipeline
from startrails.workflow.base import Workflow

if TYPE_CHECKING:
    from startrails.app import App
    from startrails.lib.project_denoise import DenoiseProject

ProgressObserver = Callable[[int, int, int, bool, Optional[dict[str, Any]]], None]


class DenoiseWorkflow(Workflow):
    """Workflow controller orchestrating the Denoise mode pipeline and data."""

    def __init__(self, app):
        super().__init__(app)
        self._project = app.project
        self._cancel_event = Event()
        self._session_operation = None

    @contextmanager
    def operation_session(self):
        self._cancel_event = Event()
        revision = self.project.processing_revision
        session = DenoiseOperation(self._cancel_event, lambda: self.project is not self.app.project or revision != self.project.processing_revision)
        session.startJob(1)
        self._session_operation = session
        self.app.activeOperation = session
        try:
            yield
        finally:
            self._session_operation = None
            if self.app.activeOperation is session:
                self.app.activeOperation = None

    def _new_operation(self, operation_type, *args):
        revision = self.project.processing_revision
        signature = self.project.source_signature(stacking=True)
        check = lambda: self.project is not self.app.project or revision != self.project.processing_revision or signature != self.project.source_signature(stacking=True)
        if self._session_operation is not None:
            input_check = check
            session_check = self._session_operation.shouldInterrupt
            check = lambda: input_check() or session_check()
        token = self._cancel_event if self._session_operation is not None else Event()
        return operation_type(*args, cancel_event=token, cancel_check=check)

    def save_project(self) -> None:
        if self._project is self.app.project:
            super().save_project()

    def invalidate_results(self, alignment: bool = True, reference_changed: bool = False) -> None:
        self.project.bind_files()
        self.project.invalidate_results(alignment=alignment)
        if reference_changed:
            self.project.mask_invalidated = True
        self.save_project()

    @property
    def mode_name(self) -> str:
        return "denoise"

    @property
    def project(self) -> DenoiseProject:
        return self._project

    # -------------------------------------------------------------------------
    # Input files management (Star, Noise/Dark, Vignetting/Flat)
    # -------------------------------------------------------------------------

    def get_star_files(self) -> List[DenoiseInputFile]:
        return self.project.star_files

    def add_star_files(self, paths: List[str], clear: bool = False) -> None:
        previous_reference = self.project.get_reference_file()
        if clear:
            self.project.star_files = []
            self.project.reference_file = None
        for p in paths:
            file_obj = DenoiseInputFile(basename=os.path.basename(p), path=p)
            self.project.star_files.append(file_obj)
        reference_changed = previous_reference is not None and self.project.get_reference_file() is not previous_reference
        self.invalidate_results(reference_changed=clear or reference_changed)

    def remove_star_file(self, file: DenoiseInputFile) -> None:
        if file in self.project.star_files:
            previous_reference = self.project.get_reference_file()
            self.project.star_files.remove(file)
            if previous_reference is file:
                self.project.reference_file = None
            reference_changed = self.project.get_reference_file() is not previous_reference
            self.invalidate_results(reference_changed=reference_changed)

    def get_noise_files(self) -> List[DenoiseInputFile]:
        return self.project.noise_files

    def add_noise_files(self, paths: List[str], clear: bool = False) -> None:
        if clear:
            self.project.noise_files = []
        for p in paths:
            self.project.noise_files.append(
                DenoiseInputFile(basename=os.path.basename(p), path=p)
            )
        self.invalidate_results()

    def remove_noise_file(self, file: DenoiseInputFile) -> None:
        if file in self.project.noise_files:
            self.project.noise_files.remove(file)
            self.invalidate_results()

    def get_reference_file(self) -> Optional[DenoiseInputFile]:
        return self.project.get_reference_file()

    def set_reference_file(self, file: DenoiseInputFile) -> None:
        if file is not self.project.get_reference_file():
            self.project.set_reference_file(file)
            self.invalidate_results(reference_changed=True)
        elif self.project.reference_file is None:
            self.project.set_reference_file(file)
            self.save_project()

    def get_config(self) -> DenoiseProject:
        """Return a DenoiseProject representation of current project state."""
        self.project.validate_cached_results()
        if self.project.mask_path and not self.project.mask_invalidated and not Path(self.project.mask_path).is_file():
            raise FileNotFoundError(f"Sky mask is missing: {self.project.mask_path}. Detect or paint a replacement mask.")
        return self.project.to_denoise_config()

    # -------------------------------------------------------------------------
    # Observable pipeline operations
    # -------------------------------------------------------------------------

    def do_detect_sky(
        self,
        image: np.ndarray,
        progress_bar: Optional[ProgressObserver] = None,
        *,
        model_type: str,
        model_path: Optional[str],
        device: str,
        input_size: int,
    ) -> Optional[np.ndarray]:
        """Run autonomous neural sky detection."""
        detector = self._new_operation(DetectSky)
        if progress_bar is not None:
            detector.addObserver(progress_bar)
        self.app.activeOperation = detector
        try:
            mask = detector.detect(
                image,
                model_type=model_type,
                model_path=model_path,
                device=device,
                input_size=input_size,
            )
            return mask
        finally:
            self.app.activeOperation = self._session_operation
            if progress_bar is not None:
                detector.removeObserver(progress_bar)
            self.save_project()

    def do_refine_mask(
        self,
        image: np.ndarray,
        coarse_mask: np.ndarray,
        progress_bar: Optional[ProgressObserver] = None,
        *,
        search_radius: Optional[int],
        erosion_pixels: int,
        foliage_protection: bool,
    ) -> Optional[np.ndarray]:
        """Refine celestial sky mask along high-frequency terrain boundaries."""
        refiner = self._new_operation(RefineMask)
        if progress_bar is not None:
            refiner.addObserver(progress_bar)
        self.app.activeOperation = refiner
        try:
            refined = refiner.refine(
                image,
                coarse_mask,
                search_radius=search_radius,
                erosion_pixels=erosion_pixels,
                foliage_protection=foliage_protection,
            )
            return refined
        finally:
            self.app.activeOperation = self._session_operation
            if progress_bar is not None:
                refiner.removeObserver(progress_bar)
            self.save_project()

    @staticmethod
    def has_cached_alignment(config: DenoiseProject) -> bool:
        """Whether all non-reference frames have reusable transforms."""
        if not config.star_images:
            return False
        base_path = AlignStars.get_base_image_path(config)
        return all(Path(path).resolve() == base_path or config.homographies.get(Path(path).resolve()) is not None
                   for path in config.star_images)

    def do_align_stars(
        self,
        config: Optional[DenoiseProject] = None,
        warp_frames: bool = False,
        sky_mask: Optional[np.ndarray] = None,
        progress_bar: Optional[ProgressObserver] = None,
    ) -> Optional[AlignResult]:
        """Detect and align stars via projective homography estimation."""
        cfg = config or self.get_config()
        aligner = self._new_operation(AlignStars)
        if progress_bar is not None:
            aligner.addObserver(progress_bar)
        self.app.activeOperation = aligner
        try:
            result = aligner.align(
                config=cfg,
                warp_frames=warp_frames,
                sky_mask=sky_mask,
            )
            if result is not None and not aligner.shouldInterrupt():
                self.project.alignment_signature = self.project.source_signature()
                for p, mat in result.homographies.items():
                    self.project.homographies[str(p)] = mat
                for f in getattr(self.project, "star_files", []):
                    if f.path:
                        p_str = str(f.path)
                        p_res = str(Path(f.path).resolve())
                        if p_str in self.project.homographies or p_res in self.project.homographies:
                            f.aligned = True
            return result
        finally:
            self.app.activeOperation = self._session_operation
            if progress_bar is not None:
                aligner.removeObserver(progress_bar)
            self.save_project()

    def _get_project_stem(self) -> str:
        if self.project is not None and hasattr(self.project, "get_project_stem"):
            return self.project.get_project_stem()
        if not self.project or not hasattr(self.project, "projectFile") or not self.project.projectFile:
            return "project"
        name = Path(self.project.projectFile).name
        if name.endswith(".proj_denoise"):
            return name[:-len(".proj_denoise")]
        if name.endswith(".json"):
            return name[:-5]
        return Path(self.project.projectFile).stem

    # -------------------------------------------------------------------------
    # Output file operations
    # -------------------------------------------------------------------------

    def get_output_file_list(self) -> List[OutputFile]:
        if not self.project or not hasattr(self.project, "get_output_dir"):
            return []
        out_dir = self.project.get_output_dir()
        if not out_dir.exists():
            return []

        out_files: List[OutputFile] = []
        seen_paths = set()
        stem = self._get_project_stem()

        # Prioritized known artifact roles
        final_comp = (
            Path(self.project.final_output_path).resolve()
            if getattr(self.project, "final_output_path", None)
            else (out_dir / f"{stem}_final.tif").resolve()
        )
        candidates = [
            (final_comp, "Final Composite"),
            (Path(self.project.output_path).resolve() if getattr(self.project, "output_path", None) else (out_dir / f"{stem}.tif").resolve(), "Composite"),
            (self.project.artifact_path("sky_stack"), "Sky Stack"),
            (self.project.artifact_path("ground_stack"), "Ground Stack"),
            ((out_dir / "base_composite.tif").resolve(), "Base Stack"),
            (self.project.artifact_path("gradient_mask"), "Gradient Mask"),
            (self.project.artifact_path("refined_mask"), "Refined Mask"),
            (self.project.artifact_path("mask"), "Sky Mask"),
        ]

        for cand_path, role in candidates:
            if cand_path.is_file() and str(cand_path) not in seen_paths:
                seen_paths.add(str(cand_path))
                mtime = cand_path.stat().st_mtime
                out_files.append(OutputFile(basename=cand_path.name, path=str(cand_path), operation=role, mtime=mtime))

        for p in sorted(out_dir.iterdir()):
            if p.is_file() and str(p.resolve()) not in seen_paths:
                if p.suffix.lower() in [".tif", ".tiff", ".png", ".jpg", ".jpeg"]:
                    seen_paths.add(str(p.resolve()))
                    mtime = p.stat().st_mtime
                    out_files.append(OutputFile(basename=p.name, path=str(p.resolve()), operation="Output", mtime=mtime))

        return out_files

    def remove_output_file(self, file: OutputFile) -> None:
        if file is None or not getattr(file, "path", None):
            return
        p = Path(file.path)
        if p.is_file():
            try:
                p.unlink()
            except Exception:
                pass
        if self.project is not None:
            if getattr(self.project, "final_output_path", None) and Path(self.project.final_output_path).resolve() == p.resolve():
                self.project.final_output_path = None
            if getattr(self.project, "output_path", None) and Path(self.project.output_path).resolve() == p.resolve():
                self.project.output_path = None
            if getattr(self.project, "gradient_mask_path", None) and Path(self.project.gradient_mask_path).resolve() == p.resolve():
                self.project.gradient_mask_path = None
            if getattr(self.project, "sky_stack_path", None) and Path(self.project.sky_stack_path).resolve() == p.resolve():
                self.project.sky_stack_path = None
            if getattr(self.project, "ground_stack_path", None) and Path(self.project.ground_stack_path).resolve() == p.resolve():
                self.project.ground_stack_path = None
            if getattr(self.project, "mask_path", None) and Path(self.project.mask_path).resolve() == p.resolve():
                self.project.mask_path = None
            self.save_project()

    removeOutputFile = remove_output_file

    def do_stack_denoise(
        self,
        config: Optional[DenoiseProject] = None,
        sky_mask: Optional[np.ndarray] = None,
        progress_bar: Optional[ProgressObserver] = None,
        aligned_sky_frames: Optional[List[np.ndarray]] = None,
        sky_coverages: Optional[List[np.ndarray]] = None,
        raw_ground_frames: Optional[List[np.ndarray]] = None,
    ) -> Optional[HorizonCompositor]:
        cfg = config or self.get_config()
        if hasattr(self.project, "get_output_dir"):
            out_dir = self.project.get_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            if not cfg.sky_stack_path:
                cfg.sky_stack_path = cfg.artifact_path("sky_stack")
            if not cfg.ground_stack_path:
                cfg.ground_stack_path = cfg.artifact_path("ground_stack")
            if not cfg.gradient_mask_path:
                cfg.gradient_mask_path = cfg.artifact_path("gradient_mask")
            if not cfg.output_path:
                stem = self._get_project_stem()
                cfg.output_path = out_dir / f"{stem}.tif"

        stacker = self._new_operation(StackDenoise)
        if progress_bar is not None:
            stacker.addObserver(progress_bar)
        self.app.activeOperation = stacker
        try:
            compositor = stacker.stack(
                config=cfg,
                aligned_sky_frames=aligned_sky_frames,
                sky_coverages=sky_coverages,
                raw_ground_frames=raw_ground_frames,
                sky_mask=sky_mask,
            )
            if compositor is not None and not stacker.shouldInterrupt() and hasattr(self.project, "get_output_dir"):
                out_dir = self.project.get_output_dir()
                out_dir.mkdir(parents=True, exist_ok=True)
                if cfg.sky_stack_path:
                    self.project.sky_stack_path = str(cfg.sky_stack_path)
                if cfg.ground_stack_path:
                    self.project.ground_stack_path = str(cfg.ground_stack_path)
                if cfg.gradient_mask_path:
                    self.project.gradient_mask_path = str(cfg.gradient_mask_path)
                if cfg.output_path:
                    self.project.output_path = str(cfg.output_path)
                self.project.record_stacks()
            return compositor
        finally:
            self.app.activeOperation = self._session_operation
            if progress_bar is not None:
                stacker.removeObserver(progress_bar)
            self.save_project()

    def do_compose_horizon(
        self,
        compositor: HorizonCompositor,
        config: Optional[DenoiseProject] = None,
        progress_bar: Optional[ProgressObserver] = None,
        write_output: bool = True,
    ) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Blend sky and ground stacks with seamless horizon band smoothing."""
        cfg = config or self.get_config()
        if hasattr(self.project, "get_output_dir"):
            out_dir = self.project.get_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            if not cfg.output_path:
                stem = self._get_project_stem()
                cfg.output_path = out_dir / f"{stem}_final.tif"
            if not cfg.gradient_mask_path:
                cfg.gradient_mask_path = cfg.artifact_path("gradient_mask")

        composer = self._new_operation(ComposeHorizon)
        if progress_bar is not None:
            composer.addObserver(progress_bar)
        self.app.activeOperation = composer
        try:
            result = composer.compose(
                compositor=compositor,
                config=cfg,
                write_output=write_output,
            )
            if result and result[1] and hasattr(self.project, "get_output_dir"):
                self.project.final_output_path = str(result[1])
                if cfg.gradient_mask_path:
                    self.project.gradient_mask_path = str(cfg.gradient_mask_path)
            return result
        finally:
            self.app.activeOperation = self._session_operation
            if progress_bar is not None:
                composer.removeObserver(progress_bar)
            self.save_project()

    def do_pipeline(
        self,
        config: Optional[DenoiseProject] = None,
        progress_bar: Optional[ProgressObserver] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Path:
        cfg = config or self.get_config()
        if not cfg.output_path and hasattr(self.project, "get_output_dir"):
            out_dir = self.project.get_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = self._get_project_stem()
            cfg.output_path = out_dir / f"{stem}.tif"
        pipeline = self._new_operation(DenoisePipeline, cfg)
        if progress_bar is not None:
            pipeline.addObserver(progress_bar)
        self.app.activeOperation = pipeline
        try:
            out_path = pipeline.run(cfg, progress_callback=progress_callback)
            if out_path:
                self.last_compositor = pipeline.last_compositor
                self.project.homographies = {str(path): value for path, value in cfg.homographies.items()}
                self.project.alignment_signature = self.project.source_signature()
                self.project.sky_stack_path = str(cfg.sky_stack_path) if cfg.sky_stack_path else None
                self.project.ground_stack_path = str(cfg.ground_stack_path) if cfg.ground_stack_path else None
                self.project.gradient_mask_path = str(cfg.gradient_mask_path) if cfg.gradient_mask_path else None
                self.project.output_path = str(out_path)
                self.project.record_stacks()
            return out_path
        finally:
            self.app.activeOperation = self._session_operation
            if progress_bar is not None:
                pipeline.removeObserver(progress_bar)
            self.save_project()
