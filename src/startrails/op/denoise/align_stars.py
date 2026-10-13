"""Observable operation for celestial star alignment and frame warping."""

from __future__ import annotations
from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import numpy as np

from startrails.lib.util import Observable, imread
from startrails.lib.denoise.config import DenoiseConfig
from startrails.lib.denoise.io.mask import MaskHandler
from startrails.lib.denoise.calibration.dark import DarkCalibrator
from startrails.lib.denoise.calibration.flat import FlatCalibrator
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
    base_icc: Optional[bytes] = None
    sky_mask: Optional[np.ndarray] = None


class AlignStars(Observable):
    """Detects stars, matches asterisms, and estimates homographies across frames."""

    def __init__(self):
        super().__init__()

    @staticmethod
    def prepare_calibrator(config: DenoiseConfig) -> Callable[[np.ndarray], np.ndarray]:
        """Prepare dark and flat master calibration frames if configured."""
        master_dark: Optional[np.ndarray] = None
        if config.noise_images:
            darks = [imread(p, to_rgb=True, as_float=True) for p in config.noise_images]
            master_dark = DarkCalibrator.compute_master_dark(darks, use_gpu=config.use_gpu)

        master_flat: Optional[np.ndarray] = None
        if config.vignetting_images:
            flats = [imread(p, to_rgb=True, as_float=True) for p in config.vignetting_images]
            master_flat = FlatCalibrator.compute_master_flat(flats, master_dark=master_dark, use_gpu=config.use_gpu)

        def calibrate(img: np.ndarray) -> np.ndarray:
            if master_dark is not None:
                img = DarkCalibrator.apply_dark(img, master_dark)
            if master_flat is not None:
                img = FlatCalibrator.apply_flat(img, master_flat)
            return img

        return calibrate

    @staticmethod
    def get_base_image_path(config: DenoiseConfig) -> Path:
        """Resolve base reference frame path."""
        if config.base_image:
            return Path(config.base_image).resolve()
        if config.star_images:
            mid_idx = len(config.star_images) // 2
            return Path(config.star_images[mid_idx]).resolve()
        raise ValueError("No star images provided in configuration.")

    def align(
        self,
        config: DenoiseConfig,
        warp_frames: bool = True,
        sky_mask: Optional[np.ndarray] = None,
        base_calibrated: Optional[np.ndarray] = None,
    ) -> Optional[AlignResult]:
        """Align all star images in config to base reference frame.

        Args:
            config: Configuration specifying star_images, base_image, and alignment parameters.
            warp_frames: Whether to warp images and produce aligned_sky_frames and coverages.
            sky_mask: Pre-computed or user-defined sky mask (H, W). If None, resolved from config.
            base_calibrated: Pre-loaded and calibrated base image array. If None, loaded from disk.

        Returns:
            AlignResult or None if interrupted.
        """
        if not config.star_images:
            raise ValueError("No star images provided in configuration.")

        n_stars = len(config.star_images)
        self.startJob(n_stars)

        calibrate_fn = self.prepare_calibrator(config)
        base_path = self.get_base_image_path(config)

        if base_calibrated is None:
            base_raw = imread(base_path, to_rgb=True, as_float=True)
            base_calibrated = calibrate_fn(base_raw)
        h, w = base_calibrated.shape[:2]

        if sky_mask is None:
            sky_mask = MaskHandler.create_mask(
                shape=(h, w),
                mask_path=config.mask_path,
                mask_array=config.mask_array,
            )

        eroded_sky_mask = StarDetector.prepare_sky_mask(sky_mask)

        # Detect stars in base frame
        ref_stars = StarDetector.detect_stars(base_calibrated, eroded_sky_mask)
        logger.info(f"Detected {len(ref_stars)} stars in reference frame: {base_path.name}")

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
                frame_raw = imread(p_path, to_rgb=True, as_float=True)
                frame_cal = calibrate_fn(frame_raw)

            # Homography estimation
            matrix = config.homographies.get(p_resolved)
            if matrix is None and p_resolved in config.homographies:
                matrix = config.homographies[p_resolved]

            if matrix is None:
                if p_resolved == base_path:
                    matrix = np.eye(2, 3, dtype=np.float32)
                    config.homographies[p_resolved] = matrix
                else:
                    target_stars = StarDetector.detect_stars(frame_cal, eroded_sky_mask)
                    pts_ref, pts_target = StarMatcher.match_stars(ref_stars, target_stars)
                    if len(pts_target) >= 3:
                        matrix = TransformModel.estimate(pts_target, pts_ref)
                    if matrix is not None:
                        config.homographies[p_resolved] = matrix

            if warp_frames:
                if matrix is None:
                    warped = frame_cal.copy()
                    coverage = (sky_mask > 0.5) if sky_mask is not None else np.ones((h, w), dtype=bool)
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

            self.updateJob(1, {"index": i, "frame": p_path, "matrix": matrix})

        return AlignResult(
            homographies=config.homographies,
            aligned_sky_frames=aligned_sky_frames,
            sky_coverages=sky_coverages,
            raw_ground_frames=raw_ground_frames,
            base_calibrated=base_calibrated,
            base_icc=None,
            sky_mask=sky_mask,
        )
