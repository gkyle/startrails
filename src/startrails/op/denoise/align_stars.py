"""Observable operation for celestial star alignment and frame warping."""

from __future__ import annotations
from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import numpy as np

from startrails.lib.util import imread
from startrails.op.denoise.base import DenoiseOperation
from startrails.lib.project_denoise import DenoiseProject
from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.denoise.calibration.dark import DarkCalibrator
from startrails.lib.denoise.alignment.detector import StarDetector, Star
from startrails.lib.denoise.alignment.matcher import StarMatcher
from startrails.lib.denoise.alignment.transform import TransformModel
from startrails.lib.denoise.alignment.warper import ImageWarper

logger = logging.getLogger(__name__)


@dataclass
class AlignResult:
    """Output bundle from star alignment and warping."""
    homographies: dict[Path, np.ndarray] = field(default_factory=dict)
    aligned_sky_frames: List[np.ndarray] = field(default_factory=list)
    sky_coverages: List[np.ndarray] = field(default_factory=list)
    raw_ground_frames: List[np.ndarray] = field(default_factory=list)
    base_calibrated: Optional[np.ndarray] = None
    sky_mask: Optional[np.ndarray] = None


class AlignStars(DenoiseOperation):
    """Detects stars, matches asterisms, and estimates homographies across frames."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)

    @staticmethod
    def prepare_calibrator(config: DenoiseProject) -> Callable[[np.ndarray], np.ndarray]:
        """Prepare dark master calibration frame if configured."""
        master_dark: Optional[np.ndarray] = None
        if config.noise_images:
            darks = [imread(p, to_rgb=True, as_float=False) for p in config.noise_images]
            master_dark = DarkCalibrator.compute_master_dark(darks, use_gpu=config.use_gpu)

        def calibrate(img: np.ndarray) -> np.ndarray:
            if master_dark is not None:
                img = DarkCalibrator.subtract_dark(img, master_dark)
            return img

        return calibrate

    @staticmethod
    def get_base_image_path(config: DenoiseProject) -> Path:
        """Resolve base reference frame path."""
        if config.base_image:
            return Path(config.base_image).resolve()
        if config.star_images:
            mid_idx = len(config.star_images) // 2
            return Path(config.star_images[mid_idx]).resolve()
        raise ValueError("No star images provided in configuration.")

    def align(
        self,
        config: DenoiseProject,
        warp_frames: bool = False,
        sky_mask: Optional[np.ndarray] = None,
        base_calibrated: Optional[np.ndarray] = None,
        calibrate_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    ) -> Optional[AlignResult]:
        """Align all star images in config to base reference frame.

        Args:
            config: Configuration specifying star_images, base_image, and alignment parameters.
            warp_frames: Whether to warp images and produce aligned_sky_frames and coverages.
            sky_mask: Pre-computed or user-defined sky mask (H, W). If None, resolved from config.
            base_calibrated: Pre-loaded and calibrated base image array. If None, loaded from disk.
            calibrate_fn: Prepared calibration shared with base loading. If None, prepared here.

        Returns:
            AlignResult or None if interrupted.
        """
        if not config.star_images:
            raise ValueError("No star images provided in configuration.")

        n_stars = len(config.star_images)
        self.startJob(n_stars)
        if self.shouldInterrupt():
            return None

        if calibrate_fn is None:
            calibrate_fn = self.prepare_calibrator(config)
        base_path = self.get_base_image_path(config)

        if base_calibrated is None:
            base_raw = imread(base_path, to_rgb=True, as_float=False)
            base_calibrated = calibrate_fn(base_raw)
        elif base_calibrated.dtype in (np.float32, np.float64):
            sample = imread(base_path, to_rgb=False, as_float=False)
            if sample.dtype == np.uint16:
                base_calibrated = np.clip(base_calibrated * 65535.0 + 0.5, 0, 65535).astype(np.uint16)
            elif sample.dtype == np.uint8:
                base_calibrated = np.clip(base_calibrated * 255.0 + 0.5, 0, 255).astype(np.uint8)
            del sample
        h, w = base_calibrated.shape[:2]

        if sky_mask is None:
            sky_mask = MaskHandler.create_mask(
                shape=(h, w),
                mask_path=config.mask_path,
                mask_array=config.mask_array,
            )

        ref_stars = None
        eroded_sky_mask = None

        aligned_sky_frames: List[np.ndarray] = []
        sky_coverages: List[np.ndarray] = []
        raw_ground_frames: List[np.ndarray] = []

        for i, p in enumerate(config.star_images):
            if self.shouldInterrupt():
                return None

            p_path = Path(p)
            p_resolved = p_path.resolve()

            # Calibration and load
            if p_resolved == base_path:
                frame_cal = base_calibrated
            else:
                frame_raw = imread(p_path, to_rgb=True, as_float=False)
                frame_cal = calibrate_fn(frame_raw)

            # Homography estimation
            matrix = config.homographies.get(p_resolved)
            reused_transform = matrix is not None or p_resolved == base_path

            if matrix is None:
                if p_resolved == base_path:
                    matrix = np.eye(2, 3, dtype=np.float32)
                    config.homographies[p_resolved] = matrix
                else:
                    if ref_stars is None:
                        eroded_sky_mask = StarDetector.prepare_sky_mask(sky_mask)
                        ref_stars = StarDetector.detect_stars(base_calibrated, eroded_sky_mask)
                        logger.info(f"Detected {len(ref_stars)} stars in reference frame: {base_path.name}")
                    target_stars = StarDetector.detect_stars(frame_cal, eroded_sky_mask)
                    pts_ref, pts_target = StarMatcher.match_stars(ref_stars, target_stars)
                    if len(pts_target) >= 3:
                        matrix = TransformModel.estimate(pts_target, pts_ref)
                    if matrix is not None:
                        config.homographies[p_resolved] = matrix

            if matrix is None:
                logger.warning("Could not align frame %s; excluding it from the sky stack", p_path)

            if warp_frames:
                if matrix is None:
                    warped = frame_cal.copy()
                    coverage = np.zeros((h, w), dtype=bool)
                else:
                    warped, in_bounds = ImageWarper.warp(frame_cal, matrix, (h, w))
                    if sky_mask is not None:
                        warped_mask = ImageWarper.warp_mask(
                            sky_mask.astype(np.float32), matrix, (h, w)
                        )
                        coverage = in_bounds & (warped_mask > 0.5)
                    else:
                        coverage = in_bounds

                if config.taper_mask_edges and config.mask_taper_pixels > 0:
                    coverage = ImageWarper.compute_tapered_mask(
                        coverage, taper_radius=float(config.mask_taper_pixels)
                    )

                aligned_sky_frames.append(warped)
                sky_coverages.append(coverage)
                raw_ground_frames.append(frame_cal)

            progress_data = {"index": i, "total": len(config.star_images), "filename": p_path.name, "frame": p_path, "matrix": matrix}
            if reused_transform:
                progress_data["desc"] = f"Preparing aligned frame {i + 1}/{n_stars}: {p_path.name}"
            self.updateJob(1, progress_data)

        return AlignResult(
            homographies=config.homographies,
            aligned_sky_frames=aligned_sky_frames,
            sky_coverages=sky_coverages,
            raw_ground_frames=raw_ground_frames,
            base_calibrated=base_calibrated,
            sky_mask=sky_mask,
        )
