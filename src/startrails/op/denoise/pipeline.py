"""Orchestrator pipeline chaining denoise stages (Observable)."""

from __future__ import annotations
import logging
from concurrent.futures import CancelledError
from pathlib import Path
from typing import Callable, Optional, Tuple, List
import numpy as np

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.util import imread
from startrails.op.denoise.base import DenoiseOperation
from startrails.lib.denoise.config import DenoiseConfig
from startrails.lib.denoise.profiler import PipelineProfiler
from startrails.lib.denoise.io.mask import MaskHandler
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor
from startrails.op.denoise.detect_sky import DetectSky
from startrails.op.denoise.refine_mask import RefineMask
from startrails.op.denoise.align_stars import AlignStars, AlignResult
from startrails.op.denoise.stack_denoise import StackDenoise
from startrails.op.denoise.compose_horizon import ComposeHorizon

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]


class DenoisePipeline(DenoiseOperation):
    """Orchestrates image calibration, sky detection, alignment, stacking, and composition."""

    def __init__(self, config: Optional[DenoiseConfig] = None, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)
        self.config = config
        self._artifacts = None
        self.last_profile: Optional[PipelineProfiler] = None
        self.last_compositor: Optional[HorizonCompositor] = None
        self.last_gradient_mask: Optional[np.ndarray] = None

    def _get_base_image_path(self) -> Path:
        if self.config is None:
            raise ValueError("No configuration provided.")
        return AlignStars.get_base_image_path(self.config)

    def _resolve_refined_mask_export_path(self) -> Optional[Path]:
        if self.config is None or not (self.config.export_refined_mask and self.config.output_path):
            return None
        out_p = Path(self.config.output_path).resolve()
        return (
            Path(self.config.refined_mask_path).resolve()
            if self.config.refined_mask_path
            else out_p.parent / f"{out_p.stem}.refined_mask.png"
        )

    def _load_base_and_mask(
        self,
        calibrate_fn: Callable[[np.ndarray], np.ndarray],
        profiler: Optional[PipelineProfiler] = None,
        _report: Optional[ProgressCallback] = None,
    ) -> Tuple[np.ndarray, Optional[bytes], Optional[np.ndarray], Tuple[int, int]]:
        """Load and calibrate base image, load/auto-detect/refine sky mask."""
        if self.config is None:
            raise ValueError("No configuration provided.")
        if profiler is None:
            profiler = PipelineProfiler()

        def report(progress: float, message: str):
            if _report:
                _report(progress, message)

        def on_refine_progress(total, increment, count, done, data):
            message = data.get("desc", "Refining sky mask...") if isinstance(data, dict) else "Refining sky mask..."
            report(0.20 + 0.04 * count / max(total, 1), message)

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
                detect_op = DetectSky(self.cancel_event, self.cancel_check)
                coarse_sky = detect_op.detect(
                    base_calibrated,
                    model_type=model_name,
                    model_path=self.config.auto_mask_path,
                    device="auto" if self.config.use_gpu else "cpu",
                )
            if coarse_sky is None or self.shouldInterrupt():
                raise CancelledError()
            report(0.19, "Refining detected sky mask to natural horizon...")
            mask_out = self._resolve_refined_mask_export_path()
            if mask_out:
                report(0.20, f"Exporting refined mask: {mask_out.name}...")
            with profiler.measure("2b. Sky Mask Refinement"):
                refine_op = RefineMask(self.cancel_event, self.cancel_check)
                refine_op.addObserver(on_refine_progress)
                sky_mask = refine_op.refine(
                    base_calibrated,
                    coarse_sky,
                    search_radius=self.config.mask_search_radius,
                    erosion_pixels=self.config.mask_erosion_pixels,
                    foliage_protection=self.config.mask_foliage_protection,
                    export_path=self._artifacts.stage(mask_out) if mask_out and self._artifacts else mask_out,
                )
            if mask_out:
                self.config.refined_mask_path = mask_out
                logger.info(f"Exported automatic refined mask to {mask_out}")
        elif self.config.refine_sky_mask and sky_mask is not None:
            report(0.19, "Refining sky mask edges to natural horizon...")
            mask_out = self._resolve_refined_mask_export_path()
            if mask_out:
                report(0.20, f"Exporting refined mask: {mask_out.name}...")
            with profiler.measure("2b. Sky Mask Refinement"):
                refine_op = RefineMask(self.cancel_event, self.cancel_check)
                refine_op.addObserver(on_refine_progress)
                sky_mask = refine_op.refine(
                    base_calibrated,
                    sky_mask,
                    search_radius=self.config.mask_search_radius,
                    erosion_pixels=self.config.mask_erosion_pixels,
                    foliage_protection=self.config.mask_foliage_protection,
                    export_path=self._artifacts.stage(mask_out) if mask_out and self._artifacts else mask_out,
                )
            if mask_out:
                self.config.refined_mask_path = mask_out
                logger.info(f"Exported refined mask to {mask_out}")

        if self.shouldInterrupt():
            raise CancelledError()
        return base_calibrated, None, sky_mask, (h, w)

    def stack_base_frames(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        profiler: Optional[PipelineProfiler] = None,
    ) -> Tuple[HorizonCompositor, List[np.ndarray], Optional[bytes]]:
        """Calibrate, align, and stack base sky and ground frames."""
        if self.config is None:
            raise ValueError("No configuration provided.")

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
            base_calibrated, base_icc, sky_mask, (h, w) = self._load_base_and_mask(
                calibrate_fn, profiler=profiler, _report=_report
            )

        n_stars = len(self.config.star_images)
        _report(0.25, f"Aligning and warping {n_stars} frames...")

        align_op = AlignStars(self.cancel_event, self.cancel_check)
        if progress_callback:
            def _align_cb(total, inc, count, done, data):
                prog = 0.25 + 0.45 * (count / max(1, total))
                name = data["frame"].name if data and "frame" in data else ""
                _report(prog, f"Aligned frame {count}/{total}: {name}")
            align_op.addObserver(_align_cb)

        with profiler.measure("3. Frame Alignment & Warping"):
            align_result = align_op.align(
                self.config,
                warp_frames=True,
                sky_mask=sky_mask,
                base_calibrated=base_calibrated,
            )

        if align_result is None or self.shouldInterrupt():
            raise CancelledError("Pipeline cancelled during alignment")

        _report(0.70, "Stacking base sky and ground frames...")
        stack_op = StackDenoise(self.cancel_event, self.cancel_check)
        stack_op.addObserver(lambda total, inc, count, done, data: _report(0.70 + 0.19 * count / max(1, total), (data or {}).get("desc", "Stacking sky and ground...")))

        with profiler.measure("4. Base Stacking"):
            compositor = stack_op.stack(
                self.config,
                align_result.aligned_sky_frames,
                align_result.sky_coverages,
                align_result.raw_ground_frames,
                align_result.sky_mask,
                base_icc=base_icc,
                artifacts=self._artifacts,
            )

        if compositor is None or self.shouldInterrupt():
            raise CancelledError("Pipeline cancelled during stacking")

        self.last_compositor = compositor
        return compositor, align_result.sky_coverages, None

    def run(
        self,
        config: Optional[DenoiseConfig] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Path:
        """Run the complete denoise pipeline according to configuration.

        Returns:
            output_path: Path to the generated stacked image
        """
        if config is not None:
            self.config = config
        if self.config is None:
            raise ValueError("No configuration provided.")

        def _report(progress: float, message: str):
            if self.job is not None:
                count = min(99, max(self.job.count, int(progress * 100)))
                self.updateJob(count - self.job.count, {"desc": message})
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

        with ArtifactTransaction(self.shouldInterrupt) as transaction:
            self._artifacts = transaction
            try:
                compositor, sky_coverages, base_icc = self.stack_base_frames(
                    progress_callback=_report,
                    profiler=profiler,
                )

                if self.shouldInterrupt():
                    raise CancelledError()
                _report(0.90, "Evaluating horizon composite...")
                compose_op = ComposeHorizon(self.cancel_event, self.cancel_check)
                compose_op.addObserver(lambda total, inc, count, done, data: _report(0.90 + 0.09 * count / max(1, total), "Compositing final image..."))

                with profiler.measure("5. Output File Export"):
                    result = compose_op.compose(
                        compositor,
                        self.config,
                        sky_coverages=sky_coverages,
                        base_icc=base_icc,
                        write_output=True,
                        artifacts=self._artifacts,
                    )

                if result is None or self.shouldInterrupt():
                    raise CancelledError()
                stacked, written_path = result
                transaction.commit()
            finally:
                self._artifacts = None
        self.last_gradient_mask = compose_op.last_gradient_mask

        _report(1.0, f"Stacking completed successfully: {written_path}")
        self.updateJob(100 - self.job.count, written_path)

        if self.config.verbose:
            summary = profiler.format_summary()
            logger.info(summary)
            print(summary)

        return written_path


Pipeline = DenoisePipeline
