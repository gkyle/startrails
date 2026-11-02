"""Numerical contracts for Finish two-scale Structure/Detail sharpening."""

from __future__ import annotations

import unittest

import numpy as np

from startrails.lib.finish.starless_filters import (
    LOCAL_HEADROOM_FRACTION,
    MAX_LUMINANCE_DELTA,
    sharpen_starless,
)
from startrails.lib.image_io import rgb_luminance
from startrails.op.finish.sharpen_starless import SharpenStarless


def _broad_pattern(height: int = 96, width: int = 256) -> np.ndarray:
    x = np.arange(width)[None, :]
    return np.broadcast_to(0.05 * np.cos(2 * np.pi * x / 160.0), (height, width))


def _fine_pattern(height: int = 96, width: int = 256) -> np.ndarray:
    y = np.arange(height)[:, None]
    x = np.arange(width)[None, :]
    return 0.01 * np.cos(2 * np.pi * x / 4.0) * np.cos(2 * np.pi * y / 4.0)


def _gray_image(pattern: np.ndarray, level: float = 0.3) -> np.ndarray:
    return np.repeat((level + pattern)[..., np.newaxis], 3, axis=2).astype(np.float32)


class TestStarlessSharpening(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(7)
        self.image = (0.08 + 0.5 * rng.random((48, 71, 3))).astype(np.float32)
        self.mask = np.ones(self.image.shape[:2], np.float32)

    def test_zero_amounts_are_exact_identity_and_inputs_are_unmodified(self):
        image_before = self.image.copy()
        mask_before = self.mask.copy()
        result = sharpen_starless(self.image, self.mask, 0.0, 0.0)
        np.testing.assert_array_equal(result, self.image)
        self.assertIsNot(result, self.image)
        np.testing.assert_array_equal(self.image, image_before)
        np.testing.assert_array_equal(self.mask, mask_before)

    def test_structure_and_detail_act_on_independent_spatial_scales(self):
        broad = _gray_image(_broad_pattern())
        fine = _gray_image(_fine_pattern())
        mask = np.ones(broad.shape[:2], np.float32)

        broad_structure = sharpen_starless(broad, mask, 100.0, 0.0)
        broad_detail = sharpen_starless(broad, mask, 0.0, 100.0)
        fine_structure = sharpen_starless(fine, mask, 100.0, 0.0)
        fine_detail = sharpen_starless(fine, mask, 0.0, 100.0)

        interior = np.s_[20:76, 20:236]
        broad_change = float(np.mean(np.abs((broad_structure - broad)[interior][..., 0])))
        broad_detail_change = float(np.mean(np.abs((broad_detail - broad)[interior][..., 0])))
        fine_change = float(np.mean(np.abs((fine_detail - fine)[interior][..., 0])))
        fine_structure_change = float(np.mean(np.abs((fine_structure - fine)[interior][..., 0])))

        self.assertGreater(broad_change, 0.002)
        self.assertLess(broad_detail_change, 1e-4)
        self.assertGreater(fine_change, 5e-4)
        self.assertLess(fine_structure_change, 1e-4)

    def test_sky_delta_is_protected_by_soft_mask_and_ground_is_exact(self):
        ground_mask = np.zeros_like(self.mask)
        ground_mask[:, : self.image.shape[1] // 2] = 1.0

        full = sharpen_starless(self.image, self.mask, 60.0, 40.0)
        protected = sharpen_starless(self.image, ground_mask, 60.0, 40.0)
        half = sharpen_starless(self.image, np.full_like(self.mask, 0.5), 60.0, 40.0)

        np.testing.assert_array_equal(
            protected[:, self.image.shape[1] // 2 :], self.image[:, self.image.shape[1] // 2 :]
        )
        self.assertGreater(float(np.max(np.abs(protected - self.image))), 0.0)
        expected_half = self.image + 0.5 * (full - self.image)
        np.testing.assert_allclose(half, expected_half, atol=1e-7, rtol=0)

    def test_ground_luminance_does_not_bleed_across_the_mask_boundary(self):
        """Normalized masked bands make sky output independent of ground pixels."""
        sky_pattern = _broad_pattern(96, 128) + _fine_pattern(96, 128)
        sky = _gray_image(sky_pattern)
        sky_mask = np.zeros(sky.shape[:2], np.float32)
        sky_mask[:, :64] = 1.0

        dark_ground = sky.copy()
        bright_ground = sky.copy()
        dark_ground[:, 64:] = 0.0
        bright_ground[:, 64:] = 1.0

        dark_result = sharpen_starless(dark_ground, sky_mask, 100.0, 100.0)
        bright_result = sharpen_starless(bright_ground, sky_mask, 100.0, 100.0)
        np.testing.assert_array_equal(dark_result[:, :64], bright_result[:, :64])
        np.testing.assert_array_equal(dark_result[:, 64:], dark_ground[:, 64:])
        np.testing.assert_array_equal(bright_result[:, 64:], bright_ground[:, 64:])

    def test_max_channel_headroom_keeps_gain_scalar_without_clipping(self):
        x = np.arange(128, dtype=np.float32)
        scale = 1.0 + 0.05 * np.cos(2 * np.pi * x / 64.0)
        color = np.array([0.95, 0.6, 0.5], np.float32)
        image = np.broadcast_to(color[None, None, :] * scale[None, :, None], (64, 128, 3)).astype(np.float32)
        result = sharpen_starless(image, np.ones(image.shape[:2], np.float32), 100.0, 0.0)

        self.assertLessEqual(float(result.max()), 1.0 + 1e-6)
        gain = result / image
        np.testing.assert_allclose(gain[..., 0], gain[..., 1], atol=1e-6, rtol=0)
        np.testing.assert_allclose(gain[..., 2], gain[..., 1], atol=1e-6, rtol=0)

    def test_dark_and_constant_images_remain_finite_and_neutral(self):
        for value in (0.0, 0.25):
            with self.subTest(value=value):
                image = np.full((23, 31, 3), value, np.float32)
                result = sharpen_starless(image, np.ones((23, 31), np.float32), 100.0, 100.0)
                self.assertTrue(np.isfinite(result).all())
                np.testing.assert_array_equal(result, image)

        dark = np.full((16, 16, 3), 1e-7, np.float32)
        dark[:, :8] = 0.0
        result = sharpen_starless(dark, np.ones((16, 16), np.float32), 100.0, 100.0)
        self.assertTrue(np.isfinite(result).all())
        self.assertGreaterEqual(float(result.min()), 0.0)
        self.assertLessEqual(float(result.max()), 1.0)
        np.testing.assert_array_equal(result[:, :8], dark[:, :8])

    def test_luminance_delta_and_color_gain_are_bounded(self):
        x = np.arange(80, dtype=np.float32)
        luminance = (0.3 + 0.12 * np.sin(12 * np.pi * x / 80.0)).astype(np.float32)
        luminance = np.broadcast_to(luminance[None, :], (64, 80)).copy()
        image = np.stack((luminance * 1.05, luminance, luminance * 0.8), axis=2).astype(np.float32)
        result = sharpen_starless(image, np.ones(image.shape[:2], np.float32), 100.0, 100.0)

        source_luminance = rgb_luminance(image)
        result_luminance = rgb_luminance(result)
        cap = np.minimum(
            MAX_LUMINANCE_DELTA,
            LOCAL_HEADROOM_FRACTION * np.minimum(source_luminance, 1.0 - source_luminance),
        )
        self.assertTrue(np.all(np.abs(result_luminance - source_luminance) <= cap + 1e-6))
        self.assertGreaterEqual(float(result.min()), 0.0)
        self.assertLessEqual(float(result.max()), 1.0)

        # Multiplicative gain preserves channel ratios away from clipping.
        gain = result / image
        np.testing.assert_allclose(gain[..., 0], gain[..., 1], atol=1e-6, rtol=0)
        np.testing.assert_allclose(gain[..., 2], gain[..., 1], atol=1e-6, rtol=0)
        self.assertTrue(np.all(gain <= 1.0 + LOCAL_HEADROOM_FRACTION + 1e-6))

    def test_odd_and_tiny_dimensions(self):
        for shape in ((1, 1), (2, 3), (17, 9), (5, 64)):
            with self.subTest(shape=shape):
                pattern = np.linspace(-0.02, 0.02, shape[1], dtype=np.float32)[None, :]
                image = _gray_image(np.broadcast_to(pattern, shape).copy())
                result = sharpen_starless(image, np.ones(shape, np.float32), 100.0, 100.0)
                self.assertEqual(result.shape, image.shape)
                self.assertTrue(np.isfinite(result).all())

    def test_chunk_halos_do_not_create_seams(self):
        rng = np.random.default_rng(11)
        image = _gray_image(_fine_pattern(128, 160) + _broad_pattern(128, 160))
        image += (0.02 * rng.standard_normal(image.shape)).astype(np.float32)
        image = np.clip(image, 0.0, 1.0)
        mask = np.ones(image.shape[:2], np.float32)

        reference = sharpen_starless(image, mask, 45.0, 65.0, chunk_rows=image.shape[0])
        for chunk_rows in (1, 3, 17, 63):
            with self.subTest(chunk_rows=chunk_rows):
                np.testing.assert_array_equal(
                    sharpen_starless(image, mask, 45.0, 65.0, chunk_rows=chunk_rows),
                    reference,
                )

    def test_observable_operation_matches_function_and_cancels_without_mutation(self):
        image_before = self.image.copy()
        expected = sharpen_starless(self.image, self.mask, 70.0, 30.0)
        actual = SharpenStarless().sharpen(self.image, self.mask, structure_amount=70.0, detail_amount=30.0)
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(self.image, image_before)
        self.assertIsNone(
            SharpenStarless(cancel_check=lambda: True).sharpen(
                self.image,
                self.mask,
                structure_amount=70.0,
                detail_amount=30.0,
            )
        )


if __name__ == "__main__":
    unittest.main()
