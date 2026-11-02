"""Workflow and project integration tests for Step 10B ranked star layers.

The numerical catalog and effect implementations are exercised with small
synthetic layers. Expensive boundaries are patched only to prove incremental
reuse, never to replace the behavior under test.
"""

from __future__ import annotations

from concurrent.futures import CancelledError
from dataclasses import replace
from pathlib import Path
import json
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from support import QtTestCase

from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.finish.defaults import (
    BLEND_ADD,
    BLEND_SCREEN,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_FINISHED_STARS,
    ROLE_ROUND_DELTA,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    ROLE_STAR_CATALOG,
    FINISH_DEFAULTS,
    FinishSettings,
)
from startrails.lib.finish.star_analysis import STAR_ANALYSIS_VERSION
from startrails.lib.finish.star_catalog import STAR_CATALOG_VERSION, load_catalog
from startrails.lib.finish.star_effects import STAR_EFFECT_VERSION, load_round_delta
from startrails.lib.finish.starless_filters import STARLESS_FILTER_VERSION
from startrails.lib.image_io import imread, imwrite
from startrails.lib.project_finish import FinishProject
from startrails.workflow.finish import FinishWorkflow
import startrails.workflow.finish as workflow_module


def gaussian_stars(shape: tuple[int, int] = (64, 64)) -> np.ndarray:
    """Three deterministic, separated star blobs on a zero star layer."""
    height, width = shape
    yy, xx = np.mgrid[0:height, 0:width]
    stars = np.zeros((height, width, 3), dtype=np.float32)
    for cy, cx, sigma, amplitude, color in (
        (16.0, 16.0, 2.0, 0.85, (1.0, 0.8, 0.6)),
        (32.0, 33.0, 2.2, 0.70, (0.7, 0.9, 1.0)),
        (48.0, 22.0, 1.8, 0.55, (0.9, 0.9, 0.9)),
    ):
        blob = amplitude * np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2) / (2.0 * sigma**2)))
        for channel, weight in enumerate(color):
            stars[..., channel] += (blob * weight).astype(np.float32)
    return np.clip(stars, 0.0, 1.0).astype(np.float32)


