"""Gap-fill progress includes partial patches at the image edges."""

from unittest.mock import patch

import cv2
import numpy as np
import torch

from support import IsolatedTestCase
from startrails.lib.file import OutputFile
from startrails.op.fillGaps import FillGaps


class IdentityGapModel(torch.nn.Module):
    def forward(self, pixels):
        return pixels, torch.zeros_like(pixels[:, 0])


class FillGapsTests(IsolatedTestCase):
    def test_progress_reaches_completion_only_after_partial_edge_patches(self):
        with (
            patch("startrails.op.fillGaps.UNet", return_value=IdentityGapModel()),
            patch("startrails.op.fillGaps.torch.load", return_value={}),
            patch("startrails.op.fillGaps.torch.cuda.is_available", return_value=False),
        ):
            filler = FillGaps()
        source = self.root / "input.png"
        image = np.full((208, 200, 3), 100, dtype=np.uint8)
        self.assertTrue(cv2.imwrite(str(source), image))
        output_path = self.root / "filled.png"
        mask_path = self.root / "mask.png"
        progress = []
        filler.addObserver(lambda total, increment, count, done, data: progress.append((total, count, done)))
        filler.fillGaps(
            OutputFile(source.name, str(source)),
            OutputFile(output_path.name, str(output_path)),
            OutputFile(mask_path.name, str(mask_path)),
        )
        # Both image dimensions cover three strides of 96 pixels, including
        # partial patches at the boundaries: nine patches in total.
        self.assertEqual(progress[-1], (9, 9, True))
        self.assertTrue(all(not done and count < total for total, count, done in progress[:-1]))
        np.testing.assert_array_equal(cv2.imread(str(output_path)), image)
