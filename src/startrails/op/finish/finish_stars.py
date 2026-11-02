"""Observable operation composing the finished star layer and writing its TIFF."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.finish.defaults import INTERMEDIATE_BIT_DEPTH, FinishSettings
from startrails.lib.finish.star_catalog import RankedStarCatalog
from startrails.lib.finish.star_effects import SparseRoundDelta, compose_star_layer
from startrails.lib.image_io import imwrite
from startrails.lib.util import Observable


class FinishStars(Observable):
    """Cancelable wrapper around composition and lossless intermediate writing.

    Catalog analysis, Round/Glow layer rendering and persistence belong to the
    workflow. This operation only composes the current in-memory layers and
    stages the derived TIFF, so effect toggles and amounts can never trigger a
    worker job or depend on stale TIFF pixels.
    """

    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__(cancel_event, cancel_check)

    def finish(
        self,
        stars: np.ndarray,
        settings: FinishSettings,
        *,
        catalog: RankedStarCatalog,
        inclusion_mask: np.ndarray,
        round_delta: Optional[SparseRoundDelta],
        glow: Optional[np.ndarray],
        output_path: Path,
        artifacts: ArtifactTransaction,
        compare: bool = False,
    ) -> Optional[Path]:
        """Compose ``S_fin`` and stage a 16-bit TIFF without publishing it.

        Returns the resolved destination once written, or None when interrupted.
        ``inclusion_mask`` is the workflow-owned included-star mask for the
        current catalog/cutoff. The caller owns the transaction so publication
        remains atomic with the project state change.
        """
        self.startJob(2)
        if self.shouldInterrupt():
            return None

        finished = compose_star_layer(
            stars,
            catalog,
            round_delta,
            glow,
            settings,
            inclusion_mask=inclusion_mask,
            compare=compare,
        )
        if self.shouldInterrupt():
            return None
        self.updateJob(1, {"desc": "Finished stars composed."})

        destination = Path(output_path).resolve()
        staged = artifacts.stage(destination)
        written = imwrite(
            staged,
            finished,
            convertBGR=True,
            bit_depth=INTERMEDIATE_BIT_DEPTH,
            compression=settings.tiff_deflate_compression,
        )
        if written != staged:
            written.unlink(missing_ok=True)
            raise OSError("Finished stars staging path changed unexpectedly; nothing was published.")
        self.updateJob(1, {"desc": "Finished stars complete."})
        return destination


__all__ = ["FinishStars"]
