"""Tests for Finish mode model manifests, Nox model contracts, and GraXpert normalization."""

from pathlib import Path
import tempfile
import unittest
import numpy as np
import torch

from startrails.lib.finish.graxpert import (
    EXPECTED_PARAM_COUNT as GRAXPERT_EXPECTED_PARAM_COUNT,
    EXPECTED_WEIGHT_TENSOR_COUNT as GRAXPERT_EXPECTED_WEIGHT_TENSOR_COUNT,
    GRAXPERT_MODEL_RELATIVE_PATH,
    GRAXPERT_MODEL_VERSION,
    MIN_MAD_EPSILON,
    build_graxpert_model,
    compute_graxpert_stats,
    graxpert_model_identity,
    graxpert_tile_postprocess,
    graxpert_tile_preprocess,
    load_graxpert_model,
)
from startrails.lib.finish.nox import (
    EXPECTED_PARAM_COUNT,
    EXPECTED_WEIGHT_TENSOR_COUNT,
    NOX_MODEL_RELATIVE_PATH,
    NOX_MODEL_VERSION,
    NoxColor,
    RadialChromaConfig,
    apply_radial_chroma_postfilter,
    expected_state_dict_shapes,
    load_nox_model,
    nox_model_identity,
    validate_separation_stride,
)


