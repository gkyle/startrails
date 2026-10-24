"""Gap filling processes image edges and reports completion after all patches."""

from unittest.mock import patch

import cv2
import numpy as np
import torch

from support import IsolatedTestCase
from startrails.lib.file import OutputFile
from startrails.models.fillGaps.model import UNet
from startrails.op.fillGaps import FillGaps


class IdentityGapModel(torch.nn.Module):
    def forward(self, pixels):
        return pixels, torch.zeros_like(pixels[:, 0])


class FillGapsTests(IsolatedTestCase):
    def test_real_model_fills_partial_edges_and_small_images(self):
        # Keep the real encoder/decoder shape constraints, with deterministic
        # predictions: mid-gray pixels and a mask that selects every prediction.
        weights = UNet(in_channels=3, out_channels=4).state_dict()
        weights["final_conv.weight"].zero_()
        weights["final_conv.bias"].zero_()
        with (
            patch("startrails.op.fillGaps.torch.load", return_value=weights),
            patch("startrails.op.fillGaps.torch.cuda.is_available", return_value=False),
        ):
            filler = FillGaps()
        previous_threads = torch.get_num_threads()
        torch.set_num_threads(1)
        self.addCleanup(torch.set_num_threads, previous_threads)
        # 200 leaves the same 8-pixel remainder as the reported 4040-pixel
        # height; check both axes, plus an image smaller than the model minimum.
        for shape, dtype in (((200, 200, 3), np.uint8), ((7, 9, 3), np.uint16)):
            with self.subTest(shape=shape, dtype=dtype):
                source = self.root / "input.png"
                output_path = self.root / "filled.png"
                mask_path = self.root / "mask.png"
                image = np.full(shape, 100, dtype=dtype)
                self.assertTrue(cv2.imwrite(str(source), image))
                filled, mask = filler.fillGaps(
                    OutputFile(source.name, str(source)),
                    OutputFile(output_path.name, str(output_path)),
                    OutputFile(mask_path.name, str(mask_path)),
                )
                max_value = np.iinfo(dtype).max
                expected_image = np.full(shape, max_value // 2, dtype=dtype)
                expected_mask = np.full(shape, max_value, dtype=dtype)
                np.testing.assert_array_equal(filled, expected_image)
                np.testing.assert_array_equal(mask, expected_mask)
                np.testing.assert_array_equal(
                    cv2.imread(str(output_path), cv2.IMREAD_UNCHANGED), expected_image,
                )
                np.testing.assert_array_equal(
                    cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED), expected_mask,
                )

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
