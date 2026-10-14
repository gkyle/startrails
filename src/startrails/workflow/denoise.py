"""Denoise workflow implementation managing astrophotography denoising operations."""

from __future__ import annotations
import os
from contextlib import contextmanager
from threading import Event
from startrails.op.denoise.base import DenoiseOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import numpy as np

from startrails.lib.file import DenoiseInputFile, OutputFile
from startrails.lib.denoise.config import DenoiseConfig
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

    getStarFiles = get_star_files

    def add_star_files(self, paths: List[str], clear: bool = False) -> None:
        if clear:
            self.project.star_files = []
            self.project.reference_file = None
        for p in paths:
            file_obj = DenoiseInputFile(basename=os.path.basename(p), path=p)
            self.project.star_files.append(file_obj)
        if self.project.star_files and self.project.reference_file is None:
            self.project.set_reference_file(self.project.star_files[0])
        self.invalidate_results(reference_changed=clear)

    addStarFiles = add_star_files

    def remove_star_file(self, file: DenoiseInputFile) -> None:
        if file in self.project.star_files:
            reference_changed = self.project.get_reference_file() is file
            self.project.star_files.remove(file)
            if self.project.reference_file is file:
                if self.project.star_files:
                    self.project.set_reference_file(self.project.star_files[0])
                else:
                    self.project.reference_file = None
            self.invalidate_results(reference_changed=reference_changed)

    removeStarFile = remove_star_file

    def get_noise_files(self) -> List[DenoiseInputFile]:
        return self.project.noise_files

    getNoiseFiles = get_noise_files

    def add_noise_files(self, paths: List[str], clear: bool = False) -> None:
        if clear:
            self.project.noise_files = []
        for p in paths:
            self.project.noise_files.append(
                DenoiseInputFile(basename=os.path.basename(p), path=p)
            )
        self.invalidate_results()

    addNoiseFiles = add_noise_files

    def remove_noise_file(self, file: DenoiseInputFile) -> None:
        if file in self.project.noise_files:
            self.project.noise_files.remove(file)
            self.invalidate_results()

    removeNoiseFile = remove_noise_file


    def get_reference_file(self) -> Optional[DenoiseInputFile]:
        return self.project.get_reference_file()

    getReferenceFile = get_reference_file

    def set_reference_file(self, file: DenoiseInputFile) -> None:
        if file is not self.project.get_reference_file():
            self.project.set_reference_file(file)
            self.invalidate_results(reference_changed=True)

    setReferenceFile = set_reference_file

    def get_config(self) -> DenoiseConfig:
        """Return a DenoiseConfig representation of current project state."""
        self.project.validate_cached_results()
        if self.project.mask_path and not self.project.mask_invalidated and not Path(self.project.mask_path).is_file():
            raise FileNotFoundError(f"Sky mask is missing: {self.project.mask_path}. Detect or paint a replacement mask.")
        return self.project.to_denoise_config()

    getConfig = get_config

    # -------------------------------------------------------------------------
    # Observable pipeline operations
    # -------------------------------------------------------------------------

    def do_detect_sky(
        self,
        image: np.ndarray,
        progress_bar: Optional[Any] = None,
        model_type: str = "auto",
        model_path: Optional[str] = None,
        device: str = "auto",
        input_size: int = 1024,
    ) -> Optional[np.ndarray]:
        """Run autonomous neural / heuristic sky detection."""
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

    doDetectSky = do_detect_sky

    def do_refine_mask(
        self,
        image: np.ndarray,
        coarse_mask: np.ndarray,
        progress_bar: Optional[Any] = None,
        search_radius: Optional[int] = None,
        erosion_pixels: int = 5,
        foliage_protection: bool = True,
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

    doRefineMask = do_refine_mask

    def do_align_stars(
        self,
        config: Optional[DenoiseConfig] = None,
        warp_frames: bool = True,
        sky_mask: Optional[np.ndarray] = None,
        progress_bar: Optional[Any] = None,
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

    doAlignStars = do_align_stars

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
            (Path(self.project.sky_stack_path).resolve() if getattr(self.project, "sky_stack_path", None) else (out_dir / "sky_stack.tif").resolve(), "Sky Stack"),
            (Path(self.project.ground_stack_path).resolve() if getattr(self.project, "ground_stack_path", None) else (out_dir / "ground_stack.tif").resolve(), "Ground Stack"),
            ((out_dir / "base_composite.tif").resolve(), "Base Stack"),
            (Path(self.project.gradient_mask_path).resolve() if getattr(self.project, "gradient_mask_path", None) else (out_dir / "gradient_mask.png").resolve(), "Gradient Mask"),
            (Path(self.project.refined_mask_path).resolve() if getattr(self.project, "refined_mask_path", None) else (out_dir / "refined_mask.png").resolve(), "Refined Mask"),
            (Path(self.project.mask_path).resolve() if getattr(self.project, "mask_path", None) else (out_dir / "mask.png").resolve(), "Sky Mask"),
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

    getOutputFileList = get_output_file_list

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
        aligned_sky_frames: List[np.ndarray],
        sky_coverages: List[np.ndarray],
        raw_ground_frames: List[np.ndarray],
        sky_mask: np.ndarray,
        config: Optional[DenoiseConfig] = None,
        base_icc: Optional[bytes] = None,
        progress_bar: Optional[Any] = None,
    ) -> Optional[HorizonCompositor]:
        cfg = config or self.get_config()
        if hasattr(self.project, "get_output_dir"):
            out_dir = self.project.get_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            if not cfg.sky_stack_path:
                cfg.sky_stack_path = out_dir / "sky_stack.tif"
            if not cfg.ground_stack_path:
                cfg.ground_stack_path = out_dir / "ground_stack.tif"
            if not cfg.gradient_mask_path:
                cfg.gradient_mask_path = out_dir / "gradient_mask.png"
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
                base_icc=base_icc,
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

    doStackDenoise = do_stack_denoise

    def do_compose_horizon(
        self,
        compositor: HorizonCompositor,
        config: Optional[DenoiseConfig] = None,
        progress_bar: Optional[Any] = None,
        sky_coverages: Optional[List[np.ndarray]] = None,
        base_icc: Optional[bytes] = None,
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
                cfg.gradient_mask_path = out_dir / "gradient_mask.png"

        composer = self._new_operation(ComposeHorizon)
        if progress_bar is not None:
            composer.addObserver(progress_bar)
        self.app.activeOperation = composer
        try:
            result = composer.compose(
                compositor=compositor,
                config=cfg,
                sky_coverages=sky_coverages,
                base_icc=base_icc,
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

    doComposeHorizon = do_compose_horizon

    def do_pipeline(
        self,
        config: Optional[DenoiseConfig] = None,
        progress_bar: Optional[Any] = None,
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

    doPipeline = do_pipeline
