"""Orchestrator pipeline chaining denoise stages (Observable)."""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Callable, Optional, Tuple, List
import numpy as np

from startrails.lib.util import Observable, imread
from startrails.lib.denoise.config import DenoiseConfig
from startrails.lib.denoise.profiler import PipelineProfiler
from startrails.lib.denoise.io.mask import MaskHandler
from startrails.lib.denoise.io.sky_detector import AutoSkyDetector
from startrails.lib.denoise.io.mask_refiner import MaskRefiner
from startrails.lib.denoise.alignment.detector import StarDetector
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor
from startrails.op.denoise.align_stars import AlignStars, AlignResult
from startrails.op.denoise.stack_denoise import StackDenoise
from startrails.op.denoise.compose_horizon import ComposeHorizon

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]


class DenoisePipeline(Observable):
    """Orchestrates image calibration, sky detection, alignment, stacking, and composition."""

    def __init__(self, config: DenoiseConfig):
        super().__init__()
        self.config = config
        self.last_profile: Optional[PipelineProfiler] = None
        self.last_compositor: Optional[HorizonCompositor] = None
        self.last_gradient_mask: Optional[np.ndarray] = None

    def _get_base_image_path(self) -> Path:
        return AlignStars.get_base_image_path(self.config)

    def _load_base_and_mask(
        self,
        calibrate_fn: Callable[[np.ndarray], np.ndarray],
        profiler: Optional[PipelineProfiler] = None,
        _report: Optional[ProgressCallback] = None,
    ) -> Tuple[np.ndarray, Optional[bytes], Optional[np.ndarray], Optional[np.ndarray], Tuple[int, int]]:
        """Load and calibrate base image, load/auto-detect/refine sky mask."""
        if profiler is None:
            profiler = PipelineProfiler()

        def report(progress: float, message: str):
            if _report:
                _report(progress, message)

        base_path = self._get_base_image_path()
        report(0.15, f"Reading base frame: {base_path.name}...")
        base_raw = imread(base_path, to_rgb=True, as_float=True)
        base_calibrated = calibrate_fn(base_raw)
        h, w = base_calibrated.shape[:2]

        sky_mask: Optional[np.ndarray] = None
        if self.config.mask_path or self.config.mask_array is not None:
            sky_mask = MaskHandler.create_mask(
                shape=(h, w),
                mask_path=self.config.mask_path,
                mask_array=self.config.mask_array,
            )

        if self.config.auto_mask:
            model_name = self.config.auto_mask_model or "auto"
            report(0.18, f"Running auto sky detection ({model_name})...")
            with profiler.measure("2a. Automatic Sky Detection"):
                coarse_sky = AutoSkyDetector.detect(
                    base_calibrated,
                    model_type=model_name,
                    model_path=self.config.auto_mask_path,
                    device="auto",
                )
            report(0.19, "Refining detected sky mask to natural horizon...")
            with profiler.measure("2b. Sky Mask Refinement"):
                sky_mask = MaskRefiner.refine(
                    base_calibrated,
                    coarse_sky,
                    search_radius=self.config.mask_search_radius,
                    erosion_pixels=self.config.mask_erosion_pixels,
                    foliage_protection=self.config.mask_foliage_protection,
                )
            if self.config.export_refined_mask and self.config.output_path:
                out_p = Path(self.config.output_path).resolve()
                mask_out = (
                    Path(self.config.refined_mask_path).resolve()
                    if self.config.refined_mask_path
                    else out_p.parent / f"{out_p.stem}.refined_mask.png"
                )
                report(0.20, f"Exporting refined mask: {mask_out.name}...")
                MaskHandler.save_mask(sky_mask, mask_out)
                self.config.refined_mask_path = mask_out
                logger.info(f"Exported automatic refined mask to {mask_out}")
        elif self.config.refine_sky_mask and sky_mask is not None:
            report(0.19, "Refining sky mask edges to natural horizon...")
            with profiler.measure("2b. Sky Mask Refinement"):
                sky_mask = MaskRefiner.refine(
                    base_calibrated,
                    sky_mask,
                    search_radius=self.config.mask_search_radius,
                    erosion_pixels=self.config.mask_erosion_pixels,
                    foliage_protection=self.config.mask_foliage_protection,
                )
            if self.config.export_refined_mask and self.config.output_path:
                out_p = Path(self.config.output_path).resolve()
                mask_out = (
                    Path(self.config.refined_mask_path).resolve()
                    if self.config.refined_mask_path
                    else out_p.parent / f"{out_p.stem}.refined_mask.png"
                )
                report(0.20, f"Exporting refined mask: {mask_out.name}...")
                MaskHandler.save_mask(sky_mask, mask_out)
                self.config.refined_mask_path = mask_out
                logger.info(f"Exported refined mask to {mask_out}")

        eroded_sky_mask = StarDetector.prepare_sky_mask(sky_mask)
        return base_calibrated, None, sky_mask, eroded_sky_mask, (h, w)

    def compute_homographies(self, progress_callback: Optional[ProgressCallback] = None) -> dict[Path, np.ndarray]:
        """Compute and cache alignment homographies for all star images."""
        align_op = AlignStars()
        if progress_callback:
            def _cb(total, inc, count, done, data):
                progress_callback(count / max(1, total), f"Aligned frame {count}/{total}")
            align_op.addObserver(_cb)

        result = align_op.align(self.config, warp_frames=False)
        return self.config.homographies

    def stack_base_frames(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        profiler: Optional[PipelineProfiler] = None,
    ) -> Tuple[HorizonCompositor, List[np.ndarray], Optional[bytes]]:
        """Calibrate, align, and stack base sky and ground frames."""
        def _report(progress: float, message: str):
            if progress_callback:
                progress_callback(progress, message)

        if profiler is None:
            profiler = PipelineProfiler()

        if not self.config.star_images:
            raise ValueError("No star images provided in configuration.")

        _report(0.02, "Initializing stacking pipeline...")
        calibrate_fn = AlignStars.prepare_calibrator(self.config)

        with profiler.measure("1 & 2. Frame Loading & Mask Preparation"):
            base_calibrated, base_icc, sky_mask, eroded_sky_mask, (h, w) = self._load_base_and_mask(
                calibrate_fn, profiler=profiler, _report=_report
            )

        n_stars = len(self.config.star_images)
        _report(0.25, f"Aligning and warping {n_stars} frames...")

        align_op = AlignStars()
        if progress_callback:
            def _align_cb(total, inc, count, done, data):
                prog = 0.25 + 0.45 * (count / max(1, total))
                name = data["frame"].name if data and "frame" in data else ""
                _report(prog, f"Aligned frame {count}/{total}: {name}")
            align_op.addObserver(_align_cb)

        with profiler.measure("3. Frame Alignment & Warping"):
            align_result = align_op.align(self.config, warp_frames=True, sky_mask=sky_mask)

        if align_result is None or self.shouldInterrupt():
            raise RuntimeError("Pipeline cancelled during alignment")

        _report(0.70, "Stacking base sky and ground frames...")
        stack_op = StackDenoise()

        with profiler.measure("4. Base Stacking"):
            compositor = stack_op.stack(
                self.config,
                align_result.aligned_sky_frames,
                align_result.sky_coverages,
                align_result.raw_ground_frames,
                align_result.sky_mask,
                base_icc=base_icc,
            )

        if compositor is None or self.shouldInterrupt():
            raise RuntimeError("Pipeline cancelled during stacking")

        self.last_compositor = compositor
        return compositor, align_result.sky_coverages, None

    def run(self, progress_callback: Optional[ProgressCallback] = None) -> Path:
        """Run the complete denoise pipeline according to configuration.

        Returns:
            output_path: Path to the generated stacked image
        """
        def _report(progress: float, message: str):
            if progress_callback:
                progress_callback(progress, message)

        profiler = PipelineProfiler()
        self.last_profile = profiler

        if not self.config.star_images:
            raise ValueError("No star images provided in configuration.")

        if not self.config.output_path:
            raise ValueError("No output path specified.")

        output_path = Path(self.config.output_path).resolve()

        self.startJob(100)

        compositor, sky_coverages, base_icc = self.stack_base_frames(
            progress_callback=progress_callback,
            profiler=profiler,
        )

        _report(0.90, "Evaluating horizon composite...")
        compose_op = ComposeHorizon()

        with profiler.measure("5. Output File Export"):
            stacked, written_path = compose_op.compose(
                compositor,
                self.config,
                sky_coverages=sky_coverages,
                base_icc=base_icc,
                write_output=True,
            )

        if self.config.export_gradient_mask and sky_coverages:
            h, w = stacked.shape[:2]
            sky_mask = MaskHandler.create_mask(shape=(h, w), mask_path=self.config.mask_path, mask_array=self.config.mask_array)
            self.last_gradient_mask = MaskHandler.compute_gradient_mask(sky_coverages, sky_mask=sky_mask)

        _report(1.0, f"Stacking completed successfully: {written_path}")
        self.updateJob(100, written_path)

        if self.config.verbose:
            summary = profiler.format_summary()
            logger.info(summary)
            print(summary)

        return written_path


Pipeline = DenoisePipeline
