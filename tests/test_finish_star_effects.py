"""Focused numeric contracts for the shared star analysis and star effects."""

from __future__ import annotations

import unittest
from dataclasses import replace

import numpy as np

from startrails.lib.finish.defaults import FinishSettings
from startrails.lib.finish.star_analysis import StarAnalysisResult, StarCandidate, analyze_stars
from startrails.lib.finish.star_effects import (
    STAR_EFFECT_VERSION,
    _apply_glow,
    _footprint_flux,
    _measure_local,
    apply_star_effects,
)


def _add_gaussian(image, x, y, a, b, theta, amplitude):
    radius = int(np.ceil(4.5 * max(a, b))) + 1
    iy, ix = int(round(y)), int(round(x))
    y0, y1 = max(0, iy - radius), min(image.shape[0], iy + radius + 1)
    x0, x1 = max(0, ix - radius), min(image.shape[1], ix + radius + 1)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dx, dy = xx - x, yy - y
    ct, st = np.cos(theta), np.sin(theta)
    u = ct * dx + st * dy
    v = -st * dx + ct * dy
    profile = np.exp(-0.5 * ((u / a) ** 2 + (v / b) ** 2))
    image[y0:y1, x0:x1] += profile[..., None] * np.asarray(amplitude, np.float32)


def _add_coma(image, x, y, a, b, theta, amplitude, tail_frac=0.35, tail_px=5.0):
    radius = int(np.ceil(5.0 * max(a, b) + 2.0 * tail_px)) + 1
    iy, ix = int(round(y)), int(round(x))
    y0, y1 = max(0, iy - radius), min(image.shape[0], iy + radius + 1)
    x0, x1 = max(0, ix - radius), min(image.shape[1], ix + radius + 1)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dx, dy = xx - x, yy - y
    ct, st = np.cos(theta), np.sin(theta)
    u = ct * dx + st * dy
    v = -st * dx + ct * dy
    core = np.exp(-0.5 * ((u / a) ** 2 + (v / b) ** 2))
    tail = np.where(
        u > 0,
        np.exp(-u / tail_px) * np.exp(-0.5 * (v / max(b * 0.8, 0.7)) ** 2),
        0.0,
    )
    tail /= max(float(tail.sum()), 1e-9)
    tail *= tail_frac * 2.0 * np.pi * a * b
    profile = core + tail
    image[y0:y1, x0:x1] += profile[..., None] * np.asarray(amplitude, np.float32)


def _settings(**overrides):
    return replace(FinishSettings(), **overrides)


def _mask(height, width, value=1.0):
    return np.full((height, width), value, np.float32)


def _add_noise(image, sigma=0.0005):
    image += np.random.default_rng(4).normal(0.0, sigma, image.shape).astype(np.float32)
    np.clip(image, 0.0, 1.0, out=image)


def _nearest(candidates, x, y):
    return min(candidates, key=lambda c: (c.x - x) ** 2 + (c.y - y) ** 2)


class TestStarAnalysis(unittest.TestCase):
    def test_noise_and_constant_do_not_create_stars(self):
        rng = np.random.default_rng(8)
        stars = np.clip(rng.normal(0.0, 0.0015, (128, 128, 3)).astype(np.float32), 0.0, 1.0)
        source = np.full((128, 128, 3), 0.2, np.float32)
        result = analyze_stars(stars, source, _mask(128, 128))
        self.assertIsNotNone(result)
        self.assertEqual(len(result.candidates), 0)

    def test_saturation_uses_source_not_star_layer(self):
        stars = np.zeros((96, 96, 3), np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 30, 30, 2.6, 1.4, 0.3, [0.30, 0.30, 0.30])
        _add_gaussian(source, 30, 30, 2.6, 1.4, 0.3, [1.4, 1.4, 1.4])
        np.clip(source, 0.0, 1.0, out=source)
        result = analyze_stars(stars, source, _mask(96, 96))
        self.assertIsNotNone(result)
        saturated = [c for c in result.candidates if c.is_saturated]
        self.assertEqual(len(saturated), 1)
        self.assertLess(saturated[0].peak_brightness, 0.995)
        self.assertAlmostEqual(saturated[0].effective_peak, 1.0, places=5)


