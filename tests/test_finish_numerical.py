"""Finish numerical contracts, ordinary image artifacts and export behavior."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from startrails.lib.finish.composition import blend_denoise, compute_denoise_endpoint_signature, recombine_layers
from startrails.lib.finish.defaults import BLEND_ADD, BLEND_SCREEN, FINISH_DEFAULTS, SCOPE_SKY_ONLY, SCOPE_WHOLE_IMAGE
from startrails.lib.finish.separation import compute_separation_signature, star_residual
from startrails.lib.image_io import imread, normalize_image, quantize_image
from startrails.op.finish.recombine import Recombine
from startrails.op.finish.separate_stars import SeparateStars


class TestFinishNumerical(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = np.array([[[0.2, 0.5, 0.8]], [[0.1, 0.4, 0.7]], [[0.3, 0.6, 0.9]]], np.float32)
        self.model = np.full_like(self.source, 0.4)
        self.mask = np.array([[1], [0.5], [0]], np.float32)
        self.source = normalize_image(quantize_image(self.source, bit_depth=8))
        self.paths = dict(
            starless_path=self.root / "starless.tif",
            stars_path=self.root / "stars.tif",
            chunk_rows=1,
            settings=FINISH_DEFAULTS,
        )

    def separate(self):
        return SeparateStars().separate(self.source, self.model, self.mask, **self.paths)

    def read_separation(self):
        starless_file, stars_file = self.separate()
        return (
            imread(starless_file.path, to_rgb=True, as_float=True),
            imread(stars_file.path, to_rgb=True, as_float=True),
        )

    def test_separation_images_preserve_soft_mask_precision_and_derive_signed_residual(self):
        base, stars = self.read_separation()
        expected = np.stack((self.model[0], (self.source[1] + self.model[1]) / 2, self.source[2]))
        # Integer TIFF rounds once to the nearest 16-bit sample.
        np.testing.assert_allclose(base, expected, atol=0.5 / 65535 + np.finfo(np.float32).eps, rtol=0)
        eight_bit_base = normalize_image(quantize_image(expected, bit_depth=8))
        self.assertGreater(float(np.max(abs(eight_bit_base - expected))), 1 / 65535)
        residual = star_residual(self.source, base)
        self.assertLess(residual[0, 0, 0], 0)
        self.assertGreater(residual[0, 0, 2], 0)
        np.testing.assert_allclose(stars, np.maximum(residual, 0), atol=0.5 / 65535 + np.finfo(np.float32).eps, rtol=0)
        np.testing.assert_array_equal(base[2], self.source[2])
        np.testing.assert_array_equal(stars[2], 0)
        self.assertEqual(imread(self.paths["starless_path"]).dtype, np.uint16)
        self.assertEqual(imread(self.paths["stars_path"]).dtype, np.uint16)
        self.assertEqual({p.name for p in self.root.iterdir()}, {"starless.tif", "stars.tif"})

    def test_block_size_independence_and_unmodified_inputs(self):
        source_before, model_before, mask_before = self.source.copy(), self.model.copy(), self.mask.copy()
        first, _ = self.read_separation()
        SeparateStars().separate(self.source, self.model, self.mask, **(self.paths | {"chunk_rows": 3}))
        np.testing.assert_array_equal(imread(self.paths["starless_path"], to_rgb=True, as_float=True), first)
        for original, before in ((self.source, source_before), (self.model, model_before), (self.mask, mask_before)):
            np.testing.assert_array_equal(original, before)

    def test_failed_or_cancelled_separation_preserves_previous_images(self):
        self.separate()
        before = {p: p.read_bytes() for p in self.root.iterdir()}
        self.mask[-1] = np.nan
        with self.assertRaises(ValueError):
            self.separate()
        self.mask[-1] = 0
        operation = SeparateStars()
        operation.addObserver(lambda total, increment, *args: operation.requestInterrupt() if increment else None)
        self.assertIsNone(operation.separate(self.source, self.model, self.mask, **self.paths))
        self.assertEqual({p: p.read_bytes() for p in self.root.iterdir()}, before)

    def test_separation_export_failure_does_not_publish_partial_pair(self):
        self.separate()
        before = {p: p.read_bytes() for p in self.root.iterdir()}
        from startrails.op.finish import separate_stars as operation_module

        original_write = operation_module.imwrite
        writes = 0

        def write_or_fail(path, pixels, **kwargs):
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError("disk full")
            return original_write(path, pixels, **kwargs)

        # Writer failures propagate, while the transaction retains both old images.
        with patch.object(operation_module, "imwrite", side_effect=write_or_fail):
            with self.assertRaises(OSError):
                self.separate()
        self.assertEqual({p: p.read_bytes() for p in self.root.iterdir()}, before)

    def test_invalid_mask_does_not_publish_images(self):
        for mask in (self.mask.astype(np.uint8), np.full_like(self.mask, np.nan), np.ones((1, 1), np.float32)):
            with self.subTest(mask=mask):
                with self.assertRaises(ValueError):
                    SeparateStars().separate(self.source, self.model, mask, **self.paths)
                self.assertFalse(self.paths["starless_path"].exists())
                self.assertFalse(self.paths["stars_path"].exists())
        self.assertFalse(list(self.root.glob(".artifact-*")))
        with self.assertRaises(ValueError):
            star_residual(np.zeros((1, 1, 3), np.uint16), np.zeros((1, 1, 3), np.uint16))

    def test_denoise_endpoints_scopes_and_soft_boundary(self):
        base = self.model
        full = np.full_like(base, 0.6)
        np.testing.assert_array_equal(blend_denoise(base, full, self.mask, 0, SCOPE_SKY_ONLY), base)
        np.testing.assert_allclose(blend_denoise(base, full, self.mask, 100, SCOPE_WHOLE_IMAGE), full)
        expected = np.array([[[0.6] * 3], [[0.5] * 3], [[0.4] * 3]], np.float32)
        np.testing.assert_allclose(blend_denoise(base, full, self.mask, 100, SCOPE_SKY_ONLY), expected)
        for scope in (SCOPE_SKY_ONLY, SCOPE_WHOLE_IMAGE):
            with self.assertRaises(ValueError):
                blend_denoise(base, full, self.mask, float("nan"), scope)

    def test_recombination_neutral_and_zero_amount_even_with_glow(self):
        base, stars = self.read_separation()
        negative = np.minimum(star_residual(self.source, base), 0)
        np.testing.assert_allclose(
            recombine_layers(base, stars, negative, 100, BLEND_ADD), self.source, atol=np.finfo(np.float32).eps, rtol=0
        )
        for mode in (BLEND_ADD, BLEND_SCREEN):
            np.testing.assert_array_equal(recombine_layers(base, stars + 0.1, negative, 0, mode), base)
        # Independently known Screen value: F=.4, S=.2 at 50% -> .46.
        np.testing.assert_allclose(
            recombine_layers(self.model, np.full_like(self.model, 0.2), np.zeros_like(self.model), 50, BLEND_SCREEN),
            0.46,
        )

    def test_observable_separation_cancellation_and_image_outputs(self):
        outputs = SeparateStars().separate(self.source, self.model, self.mask, **self.paths)
        self.assertEqual([f.operation for f in outputs], ["Starless", "Stars"])
        self.assertIsNone(
            SeparateStars(cancel_check=lambda: True).separate(self.source, self.model, self.mask, **self.paths)
        )

    def test_export_uses_output_path_and_explicit_bit_depth(self):
        for bit_depth, suffix, dtype in (
            (8, ".jpg", np.uint8),
            (8, ".tif", np.uint8),
            (16, ".tiff", np.uint16),
        ):
            with self.subTest(bit_depth=bit_depth, suffix=suffix):
                destination = self.root / ("export" + suffix)
                _, path = Recombine().recombine(
                    self.model,
                    np.zeros_like(self.model),
                    np.zeros_like(self.model),
                    FINISH_DEFAULTS,
                    bit_depth=bit_depth,
                    output_path=destination,
                )
                self.assertEqual(path, destination)
                decoded = imread(path)
                self.assertEqual(decoded.dtype, dtype)
                np.testing.assert_allclose(decoded / np.iinfo(dtype).max, self.model, atol=1 / 255, rtol=0)

    def test_failed_export_preserves_destination_and_cleans_staging(self):
        destination = self.root / "composite.tif"
        destination.write_bytes(b"previous export")
        with patch("startrails.op.finish.recombine.imwrite", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                Recombine().recombine(
                    self.model,
                    self.model,
                    self.model,
                    FINISH_DEFAULTS,
                    bit_depth=8,
                    output_path=destination,
                )
        self.assertEqual(destination.read_bytes(), b"previous export")
        self.assertFalse(list(self.root.glob(".artifact-*")))

    def test_signatures_disambiguate_inputs_and_invalidate_options(self):
        options = dict(stride=256, upsample=False, linear=False, highlights_protection=True, mask_feather_radius_px=0.0)
        first = compute_separation_signature("a|mask:b", "c", "m", **options)
        self.assertNotEqual(first, compute_separation_signature("a", "b|mask:c", "m", **options))
        self.assertEqual(first, compute_separation_signature("a|mask:b", "c", "m", **options))
        for name, value in dict(
            stride=128, upsample=True, linear=True, highlights_protection=False, mask_feather_radius_px=2.5
        ).items():
            self.assertNotEqual(first, compute_separation_signature("a|mask:b", "c", "m", **(options | {name: value})))
        self.assertNotEqual(
            compute_denoise_endpoint_signature("a|model:b", "c"),
            compute_denoise_endpoint_signature("a", "b|model:c"),
        )
        self.assertNotEqual(
            compute_denoise_endpoint_signature(first, "m"),
            compute_denoise_endpoint_signature("changed separation", "m"),
        )
        # Adapter tile constants are part of the inference key, not caller options.
        baseline = compute_denoise_endpoint_signature(first, "m")
        with patch("startrails.lib.finish.composition.WINDOW_SIZE", 512):
            self.assertNotEqual(compute_denoise_endpoint_signature(first, "m"), baseline)


if __name__ == "__main__":
    unittest.main()
