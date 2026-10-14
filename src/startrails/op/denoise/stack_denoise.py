"""Observable operation for freeze-ground celestial sky and stationary landscape stacking."""

from __future__ import annotations
import logging
from contextlib import nullcontext
from startrails.lib.artifacts import ArtifactTransaction
from pathlib import Path
from typing import List, Optional
import numpy as np

from startrails.lib.util import imwrite
from startrails.op.denoise.base import DenoiseOperation
from startrails.lib.denoise.config import DenoiseConfig
from startrails.lib.denoise.io.mask import MaskHandler
from startrails.lib.denoise.stacking.freeze_ground import FreezeGroundStacker
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor

logger = logging.getLogger(__name__)


class StackDenoise(DenoiseOperation):
    """Executes Freeze-Ground sigma-clipped or mean stacking of sky and ground frames."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)

    def stack(
        self,
        config: DenoiseConfig,
        aligned_sky_frames: List[np.ndarray],
        sky_coverages: List[np.ndarray],
        raw_ground_frames: List[np.ndarray],
        sky_mask: np.ndarray,
        base_icc: Optional[bytes] = None,
        artifacts: Optional[ArtifactTransaction] = None,
    ) -> Optional[HorizonCompositor]:
        """Stack frames and prepare HorizonCompositor.

        Returns:
            HorizonCompositor or None if interrupted.
        """
        n_sky = len(aligned_sky_frames)
        n_ground = len(raw_ground_frames)
        total_steps = n_sky + n_ground + 1
        self.startJob(total_steps)

        if self.shouldInterrupt():
            return None

        def _on_frame_progress(inc: int, data: Optional[dict] = None):
            self.updateJob(inc, data)

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
            progress_callback=_on_frame_progress,
            should_interrupt=self.shouldInterrupt,
        )

        if compositor is None or self.shouldInterrupt():
            return None

        self.updateJob(0, {"desc": "Saving base stacks and composite..."})

        # Save intermediate base stacks, composite, and gradient mask if paths are specified
        if config.output_path or config.sky_stack_path or config.ground_stack_path:
            folder = (
                Path(config.output_path).resolve().parent
                if config.output_path
                else (Path(config.sky_stack_path).resolve().parent if config.sky_stack_path else Path.cwd())
            )
            sky_path = Path(config.sky_stack_path).resolve() if config.sky_stack_path else (folder / "sky_stack.tif")
            ground_path = Path(config.ground_stack_path).resolve() if config.ground_stack_path else (folder / "ground_stack.tif")
            base_comp_path = folder / "base_composite.tif"
            output_path = Path(config.output_path).resolve() if config.output_path else (folder / "composite.tif")
            grad_mask_path = Path(config.gradient_mask_path).resolve() if config.gradient_mask_path else (folder / "gradient_mask.png")
            transaction = artifacts or ArtifactTransaction(self.shouldInterrupt)
            with nullcontext(transaction) if artifacts is not None else transaction:
                imwrite(transaction.stage(sky_path), compositor.sky_stack, convertBGR=True)
                imwrite(transaction.stage(ground_path), compositor.ground_stack, convertBGR=True)
                imwrite(transaction.stage(base_comp_path), compositor.base_composite, convertBGR=True)
                imwrite(transaction.stage(output_path), compositor.base_composite, convertBGR=True)
                if compositor.gradient_mask is not None:
                    MaskHandler.save_mask(compositor.gradient_mask, transaction.stage(grad_mask_path))
                if artifacts is None:
                    transaction.commit()
            config.sky_stack_path = sky_path
            config.ground_stack_path = ground_path
            config.output_path = output_path
            config.gradient_mask_path = grad_mask_path

        self.updateJob(1, {"desc": "Stacking complete", "stage": "done", "compositor": compositor})
        return compositor
