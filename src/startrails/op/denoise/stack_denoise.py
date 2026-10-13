"""Observable operation for freeze-ground celestial sky and stationary landscape stacking."""

from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Optional
import numpy as np

from startrails.lib.util import Observable, imwrite
from startrails.lib.denoise.config import DenoiseConfig
from startrails.lib.denoise.stacking.freeze_ground import FreezeGroundStacker
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor

logger = logging.getLogger(__name__)


class StackDenoise(Observable):
    """Executes Freeze-Ground sigma-clipped or mean stacking of sky and ground frames."""

    def __init__(self):
        super().__init__()

    def stack(
        self,
        config: DenoiseConfig,
        aligned_sky_frames: List[np.ndarray],
        sky_coverages: List[np.ndarray],
        raw_ground_frames: List[np.ndarray],
        sky_mask: np.ndarray,
        base_icc: Optional[bytes] = None,
    ) -> Optional[HorizonCompositor]:
        """Stack frames and prepare HorizonCompositor.

        Returns:
            HorizonCompositor or None if interrupted.
        """
        self.startJob(2)

        if self.shouldInterrupt():
            return None

        compositor = FreezeGroundStacker.stack_base_and_prepare_compositor(
            aligned_sky_frames=aligned_sky_frames,
            sky_coverages=sky_coverages,
            raw_ground_frames=raw_ground_frames,
            sky_mask=sky_mask,
            feather_radius=3.0,
            horizon_denoise_radius=config.horizon_denoise_radius,
            horizon_denoise_eps=config.horizon_denoise_eps,
            stack_method=getattr(config, "stack_method", "sigma_clipped"),
            sigma_clip_threshold=getattr(config, "sigma_clip_threshold", 1.2),
            sigma_clip_iterations=getattr(config, "sigma_clip_iterations", 3),
            use_gpu=config.use_gpu,
            max_workers=config.max_workers,
        )

        self.updateJob(1, compositor)

        if self.shouldInterrupt():
            return None

        # Save intermediate base stacks if paths are specified
        if config.output_path or config.sky_stack_path or config.ground_stack_path:
            folder = Path(config.output_path).resolve().parent if config.output_path else Path.cwd()
            sky_path = Path(config.sky_stack_path).resolve() if config.sky_stack_path else (folder / "sky_stack.tif")
            ground_path = Path(config.ground_stack_path).resolve() if config.ground_stack_path else (folder / "ground_stack.tif")
            try:
                imwrite(sky_path, compositor.sky_stack, convertBGR=True)
                imwrite(ground_path, compositor.ground_stack, convertBGR=True)
                config.sky_stack_path = sky_path
                config.ground_stack_path = ground_path
            except Exception as e:
                logger.warning(f"Could not save intermediate base stacks: {e}")

        self.updateJob(1, compositor)
        return compositor
