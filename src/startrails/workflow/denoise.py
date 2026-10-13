"""Denoise workflow implementation managing astrophotography denoising operations."""

from __future__ import annotations
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
import numpy as np

from startrails.lib.file import DenoiseInputFile
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

    @property
    def mode_name(self) -> str:
        return "denoise"

    @property
    def project(self) -> DenoiseProject:
        return self.app.project

    # -------------------------------------------------------------------------
    # Input files management (Star, Noise/Dark, Vignetting/Flat)
    # -------------------------------------------------------------------------

    def get_star_files(self) -> List[DenoiseInputFile]:
        return self.project.star_files

    getStarFiles = get_star_files

    def add_star_files(self, paths: List[str], clear: bool = False) -> None:
        if clear:
            self.project.star_files = []
        for p in paths:
            file_obj = DenoiseInputFile(basename=os.path.basename(p), path=p)
            self.project.star_files.append(file_obj)
        if self.project.star_files and self.project.reference_file is None:
            self.project.set_reference_file(self.project.star_files[0])
        self.save_project()

    addStarFiles = add_star_files

    def remove_star_file(self, file: DenoiseInputFile) -> None:
        if file in self.project.star_files:
            self.project.star_files.remove(file)
            if self.project.reference_file is file:
                self.project.reference_file = (
                    self.project.star_files[0] if self.project.star_files else None
                )
            self.save_project()

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
        self.save_project()

    addNoiseFiles = add_noise_files

    def remove_noise_file(self, file: DenoiseInputFile) -> None:
        if file in self.project.noise_files:
            self.project.noise_files.remove(file)
            self.save_project()

    removeNoiseFile = remove_noise_file

    def get_vignetting_files(self) -> List[DenoiseInputFile]:
        return self.project.vignetting_files

    getVignettingFiles = get_vignetting_files

    def add_vignetting_files(self, paths: List[str], clear: bool = False) -> None:
        if clear:
            self.project.vignetting_files = []
        for p in paths:
            self.project.vignetting_files.append(
                DenoiseInputFile(basename=os.path.basename(p), path=p)
            )
        self.save_project()

    addVignettingFiles = add_vignetting_files

    def remove_vignetting_file(self, file: DenoiseInputFile) -> None:
        if file in self.project.vignetting_files:
            self.project.vignetting_files.remove(file)
            self.save_project()

    removeVignettingFile = remove_vignetting_file

    def get_reference_file(self) -> Optional[DenoiseInputFile]:
        return self.project.get_reference_file()

    getReferenceFile = get_reference_file

    def set_reference_file(self, file: DenoiseInputFile) -> None:
        self.project.set_reference_file(file)
        self.save_project()

    setReferenceFile = set_reference_file

    def get_config(self) -> DenoiseConfig:
        """Return a DenoiseConfig representation of current project state."""
        return self.project.to_denoise_config()

    getConfig = get_config

    # -------------------------------------------------------------------------
    # Observable pipeline operations
    # -------------------------------------------------------------------------

    def do_detect_sky(
        self,
        image: np.ndarray,
        progressBar: Optional[Any] = None,
        model_type: str = "auto",
        model_path: Optional[str] = None,
        device: str = "auto",
        input_size: int = 1024,
    ) -> Optional[np.ndarray]:
        """Run autonomous neural / heuristic sky detection."""
        detector = DetectSky()
        if progressBar is not None:
            detector.addObserver(progressBar)
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
            self.app.activeOperation = None
            if progressBar is not None:
                detector.removeObserver(progressBar)
            self.save_project()

    doDetectSky = do_detect_sky

    def do_refine_mask(
        self,
        image: np.ndarray,
        coarse_mask: np.ndarray,
        progressBar: Optional[Any] = None,
        search_radius: Optional[int] = None,
        erosion_pixels: int = 5,
        foliage_protection: bool = True,
    ) -> Optional[np.ndarray]:
        """Refine celestial sky mask along high-frequency terrain boundaries."""
        refiner = RefineMask()
        if progressBar is not None:
            refiner.addObserver(progressBar)
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
            self.app.activeOperation = None
            if progressBar is not None:
                refiner.removeObserver(progressBar)
            self.save_project()

    doRefineMask = do_refine_mask

    def do_align_stars(
        self,
        config: Optional[DenoiseConfig] = None,
        warp_frames: bool = True,
        sky_mask: Optional[np.ndarray] = None,
        progressBar: Optional[Any] = None,
    ) -> Optional[AlignResult]:
        """Detect and align stars via projective homography estimation."""
        cfg = config or self.get_config()
        aligner = AlignStars()
        if progressBar is not None:
            aligner.addObserver(progressBar)
        self.app.activeOperation = aligner
        try:
            result = aligner.align(
                config=cfg,
                warp_frames=warp_frames,
                sky_mask=sky_mask,
            )
            if result is not None:
                for p, mat in result.homographies.items():
                    self.project.homographies[str(p)] = mat
            return result
        finally:
            self.app.activeOperation = None
            if progressBar is not None:
                aligner.removeObserver(progressBar)
            self.save_project()

    doAlignStars = do_align_stars

    def do_stack_denoise(
        self,
        aligned_sky_frames: List[np.ndarray],
        sky_coverages: List[np.ndarray],
        raw_ground_frames: List[np.ndarray],
        sky_mask: np.ndarray,
        config: Optional[DenoiseConfig] = None,
        base_icc: Optional[bytes] = None,
        progressBar: Optional[Any] = None,
    ) -> Optional[HorizonCompositor]:
        """Perform separate sky-tracked and stationary ground selective stacking."""
        cfg = config or self.get_config()
        stacker = StackDenoise()
        if progressBar is not None:
            stacker.addObserver(progressBar)
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
            return compositor
        finally:
            self.app.activeOperation = None
            if progressBar is not None:
                stacker.removeObserver(progressBar)
            self.save_project()

    doStackDenoise = do_stack_denoise

    def do_compose_horizon(
        self,
        compositor: HorizonCompositor,
        config: Optional[DenoiseConfig] = None,
        progressBar: Optional[Any] = None,
        sky_coverages: Optional[List[np.ndarray]] = None,
        base_icc: Optional[bytes] = None,
        write_output: bool = True,
    ) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Blend sky and ground stacks with seamless horizon band smoothing."""
        cfg = config or self.get_config()
        composer = ComposeHorizon()
        if progressBar is not None:
            composer.addObserver(progressBar)
        self.app.activeOperation = composer
        try:
            result = composer.compose(
                compositor=compositor,
                config=cfg,
                sky_coverages=sky_coverages,
                base_icc=base_icc,
                write_output=write_output,
            )
            return result
        finally:
            self.app.activeOperation = None
            if progressBar is not None:
                composer.removeObserver(progressBar)
            self.save_project()

    doComposeHorizon = do_compose_horizon

    def do_pipeline(
        self,
        config: Optional[DenoiseConfig] = None,
        progressBar: Optional[Any] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Path:
        """Run end-to-end full denoise pipeline."""
        cfg = config or self.get_config()
        pipeline = DenoisePipeline(cfg)
        if progressBar is not None:
            pipeline.addObserver(progressBar)
        self.app.activeOperation = pipeline
        try:
            out_path = pipeline.run(cfg, progress_callback=progress_callback)
            return out_path
        finally:
            self.app.activeOperation = None
            if progressBar is not None:
                pipeline.removeObserver(progressBar)
            self.save_project()

    doPipeline = do_pipeline
