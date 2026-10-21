"""Observable operation for interactive horizon composition and final export."""

from __future__ import annotations
import logging
from contextlib import nullcontext
from startrails.lib.artifacts import ArtifactTransaction
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

from startrails.lib.util import imwrite
from startrails.op.denoise.base import DenoiseOperation
from startrails.lib.project_denoise import DenoiseProject
from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor

logger = logging.getLogger(__name__)


class ComposeHorizon(DenoiseOperation):
    """Composites celestial sky and landscape ground with horizon denoising and tuning."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)
        self.last_gradient_mask: Optional[np.ndarray] = None

    def compose(
        self,
        compositor: HorizonCompositor,
        config: DenoiseProject,
        *,
        write_output: bool,
        artifacts: Optional[ArtifactTransaction] = None,
    ) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Evaluate horizon composite and optionally write final output to disk.

        Returns:
            (stacked_array, written_path) or None if interrupted.
        """
        self.startJob(2)

        if self.shouldInterrupt():
            return None

        stacked = compositor.composite(
            horizon_blend_percent=config.horizon_blend_percent,
            horizon_denoise_strength=config.horizon_denoise_strength,
            denoise_enabled=config.denoise_horizon_band,
            horizon_blur_radius=config.horizon_blur_radius,
            enable_corrections=config.enable_horizon_corrections,
            horizon_color_denoise_strength=config.horizon_color_denoise_strength,
            horizon_value_denoise_strength=config.horizon_value_denoise_strength,
            cancel_check=self.shouldInterrupt,
        )

        if stacked is None or self.shouldInterrupt():
            return None

        self.updateJob(1, {"desc": "Horizon blended. Saving composite..." if write_output and config.output_path else "Horizon blended.", "stacked": stacked, "color_space": "rgb"})

        if self.shouldInterrupt():
            return None

        written_path: Optional[Path] = None
        if write_output and config.output_path:
            output_path = Path(config.output_path).resolve()
            transaction = artifacts or ArtifactTransaction(self.shouldInterrupt)
            with nullcontext(transaction) if artifacts is not None else transaction:
                imwrite(transaction.stage(output_path), stacked, convertBGR=True,
                        quality=config.jpeg_quality, optimize=config.jpeg_optimize)

                if config.export_gradient_mask and compositor.gradient_mask is not None:
                    grad_mask_out = (
                        config.artifact_path("gradient_mask")
                    )
                    gradient_mask = compositor.gradient_mask
                    MaskHandler.save_mask(gradient_mask, transaction.stage(grad_mask_out))
                    config.gradient_mask_path = grad_mask_out
                    self.last_gradient_mask = gradient_mask
                if artifacts is None:
                    transaction.commit()
            written_path = output_path

        self.updateJob(1, {"desc": "Composite complete", "stacked": stacked, "color_space": "rgb", "path": written_path, "gradient_mask": self.last_gradient_mask})
        return stacked, written_path
