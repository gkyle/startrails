"""Focused contracts for the Step 10B ranked star catalog and included mask."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from startrails.lib.finish import star_catalog as star_catalog_module
from startrails.lib.finish.star_analysis import STAR_ANALYSIS_VERSION, analyze_stars
from startrails.lib.finish.star_catalog import (
    STAR_CATALOG_VERSION,
    build_catalog,
    extend_catalog,
    included_mask,
    load_catalog,
    save_catalog,
)
from startrails.lib.finish.star_effects import build_round_delta, render_glow


def _add_gaussian(image, x, y, a, b, amplitude, theta=0.3):
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


def _scene(shape=(96, 96)):
    stars = np.zeros((*shape, 3), np.float32)
    source = np.zeros_like(stars)
    for x, y, a, b, amplitude in (
        (20, 20, 2.5, 1.5, 0.35),
        (60, 25, 2.0, 2.0, 0.25),
        (30, 65, 3.0, 1.2, 0.50),
        (75, 70, 1.8, 1.8, 0.18),
        (45, 45, 2.2, 1.4, 0.30),
    ):
        _add_gaussian(stars, x, y, a, b, [amplitude] * 3)
        _add_gaussian(source, x, y, a, b, [amplitude + 0.1] * 3)
    np.clip(source, 0.0, 1.0, out=source)
    return stars, source, np.ones(shape, np.float32)


def _component_pixel(catalog, rank):
    component = catalog.component_ids[rank]
    return tuple(int(value) for value in np.argwhere(catalog.labels == component)[0])


class TestRankedStarCatalog(unittest.TestCase):
    def test_all_catalog_reproduces_analyze_stars_in_rank_order(self):
        stars, source, mask = _scene()
        analysis = analyze_stars(stars, source, mask)
        catalog = build_catalog(stars, source, mask, cutoff=None)

        self.assertIsNotNone(analysis)
        self.assertIsNotNone(catalog)
        self.assertEqual(len(catalog.analysis.candidates), len(analysis.candidates))
        by_position = {(round(c.x, 9), round(c.y, 9)): c for c in analysis.candidates}
        for candidate in catalog.analysis.candidates:
            expected = by_position[(round(candidate.x, 9), round(candidate.y, 9))]
            self.assertEqual(candidate, expected)
        self.assertTrue(np.all(catalog.measured))
        self.assertEqual(catalog.included_count(None), len(catalog.analysis.candidates))
        scores = catalog.scores
        self.assertTrue(np.all(scores[:-1] >= scores[1:]))

        expected_mask = np.ones(stars.shape[:2], np.float32)
        np.testing.assert_array_equal(included_mask(catalog, cutoff=None), expected_mask)
        np.testing.assert_array_equal(
            included_mask(catalog, cutoff=len(catalog.analysis.candidates) + 10), expected_mask
        )

    def test_build_is_deterministic(self):
        stars, source, mask = _scene()
        first = build_catalog(stars, source, mask, cutoff=None)
        second = build_catalog(stars, source, mask, cutoff=None)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.analysis.candidates, second.analysis.candidates)
        np.testing.assert_array_equal(first.scores, second.scores)

    def test_partial_cutoff_keeps_cheap_excluded_candidates_and_owns_mask(self):
        stars, source, mask = _scene()
        catalog = build_catalog(stars, source, mask, cutoff=2)
        self.assertIsNotNone(catalog)
        total = len(catalog.analysis.candidates)
        self.assertGreater(total, 2)
        self.assertEqual(catalog.measured.tolist(), [True, True] + [False] * (total - 2))
        self.assertEqual(catalog.included_count(2), 2)
        self.assertEqual(catalog.cutoff_score(2), float(catalog.scores[1]))
        self.assertEqual(catalog.cutoff_score(0), 0.0)

        for rank in range(2, total):
            candidate = catalog.analysis.candidates[rank]
            self.assertFalse(candidate.is_valid)
            self.assertEqual(candidate.skip_reason, "excluded")
            self.assertGreater(candidate.footprint_radius_px, 0.0)
            self.assertGreater(candidate.core_radius_px, 0.0)

        included_mask_result = included_mask(catalog, cutoff=2)
        self.assertEqual(included_mask_result.dtype, np.float32)
        self.assertEqual(included_mask_result.shape, stars.shape[:2])
        for rank in range(2):
            pixel = _component_pixel(catalog, rank)
            self.assertGreater(included_mask_result[pixel], 0.5)
        for rank in range(2, total):
            pixel = _component_pixel(catalog, rank)
            self.assertEqual(float(included_mask_result[pixel]), 0.0)

        included_stars = stars * included_mask_result[..., None]
        for rank in range(2, total):
            pixel = _component_pixel(catalog, rank)
            self.assertTrue(np.all(included_stars[pixel] == 0.0))
        np.testing.assert_array_equal(included_mask(catalog, cutoff=0), np.zeros(stars.shape[:2], np.float32))
        np.testing.assert_array_equal(included_mask(catalog, cutoff=None), np.ones(stars.shape[:2], np.float32))

        for invalid in (-1, 1.5, True):
            with self.subTest(cutoff=invalid):
                with self.assertRaises(ValueError):
                    included_mask(catalog, cutoff=invalid)

    def test_last_included_ranks_fade_to_zero_at_the_cutoff(self):
        stars = np.zeros((128, 128, 3), np.float32)
        source = np.zeros_like(stars)
        for row, y in enumerate(range(15, 115, 22)):
            for column, x in enumerate(range(15, 115, 22)):
                amplitude = 0.12 + 0.01 * (row * 5 + column)
                _add_gaussian(stars, x, y, 1.8, 1.8, [amplitude] * 3, theta=0.0)
                _add_gaussian(source, x, y, 1.8, 1.8, [amplitude + 0.1] * 3, theta=0.0)
        catalog = build_catalog(stars, source, np.ones((128, 128), np.float32), cutoff=None)
        self.assertIsNotNone(catalog)
        total = len(catalog.analysis.candidates)
        self.assertGreaterEqual(total, 10)

        # Use a partial cutoff (one below All) so the fade applies.
        included_count = total - 1
        faded = included_mask(catalog, cutoff=included_count)
        first_pixel = _component_pixel(catalog, 0)
        last_pixel = _component_pixel(catalog, included_count - 1)
        self.assertGreater(faded[first_pixel], 0.5)
        self.assertEqual(float(faded[last_pixel]), 0.0)

    def test_extend_measures_only_new_ranks_and_matches_all(self):
        stars, source, mask = _scene()
        partial = build_catalog(stars, source, mask, cutoff=1)
        complete = build_catalog(stars, source, mask, cutoff=None)
        self.assertIsNotNone(partial)
        self.assertIsNotNone(complete)
        total = len(complete.analysis.candidates)

        with patch(
            "startrails.lib.finish.star_catalog._build_candidate",
            wraps=star_catalog_module._build_candidate,
        ) as measured:
            extended = extend_catalog(partial, stars, source, mask, cutoff=None)

        self.assertIsNotNone(extended)
        self.assertEqual(measured.call_count, total - 1)
        self.assertEqual(extended.analysis.candidates, complete.analysis.candidates)
        self.assertTrue(np.all(extended.measured))
        self.assertEqual(int(np.count_nonzero(partial.measured)), 1)
        self.assertEqual(partial.analysis.candidates[0], complete.analysis.candidates[0])

        with self.assertRaises(ValueError):
            extend_catalog(partial, np.zeros_like(stars), source, mask, cutoff=None)

    def test_cutoff_view_is_history_independent(self):
        stars, source, mask = _scene()
        fresh = build_catalog(stars, source, mask, cutoff=2)
        partial = build_catalog(stars, source, mask, cutoff=2)
        self.assertIsNotNone(fresh)
        self.assertIsNotNone(partial)
        all_measured = extend_catalog(partial, stars, source, mask, cutoff=None)
        self.assertIsNotNone(all_measured)

        # Full measurements are retained for persistence, but lowering the
        # cutoff must not let those replace the cheap excluded shadows.
        self.assertNotEqual(
            all_measured.analysis.candidates[2].core_radius_px,
            all_measured.cheap_candidates[2].core_radius_px,
        )
        view = all_measured.analysis_for_cutoff(2)
        self.assertEqual(view.candidates, fresh.analysis.candidates)
        np.testing.assert_array_equal(
            included_mask(all_measured, cutoff=2),
            included_mask(fresh, cutoff=2),
        )
        self.assertIs(all_measured.analysis_for_cutoff(None), all_measured.analysis)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.npz"
            save_catalog(path, all_measured, identity="history-catalog")
            loaded = load_catalog(path, identity="history-catalog")
            self.assertEqual(loaded.cheap_candidates, all_measured.cheap_candidates)
            self.assertEqual(loaded.analysis_for_cutoff(2).candidates, fresh.analysis.candidates)
            np.testing.assert_array_equal(
                included_mask(loaded, cutoff=2),
                included_mask(fresh, cutoff=2),
            )
            deltas, halos = [], []
            for catalog in (fresh, all_measured, loaded):
                kwargs = {"cutoff": 2, "inclusion_mask": included_mask(catalog, cutoff=2)}
                deltas.append(build_round_delta(stars, mask, catalog, **kwargs))
                halos.append(render_glow(stars, mask, catalog, **kwargs, glow_star_count=2, radius_px=15.0))
            for delta, halo in zip(deltas[1:], halos[1:]):
                np.testing.assert_array_equal(delta.decision, deltas[0].decision)
                np.testing.assert_array_equal(delta.values, deltas[0].values)
                np.testing.assert_array_equal(halo, halos[0])

    def test_save_load_roundtrip_validation_and_reopen_extension(self):
        stars, source, mask = _scene()
        catalog = build_catalog(stars, source, mask, cutoff=2)
        self.assertIsNotNone(catalog)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.npz"
            save_catalog(path, catalog, identity="separation-source-sky-v2")
            loaded = load_catalog(path, identity="separation-source-sky-v2")

            self.assertEqual(loaded.analysis.candidates, catalog.analysis.candidates)
            self.assertEqual(loaded.cheap_candidates, catalog.cheap_candidates)
            np.testing.assert_array_equal(loaded.measured, catalog.measured)
            np.testing.assert_array_equal(loaded.scores, catalog.scores)
            np.testing.assert_array_equal(loaded.labels, catalog.labels)
            np.testing.assert_array_equal(included_mask(loaded, cutoff=2), included_mask(catalog, cutoff=2))
            self.assertFalse(loaded.measured.flags.writeable)
            self.assertFalse(loaded.labels.flags.writeable)

            with np.load(path, allow_pickle=False) as archive:
                self.assertEqual(int(archive["star_catalog_version"]), STAR_CATALOG_VERSION)
                self.assertEqual(int(archive["star_analysis_version"]), STAR_ANALYSIS_VERSION)
                persisted = set(archive.files)
            self.assertIn("cheap_y", persisted)
            self.assertFalse({"detail", "stars", "source"}.intersection(persisted))

            with self.assertRaises(ValueError):
                load_catalog(path, identity="different-identity")

            complete = build_catalog(stars, source, mask, cutoff=None)
            with patch(
                "startrails.lib.finish.star_catalog.cv2.connectedComponentsWithStats",
                side_effect=AssertionError("reopen must not rerun connected components"),
            ):
                extended = extend_catalog(loaded, stars, source, mask, cutoff=None)
            self.assertIsNotNone(extended)
            self.assertEqual(extended.analysis.candidates, complete.analysis.candidates)

            with np.load(path, allow_pickle=False) as archive:
                base = {name: archive[name].copy() for name in archive.files}

            bad_prefix = np.asarray(base["measured"], dtype=bool).copy()
            bad_prefix[0] = False
            bad_prefix[-1] = True
            bad_score = np.asarray(base["scores"], dtype=np.float64).copy()
            bad_score[0] = -1.0
            bad_radius = np.asarray(base["candidate_core_radius_px"], dtype=np.float64).copy()
            bad_radius[0] = -1.0
            bad_centroid = np.asarray(base["candidate_y"], dtype=np.float64).copy()
            bad_centroid[0] = stars.shape[0] + 1.0
            bad_ellipticity = np.asarray(base["candidate_ellipticity"], dtype=np.float64).copy()
            bad_ellipticity[0] = 1.5
            unmeasured_valid = np.asarray(base["candidate_is_valid"], dtype=bool).copy()
            unmeasured_valid[-1] = True
            malformed = (
                ("schema-version", {"star_catalog_version": np.asarray(STAR_CATALOG_VERSION + 1, np.int64)}),
                ("analysis-version", {"star_analysis_version": np.asarray(STAR_ANALYSIS_VERSION + 1, np.int64)}),
                ("prefix", {"measured": bad_prefix}),
                ("float-labels", {"labels": np.asarray(base["labels"], dtype=np.float64)}),
                ("nan-bool", {"measured": np.full(base["measured"].shape, np.nan, np.float64)}),
                ("nonfinite-score", {"scores": np.asarray(base["scores"], dtype=np.float64) * np.nan}),
                ("negative-score", {"scores": bad_score}),
                ("negative-radius", {"candidate_core_radius_px": bad_radius}),
                ("centroid", {"candidate_y": bad_centroid}),
                ("ellipticity", {"candidate_ellipticity": bad_ellipticity}),
                ("unmeasured-valid", {"candidate_is_valid": unmeasured_valid}),
            )
            for name, updates in malformed:
                with self.subTest(malformed=name):
                    variant = dict(base)
                    variant.update(updates)
                    variant_path = Path(directory) / f"bad-{name}.npz"
                    with open(variant_path, "wb") as handle:
                        np.savez_compressed(handle, **variant)
                    with self.assertRaises(ValueError):
                        load_catalog(variant_path, identity="separation-source-sky-v2")

            corrupt = Path(directory) / "corrupt.npz"
            corrupt.write_bytes(b"not an npz archive")
            with self.assertRaises(ValueError):
                load_catalog(corrupt, identity="separation-source-sky-v2")

    def test_interrupt_returns_none(self):
        stars, source, mask = _scene()
        self.assertIsNone(build_catalog(stars, source, mask, cutoff=None, should_interrupt=lambda: True))


if __name__ == "__main__":
    unittest.main()
