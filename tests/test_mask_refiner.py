"""Mask invariants, progress/publication ordering, and failure propagation."""

from unittest.mock import patch

import numpy as np

from support import IsolatedTestCase
from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.denoise.mask_refiner import MaskRefiner
from startrails.op.denoise.refine_mask import RefineMask


class MaskRefinerTests(IsolatedTestCase):
    def setUp(self):
        super().setUp()
        self.image = np.full((48, 80, 3), 0.02, np.float32)
        self.image[:24] = (0.2, 0.3, 0.4)
        self.mask = np.zeros((48, 80), np.float32)
        self.mask[:24] = 1

    def test_refinement_recovers_bright_sky_inside_the_search_ribbon(self):
        rough = np.zeros_like(self.mask)
        rough[:21] = 1
        result = MaskRefiner.refine(self.image, rough, search_radius=5, erosion_pixels=0, foliage_protection=False)
        # The image has sky through row 23, beyond the rough mask at row 20.
        # Check recovery within the ribbon and exclusion of definite dark ground.
        self.assertTrue(result[22].all())
        self.assertFalse(result[28].any())

    def test_uniform_masks_and_distinct_sky_ground_remain_valid_without_mutating_inputs(self):
        for mask in (np.zeros_like(self.mask), np.ones_like(self.mask), self.mask):
            for image in (self.image, self.image[..., 0]):
                with self.subTest(uniform=bool(np.all(mask == mask[0, 0])), rgb=image.ndim == 3):
                    before_image, before_mask = image.copy(), mask.copy()
                    result = MaskRefiner.refine(
                        image, mask, search_radius=3, erosion_pixels=0, foliage_protection=False
                    )
                    self.assertEqual(result.shape, mask.shape)
                    self.assertEqual(result.dtype, np.float32)
                    self.assertTrue(np.isin(result, (0, 1)).all())
                    np.testing.assert_array_equal(result[:8], mask[:8])
                    np.testing.assert_array_equal(result[-8:], mask[-8:])
                    np.testing.assert_array_equal(image, before_image)
                    np.testing.assert_array_equal(mask, before_mask)

    def refine(self, operation, path):
        return operation.refine(
            self.image, self.mask, search_radius=3, erosion_pixels=0, foliage_protection=False, export_path=path
        )

    def test_completion_follows_export_and_progress_is_monotonic(self):
        operation = RefineMask()
        path = self.root / "mask.png"
        counts = []

        def notify(total, increment, count, done, data):
            counts.append(count)
            if done:
                self.assertTrue(path.is_file())

        operation.addObserver(notify)
        result = self.refine(operation, path)
        self.assertEqual(counts, sorted(counts))
        np.testing.assert_array_equal(MaskHandler.load_mask(path), result)

    def test_cancelled_refinement_does_not_export_or_report_success(self):
        operation = RefineMask()
        path = self.root / "mask.png"
        done_events = []

        def notify(total, increment, count, done, data):
            done_events.append(done)
            if data and data.get("completed_tiles") == 1:
                operation.requestInterrupt()

        operation.addObserver(notify)
        # Force two small partitions to exercise cancellation during processing,
        # without requiring a production-sized image or a particular worker count.
        with patch.object(MaskRefiner, "_refinement_regions", return_value=[(0, 0, 40, 48), (40, 0, 80, 48)]):
            self.assertIsNone(self.refine(operation, path))
        self.assertFalse(path.exists())
        self.assertFalse(any(done_events))

    def test_cancellation_during_save_notification_preserves_existing_mask(self):
        operation = RefineMask()
        path = self.root / "mask.png"
        path.write_bytes(b"existing mask")

        def notify(total, increment, count, done, data):
            if data and data.get("desc") == "Saving refined sky mask...":
                operation.requestInterrupt()

        operation.addObserver(notify)
        self.assertIsNone(self.refine(operation, path))
        self.assertEqual(path.read_bytes(), b"existing mask")

    def test_region_failure_propagates_without_export(self):
        path = self.root / "mask.png"
        with (
            patch.object(MaskRefiner, "_refinement_regions", return_value=[(0, 0, 40, 48), (40, 0, 80, 48)]),
            patch.object(MaskRefiner, "_refine_region", side_effect=OSError("region failed")),
        ):
            with self.assertRaisesRegex(OSError, "region failed"):
                self.refine(RefineMask(), path)
        self.assertFalse(path.exists())
