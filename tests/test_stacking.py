"""Analytical CPU reductions and partition/storage equivalence."""

import numpy as np

from support import IsolatedTestCase
from startrails.lib.denoise.stacking.disk_buffer import DiskFrameBuffer
from startrails.lib.denoise.stacking.freeze_ground import FreezeGroundStacker


class StackingTests(IsolatedTestCase):
    def stack(self, frames, coverages=None, method="mean", **kwargs):
        return FreezeGroundStacker.stack_frames(
            frames,
            coverages,
            method=method,
            sigma_threshold=1.2,
            iterations=3,
            use_gpu=False,
            max_workers=kwargs.pop("max_workers", 1),
            **kwargs,
        )

    def test_mean_respects_weighted_and_boolean_coverage_including_holes(self):
        frames = [np.full((7, 5, 3), value, np.float32) for value in (0.2, 0.8)]
        for floating in (False, True):
            with self.subTest(weighted=floating):
                masks = [np.ones((7, 5), np.float32 if floating else bool) for _ in frames]
                masks[0][:, 0] = 0
                for mask in masks:
                    mask[:, 1] = 0
                if floating:
                    masks[0][:, 2:] = 0.25
                    masks[1][:, 2:] = 0.75
                result = self.stack(frames, masks, chunk_rows=3)
                expected = np.full_like(result, 0.65 if floating else 0.5)
                expected[:, 0] = 0.8
                expected[:, 1] = 0
                np.testing.assert_allclose(result, expected, atol=1e-7, rtol=0)
                self.assertEqual(result.dtype, np.float32)
                self.assertTrue(np.isfinite(result).all())

    def test_sigma_clipping_removes_an_outlier_and_preserves_two_sample_fallback(self):
        frames = [np.full((7, 5), value, np.float32) for value in (0.2, 0.2, 0.2, 0.9)]
        np.testing.assert_allclose(self.stack(frames, method="sigma_clipped"), 0.2, atol=1e-7, rtol=0)
        np.testing.assert_allclose(
            self.stack(frames[:1] + frames[-1:], method="sigma_clipped"), 0.55, atol=1e-7, rtol=0
        )

    def test_disk_and_list_reductions_match_across_chunks_and_workers(self):
        rng = np.random.default_rng(31)
        frames = rng.integers(0, 65535, (4, 11, 5, 3), dtype=np.uint16)
        expected = frames.astype(np.float32).mean(axis=0) / 65535
        with DiskFrameBuffer(frames.shape, frames.dtype, scratch_dir=self.root, window_bytes=33) as buffer:
            for index, frame in enumerate(frames):
                buffer.write_frame(index, frame)
            for storage in (list(frames), buffer):
                for rows, workers in ((1, 1), (3, 2)):
                    with self.subTest(disk=storage is buffer, rows=rows, workers=workers):
                        actual = self.stack(storage, chunk_rows=rows, max_workers=workers)
                        np.testing.assert_allclose(actual, expected, atol=1e-7, rtol=0)

    def test_single_frame_normalizes_integer_input_without_mutating_it(self):
        pixels = np.array([[0, 255]], np.uint8)
        np.testing.assert_array_equal(self.stack([pixels]), [[0, 1]])
        np.testing.assert_array_equal(pixels, [[0, 255]])
        with self.assertRaises(ValueError):
            self.stack([])
