"""Geometric correspondence and failure coverage on real tiny images."""

from itertools import permutations
from unittest.mock import patch

import cv2
import numpy as np

from support import IsolatedTestCase
from startrails.lib.denoise.alignment.detector import Star
from startrails.lib.denoise.alignment.matcher import StarMatcher
from startrails.lib.denoise.alignment.transform import TransformModel
from startrails.lib.denoise.alignment.warper import ImageWarper
from startrails.lib.image_io import imwrite
from startrails.lib.project_denoise import DenoiseProject
from startrails.op.denoise.align_stars import AlignStars


class AlignmentTests(IsolatedTestCase):
    def test_triangle_matching_is_independent_of_detection_order(self):
        points = np.array([[10, 10], [53, 13], [21, 79]], dtype=np.float32)
        reference = [Star(*point, 1.0) for point in points]
        for order in permutations(range(3)):
            with self.subTest(order=order):
                target = [Star(*(points[i] + [7, -4]), 1.0) for i in order]
                ref, found = StarMatcher.match_stars(reference, target)
                self.assertEqual(len(ref), 3)
                np.testing.assert_array_equal(found - ref, np.tile([7, -4], (3, 1)))

    def test_estimated_transform_and_warp_map_target_pixels_to_reference(self):
        target = np.array([[4, 4], [15, 4], [15, 15], [4, 15]], np.float32)
        reference = target + [3, 2]
        matrix = TransformModel.estimate(target, reference)
        transformed = (
            cv2.perspectiveTransform(target[None], matrix)
            if matrix.shape == (3, 3)
            else cv2.transform(target[None], matrix)
        )
        # The integer translation is exactly representable; estimation allows subpixel roundoff.
        np.testing.assert_allclose(transformed[0], reference, atol=1e-5, rtol=0)
        image = np.zeros((24, 24), np.float32)
        image[8, 9] = 1
        warped, coverage = ImageWarper.warp(image, matrix, image.shape)
        self.assertAlmostEqual(float(warped[10, 12]), 1, places=5)
        self.assertFalse(coverage[0].any())
        self.assertTrue(coverage[10, 12])

    def test_failed_matching_or_estimation_retains_ground_without_sky_coverage(self):
        base = np.full((16, 16, 3), 0.2, np.float32)
        target = np.full_like(base, 0.8)
        paths = [imwrite(self.root / name, pixels) for name, pixels in (("base.tif", base), ("target.tif", target))]
        for matches in (np.empty((0, 2), np.float32), np.array([[1, 1], [8, 2], [3, 10]], np.float32)):
            with self.subTest(matches=len(matches)):
                config = DenoiseProject(star_images=paths, base_image=paths[0], use_gpu=False, taper_mask_edges=False)
                with (
                    patch.object(StarMatcher, "match_stars", return_value=(matches, matches)),
                    patch.object(TransformModel, "estimate", return_value=None),
                    self.assertLogs("startrails.op.denoise.align_stars", level="WARNING") as logs,
                ):
                    result = AlignStars().align(
                        config, warp_frames=True, base_calibrated=base, sky_mask=np.ones(base.shape[:2])
                    )
                self.assertIn("target.tif", logs.output[0])
                self.assertFalse(result.sky_coverages[1].any())
                self.assertTrue(result.sky_coverages[0].all())
                np.testing.assert_allclose(result.raw_ground_frames[1] / 65535, target, atol=1 / 65535, rtol=0)
