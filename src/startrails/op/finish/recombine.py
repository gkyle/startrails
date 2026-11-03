"""Observable operation for recombining finished starless and stars layers."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Optional, Tuple, Union
import numpy as np

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.finish.composition import recombine_layers
from startrails.lib.finish.defaults import FinishSettings
from startrails.lib.image_io import imwrite
from startrails.lib.util import Observable


class Recombine(Observable):
    """Observable operation for layer recombination and optional export."""

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)

    def recombine(
        self,
        finished_starless: np.ndarray,
        stars: np.ndarray,
        negative_residual: np.ndarray,
        settings: FinishSettings,
        *,
        bit_depth: int,
        output_path: Optional[Union[str, Path]] = None,
        artifacts: Optional[ArtifactTransaction] = None,
    ) -> Optional[Tuple[np.ndarray, Optional[Path]]]:
        """Execute single-layer recombination and optionally write output.

        Args:
            finished_starless: Clamped starless array (H, W, 3).
            stars: Separated positive star layer S (H, W, 3), used unchanged.
            negative_residual: Unscaled negative residual array (H, W, 3).
            settings: Resolved Finish settings with Stars Amount, blend mode and codec options.
            bit_depth: Required source bit depth for export; caller chooses the source-matching output path.
            output_path: Optional file path to export image artifact.
            artifacts: Optional transaction to stage and commit output.

        Returns:
            (composite_array, written_path) or None if cancelled.
        """
        self.startJob(2)
        if self.shouldInterrupt():
            return None

        composite = recombine_layers(
            finished_starless,
            stars,
            negative_residual,
            settings.star_amount,
            settings.blend_mode,
        )

        self.updateJob(1, {"desc": "Layers recombined."})
        if self.shouldInterrupt():
            return None

        written_path: Optional[Path] = None
        if output_path is not None:
            dest = Path(output_path).resolve()
            transaction = artifacts or ArtifactTransaction(self.shouldInterrupt)
            with nullcontext(transaction) if artifacts is not None else transaction:
                stage_path = transaction.stage(dest)
                written = imwrite(
                    stage_path,
                    composite,
                    convertBGR=True,
                    bit_depth=bit_depth,
                    quality=settings.jpeg_quality,
                    optimize=settings.jpeg_optimize,
                    compression=settings.tiff_deflate_compression,
                )
                if written != stage_path:
                    written.unlink(missing_ok=True)
                    raise OSError("Export staging path changed unexpectedly; output was not published.")
                if artifacts is None:
                    transaction.commit()
            written_path = dest

        self.updateJob(1, {"desc": "Recombination complete."})
        return composite, written_path