class TestStarEffects(unittest.TestCase):
    shape = (128, 128, 3)

    def setUp(self):
        rng = np.random.default_rng(11)
        self.stars = np.clip(rng.normal(0.0, 0.001, self.shape).astype(np.float32), 0.0, 1.0)
        self.source = np.clip(self.stars + 0.1, 0.0, 1.0)
        self.mask = _mask(*self.shape[:2])

    def test_neutral_is_exact_identity_and_read_only(self):
        stars_before = self.stars.copy()
        source_before = self.source.copy()
        mask_before = self.mask.copy()
        result = apply_star_effects(self.stars, self.mask, _settings(), source=self.source)
        self.assertIsNotNone(result)
        self.assertTrue(np.array_equal(result, self.stars))
        self.assertFalse(np.shares_memory(result, self.stars))
        self.assertTrue(np.array_equal(self.stars, stars_before))
        self.assertTrue(np.array_equal(self.source, source_before))
        self.assertTrue(np.array_equal(self.mask, mask_before))

    def test_round_isolated_trailing_and_coma_tolerances(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 38, 40, 3.5, 1.8, 0.4, [0.45, 0.45, 0.45])
        _add_gaussian(source, 38, 40, 3.5, 1.8, 0.4, [0.55, 0.55, 0.55])
        _add_gaussian(stars, 84, 38, 6.0, 1.3, 0.7, [0.50, 0.50, 0.50])
        _add_gaussian(source, 84, 38, 6.0, 1.3, 0.7, [0.60, 0.60, 0.60])
        _add_coma(stars, 45, 92, 2.4, 1.2, 0.1, [0.45, 0.45, 0.45])
        _add_coma(source, 45, 92, 2.4, 1.2, 0.1, [0.55, 0.55, 0.55])
        _add_noise(stars)
        before = analyze_stars(stars, source, self.mask)
        self.assertIsNotNone(before)
        checked = 0
        result = apply_star_effects(
            stars,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        self.assertIsNotNone(result)
        after = analyze_stars(result, source, self.mask)
        self.assertIsNotNone(after)
        for original in before.candidates:
            if not original.is_valid or original.is_saturated:
                continue
            updated = _nearest(after.candidates, original.x, original.y)
            self.assertLess(np.hypot(updated.x - original.x, updated.y - original.y), 0.5)
            self.assertLessEqual(updated.ellipticity, 0.10)
            flux_before = _footprint_flux(stars, original.x, original.y, original.footprint_radius_px)
            flux_after = _footprint_flux(result, original.x, original.y, original.footprint_radius_px)
            error = np.abs(flux_after - flux_before) / np.maximum(np.abs(flux_before), 1e-9)
            self.assertLessEqual(float(error.max()), 0.01)
            checked += 1
        self.assertEqual(checked, 3)

    def test_round_amount_scales_the_same_correction(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 60, 60, 3.8, 1.5, 0.4, [0.55, 0.55, 0.55])
        _add_gaussian(source, 60, 60, 3.8, 1.5, 0.4, [0.65, 0.65, 0.65])
        full = apply_star_effects(
            stars,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        half = apply_star_effects(
            stars,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=50.0),
            source=source,
        )
        full_delta = full - stars
        half_delta = half - stars
        changed = np.any(np.abs(full_delta) > 1e-7, axis=2)
        self.assertTrue(np.any(changed))
        np.testing.assert_allclose(half_delta[changed], 0.5 * full_delta[changed], atol=2e-4, rtol=0.0)

    def test_round_skips_saturated_source_even_when_star_layer_is_below_one(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 35, 40, 3.0, 1.3, 0.5, [0.32, 0.32, 0.32])
        _add_gaussian(source, 35, 40, 3.0, 1.3, 0.5, [1.5, 1.5, 1.5])
        np.clip(source, 0.0, 1.0, out=source)
        _add_gaussian(stars, 90, 40, 3.0, 1.3, 0.5, [0.45, 0.45, 0.45])
        _add_gaussian(source, 90, 40, 3.0, 1.3, 0.5, [0.55, 0.55, 0.55])
        result = apply_star_effects(
            stars,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        self.assertIsNotNone(result)
        self.assertTrue(np.array_equal(result[20:55, 18:52], stars[20:55, 18:52]))
        self.assertFalse(np.array_equal(result[20:55, 75:105], stars[20:55, 75:105]))

    def test_conservative_blend_border_and_noise_handling(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 55, 50, 3.0, 1.4, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(stars, 64, 50, 3.0, 1.4, 0.2, [0.4, 0.4, 0.4])
        source[:] = np.clip(stars + 0.1, 0.0, 1.0)
        blend_result = apply_star_effects(
            stars,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        self.assertTrue(np.array_equal(blend_result, stars))

        border_stars = np.zeros(self.shape, np.float32)
        border_source = np.zeros_like(border_stars)
        _add_gaussian(border_stars, 3, 60, 3.0, 1.4, 0.2, [0.5, 0.5, 0.5])
        border_source[:] = np.clip(border_stars + 0.1, 0.0, 1.0)
        border_result = apply_star_effects(
            border_stars,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=border_source,
        )
        self.assertTrue(np.array_equal(border_result, border_stars))

        noise = np.clip(np.random.default_rng(2).normal(0.0, 0.0015, self.shape), 0.0, 1.0).astype(np.float32)
        noise_source = np.full(self.shape, 0.15, np.float32)
        noise_result = apply_star_effects(
            noise,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=noise_source,
        )
        self.assertTrue(np.array_equal(noise_result, noise))

    def test_overlapping_correction_footprints_are_skipped(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 45, 55, 3.0, 1.5, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(stars, 65, 55, 3.0, 1.5, 0.2, [0.5, 0.5, 0.5])
        source[:] = np.clip(stars + 0.1, 0.0, 1.0)
        analysis = analyze_stars(stars, source, self.mask)
        self.assertIsNotNone(analysis)
        eligible = [c for c in analysis.candidates if c.is_valid and not c.is_blended]
        self.assertGreaterEqual(len(eligible), 2)
        result = apply_star_effects(
            stars,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        self.assertTrue(np.array_equal(result, stars))

    def test_sky_mask_is_a_delta_mask_and_zero_mask_is_exact(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 35, 50, 3.2, 1.5, 0.4, [0.5, 0.5, 0.5])
        _add_gaussian(source, 35, 50, 3.2, 1.5, 0.4, [0.6, 0.6, 0.6])
        _add_gaussian(stars, 90, 50, 3.2, 1.5, 0.4, [0.5, 0.5, 0.5])
        _add_gaussian(source, 90, 50, 3.2, 1.5, 0.4, [0.6, 0.6, 0.6])
        mask = _mask(*self.shape[:2])
        mask[:, :64] = 0.0
        result = apply_star_effects(
            stars,
            mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        self.assertTrue(np.array_equal(result[:, :64], stars[:, :64]))
        self.assertFalse(np.array_equal(result[:, 64:], stars[:, 64:]))

        full = apply_star_effects(
            stars,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        half_mask = _mask(*self.shape[:2], 0.5)
        half = apply_star_effects(
            stars,
            half_mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        full_delta = full - stars
        half_delta = half - stars
        changed = np.any(np.abs(full_delta) > 1e-7, axis=2)
        self.assertTrue(np.any(changed))
        np.testing.assert_allclose(half_delta[changed], 0.5 * full_delta[changed], atol=2e-4, rtol=0.0)
        unchanged = ~changed
        self.assertTrue(np.array_equal(half[unchanged], stars[unchanged]))

    def test_glow_selects_bright_color_preserving_bounded_and_disabled(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 40, 40, 2.5, 1.4, 0.2, [0.55, 0.40, 0.30])
        _add_gaussian(source, 40, 40, 2.5, 1.4, 0.2, [0.65, 0.50, 0.38])
        _add_gaussian(stars, 90, 40, 2.5, 1.4, 0.2, [0.10, 0.10, 0.10])
        _add_gaussian(source, 90, 40, 2.5, 1.4, 0.2, [0.12, 0.12, 0.12])
        settings = _settings(star_glow_enabled=True, star_glow_amount=50.0, star_glow_radius_px=10.0)
        analysis = analyze_stars(stars, source, self.mask)
        self.assertIsNotNone(analysis)
        bright = _nearest(analysis.candidates, 40, 40)
        before_flux = _footprint_flux(stars, bright.x, bright.y, bright.footprint_radius_px)
        result = apply_star_effects(stars, self.mask, settings, source=source)
        self.assertIsNotNone(result)
        self.assertGreater(result.max(), stars.max())
        self.assertLessEqual(float(result.max()), 1.0)
        added = _footprint_flux(result, bright.x, bright.y, 20.0) - _footprint_flux(stars, bright.x, bright.y, 20.0)
        np.testing.assert_allclose(added, 0.5 * before_flux, atol=2e-3, rtol=0.01)
        self.assertTrue(np.array_equal(result[20:60, 70:110], stars[20:60, 70:110]))

        disabled = apply_star_effects(stars, self.mask, _settings(), source=source)
        self.assertTrue(np.array_equal(disabled, stars))

        # Border star is not selected; no wrap or non-finite output.
        border_stars = np.zeros(self.shape, np.float32)
        border_source = np.zeros_like(border_stars)
        _add_gaussian(border_stars, 3, 60, 2.5, 1.4, 0.2, [0.6, 0.6, 0.6])
        border_source[:] = np.clip(border_stars + 0.1, 0.0, 1.0)
        border = apply_star_effects(
            border_stars,
            self.mask,
            _settings(star_glow_enabled=True, star_glow_amount=100.0, star_glow_radius_px=12.0),
            source=border_source,
        )
        self.assertTrue(np.isfinite(border).all())
        self.assertTrue(np.array_equal(border, border_stars))

        # A clipped source core with a depressed star layer is still selected by
        # the source peak, while a zero-mask region stays exact.
        saturated_stars = np.zeros(self.shape, np.float32)
        saturated_source = np.zeros_like(saturated_stars)
        _add_gaussian(saturated_stars, 35, 55, 2.5, 1.4, 0.2, [0.22, 0.22, 0.22])
        _add_gaussian(saturated_source, 35, 55, 2.5, 1.4, 0.2, [1.4, 1.4, 1.4])
        np.clip(saturated_source, 0.0, 1.0, out=saturated_source)
        zero_mask = _mask(*self.shape[:2])
        zero_mask[:, :64] = 0.0
        saturated_glow = apply_star_effects(
            saturated_stars,
            zero_mask,
            _settings(star_glow_enabled=True, star_glow_amount=100.0, star_glow_radius_px=10.0),
            source=saturated_source,
        )
        self.assertTrue(np.array_equal(saturated_glow[:, :64], saturated_stars[:, :64]))
        saturated_glow_full = apply_star_effects(
            saturated_stars,
            self.mask,
            _settings(star_glow_enabled=True, star_glow_amount=100.0, star_glow_radius_px=10.0),
            source=saturated_source,
        )
        self.assertFalse(np.array_equal(saturated_glow_full, saturated_stars))

    def test_faint_suppression_is_whole_footprint_and_neutral_when_off(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 40, 50, 2.5, 1.3, 0.2, [0.55, 0.55, 0.55])
        _add_gaussian(source, 40, 50, 2.5, 1.3, 0.2, [0.65, 0.65, 0.65])
        _add_gaussian(stars, 90, 50, 2.5, 1.3, 0.2, [0.06, 0.06, 0.06])
        _add_gaussian(source, 90, 50, 2.5, 1.3, 0.2, [0.08, 0.08, 0.08])
        settings = _settings(faint_star_suppression=True, faint_star_amount=100.0)
        analysis = analyze_stars(stars, source, self.mask)
        bright = _nearest(analysis.candidates, 40, 50)
        faint = _nearest(analysis.candidates, 90, 50)
        result = apply_star_effects(stars, self.mask, settings, source=source)
        self.assertIsNotNone(result)
        bright_before = _footprint_flux(stars, bright.x, bright.y, bright.footprint_radius_px)
        bright_after = _footprint_flux(result, bright.x, bright.y, bright.footprint_radius_px)
        np.testing.assert_allclose(bright_after, bright_before, atol=1e-6)
        faint_before = _footprint_flux(stars, faint.x, faint.y, faint.footprint_radius_px)
        faint_after = _footprint_flux(result, faint.x, faint.y, faint.footprint_radius_px)
        self.assertLess(float(faint_after.sum()), 0.30 * float(faint_before.sum()))

        # All changed pixels inside the faint footprint use one scalar.
        y0, y1 = 35, 65
        x0, x1 = 75, 105
        before = stars[y0:y1, x0:x1]
        after = result[y0:y1, x0:x1]
        selected = before.max(axis=2) > 0.005
        ratios = after[selected] / before[selected]
        self.assertLess(float(ratios.std()), 5e-5)

        disabled = apply_star_effects(stars, self.mask, _settings(), source=source)
        self.assertTrue(np.array_equal(disabled, stars))

        zero_mask = _mask(*self.shape[:2])
        zero_mask[:, :64] = 0.0
        masked = apply_star_effects(stars, zero_mask, settings, source=source)
        self.assertTrue(np.array_equal(masked[:, :64], stars[:, :64]))

    def test_glow_is_order_independent_and_uses_pre_halo_flux(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 48, 60, 2.2, 1.2, 0.2, [0.45, 0.30, 0.22])
        _add_gaussian(source, 48, 60, 2.2, 1.2, 0.2, [0.55, 0.40, 0.30])
        _add_gaussian(stars, 88, 60, 2.2, 1.2, 0.2, [0.40, 0.32, 0.26])
        _add_gaussian(source, 88, 60, 2.2, 1.2, 0.2, [0.50, 0.42, 0.34])
        analysis = analyze_stars(stars, source, self.mask)
        self.assertIsNotNone(analysis)
        self.assertEqual(len(analysis.candidates), 2)
        forward = stars.copy()
        _apply_glow(forward, analysis, self.mask, 50.0, 30.0, lambda: False)
        reversed_analysis = StarAnalysisResult(
            candidates=tuple(reversed(analysis.candidates)), image_shape=analysis.image_shape
        )
        backward = stars.copy()
        _apply_glow(backward, reversed_analysis, self.mask, 50.0, 30.0, lambda: False)
        np.testing.assert_allclose(forward, backward, atol=1e-6, rtol=0.0)

        isolated_sum = np.zeros_like(stars)
        for candidate in analysis.candidates:
            one = StarAnalysisResult(candidates=(candidate,), image_shape=analysis.image_shape)
            partial = stars.copy()
            _apply_glow(partial, one, self.mask, 50.0, 30.0, lambda: False)
            isolated_sum += partial - stars
        np.testing.assert_allclose(forward, stars + isolated_sum, atol=1e-6, rtol=0.0)

    def test_glow_uses_full_kernel_at_frame_edge_not_patch_renormalization(self):
        centered = np.zeros(self.shape, np.float32)
        edge = np.zeros(self.shape, np.float32)
        source = np.zeros_like(centered)
        _add_gaussian(centered, 64, 64, 1.6, 1.0, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(edge, 12, 64, 1.6, 1.0, 0.2, [0.5, 0.5, 0.5])
        source[:] = np.clip(centered + edge + 0.1, 0.0, 1.0)
        for label, stars in (("center", centered), ("edge", edge)):
            scene_source = np.clip(stars + 0.1, 0.0, 1.0)
            analysis = analyze_stars(stars, scene_source, self.mask)
            self.assertIsNotNone(analysis)
            self.assertEqual(len(analysis.candidates), 1)
            self.assertTrue(analysis.candidates[0].is_valid)
            if label == "center":
                center_analysis = analysis
            else:
                edge_analysis = analysis
        center_out = centered.copy()
        _apply_glow(center_out, center_analysis, self.mask, 100.0, 60.0, lambda: False)
        edge_out = edge.copy()
        _apply_glow(edge_out, edge_analysis, self.mask, 100.0, 60.0, lambda: False)
        center_added = float((center_out - centered).sum())
        edge_added = float((edge_out - edge).sum())
        self.assertGreater(center_added, 0.0)
        self.assertLess(edge_added, center_added)
        self.assertLessEqual(edge_added, center_added * 1.000001)

    def test_suppression_feathers_edge_and_skips_overlapping_neighbor_core(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 60, 60, 2.5, 1.3, 0.2, [0.06, 0.06, 0.06])
        _add_gaussian(source, 60, 60, 2.5, 1.3, 0.2, [0.08, 0.08, 0.08])
        _add_noise(stars, 0.001)
        analysis = analyze_stars(stars, source, self.mask)
        candidate = min(analysis.candidates, key=lambda c: (c.x - 60) ** 2 + (c.y - 60) ** 2)
        result = apply_star_effects(
            stars,
            self.mask,
            _settings(faint_star_suppression=True, faint_star_amount=100.0),
            source=source,
        )
        self.assertIsNotNone(result)
        yy, xx = np.mgrid[0 : self.shape[0], 0 : self.shape[1]]
        distance = np.hypot(yy - candidate.y, xx - candidate.x)
        outside = distance > candidate.footprint_radius_px + 1.0
        self.assertTrue(np.array_equal(result[outside], stars[outside]))
        core = distance <= 0.65 * candidate.footprint_radius_px
        selected = core & (stars.min(axis=2) > 1e-5)
        ratios = result[selected] / stars[selected]
        self.assertLess(float(ratios.std()), 5e-5)

        close_stars = np.zeros(self.shape, np.float32)
        close_source = np.zeros_like(close_stars)
        _add_gaussian(close_stars, 55, 60, 2.5, 1.3, 0.2, [0.06, 0.06, 0.06])
        _add_gaussian(close_stars, 75, 60, 2.5, 1.3, 0.2, [0.55, 0.55, 0.55])
        close_source[:] = np.clip(close_stars + 0.1, 0.0, 1.0)
        close = apply_star_effects(
            close_stars,
            self.mask,
            _settings(faint_star_suppression=True, faint_star_amount=100.0),
            source=close_source,
        )
        self.assertIsNotNone(close)
        self.assertTrue(np.array_equal(close, close_stars))

    def test_round_owner_query_includes_competitor_within_two_radii(self):
        # Build the primary trail alone first to learn its correction radius.
        probe = np.zeros(self.shape, np.float32)
        probe_source = np.zeros_like(probe)
        _add_gaussian(probe, 45, 64, 5.0, 2.0, 0.0, [0.60, 0.60, 0.60])
        _add_gaussian(probe_source, 45, 64, 5.0, 2.0, 0.0, [0.70, 0.70, 0.70])
        probe_analysis = analyze_stars(probe, probe_source, self.mask)
        primary = min(probe_analysis.candidates, key=lambda c: (c.x - 45) ** 2 + (c.y - 64) ** 2)
        radius = primary.footprint_radius_px
        distance = radius + 5.0 + 2.0
        self.assertLess(distance, 2.0 * radius)

        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 45, 64, 5.0, 2.0, 0.0, [0.60, 0.60, 0.60])
        _add_gaussian(source, 45, 64, 5.0, 2.0, 0.0, [0.70, 0.70, 0.70])
        _add_gaussian(stars, 45 + distance, 64, 1.2, 1.1, 0.0, [0.20, 0.20, 0.20])
        _add_gaussian(source, 45 + distance, 64, 1.2, 1.1, 0.0, [0.25, 0.25, 0.25])
        analysis = analyze_stars(stars, source, self.mask)
        corrected = min(analysis.candidates, key=lambda c: (c.x - 45) ** 2 + (c.y - 64) ** 2)
        result = apply_star_effects(
            stars,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        self.assertIsNotNone(result)
        core_pixel = (int(round(corrected.y)), int(round(corrected.x)))
        self.assertGreater(float(np.abs(result[core_pixel] - stars[core_pixel]).max()), 1e-4)
        # A pixel at 0.7 R toward the competitor is owned by the competitor once
        # the owner query uses 2R. With query radius R this pixel would be
        # changed because the competitor was never inserted into the ownership mask.
        px = int(round(corrected.x + 0.7 * radius))
        py = int(round(corrected.y))
        self.assertGreater(float(stars[py, px].max()), 1e-5)
        self.assertLess(float(np.abs(result[py, px] - stars[py, px]).max()), 1e-8)

    def test_round_protects_skipped_neighbor_core(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 55, 60, 3.0, 1.4, 0.4, [0.5, 0.5, 0.5])
        _add_gaussian(stars, 75, 60, 2.7, 1.3, 0.4, [0.30, 0.30, 0.30])
        _add_gaussian(source, 55, 60, 3.0, 1.4, 0.4, [0.6, 0.6, 0.6])
        _add_gaussian(source, 75, 60, 2.7, 1.3, 0.4, [1.4, 1.4, 1.4])
        np.clip(source, 0.0, 1.0, out=source)
        result = apply_star_effects(
            stars,
            self.mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        self.assertTrue(np.array_equal(result, stars))

    def test_round_mask_ramp_verifies_masked_centroid_flux_color_and_ellipticity(self):
        width = self.shape[1]
        ramp = np.tile(np.linspace(0.0, 1.0, width, dtype=np.float32), (self.shape[0], 1))
        changed_levels = 0
        for level in (0.5, 0.7, 0.9):
            stars = np.zeros(self.shape, np.float32)
            source = np.zeros_like(stars)
            x = float(np.argmin(np.abs(ramp[0] - level)))
            _add_gaussian(stars, x, 64, 3.2, 1.5, 0.4, [0.55, 0.34, 0.22])
            _add_gaussian(source, x, 64, 3.2, 1.5, 0.4, [0.65, 0.44, 0.32])
            before = analyze_stars(stars, source, ramp)
            candidate = min(before.candidates, key=lambda c: (c.x - x) ** 2 + (c.y - 64) ** 2)
            result = apply_star_effects(
                stars,
                ramp,
                _settings(round_stars_enabled=True, round_stars_amount=100.0),
                source=source,
            )
            self.assertIsNotNone(result)
            if np.array_equal(result, stars):
                continue
            changed_levels += 1
            cy, cx, e_after = _measure_local(result, candidate.x, candidate.y, candidate.core_radius_px)
            f_before = _footprint_flux(stars, candidate.x, candidate.y, candidate.footprint_radius_px)
            f_after = _footprint_flux(result, candidate.x, candidate.y, candidate.footprint_radius_px)
            self.assertLessEqual(float(np.hypot(cy - candidate.y, cx - candidate.x)), 0.5)
            flux_error = np.abs(f_after - f_before) / np.maximum(np.abs(f_before), 1e-9)
            self.assertLessEqual(float(flux_error.max()), 0.01)
            color_before = f_before / max(float(f_before.sum()), 1e-9)
            color_after = f_after / max(float(f_after.sum()), 1e-9)
            color_drift = np.abs(color_after - color_before) / np.maximum(np.abs(color_before), 1e-9)
            self.assertLessEqual(float(color_drift.max()), 0.01)
            self.assertLessEqual(e_after, max(0.10, candidate.ellipticity))

        self.assertGreater(changed_levels, 0)

        zero_mask = np.zeros(self.shape[:2], np.float32)
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 60, 60, 3.0, 1.4, 0.4, [0.55, 0.34, 0.22])
        _add_gaussian(source, 60, 60, 3.0, 1.4, 0.4, [0.65, 0.44, 0.32])
        zero = apply_star_effects(
            stars,
            zero_mask,
            _settings(round_stars_enabled=True, round_stars_amount=100.0),
            source=source,
        )
        self.assertTrue(np.array_equal(zero, stars))

    def test_effect_inputs_are_read_only(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 55, 60, 3.0, 1.4, 0.4, [0.5, 0.5, 0.5])
        _add_gaussian(source, 55, 60, 3.0, 1.4, 0.4, [0.6, 0.6, 0.6])
        mask = _mask(*self.shape[:2])
        stars_before, source_before, mask_before = stars.copy(), source.copy(), mask.copy()
        settings = _settings(
            round_stars_enabled=True,
            round_stars_amount=100.0,
            faint_star_suppression=True,
            faint_star_amount=100.0,
            star_glow_enabled=True,
            star_glow_amount=20.0,
            star_glow_radius_px=8.0,
        )
        result = apply_star_effects(stars, mask, settings, source=source)
        self.assertIsNotNone(result)
        self.assertTrue(np.array_equal(stars, stars_before))
        self.assertTrue(np.array_equal(source, source_before))
        self.assertTrue(np.array_equal(mask, mask_before))

    def test_global_star_amount_does_not_change_effect_artifact(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 60, 60, 3.0, 1.5, 0.4, [0.5, 0.5, 0.5])
        _add_gaussian(source, 60, 60, 3.0, 1.5, 0.4, [0.6, 0.6, 0.6])
        settings = _settings(
            round_stars_enabled=True,
            round_stars_amount=100.0,
            star_glow_enabled=True,
            star_glow_amount=30.0,
            star_glow_radius_px=8.0,
        )
        low = apply_star_effects(stars, self.mask, replace(settings, star_amount=0.0), source=source)
        high = apply_star_effects(stars, self.mask, replace(settings, star_amount=100.0), source=source)
        self.assertTrue(np.array_equal(low, high))

    def test_cancellation_and_progress_contract(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 60, 60, 3.0, 1.5, 0.4, [0.5, 0.5, 0.5])
        _add_gaussian(source, 60, 60, 3.0, 1.5, 0.4, [0.6, 0.6, 0.6])
        calls = []

        def progress(done, total, description):
            calls.append((done, total, description))

        settings = _settings(
            round_stars_enabled=True,
            round_stars_amount=100.0,
            faint_star_suppression=True,
            faint_star_amount=100.0,
            star_glow_enabled=True,
            star_glow_amount=20.0,
            star_glow_radius_px=8.0,
        )
        result = apply_star_effects(stars, self.mask, settings, source=source, progress_callback=progress)
        self.assertIsNotNone(result)
        self.assertTrue(calls)
        self.assertTrue(all(call[1] == 4 for call in calls))
        self.assertEqual(calls[-1][0], 4)
        self.assertTrue(all(calls[i][0] <= calls[i + 1][0] for i in range(len(calls) - 1)))

        cancelled = apply_star_effects(stars, self.mask, settings, source=source, should_interrupt=lambda: True)
        self.assertIsNone(cancelled)
        calls_seen = {"n": 0}

        def interrupt_after_detection():
            calls_seen["n"] += 1
            return calls_seen["n"] >= 2

        interrupted = apply_star_effects(
            stars, self.mask, settings, source=source, should_interrupt=interrupt_after_detection
        )
        self.assertIsNone(interrupted)

    def test_tiny_and_constant_inputs_are_identity(self):
        settings = _settings(round_stars_enabled=True, round_stars_amount=100.0)
        for shape in ((1, 1, 3), (8, 8, 3), (32, 32, 3)):
            stars = np.full(shape, 0.3, np.float32)
            source = np.full(shape, 0.5, np.float32)
            mask = _mask(shape[0], shape[1])
            result = apply_star_effects(stars, mask, settings, source=source)
            self.assertIsNotNone(result)
            self.assertTrue(np.array_equal(result, stars))

    def test_source_is_required_and_versioned(self):
        self.assertIsInstance(STAR_EFFECT_VERSION, int)
        self.assertGreater(STAR_EFFECT_VERSION, 0)
        with self.assertRaises(TypeError):
            apply_star_effects(self.stars, self.mask, _settings())  # type: ignore[call-arg]


if __name__ == "__main__":
    unittest.main()