class TestFinishModelSetup(unittest.TestCase):
    def test_bundled_model_identities_and_paths(self):
        self.assertEqual(NOX_MODEL_VERSION, "1.0.0")
        self.assertEqual(NOX_MODEL_RELATIVE_PATH, "removeStars/nox_color_finetuned_best.pt")
        self.assertIn(NOX_MODEL_VERSION, nox_model_identity())

        self.assertEqual(GRAXPERT_MODEL_VERSION, "3.0.2")
        self.assertEqual(
            GRAXPERT_MODEL_RELATIVE_PATH,
            "denoiseSky/graxpert/graxpert-denoise-3.0.2-mixed-int4-int8.pt",
        )
        self.assertIn(GRAXPERT_MODEL_VERSION, graxpert_model_identity())

    def test_graxpert_architecture_and_checkpoint_validation(self):
        model = build_graxpert_model()
        actual = model.state_dict()
        self.assertEqual(len(actual), GRAXPERT_EXPECTED_WEIGHT_TENSOR_COUNT)
        param_count = sum(p.numel() for p in model.parameters())
        self.assertEqual(param_count, GRAXPERT_EXPECTED_PARAM_COUNT)

        batch_nhwc = torch.full((1, 64, 64, 3), 0.25, dtype=torch.float32)
        with torch.no_grad():
            out_nhwc = model(batch_nhwc)
        self.assertEqual(tuple(out_nhwc.shape), (1, 64, 64, 3))
        self.assertTrue(torch.isfinite(out_nhwc).all())

        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.pt"
            with self.assertRaises(FileNotFoundError):
                load_graxpert_model(missing, device="cpu")

            corrupt = Path(tmpdir) / "corrupt.pt"
            corrupt.write_bytes(b"not a checkpoint")
            with self.assertRaises(ValueError):
                load_graxpert_model(corrupt, device="cpu")

    def test_nox_architecture_matches_expected_state_dict_and_param_count(self):
        model = NoxColor()
        expected = expected_state_dict_shapes()
        actual = model.state_dict()
        self.assertEqual(len(actual), EXPECTED_WEIGHT_TENSOR_COUNT)
        self.assertEqual(list(actual.keys()), list(expected.keys()))
        for key, shape in expected.items():
            self.assertEqual(tuple(actual[key].shape), shape)
        param_count = sum(p.numel() for p in model.parameters())
        self.assertEqual(param_count, EXPECTED_PARAM_COUNT)

        batch = torch.full((1, 3, 256, 256), 0.25, dtype=torch.float32)
        with torch.no_grad():
            out = model(batch)
        self.assertEqual(tuple(out.shape), (1, 3, 256, 256))
        self.assertTrue(torch.isfinite(out).all())

    def test_load_nox_model_rejects_missing_or_corrupt_weights(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.pt"
            with self.assertRaises(FileNotFoundError):
                load_nox_model(missing, device="cpu")

            corrupt = Path(tmpdir) / "corrupt.pt"
            corrupt.write_bytes(b"not a checkpoint")
            with self.assertRaises(ValueError):
                load_nox_model(corrupt, device="cpu")

    def test_validate_separation_stride_contract(self):
        validate_separation_stride(256)
        validate_separation_stride(128)
        validate_separation_stride(64)
        validate_separation_stride(512)
        for bad in (0, 1, 255, 600, 256.0, True, "256"):
            with self.subTest(stride=bad), self.assertRaises(ValueError):
                validate_separation_stride(bad)

    def test_radial_chroma_postfilter_suppresses_halo_while_preserving_uniform_sky(self):
        # Uniform image has no removed stars, so output matches starless unchanged.
        uniform = np.full((64, 64, 3), 0.2, dtype=np.float32)
        filtered_uniform, stats_uniform = apply_radial_chroma_postfilter(uniform, uniform)
        self.assertEqual(stats_uniform.detected_stars, 0)
        np.testing.assert_array_equal(filtered_uniform, uniform)

        # Synthetic removed bright star with a colored residual halo in the starless output.
        yy, xx = np.mgrid[0:64, 0:64].astype(np.float32)
        dist2 = (yy - 32.0) ** 2 + (xx - 32.0) ** 2
        star = np.exp(-dist2 / (2.0 * 1.6 ** 2))
        sky = np.full((64, 64, 3), 0.12, dtype=np.float32)
        source = np.clip(sky + star[:, :, None] * 0.75, 0.0, 1.0).astype(np.float32)

        halo = np.exp(-dist2 / (2.0 * 4.0 ** 2))
        starless = sky.copy()
        starless[:, :, 0] += halo * 0.08  # magenta/red chroma halo around removed star
        starless[:, :, 2] += halo * 0.08

        filtered, stats = apply_radial_chroma_postfilter(
            source,
            starless,
            RadialChromaConfig(peak_thresh=0.05),
        )
        self.assertGreaterEqual(stats.detected_stars, 1)
        # Chroma spread (max - min across channels) around the star center is reduced.
        chroma_before = float(np.max(starless[28:36, 28:36]) - np.min(starless[28:36, 28:36]))
        chroma_after = float(np.max(filtered[28:36, 28:36]) - np.min(filtered[28:36, 28:36]))
        self.assertLess(chroma_after, chroma_before)

    def test_graxpert_stats_and_dark_channels(self):
        # Normal image
        img = np.random.default_rng(0).uniform(0.1, 0.9, (128, 128, 3)).astype(np.float32)
        median, mad = compute_graxpert_stats(img)
        self.assertEqual(median.shape, (3,))
        self.assertEqual(mad.shape, (3,))
        self.assertTrue(np.all(mad > 0))

        # Dark image (constant zero)
        dark_img = np.zeros((128, 128, 3), dtype=np.float32)
        dark_med, dark_mad = compute_graxpert_stats(dark_img)
        self.assertTrue(np.all(dark_med == 0.0))
        # Ensure MIN_MAD_EPSILON prevents zero division
        self.assertTrue(np.all(dark_mad == MIN_MAD_EPSILON))

        # Check tile preprocess with dark stats does not produce NaNs or Infs
        tile = np.zeros((256, 256, 3), dtype=np.float32)
        preprocessed = graxpert_tile_preprocess(tile, dark_med, dark_mad)
        self.assertTrue(np.all(np.isfinite(preprocessed)))

    def test_graxpert_tile_preserves_highlights_and_reverses_normalization(self):
        original = np.array([[[0.1, 0.5, 0.8]]], dtype=np.float32)
        median = np.full(3, 0.2, dtype=np.float32)
        mad = np.full(3, 0.001, dtype=np.float32)
        np.testing.assert_allclose(
            graxpert_tile_preprocess(original, median, mad),
            [[[-4, 10, 10]]],
        )
        restored = graxpert_tile_postprocess(np.zeros_like(original), original, median, mad)
        np.testing.assert_allclose(restored, [[[0.2, 0.5, 0.8]]])

    def test_graxpert_postprocess_applies_highlight_gate_within_the_adapter(self):
        median = np.array([0.2, 0.2, 0.2], dtype=np.float32)
        mad = np.array([0.001, 0.001, 0.001], dtype=np.float32)
        # With this MAD the highlight gate switches at 0.45.
        original = np.array([[[0.1, 0.5, 0.8]]], dtype=np.float32)
        # The model returns standardized-space samples; -6 restores to 0.05.
        restored = graxpert_tile_postprocess(np.full_like(original, -6.0), original, median, mad)
        np.testing.assert_allclose(restored, [[[0.05, 0.5, 0.8]]], atol=1e-6)

        # Model identity keys endpoints but is independent of the selected provider.
        self.assertEqual(graxpert_model_identity(), graxpert_model_identity())
        self.assertIn("3.0.2", graxpert_model_identity())


if __name__ == "__main__":
    unittest.main()
