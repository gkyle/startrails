"""Gap filling processes image edges and reports completion after all patches."""

from concurrent.futures import CancelledError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
import torch

from support import IsolatedTestCase
from startrails.lib.file import OP_FILL_GAPS, OP_FILL_GAPS_MASK, InputFile, OutputFile
from startrails.lib.startrails.source_map import locate_sources
from startrails.models.fillGaps.model import UNet
from startrails.op.startrails.fill_gaps import FillGaps


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
            patch("startrails.op.startrails.fill_gaps.torch.load", return_value=weights),
            patch("startrails.op.startrails.fill_gaps.resolve_torch_device", return_value=torch.device("cpu")),
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
            patch("startrails.op.startrails.fill_gaps.UNet", return_value=IdentityGapModel()),
            patch("startrails.op.startrails.fill_gaps.torch.load", return_value={}),
            patch("startrails.op.startrails.fill_gaps.resolve_torch_device", return_value=torch.device("cpu")),
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

    def test_cancelled_fill_preserves_published_output_and_output_records(self):
        import startrails.app as app_module

        with (
            patch("startrails.op.startrails.fill_gaps.UNet", return_value=IdentityGapModel()),
            patch("startrails.op.startrails.fill_gaps.torch.load", return_value={}),
            patch("startrails.op.startrails.fill_gaps.resolve_torch_device", return_value=torch.device("cpu")),
        ):
            app = self.make_app()
            source = self.root / "input.png"
            image = np.full((7, 9, 3), 100, dtype=np.uint8)
            self.assertTrue(cv2.imwrite(str(source), image))
            app.project.rawInputFiles.append(InputFile(source.name, str(source)))
            original = app_module.fgm
            app_module.fgm = SimpleNamespace(FillGaps=FillGaps)
            try:
                basis = app.doStack(False, lambda *args: None, useGPU=False)
                records_before = list(app.getOutputFileList())
                extension = Path(basis.path).suffix
                filled_path, mask_path = FillGaps.suggestOutFileName(
                    str(app.project.get_output_dir()), extension, extension
                )

                def cancel(total, increment, count, done, data):
                    if increment:
                        app.activeOperation.requestInterrupt()

                # A first fill cancelled before publication leaves no phantom records.
                with self.assertRaises(CancelledError):
                    app.doFillGaps(basis, cancel)
                self.assertEqual(list(app.getOutputFileList()), records_before)
                self.assertFalse(Path(filled_path).exists())
                self.assertFalse(Path(mask_path).exists())

                filled = app.doFillGaps(basis, lambda *args: None)
                self.assertEqual(filled.operation, OP_FILL_GAPS)
                mask = next(
                    record for record in app.getOutputFileList()
                    if record.operation == OP_FILL_GAPS_MASK
                )
                previous_bytes = {
                    Path(filled.path): Path(filled.path).read_bytes(),
                    Path(mask.path): Path(mask.path).read_bytes(),
                }
                previous_metadata = (filled.sourceMap, filled.sourceStack, filled.gapMask)
                records = list(app.getOutputFileList())
                previous_candidates = locate_sources(
                    filled, app.project.rawInputFiles, 2, 2
                ).candidates
                self.assertTrue(previous_candidates)

                def assert_preserved():
                    self.assertEqual(list(app.getOutputFileList()), records)
                    for path, content in previous_bytes.items():
                        self.assertEqual(path.read_bytes(), content)
                    self.assertEqual(
                        (filled.sourceMap, filled.sourceStack, filled.gapMask),
                        previous_metadata,
                    )
                    self.assertEqual(
                        locate_sources(filled, app.project.rawInputFiles, 2, 2).candidates,
                        previous_candidates,
                    )

                with self.assertRaises(CancelledError):
                    app.doFillGaps(basis, cancel)
                assert_preserved()

                with patch("startrails.op.startrails.fill_gaps.imwrite", side_effect=OSError("disk full")):
                    with self.assertRaises(OSError):
                        app.doFillGaps(basis, lambda *args: None)
                assert_preserved()
            finally:
                app_module.fgm = original
