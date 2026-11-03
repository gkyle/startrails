"""Focused numeric contracts for ranked star effects and stored effect layers."""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from startrails.lib.finish.defaults import FinishSettings
from startrails.lib.finish.star_analysis import StarCandidate, analyze_stars
from startrails.lib.finish.star_catalog import build_catalog, included_mask, measure_catalog
from startrails.lib.finish.star_effects import (
    GLOW_PYRAMID_RADIUS_PX,
    STAR_EFFECT_VERSION,
    SparseRoundDelta,
    _blur_glow_seed,
    _footprint_flux,
    _measure_local,
    _neighbors,
    _round_gates,
    _round_one_owned,
    _victim_reach,
    build_round_delta,
    compose_star_layer,
    load_round_delta,
    render_glow,
    save_round_delta,
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
    image[y0:y1, x0:x1] += (core + tail)[..., None] * np.asarray(amplitude, np.float32)


def _settings(**overrides):
    return replace(FinishSettings(), **overrides)


def _mask(height, width, value=1.0):
    return np.full((height, width), value, np.float32)


def _add_noise(image, sigma=0.0005):
    image += np.random.default_rng(4).normal(0.0, sigma, image.shape).astype(np.float32)
    np.clip(image, 0.0, 1.0, out=image)


def _nearest(candidates, x, y):
    return min(candidates, key=lambda c: (c.x - x) ** 2 + (c.y - y) ** 2)


def _catalog(test, stars, source, mask, cutoff=None):
    catalog = build_catalog(stars, source, mask, cutoff=cutoff)
    test.assertIsNotNone(catalog)
    return catalog


def _inclusion(catalog, cutoff=None):
    return included_mask(catalog, cutoff=cutoff)


def _round_layers(test, stars, source, mask, *, cutoff=None):
    catalog = _catalog(test, stars, source, mask, cutoff)
    delta = build_round_delta(
        stars,
        mask,
        catalog,
        cutoff=cutoff,
        inclusion_mask=_inclusion(catalog, cutoff),
    )
    test.assertIsNotNone(delta)
    return catalog, delta


def _render_glow(stars, sky_mask, catalog, *, cutoff, glow_star_count, radius_px, should_interrupt=None):
    return render_glow(
        stars,
        sky_mask,
        catalog,
        cutoff=cutoff,
        inclusion_mask=_inclusion(catalog, cutoff),
        glow_star_count=glow_star_count,
        radius_px=radius_px,
        should_interrupt=should_interrupt,
    )


def _compose(stars, catalog, delta, glow, *, amount=100.0, glow_amount=0.0, cutoff=None, compare=False):
    settings = _settings(
        star_count_cutoff=cutoff,
        round_stars_enabled=delta is not None and amount > 0.0,
        round_stars_amount=amount,
        star_glow_enabled=glow is not None and glow_amount > 0.0,
        star_glow_amount=glow_amount,
    )
    return compose_star_layer(
        stars,
        catalog,
        delta,
        glow,
        settings,
        inclusion_mask=_inclusion(catalog, cutoff),
        compare=compare,
    )


class TestStarCatalogEffects(unittest.TestCase):
    shape = (128, 128, 3)

    def setUp(self):
        rng = np.random.default_rng(11)
        self.stars = np.clip(rng.normal(0.0, 0.001, self.shape).astype(np.float32), 0.0, 1.0)
        self.source = np.clip(self.stars + 0.1, 0.0, 1.0)
        self.mask = _mask(*self.shape[:2])

    def test_neutral_is_exact_identity_and_inputs_are_read_only(self):
        stars_before = self.stars.copy()
        source_before = self.source.copy()
        mask_before = self.mask.copy()
        catalog = _catalog(self, self.stars, self.source, self.mask, None)
        inclusion = _inclusion(catalog, None)
        result = compose_star_layer(
            self.stars,
            catalog,
            None,
            None,
            _settings(star_count_cutoff=None),
            inclusion_mask=inclusion,
        )
        self.assertTrue(np.array_equal(result, self.stars))
        self.assertFalse(np.shares_memory(result, self.stars))
        self.assertTrue(np.array_equal(self.stars, stars_before))
        self.assertTrue(np.array_equal(self.source, source_before))
        self.assertTrue(np.array_equal(self.mask, mask_before))
        compared = compose_star_layer(
            self.stars,
            catalog,
            None,
            None,
            _settings(star_count_cutoff=None),
            inclusion_mask=inclusion,
            compare=True,
        )
        self.assertTrue(np.array_equal(compared, self.stars))

    def test_round_isolated_trailing_and_coma_tolerances_at_all(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 38, 40, 3.5, 1.8, 0.4, [0.45, 0.45, 0.45])
        _add_gaussian(source, 38, 40, 3.5, 1.8, 0.4, [0.55, 0.55, 0.55])
        _add_gaussian(stars, 84, 38, 6.0, 1.3, 0.7, [0.50, 0.50, 0.50])
        _add_gaussian(source, 84, 38, 6.0, 1.3, 0.7, [0.60, 0.60, 0.60])
        _add_coma(stars, 45, 92, 2.4, 1.2, 0.1, [0.45, 0.45, 0.45])
        _add_coma(source, 45, 92, 2.4, 1.2, 0.1, [0.55, 0.55, 0.55])
        _add_noise(stars)
        catalog, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        before = catalog.analysis
        result = _compose(stars, catalog, delta, None, cutoff=None)
        self.assertIsNotNone(result)
        after = analyze_stars(result, source, self.mask)
        self.assertIsNotNone(after)
        checked = 0
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
        self.assertEqual(sum(decision == "corrected" for decision in delta.decision), 3)

    def test_round_amount_scales_the_same_verified_correction(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 60, 60, 3.8, 1.5, 0.4, [0.55, 0.55, 0.55])
        _add_gaussian(source, 60, 60, 3.8, 1.5, 0.4, [0.65, 0.65, 0.65])
        catalog, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        candidate = _nearest(catalog.analysis.candidates, 60, 60)
        full = _compose(stars, catalog, delta, None, amount=100.0, cutoff=None)
        full_delta = full - stars
        changed = np.any(np.abs(full_delta) > 1e-7, axis=2)
        self.assertTrue(np.any(changed))
        flux_before = _footprint_flux(stars, candidate.x, candidate.y, candidate.footprint_radius_px)
        color_before = flux_before / max(float(flux_before.sum()), 1e-9)
        _, _, ellipticity_before = _measure_local(stars, candidate.x, candidate.y, candidate.core_radius_px)
        for amount in (25.0, 50.0, 75.0):
            with self.subTest(amount=amount):
                partial = _compose(stars, catalog, delta, None, amount=amount, cutoff=None)
                np.testing.assert_allclose(
                    (partial - stars)[changed], (amount / 100.0) * full_delta[changed], atol=1e-6, rtol=0.0
                )
                # Isolated star: its owned region covers this core, so the
                # documented amount-aware owned-ellipticity bound applies to
                # this same-region before/after measurement.
                cy, cx, ellipticity_after = _measure_local(partial, candidate.x, candidate.y, candidate.core_radius_px)
                self.assertLessEqual(float(np.hypot(cy - candidate.y, cx - candidate.x)), 0.5)
                flux_after = _footprint_flux(partial, candidate.x, candidate.y, candidate.footprint_radius_px)
                flux_error = np.abs(flux_after - flux_before) / np.maximum(np.abs(flux_before), 1e-9)
                self.assertLessEqual(float(flux_error.max()), 0.01)
                color_after = flux_after / max(float(flux_after.sum()), 1e-9)
                color_drift = np.abs(color_after - color_before) / np.maximum(np.abs(color_before), 1e-9)
                self.assertLessEqual(float(color_drift.max()), 0.01)
                expected_ratio = 1.0 - (1.0 - 0.75) * (amount / 100.0)
                self.assertLessEqual(
                    ellipticity_after,
                    max(0.10, expected_ratio * ellipticity_before),
                )

    def test_round_skips_saturated_border_blended_and_noise(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 35, 40, 3.0, 1.3, 0.5, [0.32, 0.32, 0.32])
        _add_gaussian(source, 35, 40, 3.0, 1.3, 0.5, [1.5, 1.5, 1.5])
        np.clip(source, 0.0, 1.0, out=source)
        _add_gaussian(stars, 90, 40, 3.0, 1.3, 0.5, [0.45, 0.45, 0.45])
        _add_gaussian(source, 90, 40, 3.0, 1.3, 0.5, [0.55, 0.55, 0.55])
        catalog, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        result = _compose(stars, catalog, delta, None, cutoff=None)
        self.assertTrue(np.array_equal(result[20:55, 18:52], stars[20:55, 18:52]))
        self.assertFalse(np.array_equal(result[20:55, 75:105], stars[20:55, 75:105]))

        blend_stars = np.zeros(self.shape, np.float32)
        blend_source = np.zeros_like(blend_stars)
        _add_gaussian(blend_stars, 55, 50, 3.0, 1.4, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(blend_stars, 64, 50, 3.0, 1.4, 0.2, [0.4, 0.4, 0.4])
        blend_source[:] = np.clip(blend_stars + 0.1, 0.0, 1.0)
        blend_catalog, blend_delta = _round_layers(self, blend_stars, blend_source, self.mask, cutoff=None)
        self.assertTrue(
            np.array_equal(_compose(blend_stars, blend_catalog, blend_delta, None, cutoff=None), blend_stars)
        )

        border_stars = np.zeros(self.shape, np.float32)
        border_source = np.zeros_like(border_stars)
        _add_gaussian(border_stars, 3, 60, 3.0, 1.4, 0.2, [0.5, 0.5, 0.5])
        border_source[:] = np.clip(border_stars + 0.1, 0.0, 1.0)
        border_catalog, border_delta = _round_layers(self, border_stars, border_source, self.mask, cutoff=None)
        self.assertTrue(
            np.array_equal(_compose(border_stars, border_catalog, border_delta, None, cutoff=None), border_stars)
        )

        noise = np.clip(np.random.default_rng(2).normal(0.0, 0.0015, self.shape), 0.0, 1.0).astype(np.float32)
        noise_source = np.full(self.shape, 0.15, np.float32)
        noise_catalog, noise_delta = _round_layers(self, noise, noise_source, self.mask, cutoff=None)
        self.assertTrue(np.array_equal(_compose(noise, noise_catalog, noise_delta, None, cutoff=None), noise))
        self.assertEqual(int(noise_delta.offsets[-1]), 0)

    def test_round_resolves_included_overlap_and_protects_saturated_neighbor(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 45, 55, 3.0, 1.5, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(stars, 65, 55, 3.0, 1.5, 0.2, [0.5, 0.5, 0.5])
        source[:] = np.clip(stars + 0.1, 0.0, 1.0)
        catalog, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        self.assertGreaterEqual(int(np.sum(delta.decision == "corrected")), 2)
        result = _compose(stars, catalog, delta, None, cutoff=None)
        self.assertFalse(np.array_equal(result, stars))
        candidates = [c for c in catalog.analysis.candidates if c.is_valid]
        after = analyze_stars(result, source, self.mask)
        self.assertIsNotNone(after)
        nearest = []
        for original in candidates:
            updated = _nearest(after.candidates, original.x, original.y)
            nearest.append(id(updated))
            self.assertLess(np.hypot(updated.x - original.x, updated.y - original.y), 0.5)
        self.assertEqual(len(set(nearest)), len(candidates))
        inclusion = _inclusion(catalog, None)
        for index in range(len(delta.y0)):
            ys = int(delta.y0[index]) + delta.local_y[int(delta.offsets[index]) : int(delta.offsets[index + 1])]
            xs = int(delta.x0[index]) + delta.local_x[int(delta.offsets[index]) : int(delta.offsets[index + 1])]
            self.assertTrue(np.all(inclusion[ys, xs] > 0.0))

        for amount in (25.0, 50.0, 75.0):
            partial = _compose(stars, catalog, delta, None, amount=amount, cutoff=None)
            for original in candidates:
                cy, cx, e_after = _measure_local(partial, original.x, original.y, original.core_radius_px)
                self.assertLessEqual(float(np.hypot(cy - original.y, cx - original.x)), 0.5)
                flux_before = _footprint_flux(stars, original.x, original.y, original.footprint_radius_px)
                flux_after = _footprint_flux(partial, original.x, original.y, original.footprint_radius_px)
                self.assertLessEqual(
                    float(np.max(np.abs(flux_after - flux_before) / np.maximum(np.abs(flux_before), 1e-9))),
                    0.01,
                )
                color_before = flux_before / max(float(flux_before.sum()), 1e-9)
                color_after = flux_after / max(float(flux_after.sum()), 1e-9)
                self.assertLessEqual(
                    float(np.max(np.abs(color_after - color_before) / np.maximum(np.abs(color_before), 1e-9))),
                    0.01,
                )
                # Ellipticity is an owned-region contract; this whole-core
                # measurement is deliberately not asserted here.

        # A saturated neighbour's measured core must remain untouched even when
        # the target is considered.
        sat_stars = np.zeros(self.shape, np.float32)
        sat_source = np.zeros_like(sat_stars)
        _add_gaussian(sat_stars, 60, 80, 3.4, 1.5, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(sat_source, 60, 80, 3.4, 1.5, 0.2, [0.6, 0.6, 0.6])
        _add_gaussian(sat_stars, 82, 80, 2.8, 1.4, 0.2, [0.32, 0.32, 0.32])
        _add_gaussian(sat_source, 82, 80, 2.8, 1.4, 0.2, [1.5, 1.5, 1.5])
        np.clip(sat_source, 0.0, 1.0, out=sat_source)
        sat_catalog, sat_delta = _round_layers(self, sat_stars, sat_source, self.mask, cutoff=None)
        saturated = min(
            (c for c in sat_catalog.analysis.candidates if c.is_saturated),
            key=lambda c: (c.x - 82) ** 2 + (c.y - 80) ** 2,
        )
        sat_result = _compose(sat_stars, sat_catalog, sat_delta, None, cutoff=None)
        yy, xx = np.mgrid[0 : self.shape[0], 0 : self.shape[1]]
        core = (yy - saturated.y) ** 2 + (xx - saturated.x) ** 2 <= saturated.core_radius_px**2
        self.assertEqual(float(np.max(np.abs(sat_result[core] - sat_stars[core]))), 0.0)

    def test_round_owner_query_includes_competitor_within_two_radii(self):
        probe = np.zeros(self.shape, np.float32)
        probe_source = np.zeros_like(probe)
        _add_gaussian(probe, 45, 64, 5.0, 2.0, 0.0, [0.60, 0.60, 0.60])
        _add_gaussian(probe_source, 45, 64, 5.0, 2.0, 0.0, [0.70, 0.70, 0.70])
        probe_catalog = _catalog(self, probe, probe_source, self.mask, None)
        primary = _nearest(probe_catalog.analysis.candidates, 45, 64)
        radius = primary.footprint_radius_px
        distance = radius + 5.0 + 2.0
        self.assertLess(distance, 2.0 * radius)

        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 45, 64, 5.0, 2.0, 0.0, [0.60, 0.60, 0.60])
        _add_gaussian(source, 45, 64, 5.0, 2.0, 0.0, [0.70, 0.70, 0.70])
        _add_gaussian(stars, 45 + distance, 64, 1.2, 1.1, 0.0, [0.20, 0.20, 0.20])
        _add_gaussian(source, 45 + distance, 64, 1.2, 1.1, 0.0, [0.25, 0.25, 0.25])
        catalog, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        corrected = _nearest(catalog.analysis.candidates, 45, 64)
        result = _compose(stars, catalog, delta, None, cutoff=None)
        core_pixel = (int(round(corrected.y)), int(round(corrected.x)))
        self.assertGreater(float(np.abs(result[core_pixel] - stars[core_pixel]).max()), 1e-4)
        px = int(round(corrected.x + 0.7 * radius))
        py = int(round(corrected.y))
        self.assertGreater(float(stars[py, px].max()), 1e-5)
        self.assertLess(float(np.abs(result[py, px] - stars[py, px]).max()), 1e-8)

    def test_round_mask_ramp_verifies_masked_centroid_flux_and_color(self):
        width = self.shape[1]
        ramp = np.tile(np.linspace(0.0, 1.0, width, dtype=np.float32), (self.shape[0], 1))
        changed_levels = 0
        for level in (0.5, 0.7, 0.9):
            stars = np.zeros(self.shape, np.float32)
            source = np.zeros_like(stars)
            x = float(np.argmin(np.abs(ramp[0] - level)))
            _add_gaussian(stars, x, 64, 3.2, 1.5, 0.4, [0.55, 0.34, 0.22])
            _add_gaussian(source, x, 64, 3.2, 1.5, 0.4, [0.65, 0.44, 0.32])
            catalog, delta = _round_layers(self, stars, source, ramp, cutoff=None)
            candidate = _nearest(catalog.analysis.candidates, x, 64)
            result = _compose(stars, catalog, delta, None, cutoff=None)
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
            # Ellipticity is owned-region-only and is covered by the isolated
            # amount test; the ramp whole-core measurement is not asserted.
        self.assertGreater(changed_levels, 0)

        zero_mask = np.zeros(self.shape[:2], np.float32)
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 60, 60, 3.0, 1.4, 0.4, [0.55, 0.34, 0.22])
        _add_gaussian(source, 60, 60, 3.0, 1.4, 0.4, [0.65, 0.44, 0.32])
        zero_catalog, zero_delta = _round_layers(self, stars, source, zero_mask, cutoff=None)
        zero = _compose(stars, zero_catalog, zero_delta, None, cutoff=None)
        self.assertTrue(np.array_equal(zero, stars))

    def test_unresolved_same_component_multipeak_is_unchanged(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 76.5, 80, 3.0, 1.4, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(stars, 83.5, 80, 3.0, 1.4, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(source, 76.5, 80, 3.0, 1.4, 0.2, [0.6, 0.6, 0.6])
        _add_gaussian(source, 83.5, 80, 3.0, 1.4, 0.2, [0.6, 0.6, 0.6])
        np.clip(source, 0.0, 1.0, out=source)
        catalog, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        self.assertEqual(len(catalog.analysis.candidates), 1)
        self.assertTrue(bool(catalog.intrinsic_blended[0]))
        self.assertEqual(delta.decision[0], "ineligible:multi_peak_component")
        self.assertEqual(int(delta.offsets[-1]), 0)
        self.assertTrue(np.array_equal(_compose(stars, catalog, delta, None, cutoff=None), stars))
        hidden_mask = self.mask.copy()
        hidden_mask[:, 80:] = 0.0
        hidden_delta = build_round_delta(stars, self.mask, catalog, cutoff=None, inclusion_mask=hidden_mask)
        self.assertIsNotNone(hidden_delta)
        self.assertEqual(hidden_delta.decision[0], "ineligible:multi_peak_component")
        self.assertEqual(int(hidden_delta.offsets[-1]), 0)

    def test_owned_peak_gate_rejects_mask_removed_core_peak(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 64, 64, 3.2, 1.5, 0.4, [0.55, 0.34, 0.22])
        _add_gaussian(source, 64, 64, 3.2, 1.5, 0.4, [0.65, 0.44, 0.32])
        catalog = _catalog(self, stars, source, self.mask, None)
        candidate = _nearest(catalog.analysis.candidates, 64, 64)
        yy, xx = np.mgrid[0 : self.shape[0], 0 : self.shape[1]]
        hole = (yy - candidate.y) ** 2 + (xx - candidate.x) ** 2 <= 2.0**2
        inclusion = np.ones(self.shape[:2], np.float32)
        inclusion[hole] = 0.0
        out = stars.copy()
        status, support = _round_one_owned(
            out,
            candidate,
            0,
            [],
            self.mask,
            inclusion,
            True,
            catalog.threshold,
        )
        self.assertEqual(status, "rejected:no_owned_peak")
        self.assertIsNone(support)
        self.assertTrue(np.array_equal(out, stars))

    def test_large_diagonal_included_core_is_subtracted_beyond_two_radii(self):
        stars = np.zeros((160, 160, 3), np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 40, 80, 1.5, 1.2, 0.0, [0.5, 0.5, 0.5])
        _add_gaussian(source, 40, 80, 1.5, 1.2, 0.0, [0.6, 0.6, 0.6])
        offset = 22.0 / np.sqrt(2.0)
        _add_gaussian(stars, 40 + offset, 80 + offset, 5.0, 4.0, 0.2, [0.32, 0.32, 0.32])
        _add_gaussian(source, 40 + offset, 80 + offset, 5.0, 4.0, 0.2, [1.5, 1.5, 1.5])
        np.clip(source, 0.0, 1.0, out=source)
        catalog = _catalog(self, stars, source, np.ones((160, 160), np.float32), None)
        inclusion = np.ones(stars.shape[:2], np.float32)
        delta = build_round_delta(
            stars, np.ones((160, 160), np.float32), catalog, cutoff=None, inclusion_mask=inclusion
        )
        self.assertIsNotNone(delta)
        target = _nearest(catalog.analysis.candidates, 40, 80)
        target_rank = catalog.analysis.candidates.index(target)
        self.assertEqual(delta.decision[target_rank], "corrected")
        saturated = min(
            (c for c in catalog.analysis.candidates if c.is_saturated),
            key=lambda c: (c.x - 40 - offset) ** 2 + (c.y - 80 - offset) ** 2,
        )
        result = _compose(stars, catalog, delta, None, cutoff=None)
        yy, xx = np.mgrid[0:160, 0:160]
        core = (yy - saturated.y) ** 2 + (xx - saturated.x) ** 2 <= saturated.core_radius_px**2
        self.assertEqual(float(np.max(np.abs(result[core] - stars[core]))), 0.0)

    def test_excluded_neighbor_is_corrected_without_touching_its_label_pixels(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 45, 64, 5.0, 2.0, 0.0, [0.60, 0.60, 0.60])
        _add_gaussian(source, 45, 64, 5.0, 2.0, 0.0, [0.70, 0.70, 0.70])
        _add_gaussian(stars, 65, 64, 1.2, 1.1, 0.0, [0.20, 0.20, 0.20])
        _add_gaussian(source, 65, 64, 1.2, 1.1, 0.0, [0.25, 0.25, 0.25])
        stars_before = stars.copy()
        catalog = _catalog(self, stars, source, self.mask, 1)
        inclusion = _inclusion(catalog, 1)
        excluded_label = catalog.labels == int(catalog.component_ids[1])
        self.assertGreater(int(np.count_nonzero(excluded_label)), 0)
        self.assertTrue(np.all(inclusion[excluded_label] == 0.0))

        delta = build_round_delta(stars, self.mask, catalog, cutoff=1, inclusion_mask=inclusion)
        self.assertIsNotNone(delta)
        self.assertEqual(delta.decision[0], "corrected")
        self.assertEqual(delta.decision[1], "excluded")
        self.assertGreater(int(delta.offsets[-1]), 0)
        result = _compose(stars, catalog, delta, None, amount=100.0, cutoff=1)
        base = inclusion[..., None] * stars
        self.assertTrue(np.array_equal(result[excluded_label], base[excluded_label]))
        self.assertTrue(np.array_equal(stars, stars_before))
        for index in range(len(delta.y0)):
            ys = int(delta.y0[index]) + delta.local_y[int(delta.offsets[index]) : int(delta.offsets[index + 1])]
            xs = int(delta.x0[index]) + delta.local_x[int(delta.offsets[index]) : int(delta.offsets[index + 1])]
            self.assertTrue(np.all(inclusion[ys, xs] > 0.0))

    def test_square_centroid_stamp_reach_covers_diagonal_corners(self):
        candidate = StarCandidate(
            y=10.0,
            x=10.0,
            flux=1.0,
            peak_brightness=0.5,
            color_ratio=(1 / 3, 1 / 3, 1 / 3),
            ellipticity=0.2,
            orientation_rad=0.0,
            footprint_radius_px=5.0,
            core_radius_px=10.0,
        )
        self.assertAlmostEqual(_victim_reach(candidate), np.sqrt(2.0) * 11.0)
        self.assertEqual(_victim_reach(candidate), max(5.0, np.sqrt(2.0) * 11.0))

    def test_cutoff_history_produces_identical_round_delta(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        for index, x in enumerate((45, 80, 115)):
            _add_gaussian(stars, x, 80, 3.2, 1.4, 0.2, [0.5 - 0.05 * index] * 3)
            _add_gaussian(source, x, 80, 3.2, 1.4, 0.2, [0.6 - 0.05 * index] * 3)
        fresh = _catalog(self, stars, source, self.mask, None)
        partial = _catalog(self, stars, source, self.mask, 2)
        grown = measure_catalog(partial, stars, source, self.mask, cutoff=None)
        self.assertIsNotNone(grown)
        fresh_delta = build_round_delta(stars, self.mask, fresh, cutoff=None, inclusion_mask=_inclusion(fresh, None))
        grown_delta = build_round_delta(stars, self.mask, grown, cutoff=None, inclusion_mask=_inclusion(grown, None))
        self.assertIsNotNone(fresh_delta)
        self.assertIsNotNone(grown_delta)
        np.testing.assert_array_equal(fresh_delta.decision, grown_delta.decision)
        for name in ("y0", "x0", "height", "width", "offsets", "local_y", "local_x", "values"):
            np.testing.assert_array_equal(getattr(fresh_delta, name), getattr(grown_delta, name))

    def test_cutoff_exclusion_records_decisions_and_compare_returns_s_inc(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 40, 40, 3.2, 1.5, 0.3, [0.55, 0.55, 0.55])
        _add_gaussian(source, 40, 40, 3.2, 1.5, 0.3, [0.65, 0.65, 0.65])
        _add_gaussian(stars, 90, 90, 3.2, 1.5, 0.3, [0.06, 0.06, 0.06])
        _add_gaussian(source, 90, 90, 3.2, 1.5, 0.3, [0.08, 0.08, 0.08])
        catalog = _catalog(self, stars, source, self.mask, 1)
        self.assertEqual(catalog.included_count(1), 1)
        top = catalog.analysis.candidates[0]
        self.assertLess(np.hypot(top.x - 40, top.y - 40), 2.0)
        delta = build_round_delta(stars, self.mask, catalog, cutoff=1, inclusion_mask=_inclusion(catalog, 1))
        self.assertIsNotNone(delta)
        self.assertEqual(delta.decision[0].startswith(("corrected", "blocked:", "ineligible:")), True)
        self.assertEqual(delta.decision[1], "excluded")

        include_mask = included_mask(catalog, cutoff=1)
        bright = _nearest(catalog.analysis.candidates, 40, 40)
        faint = _nearest(catalog.analysis.candidates, 90, 90)
        self.assertGreater(float(include_mask[int(round(bright.y)), int(round(bright.x))]), 0.0)
        self.assertEqual(float(include_mask[int(round(faint.y)), int(round(faint.x))]), 0.0)

        composed = _compose(stars, catalog, delta, None, amount=100.0, cutoff=1)
        compared = _compose(stars, catalog, delta, None, amount=100.0, cutoff=1, compare=True)
        np.testing.assert_array_equal(compared, include_mask[..., None] * stars)
        self.assertTrue(np.array_equal(composed[70:110, 70:110], (include_mask[..., None] * stars)[70:110, 70:110]))

        all_catalog = _catalog(self, stars, source, self.mask, None)
        all_delta = build_round_delta(
            stars, self.mask, all_catalog, cutoff=None, inclusion_mask=_inclusion(all_catalog, None)
        )
        self.assertIsNotNone(all_delta)
        no_effects = _compose(stars, all_catalog, all_delta, None, amount=0.0, cutoff=None)
        self.assertTrue(np.array_equal(no_effects, stars))

    def test_all_cutoff_decisions_follow_step10_gates_without_exclusions(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 40, 40, 3.5, 1.8, 0.4, [0.45, 0.45, 0.45])
        _add_gaussian(source, 40, 40, 3.5, 1.8, 0.4, [0.55, 0.55, 0.55])
        _add_gaussian(stars, 55, 50, 3.0, 1.4, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(stars, 64, 50, 3.0, 1.4, 0.2, [0.4, 0.4, 0.4])
        _add_gaussian(source, 55, 50, 3.0, 1.4, 0.2, [0.6, 0.6, 0.6])
        _add_gaussian(source, 64, 50, 3.0, 1.4, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(stars, 35, 90, 3.0, 1.3, 0.5, [0.32, 0.32, 0.32])
        _add_gaussian(source, 35, 90, 3.0, 1.3, 0.5, [1.5, 1.5, 1.5])
        _add_gaussian(stars, 3, 20, 3.0, 1.4, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(source, 3, 20, 3.0, 1.4, 0.2, [0.6, 0.6, 0.6])
        _add_gaussian(stars, 100, 22, 3.5, 1.6, 0.3, [0.5, 0.5, 0.5])
        _add_gaussian(source, 100, 22, 3.5, 1.6, 0.3, [0.6, 0.6, 0.6])
        np.clip(source, 0.0, 1.0, out=source)

        catalog, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        self.assertEqual(len(delta.decision), len(catalog.analysis.candidates))
        self.assertFalse(np.any(delta.decision == "excluded"))
        for candidate, decision in zip(catalog.analysis.candidates, delta.decision):
            if _round_gates(candidate):
                self.assertTrue(
                    decision.startswith(
                        (
                            "corrected",
                            "blocked:",
                            "rejected:",
                            "ineligible:multi_peak_component",
                            "ineligible:unattributed_peak",
                            "ineligible:blended",
                        )
                    ),
                    decision,
                )
            else:
                self.assertTrue(decision.startswith("ineligible:"), decision)
        self.assertTrue(np.any(delta.decision == "corrected"))
        self.assertTrue(np.any(np.char.startswith(delta.decision.astype(str), "ineligible:")))
        self.assertTrue(np.all([reason for reason in delta.decision]))

    def test_excluded_core_m_sliver_no_longer_blocks_and_zero_m_pixels_stay_clean(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 45, 64, 5.0, 2.0, 0.0, [0.60, 0.60, 0.60])
        _add_gaussian(source, 45, 64, 5.0, 2.0, 0.0, [0.70, 0.70, 0.70])
        _add_gaussian(stars, 65, 64, 1.2, 1.1, 0.0, [0.20, 0.20, 0.20])
        _add_gaussian(source, 65, 64, 1.2, 1.1, 0.0, [0.25, 0.25, 0.25])
        catalog = _catalog(self, stars, source, self.mask, 1)
        inclusion = _inclusion(catalog, 1)
        excluded = catalog.analysis_for_cutoff(1).candidates[1]
        sliver = inclusion.copy()
        sliver[int(round(excluded.y)), int(round(excluded.x))] = 1.0

        delta = build_round_delta(stars, self.mask, catalog, cutoff=1, inclusion_mask=sliver)
        self.assertIsNotNone(delta)
        self.assertEqual(delta.decision[0], "corrected")
        self.assertGreater(int(delta.offsets[-1]), 0)
        for index in range(len(delta.y0)):
            ys = int(delta.y0[index]) + delta.local_y[int(delta.offsets[index]) : int(delta.offsets[index + 1])]
            xs = int(delta.x0[index]) + delta.local_x[int(delta.offsets[index]) : int(delta.offsets[index + 1])]
            self.assertTrue(np.all(sliver[ys, xs] > 0.0))

    def test_sparse_round_delta_save_load_and_validation(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 60, 60, 3.5, 1.5, 0.4, [0.5, 0.4, 0.3])
        _add_gaussian(source, 60, 60, 3.5, 1.5, 0.4, [0.6, 0.5, 0.4])
        _, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        self.assertGreater(len(delta.y0), 0)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "round.npz"
            self.assertEqual(save_round_delta(path, delta, identity="separation|mask"), path)
            loaded = load_round_delta(path, identity="separation|mask")
            for name in (
                "y0",
                "x0",
                "height",
                "width",
                "offsets",
                "local_y",
                "local_x",
                "values",
                "rank",
                "decision",
            ):
                np.testing.assert_array_equal(getattr(loaded, name), getattr(delta, name))
            with self.assertRaises(ValueError):
                load_round_delta(path, identity="other")
            object_path = Path(directory) / "pickled.npz"
            with object_path.open("wb") as stream:
                np.savez(
                    stream,
                    format_version=np.asarray(2, np.int32),
                    star_effect_version=np.asarray(STAR_EFFECT_VERSION, np.int32),
                    identity=np.asarray("separation|mask"),
                    image_shape=np.asarray(delta.image_shape, np.int64),
                    y0=delta.y0,
                    x0=delta.x0,
                    height=delta.height,
                    width=delta.width,
                    offsets=delta.offsets,
                    local_y=delta.local_y,
                    local_x=delta.local_x,
                    values=delta.values,
                    rank=delta.rank,
                    decision=np.asarray(list(delta.decision), dtype=object),
                )
            with self.assertRaises(ValueError):
                load_round_delta(object_path, identity="separation|mask")

        with self.assertRaises(ValueError):
            SparseRoundDelta(
                y0=np.array([0, 0], np.int32),
                x0=np.array([0, 0], np.int32),
                height=np.array([4, 4], np.int32),
                width=np.array([4, 4], np.int32),
                offsets=np.array([0, 1, 2], np.int64),
                local_y=np.array([0, 0], np.int32),
                local_x=np.array([0, 0], np.int32),
                values=np.ones((2, 3), np.float32),
                image_shape=(16, 16),
                rank=np.array([0, 1], np.int32),
                decision=np.array(["corrected", "corrected"]),
            )

    def test_load_rejects_malformed_raw_arrays_before_casting(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 60, 60, 3.5, 1.5, 0.4, [0.5, 0.4, 0.3])
        _add_gaussian(source, 60, 60, 3.5, 1.5, 0.4, [0.6, 0.5, 0.4])
        _, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        self.assertGreater(int(delta.offsets[-1]), 0)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "valid.npz"
            save_round_delta(path, delta, identity="separation|mask")
            with np.load(path, allow_pickle=False) as loaded:
                arrays = {name: np.asarray(loaded[name]) for name in loaded.files}

            def write_variant(name, overrides):
                destination = Path(directory) / f"{name}.npz"
                with destination.open("wb") as stream:
                    np.savez(stream, **(arrays | overrides))
                return destination

            variants = {
                "shape_length": {"image_shape": np.asarray([16, 16, 3], np.int64)},
                "fractional_y0": {"y0": delta.y0.astype(np.float32)},
                "fractional_offsets": {"offsets": delta.offsets.astype(np.float32)},
                "negative_y0": {"y0": np.where(np.arange(len(delta.y0)) == 0, -1, delta.y0)},
                "bad_offsets": {
                    "offsets": delta.offsets + np.where(np.arange(len(delta.offsets)) == len(delta.offsets) - 1, 1, 0)
                },
                "empty_offsets": {"offsets": np.asarray([], np.int64)},
                "scalar_shape": {"image_shape": np.asarray(16, np.int64)},
                "bad_rank": {"rank": np.full_like(delta.rank, 1)},
                "old_format": {"format_version": np.asarray(1, np.int32)},
                "old_effect": {"star_effect_version": np.asarray(1, np.int32)},
            }
            for name, overrides in variants.items():
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):
                        load_round_delta(write_variant(name, overrides), identity="separation|mask")

    def test_diagonal_bounding_boxes_pack_disjoint_support_once(self):
        probe = np.zeros(self.shape, np.float32)
        probe_source = np.zeros_like(probe)
        _add_gaussian(probe, 50, 50, 3.2, 1.4, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(probe_source, 50, 50, 3.2, 1.4, 0.2, [0.6, 0.6, 0.6])
        probe_catalog = _catalog(self, probe, probe_source, self.mask, None)
        primary = _nearest(probe_catalog.analysis.candidates, 50, 50)
        separation = primary.footprint_radius_px * 2.0 + 2.0
        offset = separation / np.sqrt(2.0)

        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 50, 50, 3.2, 1.4, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(source, 50, 50, 3.2, 1.4, 0.2, [0.6, 0.6, 0.6])
        _add_gaussian(stars, 50 + offset, 50 + offset, 3.2, 1.4, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(source, 50 + offset, 50 + offset, 3.2, 1.4, 0.2, [0.6, 0.6, 0.6])
        catalog, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        self.assertEqual(int(np.sum(delta.decision == "corrected")), 2)
        self.assertGreaterEqual(len(delta.y0), 2)
        rectangles_overlap = False
        for first in range(len(delta.y0)):
            for second in range(first + 1, len(delta.y0)):
                if (
                    delta.y0[first] < delta.y0[second] + delta.height[second]
                    and delta.y0[second] < delta.y0[first] + delta.height[first]
                    and delta.x0[first] < delta.x0[second] + delta.width[second]
                    and delta.x0[second] < delta.x0[first] + delta.width[first]
                ):
                    rectangles_overlap = True
        self.assertTrue(rectangles_overlap)
        self.assertEqual(delta.values.shape[0], int(delta.offsets[-1]))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "diagonal.npz"
            save_round_delta(path, delta, identity="diagonal")
            loaded = load_round_delta(path, identity="diagonal")
            np.testing.assert_array_equal(loaded.values, delta.values)
            np.testing.assert_array_equal(loaded.local_y, delta.local_y)
            np.testing.assert_array_equal(loaded.local_x, delta.local_x)

    def test_packed_storage_uses_actual_support_not_merged_or_padded_rectangles(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 25, 30, 5.0, 2.0, 0.3, [0.55, 0.55, 0.55])
        _add_gaussian(source, 25, 30, 5.0, 2.0, 0.3, [0.65, 0.65, 0.65])
        _add_gaussian(stars, 90, 95, 2.0, 1.1, 0.7, [0.45, 0.45, 0.45])
        _add_gaussian(source, 90, 95, 2.0, 1.1, 0.7, [0.55, 0.55, 0.55])
        _, delta = _round_layers(self, stars, source, self.mask, cutoff=None)
        self.assertGreaterEqual(len(delta.y0), 2)
        self.assertGreater(int(delta.offsets[-1]), 0)
        self.assertEqual(delta.values.shape, (int(delta.offsets[-1]), 3))
        merged_height = int(np.max(delta.y0 + delta.height) - np.min(delta.y0))
        merged_width = int(np.max(delta.x0 + delta.width) - np.min(delta.x0))
        self.assertLess(int(delta.height.max()), merged_height)
        self.assertLess(int(delta.width.max()), merged_width)
        padded_values = len(delta.y0) * int(delta.height.max()) * int(delta.width.max())
        self.assertLessEqual(delta.values.shape[0], padded_values)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "compact.npz"
            save_round_delta(path, delta, identity="compact")
            loaded = load_round_delta(path, identity="compact")
            self.assertEqual(int(loaded.offsets[-1]), int(delta.offsets[-1]))
            self.assertEqual(loaded.values.shape, delta.values.shape)

    def test_effect_layer_inputs_are_read_only_and_cancellation_returns_none(self):
        stars = np.zeros(self.shape, np.float32)
        source = np.zeros_like(stars)
        _add_gaussian(stars, 55, 60, 3.0, 1.4, 0.4, [0.5, 0.5, 0.5])
        _add_gaussian(source, 55, 60, 3.0, 1.4, 0.4, [0.6, 0.6, 0.6])
        mask = _mask(*self.shape[:2])
        stars_before, source_before, mask_before = stars.copy(), source.copy(), mask.copy()
        catalog = _catalog(self, stars, source, mask, None)
        delta = build_round_delta(stars, mask, catalog, cutoff=None, inclusion_mask=_inclusion(catalog, None))
        glow = _render_glow(stars, mask, catalog, cutoff=None, glow_star_count=100, radius_px=8.0)
        self.assertIsNotNone(delta)
        self.assertIsNotNone(glow)
        composed = compose_star_layer(
            stars,
            catalog,
            delta,
            glow,
            _settings(
                star_count_cutoff=None,
                round_stars_enabled=True,
                round_stars_amount=100.0,
                star_glow_enabled=True,
                star_glow_amount=20.0,
            ),
            inclusion_mask=_inclusion(catalog, None),
        )
        self.assertIsNotNone(composed)
        self.assertTrue(np.array_equal(stars, stars_before))
        self.assertTrue(np.array_equal(source, source_before))
        self.assertTrue(np.array_equal(mask, mask_before))
        self.assertIsNone(
            build_round_delta(
                stars,
                mask,
                catalog,
                cutoff=None,
                inclusion_mask=_inclusion(catalog, None),
                should_interrupt=lambda: True,
            )
        )
        self.assertIsNone(
            _render_glow(
                stars,
                mask,
                catalog,
                cutoff=None,
                glow_star_count=100,
                radius_px=8.0,
                should_interrupt=lambda: True,
            )
        )

    def test_tiny_and_constant_inputs_are_identity_and_versioned(self):
        self.assertEqual(STAR_EFFECT_VERSION, 4)
        for shape in ((8, 8, 3), (32, 32, 3)):
            stars = np.full(shape, 0.3, np.float32)
            source = np.full(shape, 0.5, np.float32)
            mask = _mask(shape[0], shape[1])
            catalog = _catalog(self, stars, source, mask, None)
            delta = build_round_delta(stars, mask, catalog, cutoff=None, inclusion_mask=_inclusion(catalog, None))
            self.assertIsNotNone(delta)
            result = _compose(stars, catalog, delta, None, cutoff=None)
            self.assertTrue(np.array_equal(result, stars))


class TestStarGlow(unittest.TestCase):
    shape = (128, 128, 3)

    def setUp(self):
        self.mask = _mask(*self.shape[:2])
        self.stars = np.zeros(self.shape, np.float32)
        self.source = np.zeros_like(self.stars)
        _add_gaussian(self.stars, 40, 40, 2.5, 1.4, 0.2, [0.55, 0.40, 0.30])
        _add_gaussian(self.source, 40, 40, 2.5, 1.4, 0.2, [0.65, 0.50, 0.38])
        _add_gaussian(self.stars, 90, 40, 2.5, 1.4, 0.2, [0.10, 0.10, 0.10])
        _add_gaussian(self.source, 90, 40, 2.5, 1.4, 0.2, [0.12, 0.12, 0.12])

    def test_glow_selects_top_included_valid_nonblended_without_peak_cutoff(self):
        catalog = _catalog(self, self.stars, self.source, self.mask, None)
        bright = _nearest(catalog.analysis.candidates, 40, 40)
        faint = _nearest(catalog.analysis.candidates, 90, 40)
        glow = _render_glow(self.stars, self.mask, catalog, cutoff=None, glow_star_count=100, radius_px=10.0)
        self.assertIsNotNone(glow)
        self.assertGreater(float(_footprint_flux(glow, bright.x, bright.y, 20.0).sum()), 0.0)
        # The old peak cutoff is gone: a faint but ranked, valid star glows.
        self.assertGreater(float(_footprint_flux(glow, faint.x, faint.y, 20.0).sum()), 0.0)
        bright_ratio = _footprint_flux(glow, bright.x, bright.y, 20.0)
        bright_ratio /= max(float(bright_ratio.sum()), 1e-9)
        source_ratio = _footprint_flux(self.stars, bright.x, bright.y, bright.footprint_radius_px)
        source_ratio /= max(float(source_ratio.sum()), 1e-9)
        np.testing.assert_allclose(bright_ratio, source_ratio, atol=2e-3, rtol=0.0)

        top_only = _render_glow(self.stars, self.mask, catalog, cutoff=None, glow_star_count=1, radius_px=10.0)
        self.assertIsNotNone(top_only)
        self.assertGreater(float(_footprint_flux(top_only, bright.x, bright.y, 20.0).sum()), 0.0)
        self.assertEqual(float(_footprint_flux(top_only, faint.x, faint.y, 20.0).sum()), 0.0)
        empty = _render_glow(self.stars, self.mask, catalog, cutoff=None, glow_star_count=0, radius_px=10.0)
        self.assertTrue(np.array_equal(empty, np.zeros_like(empty)))

    def test_glow_is_single_pass_linear_and_sky_masked_once(self):
        catalog = _catalog(self, self.stars, self.source, self.mask, None)
        combined = _render_glow(self.stars, self.mask, catalog, cutoff=None, glow_star_count=100, radius_px=12.0)
        self.assertIsNotNone(combined)
        isolated_sum = np.zeros_like(combined)
        for candidate in catalog.analysis.candidates:
            isolated = np.zeros_like(self.stars)
            _add_gaussian(
                isolated,
                candidate.x,
                candidate.y,
                2.5,
                1.4,
                0.2,
                [0.55, 0.40, 0.30] if candidate.x < 64 else [0.10, 0.10, 0.10],
            )
            isolated_source = np.clip(isolated + 0.1, 0.0, 1.0)
            isolated_catalog = _catalog(self, isolated, isolated_source, self.mask, None)
            glow = _render_glow(isolated, self.mask, isolated_catalog, cutoff=None, glow_star_count=100, radius_px=12.0)
            self.assertIsNotNone(glow)
            isolated_sum += glow
        np.testing.assert_allclose(combined, isolated_sum, atol=1e-4, rtol=0.0)

        zero_mask = _mask(*self.shape[:2])
        zero_mask[:, :64] = 0.0
        masked = _render_glow(self.stars, zero_mask, catalog, cutoff=None, glow_star_count=100, radius_px=10.0)
        self.assertIsNotNone(masked)
        self.assertTrue(np.array_equal(masked[:, :64], np.zeros_like(masked[:, :64])))

    def test_glow_uses_full_kernel_at_frame_edge_not_patch_renormalization(self):
        centered = np.zeros(self.shape, np.float32)
        edge = np.zeros(self.shape, np.float32)
        _add_gaussian(centered, 64, 64, 1.6, 1.0, 0.2, [0.5, 0.5, 0.5])
        _add_gaussian(edge, 12, 64, 1.6, 1.0, 0.2, [0.5, 0.5, 0.5])
        center_source = np.clip(centered + 0.1, 0.0, 1.0)
        edge_source = np.clip(edge + 0.1, 0.0, 1.0)
        center_catalog = _catalog(self, centered, center_source, self.mask, None)
        edge_catalog = _catalog(self, edge, edge_source, self.mask, None)
        center_glow = _render_glow(
            centered, self.mask, center_catalog, cutoff=None, glow_star_count=100, radius_px=60.0
        )
        edge_glow = _render_glow(edge, self.mask, edge_catalog, cutoff=None, glow_star_count=100, radius_px=60.0)
        self.assertIsNotNone(center_glow)
        self.assertIsNotNone(edge_glow)
        center_added = float(center_glow.sum())
        edge_added = float(edge_glow.sum())
        self.assertGreater(center_added, 0.0)
        self.assertLess(edge_added, center_added)
        self.assertLessEqual(edge_added, center_added * 1.000001)

    def test_glow_pyramid_matches_direct_blur_within_tolerance(self):
        yy, xx = np.mgrid[0:256, 0:256]
        seed = np.zeros((256, 256, 3), np.float32)
        for channel, amplitude in enumerate((0.5, 0.35, 0.2)):
            seed[..., channel] = amplitude * np.exp(-((yy - 128.0) ** 2 + (xx - 130.0) ** 2) / (2.0 * 3.0**2)).astype(
                np.float32
            )
        self.assertGreaterEqual(GLOW_PYRAMID_RADIUS_PX, 64.0)
        with patch("startrails.lib.finish.star_effects.GLOW_PYRAMID_RADIUS_PX", 1e9):
            direct = _blur_glow_seed(seed, 100.0)
        pyramid = _blur_glow_seed(seed, 100.0)
        direct_flux = direct.sum(axis=(0, 1), dtype=np.float64)
        pyramid_flux = pyramid.sum(axis=(0, 1), dtype=np.float64)
        np.testing.assert_allclose(pyramid_flux, direct_flux, rtol=0.01, atol=1e-6)
        direct_total = float(direct_flux.sum())
        pyramid_total = float(pyramid_flux.sum())
        direct_y = float((direct.sum(axis=2).astype(np.float64) * yy).sum() / direct_total)
        direct_x = float((direct.sum(axis=2).astype(np.float64) * xx).sum() / direct_total)
        pyramid_y = float((pyramid.sum(axis=2).astype(np.float64) * yy).sum() / pyramid_total)
        pyramid_x = float((pyramid.sum(axis=2).astype(np.float64) * xx).sum() / pyramid_total)
        self.assertLessEqual(float(np.hypot(pyramid_y - direct_y, pyramid_x - direct_x)), 0.5)

    def test_glow_disabled_composition_is_identity(self):
        catalog = _catalog(self, self.stars, self.source, self.mask, None)
        settings = _settings(star_glow_enabled=False, star_glow_amount=100.0)
        result = compose_star_layer(
            self.stars,
            catalog,
            None,
            None,
            settings,
            inclusion_mask=_inclusion(catalog, None),
        )
        self.assertTrue(np.array_equal(result, self.stars))
        self.assertTrue(np.array_equal(result, np.clip(self.stars, 0.0, 1.0)))


if __name__ == "__main__":
    unittest.main()