class TestFinishStars(QtTestCase):
    shape = (64, 64, 3)

    def write_image(self, path: Path, value: float | np.ndarray) -> Path:
        pixels = np.full(self.shape, value, np.float32) if np.isscalar(value) else np.asarray(value, np.float32)
        path.parent.mkdir(parents=True, exist_ok=True)
        imwrite(path, pixels, bit_depth=16)
        return path

    def prepare_separated_project(
        self,
        name: str,
        *,
        source: np.ndarray | None = None,
        starless: np.ndarray | None = None,
        stars: np.ndarray | None = None,
        mask: np.ndarray | None = None,
        settings: FinishSettings | None = None,
    ) -> FinishProject:
        """Publish a current separation and canonical mask without model work."""
        source_pixels = np.full(self.shape, 0.5, np.float32) if source is None else source
        starless_pixels = np.full(self.shape, 0.4, np.float32) if starless is None else starless
        stars_pixels = np.full(self.shape, 0.1, np.float32) if stars is None else stars
        mask_pixels = np.ones(self.shape[:2], np.float32) if mask is None else mask

        project = FinishProject(project_file=str(self.root / f"{name}.proj_finish"))
        source_path = self.write_image(self.root / f"{name}_source.tif", source_pixels)
        project.set_source_image(source_path)

        starless_path = self.write_image(
            project.artifact_path(ROLE_SEPARATED_STARLESS, for_write=True), starless_pixels
        )
        stars_path = self.write_image(project.artifact_path(ROLE_SEPARATED_STARS, for_write=True), stars_pixels)
        self.assertTrue(
            project.publish_separation(
                starless_path,
                stars_path,
                signature=f"{name}-separation",
                model_identity="starnet-model",
                expected_revision=project.processing_revision,
            )
        )
        mask_path = project.artifact_path(ROLE_SKY_MASK, for_write=True)
        MaskHandler.save_mask(mask_pixels, mask_path)
        project.record_artifact(ROLE_SKY_MASK, mask_path)
        if settings is not None:
            project.update_settings(settings)
        return project

    def make_workflow(self, project: FinishProject) -> FinishWorkflow:
        app = self.make_app(project)
        workflow = FinishWorkflow(app)
        app.workflow = workflow
        return workflow

    def write_finished_starless(self, project: FinishProject, value: float = 0.3) -> Path:
        path = self.write_image(project.artifact_path(ROLE_FINISHED_STARLESS, for_write=True), value)
        project.record_artifact(
            ROLE_FINISHED_STARLESS,
            path,
            options={
                "separation_signature": project.separation_signature,
                "starless_filter_version": STARLESS_FILTER_VERSION,
            },
        )
        return path

    def test_publishes_catalog_round_delta_and_derived_finished_tiff(self):
        project = self.prepare_separated_project("publish", stars=gaussian_stars())
        workflow = self.make_workflow(project)
        observed = []

        def observe(total, increment, count, done, data):
            observed.append((total, increment, count, done, data))

        result = workflow.do_finish_stars(progress_bar=observe)

        self.assertIsNotNone(result)
        self.assertEqual(result.operation, "Finished Stars")
        catalog_path = project.current_artifact_path(ROLE_STAR_CATALOG)
        round_path = project.current_artifact_path(ROLE_ROUND_DELTA)
        finished_path = project.current_artifact_path(ROLE_FINISHED_STARS)
        self.assertIsNotNone(catalog_path)
        self.assertIsNotNone(round_path)
        self.assertIsNotNone(finished_path)
        self.assertEqual(catalog_path.suffix, ".npz")
        self.assertEqual(round_path.suffix, ".npz")

        catalog_options = project.artifact_manifest[ROLE_STAR_CATALOG]["options"]
        self.assertEqual(catalog_options["analysis_version"], STAR_ANALYSIS_VERSION)
        self.assertEqual(catalog_options["catalog_version"], STAR_CATALOG_VERSION)
        round_options = project.artifact_manifest[ROLE_ROUND_DELTA]["options"]
        self.assertEqual(round_options["star_effect_version"], STAR_EFFECT_VERSION)

        # The project state stores only paths/stamps/signatures, never arrays.
        encoded = json.dumps(project.__getstate__(), default=str)
        self.assertNotIn("labels", encoded)
        self.assertNotIn("patches", encoded)

        state = workflow.get_star_finish_state()
        self.assertIsNotNone(state)
        self.assertIsNotNone(state.round_delta)
        self.assertIsNotNone(state.glow)
        # Default cutoff (10,000) includes this small catalog in full, and the
        # stored decision vector is aligned with every catalog rank.
        self.assertEqual(len(state.round_delta.decision), len(state.catalog.analysis.candidates))
        self.assertNotIn("excluded", state.round_delta.decision.tolist())

        self.assertEqual(observed[-1][0], 100)
        self.assertEqual(observed[-1][2], 100)
        self.assertTrue(observed[-1][3])
        self.assertTrue(all(not entry[3] for entry in observed[:-1]))
        self.assertLessEqual(max(entry[2] for entry in observed[:-1]), 99)

    def test_reopen_loads_catalog_and_round_delta_without_reanalysis(self):
        project = self.prepare_separated_project(
            "reopen",
            stars=gaussian_stars(),
            settings=replace(FINISH_DEFAULTS, star_count_cutoff=2),
        )
        self.assertIsNotNone(self.make_workflow(project).do_finish_stars())

        reopened = self.make_workflow(project)
        with (
            patch.object(workflow_module, "build_catalog", side_effect=AssertionError("reanalysis")),
            patch.object(workflow_module, "extend_catalog", side_effect=AssertionError("remeasurement")),
        ):
            state = reopened.prepare_star_endpoints()

        self.assertIsNotNone(state)
        self.assertEqual(state.cutoff, 2)
        self.assertEqual(state.catalog.included_count(2), 2)
        self.assertIsNotNone(state.round_delta)
        self.assertEqual(reopened.get_star_preview_status(), "ready")
        summary = reopened.get_star_catalog_summary()
        self.assertEqual(summary["included_count"], 2)

    def test_raising_cutoff_extends_only_new_measurements(self):
        project = self.prepare_separated_project("extend", stars=gaussian_stars())
        project.update_settings(replace(project.get_settings(), star_count_cutoff=1))
        self.assertIsNotNone(self.make_workflow(project).do_finish_stars())

        workflow = self.make_workflow(project)
        project.update_settings(replace(project.get_settings(), star_count_cutoff=3))
        real_extend = workflow_module.extend_catalog
        calls = []

        def counting_extend(*args, **kwargs):
            catalog = real_extend(*args, **kwargs)
            calls.append(catalog)
            return catalog

        with (
            patch.object(workflow_module, "build_catalog", side_effect=AssertionError("full reanalysis")),
            patch.object(workflow_module, "extend_catalog", side_effect=counting_extend),
        ):
            result = workflow.do_finish_stars()

        self.assertIsNotNone(result)
        self.assertEqual(len(calls), 1)
        self.assertGreaterEqual(int(np.count_nonzero(calls[0].measured)), 3)
        self.assertEqual(project.artifact_manifest[ROLE_STAR_CATALOG]["options"]["cutoff"], 3)

    def test_lower_cutoff_after_all_extension_reuses_catalog_without_reanalysis(self):
        project = self.prepare_separated_project("stable_lower", stars=gaussian_stars())
        project.update_settings(replace(project.get_settings(), star_count_cutoff=3))
        self.assertIsNotNone(self.make_workflow(project).do_finish_stars())
        project.update_settings(replace(project.get_settings(), star_count_cutoff=None))
        self.assertIsNotNone(self.make_workflow(project).do_finish_stars())

        catalog_path = project.current_artifact_path(ROLE_STAR_CATALOG)
        self.assertIsNotNone(catalog_path)
        catalog_bytes = catalog_path.read_bytes()

        workflow = self.make_workflow(project)
        project.update_settings(replace(project.get_settings(), star_count_cutoff=2))
        with (
            patch.object(workflow_module, "build_catalog", side_effect=AssertionError("reanalysis")),
            patch.object(workflow_module, "extend_catalog", side_effect=AssertionError("remeasurement")),
        ):
            state = workflow.prepare_star_endpoints()
        self.assertIsNotNone(state)
        self.assertEqual(state.catalog.included_count(2), 2)
        self.assertFalse(workflow._catalog_dirty)
        self.assertFalse(workflow._round_delta_dirty)
        # Lowering the cutoff must not rewrite the measurement schema blob.
        self.assertEqual(project.current_artifact_path(ROLE_STAR_CATALOG).read_bytes(), catalog_bytes)

    def test_glow_geometry_change_rebuilds_glow_only(self):
        project = self.prepare_separated_project(
            "glow_only",
            stars=gaussian_stars(),
            settings=replace(FINISH_DEFAULTS, star_count_cutoff=3),
        )
        workflow = self.make_workflow(project)
        self.assertIsNotNone(workflow.get_star_finish_state())

        project.update_settings(replace(project.get_settings(), glow_star_count=25, star_glow_radius_px=21.0))
        real_render = workflow_module.render_glow
        calls = []

        def counting_render(*args, **kwargs):
            glow = real_render(*args, **kwargs)
            calls.append(glow)
            return glow

        with (
            patch.object(workflow_module, "build_catalog", side_effect=AssertionError("catalog rebuild")),
            patch.object(workflow_module, "build_round_delta", side_effect=AssertionError("round rebuild")),
            patch.object(workflow_module, "render_glow", side_effect=counting_render),
        ):
            state = workflow.get_star_finish_state()

        self.assertIsNotNone(state)
        self.assertEqual(len(calls), 1)
        self.assertEqual(state.glow_star_count, 25)
        self.assertEqual(state.glow_radius_px, 21.0)

    def test_toggle_and_amount_changes_are_composition_only(self):
        project = self.prepare_separated_project(
            "composition",
            stars=gaussian_stars(),
            settings=replace(
                FINISH_DEFAULTS,
                round_stars_enabled=True,
                round_stars_amount=50.0,
                star_glow_enabled=True,
                star_glow_amount=20.0,
            ),
        )
        workflow = self.make_workflow(project)
        self.assertIsNotNone(workflow.prepare_star_endpoints())
        before = workflow.render_star_preview("finished_stars")
        self.assertIsNotNone(before)

        previous = project.get_settings()
        updated = replace(
            previous,
            round_stars_amount=10.0,
            star_glow_amount=40.0,
            star_amount=65.0,
            original_stars_amount=15.0,
            original_stars_blend_mode=BLEND_SCREEN,
        )
        self.assertEqual(workflow.star_refresh_action(previous, updated), "composition")
        project.update_settings(updated)

        with (
            patch.object(workflow_module, "build_catalog", side_effect=AssertionError("analysis job")),
            patch.object(workflow_module, "build_round_delta", side_effect=AssertionError("round job")),
            patch.object(workflow_module, "render_glow", side_effect=AssertionError("glow job")),
            patch.object(workflow, "do_finish_stars", side_effect=AssertionError("effect worker job")),
            patch.object(workflow, "do_recombine", side_effect=AssertionError("recombine worker job")),
        ):
            after = workflow.render_star_preview("finished_stars")
            composite = workflow.render_star_preview("composite")

        self.assertIsNotNone(after)
        self.assertIsNotNone(composite)
        self.assertFalse(np.array_equal(before, after))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))

    def test_cancel_and_stale_revision_preserve_previous_layers(self):
        project = self.prepare_separated_project("cancel", stars=gaussian_stars())
        workflow = self.make_workflow(project)
        finished = project.artifact_path(ROLE_FINISHED_STARS, for_write=True)

        with workflow.operation_session():
            workflow.app.activeOperation.requestInterrupt()
            self.assertIsNone(workflow.do_finish_stars())
        self.assertIsNone(project.current_artifact_path(ROLE_STAR_CATALOG))
        self.assertIsNone(project.current_artifact_path(ROLE_ROUND_DELTA))
        self.assertFalse(finished.exists())
        self.assertFalse(list(project.get_output_dir().glob(".artifact-*")))

        self.assertIsNotNone(workflow.do_finish_stars())
        catalog = project.current_artifact_path(ROLE_STAR_CATALOG)
        round_delta = project.current_artifact_path(ROLE_ROUND_DELTA)
        previous = {
            "catalog": catalog.read_bytes(),
            "round": round_delta.read_bytes(),
            "finished": finished.read_bytes(),
        }

        real_ensure = workflow._ensure_round_delta

        def invalidate_while_running(*args, **kwargs):
            delta, dirty = real_ensure(*args, **kwargs)
            project.invalidate_artifact_roles(set())
            return delta, dirty

        with patch.object(workflow, "_ensure_round_delta", side_effect=invalidate_while_running):
            self.assertIsNone(workflow.do_finish_stars())

        self.assertEqual(catalog.read_bytes(), previous["catalog"])
        self.assertEqual(round_delta.read_bytes(), previous["round"])
        self.assertEqual(finished.read_bytes(), previous["finished"])
        self.assertFalse(list(project.get_output_dir().glob(".artifact-*")))

    def test_two_layer_recombination_and_zero_amounts_return_starless(self):
        project = self.prepare_separated_project(
            "recombine",
            source=np.full(self.shape, 0.5, np.float32),
            starless=np.full(self.shape, 0.4, np.float32),
            stars=np.full(self.shape, 0.1, np.float32),
        )
        workflow = self.make_workflow(project)

        # Defaults: Finished Add 100%, Original Add 0% reconstruct the source.
        self.assertIsNotNone(workflow.do_recombine())
        np.testing.assert_allclose(
            imread(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), to_rgb=True, as_float=True),
            np.full(self.shape, 0.5, np.float32),
            atol=3 / 65535,
            rtol=0,
        )

        project.update_settings(replace(project.get_settings(), star_amount=0.0, original_stars_amount=100.0))
        self.assertIsNotNone(workflow.do_recombine())
        np.testing.assert_allclose(
            imread(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), to_rgb=True, as_float=True),
            np.full(self.shape, 0.5, np.float32),
            atol=3 / 65535,
            rtol=0,
        )

        project.update_settings(replace(project.get_settings(), star_amount=0.0, original_stars_amount=0.0))
        self.assertIsNotNone(workflow.do_recombine())
        np.testing.assert_allclose(
            imread(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), to_rgb=True, as_float=True),
            np.full(self.shape, 0.4, np.float32),
            atol=1 / 65535,
            rtol=0,
        )

        project.update_settings(
            replace(
                project.get_settings(),
                star_amount=100.0,
                blend_mode=BLEND_ADD,
                original_stars_amount=100.0,
                original_stars_blend_mode=BLEND_SCREEN,
            )
        )
        self.assertIsNotNone(workflow.do_recombine())
        composite = imread(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), to_rgb=True, as_float=True)
        self.assertTrue(np.all(composite > 0.4))

    def test_recombine_does_not_read_stale_finished_stars_tiff(self):
        project = self.prepare_separated_project(
            "stale_tiff",
            source=np.full(self.shape, 0.5, np.float32),
            starless=np.full(self.shape, 0.4, np.float32),
            stars=np.full(self.shape, 0.1, np.float32),
        )
        workflow = self.make_workflow(project)
        self.assertIsNotNone(workflow.do_finish_stars())
        finished = project.current_artifact_path(ROLE_FINISHED_STARS)
        self.assertIsNotNone(finished)
        # Simulate a leftover TIFF from old settings. It must not drive composition.
        self.write_image(finished, 0.9)
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARS))

        project.update_settings(replace(project.get_settings(), star_amount=100.0))
        self.assertIsNotNone(workflow.do_recombine())
        np.testing.assert_allclose(
            imread(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), to_rgb=True, as_float=True),
            np.full(self.shape, 0.5, np.float32),
            atol=3 / 65535,
            rtol=0,
        )

    def test_recombine_refreshes_reduced_preview_after_starless_change(self):
        project = self.prepare_separated_project(
            "recombine_preview_refresh",
            source=np.full(self.shape, 0.5, np.float32),
            starless=np.full(self.shape, 0.4, np.float32),
            stars=np.full(self.shape, 0.1, np.float32),
            settings=replace(
                FINISH_DEFAULTS,
                round_stars_enabled=True,
                round_stars_amount=40.0,
                star_glow_enabled=True,
                star_glow_amount=20.0,
            ),
        )
        workflow = self.make_workflow(project)
        self.assertIsNotNone(workflow.prepare_star_endpoints())
        self.assertEqual(workflow.get_star_preview_status(), "ready")
        self.write_finished_starless(project, value=0.25)
        self.assertNotEqual(workflow.get_star_preview_status(), "ready")

        with (
            patch.object(workflow_module, "build_catalog", side_effect=AssertionError("analysis")),
            patch.object(workflow_module, "build_round_delta", side_effect=AssertionError("round rebuild")),
            patch.object(workflow_module, "render_glow", side_effect=AssertionError("glow rebuild")),
        ):
            self.assertIsNotNone(workflow.do_recombine())
            self.assertEqual(workflow.get_star_preview_status(), "ready")
            preview = workflow.render_star_preview("composite")
        self.assertIsNotNone(preview)
        # Default composite settings use the newly cached finished-starless base.
        np.testing.assert_allclose(preview[..., 0], 0.35, atol=0.02, rtol=0)

    def test_effect_and_analysis_versions_invalidate_different_layers(self):
        project = self.prepare_separated_project("versions", stars=gaussian_stars())
        workflow = self.make_workflow(project)
        self.assertIsNotNone(workflow.do_finish_stars())
        self.assertIsNotNone(project.current_artifact_path(ROLE_STAR_CATALOG))

        project.artifact_manifest[ROLE_ROUND_DELTA]["options"]["star_effect_version"] = STAR_EFFECT_VERSION + 1
        self.assertTrue(workflow.invalidate_if_star_effects_changed())
        self.assertIsNotNone(project.current_artifact_path(ROLE_STAR_CATALOG))
        self.assertIsNone(project.current_artifact_path(ROLE_ROUND_DELTA))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARS))

        project.artifact_manifest[ROLE_STAR_CATALOG]["options"]["analysis_version"] = STAR_ANALYSIS_VERSION + 1
        self.assertTrue(workflow.invalidate_if_star_effects_changed())
        self.assertIsNone(project.current_artifact_path(ROLE_STAR_CATALOG))

    def test_failed_publication_keeps_extended_measurements_dirty_until_retry(self):
        project = self.prepare_separated_project("dirty_retry", stars=gaussian_stars())
        project.update_settings(replace(project.get_settings(), star_count_cutoff=1))
        self.assertIsNotNone(self.make_workflow(project).do_finish_stars())

        workflow = self.make_workflow(project)
        project.update_settings(replace(project.get_settings(), star_count_cutoff=3))
        with patch.object(workflow_module, "save_catalog", side_effect=CancelledError()):
            self.assertIsNone(workflow.do_finish_stars())
        self.assertTrue(workflow._catalog_dirty)
        self.assertTrue(workflow._round_delta_dirty)

        with patch.object(project, "publish_star_effects", return_value=False):
            self.assertIsNone(workflow.do_finish_stars())
        self.assertTrue(workflow._catalog_dirty)
        self.assertTrue(workflow._round_delta_dirty)
        self.assertEqual(project.artifact_manifest[ROLE_STAR_CATALOG]["options"]["cutoff"], 1)

        with (
            patch.object(workflow_module, "build_catalog", side_effect=AssertionError("full reanalysis")),
            patch.object(workflow_module, "extend_catalog", side_effect=AssertionError("remeasurement")),
        ):
            state = workflow.prepare_star_endpoints()
        self.assertIsNotNone(state)
        self.assertFalse(workflow._catalog_dirty)
        self.assertFalse(workflow._round_delta_dirty)
        self.assertEqual(project.artifact_manifest[ROLE_STAR_CATALOG]["options"]["cutoff"], 3)
        self.assertEqual(state.catalog.included_count(3), 3)

        reopened = self.make_workflow(project)
        with (
            patch.object(workflow_module, "build_catalog", side_effect=AssertionError("reopen analysis")),
            patch.object(workflow_module, "extend_catalog", side_effect=AssertionError("reopen remeasurement")),
        ):
            reopened_state = reopened.prepare_star_endpoints()
        self.assertIsNotNone(reopened_state)
        self.assertEqual(reopened_state.catalog.included_count(3), 3)

    def assert_star_blobs_load(self, project: FinishProject) -> None:
        catalog_path = project.current_artifact_path(ROLE_STAR_CATALOG)
        round_path = project.current_artifact_path(ROLE_ROUND_DELTA)
        self.assertIsNotNone(catalog_path)
        self.assertIsNotNone(round_path)
        catalog_options = project.artifact_manifest[ROLE_STAR_CATALOG]["options"]
        round_options = project.artifact_manifest[ROLE_ROUND_DELTA]["options"]
        catalog = load_catalog(catalog_path, identity=catalog_options["catalog_identity"])
        delta = load_round_delta(round_path, identity=round_options["round_identity"])
        self.assertIsNotNone(catalog)
        self.assertIsNotNone(delta)

    def test_corrupt_catalog_and_round_blobs_rebuild_through_prepare_and_recombine(self):
        project = self.prepare_separated_project("corrupt", stars=gaussian_stars())
        workflow = self.make_workflow(project)
        self.assertIsNotNone(workflow.do_finish_stars())
        catalog = project.current_artifact_path(ROLE_STAR_CATALOG)
        round_delta = project.current_artifact_path(ROLE_ROUND_DELTA)
        self.assertIsNotNone(catalog)
        self.assertIsNotNone(round_delta)
        catalog.write_bytes(b"not an npz")
        round_delta.write_bytes(b"not an npz")

        prepared = self.make_workflow(project).prepare_star_endpoints()
        self.assertIsNotNone(prepared)
        self.assert_star_blobs_load(project)

        # A later corruption is repaired by an explicit recombine as well.
        project.current_artifact_path(ROLE_STAR_CATALOG).write_bytes(b"corrupt again")
        project.current_artifact_path(ROLE_ROUND_DELTA).write_bytes(b"corrupt again")
        self.assertIsNotNone(self.make_workflow(project).do_recombine())
        self.assert_star_blobs_load(project)

    def test_reduced_endpoint_reduces_included_product_not_mask_and_stars_separately(self):
        height, width = 64, 64
        yy, xx = np.mgrid[0:height, 0:width]
        stars = np.zeros((height, width, 3), np.float32)
        for cy in (12.0, 26.0, 40.0, 54.0):
            for cx in (10.0, 24.0, 38.0, 52.0):
                blob = 0.28 * np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2) / (2.0 * 1.1**2)))
                stars += blob[..., None].astype(np.float32)
        stars = np.clip(stars, 0.0, 1.0)
        mask = (((yy // 2) + (xx // 2)) % 2).astype(np.float32)
        mask[4:60, 4:60] = 1.0
        project = self.prepare_separated_project("reduced_product", stars=stars, mask=mask)

        with patch.object(workflow_module, "STAR_PREVIEW_MAX_DIMENSION", 9):
            workflow = self.make_workflow(project)
            state = workflow.prepare_star_endpoints()
            self.assertIsNotNone(state)
            self.assertIsNotNone(workflow._reduced_preview)
            small_h, small_w = workflow._reduced_preview.stars.shape[:2]
            self.assertLessEqual(max(small_h, small_w), 9)

            full_stars = imread(
                project.current_artifact_path(ROLE_SEPARATED_STARS),
                to_rgb=True,
                as_float=True,
            )
            full_included = state.inclusion_mask[..., None] * full_stars
            expected_included = cv2.resize(full_included, (small_w, small_h), interpolation=cv2.INTER_AREA)
            expected_excluded = cv2.resize(full_stars - full_included, (small_w, small_h), interpolation=cv2.INTER_AREA)

            compare = workflow.render_star_preview("finished_stars", compare=True)
            excluded = workflow.render_star_preview("excluded_stars")
            np.testing.assert_allclose(compare, expected_included, atol=1e-6, rtol=0)
            np.testing.assert_allclose(excluded, expected_excluded, atol=1e-6, rtol=0)

            for amount in (0.0, 25.0, 50.0, 100.0):
                project.update_settings(
                    replace(
                        project.get_settings(),
                        round_stars_enabled=True,
                        round_stars_amount=amount,
                        star_glow_enabled=False,
                        star_glow_amount=0.0,
                    )
                )
                settings = project.get_settings()
                full_finished = workflow_module.compose_star_layer(
                    full_stars,
                    state.catalog,
                    state.round_delta,
                    None,
                    settings,
                    inclusion_mask=state.inclusion_mask,
                )
                expected = cv2.resize(full_finished, (small_w, small_h), interpolation=cv2.INTER_AREA)
                rendered = workflow.render_star_preview("finished_stars")
                np.testing.assert_allclose(rendered, expected, atol=1e-6, rtol=0)

    def test_prepare_rejects_settings_change_after_state_snapshot(self):
        project = self.prepare_separated_project("prepare_race", stars=gaussian_stars())
        self.assertIsNotNone(self.make_workflow(project).do_finish_stars())
        workflow = self.make_workflow(project)
        real_get_state = workflow.get_star_finish_state

        def mutate_after_state(**kwargs):
            state = real_get_state(**kwargs)
            project.update_settings(replace(project.get_settings(), star_glow_radius_px=31.0))
            return state

        with patch.object(workflow, "get_star_finish_state", side_effect=mutate_after_state):
            self.assertIsNone(workflow.prepare_star_endpoints())
        self.assertIsNone(workflow._reduced_preview)
        self.assertNotEqual(workflow.get_star_preview_status(), "ready")

    def test_cold_preview_returns_none_without_disk_or_analysis(self):
        project = self.prepare_separated_project("cold_preview", stars=gaussian_stars())
        workflow = self.make_workflow(project)
        self.assertEqual(workflow.get_star_preview_status(), "cold")

        with (
            patch.object(workflow_module, "imread", side_effect=AssertionError("disk image read")),
            patch.object(MaskHandler, "load_mask", side_effect=AssertionError("mask read")),
            patch.object(workflow_module, "build_catalog", side_effect=AssertionError("analysis")),
            patch.object(workflow_module, "build_round_delta", side_effect=AssertionError("round build")),
            patch.object(workflow_module, "render_glow", side_effect=AssertionError("glow render")),
        ):
            self.assertIsNone(workflow.render_star_preview("composite"))
            self.assertIsNone(workflow.render_star_preview("finished_stars"))
            self.assertIsNone(workflow.get_star_catalog_summary())

        self.assertEqual(workflow.get_star_preview_status(), "cold")

    def test_interactive_preview_reuses_cached_arrays_and_effects(self):
        project = self.prepare_separated_project(
            "preview_cache",
            stars=gaussian_stars(),
            settings=replace(
                FINISH_DEFAULTS,
                round_stars_enabled=True,
                round_stars_amount=80.0,
                star_glow_enabled=True,
                star_glow_amount=30.0,
            ),
        )
        workflow = self.make_workflow(project)
        with patch.object(workflow_module, "included_mask", wraps=workflow_module.included_mask) as mask_build:
            self.assertIsNotNone(workflow.prepare_star_endpoints())
            self.assertIsNotNone(workflow.render_star_preview("composite"))
            self.assertIsNotNone(workflow.render_star_preview("finished_stars"))
            self.assertIsNotNone(workflow.render_star_preview("excluded_stars"))
            self.assertIsNotNone(workflow.render_star_preview("finished_stars", region=(8, 24, 16, 40)))
        self.assertEqual(mask_build.call_count, 1)

        with (
            patch.object(workflow_module, "imread", side_effect=AssertionError("image reload")),
            patch.object(MaskHandler, "load_mask", side_effect=AssertionError("mask reload")),
            patch.object(workflow_module, "load_catalog", side_effect=AssertionError("catalog npz reload")),
            patch.object(workflow_module, "load_round_delta", side_effect=AssertionError("round npz reload")),
            patch.object(workflow_module, "render_glow", side_effect=AssertionError("glow re-render")),
            patch.object(workflow_module, "included_mask", side_effect=AssertionError("included mask rebuild")),
            patch.object(workflow_module, "build_catalog", side_effect=AssertionError("analysis")),
            patch.object(workflow_module, "build_round_delta", side_effect=AssertionError("round rebuild")),
        ):
            composite = workflow.render_star_preview("composite")
            finished = workflow.render_star_preview("finished_stars")
            excluded = workflow.render_star_preview("excluded_stars")
            crop = workflow.render_star_preview("finished_stars", region=(8, 24, 16, 40))

        self.assertIsNotNone(composite)
        self.assertIsNotNone(finished)
        self.assertIsNotNone(excluded)
        self.assertEqual(crop.shape, (16, 24, 3))

    def test_preview_layers_and_compare_base(self):
        project = self.prepare_separated_project(
            "preview",
            stars=gaussian_stars(),
            settings=replace(
                FINISH_DEFAULTS,
                round_stars_enabled=True,
                round_stars_amount=80.0,
                star_glow_enabled=True,
                star_glow_amount=30.0,
            ),
        )
        workflow = self.make_workflow(project)
        self.assertIsNotNone(workflow.prepare_star_endpoints())
        original = workflow.render_star_preview("original_stars")
        excluded = workflow.render_star_preview("excluded_stars")
        finished = workflow.render_star_preview("finished_stars")
        compare = workflow.render_star_preview("finished_stars", compare=True)

        self.assertIsNotNone(original)
        self.assertIsNotNone(excluded)
        self.assertIsNotNone(finished)
        self.assertIsNotNone(compare)
        np.testing.assert_allclose(original - excluded, compare, atol=1e-6, rtol=0)
        self.assertFalse(np.array_equal(finished, compare))

        region = workflow.render_star_preview("finished_stars", region=(4, 12, 6, 18))
        self.assertEqual(region.shape, (8, 12, 3))
        excluded_region = workflow.render_star_preview("excluded_stars", region=(4, 12, 6, 18))
        np.testing.assert_allclose(excluded_region, excluded[4:12, 6:18], atol=1e-6, rtol=0)
        composite_region = workflow.render_star_preview("composite", region=(4, 12, 6, 18))
        self.assertEqual(composite_region.shape, (8, 12, 3))


if __name__ == "__main__":
    unittest.main()
