"""Workflow regressions for single-layer Finish recombination (Step 10R).

Covers the lasting non-effect contracts: zero/neutral Stars Amount, Add/Screen
oracles with the signed separation residual, reopening cached separation and
recomposing without models, cancellation/stale publication, and exporting the
current composite.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np

from support import QtTestCase

from startrails.lib.finish.defaults import (
    BLEND_ADD,
    BLEND_SCREEN,
    FINISH_DEFAULTS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    FinishSettings,
)
from startrails.lib.finish.starless_filters import STARLESS_FILTER_VERSION
from startrails.lib.image_io import imread, imwrite
from startrails.lib.project_finish import FinishProject
from startrails.workflow.finish import FinishWorkflow

# 16-bit intermediate quantization: permit one sample per layer plus the
# add/screen round trip.
SAMPLE_TOLERANCE = 3 / 65535


class TestFinishRecombine(QtTestCase):
    shape = (32, 32, 3)

    def write_image(self, path: Path, value: float | np.ndarray) -> Path:
        pixels = np.full(self.shape, value, np.float32) if np.isscalar(value) else np.asarray(value, np.float32)
        path.parent.mkdir(parents=True, exist_ok=True)
        imwrite(path, pixels, bit_depth=16)
        return path

    def prepare_separated_project(
        self,
        name: str,
        *,
        source: float | np.ndarray = 0.5,
        starless: float | np.ndarray = 0.4,
        stars: float | np.ndarray = 0.1,
        settings: FinishSettings | None = None,
    ) -> FinishProject:
        """Publish a current separation without model work."""
        project = FinishProject(project_file=str(self.root / f"{name}.proj_finish"))
        project.set_source_image(self.write_image(self.root / f"{name}_source.tif", source))
        starless_path = self.write_image(project.artifact_path(ROLE_SEPARATED_STARLESS, for_write=True), starless)
        stars_path = self.write_image(project.artifact_path(ROLE_SEPARATED_STARS, for_write=True), stars)
        self.assertTrue(
            project.publish_separation(
                starless_path,
                stars_path,
                signature=f"{name}-separation",
                model_identity="starnet-model",
                expected_revision=project.processing_revision,
            )
        )
        if settings is not None:
            project.update_settings(settings)
        return project

    def make_workflow(self, project: FinishProject) -> FinishWorkflow:
        app = self.make_app(project)
        workflow = FinishWorkflow(app)
        app.workflow = workflow
        return workflow

    def write_finished_starless(self, project: FinishProject, value: float) -> Path:
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

    def read_composite(self, project: FinishProject) -> np.ndarray:
        path = project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        self.assertIsNotNone(path)
        return imread(path, to_rgb=True, as_float=True)

    def test_neutral_add_reconstructs_source_and_zero_amount_returns_starless(self):
        project = self.prepare_separated_project(
            "neutral",
            source=0.5,
            starless=0.4,
            stars=0.1,
            settings=replace(FINISH_DEFAULTS, star_amount=100.0, blend_mode=BLEND_ADD),
        )
        workflow = self.make_workflow(project)

        self.assertIsNotNone(workflow.do_recombine())
        np.testing.assert_allclose(
            self.read_composite(project), np.full(self.shape, 0.5, np.float32), atol=SAMPLE_TOLERANCE, rtol=0
        )
        for mode in (BLEND_ADD, BLEND_SCREEN):
            with self.subTest(mode=mode):
                project.update_settings(replace(project.get_settings(), star_amount=0.0, blend_mode=mode))
                # The layers and composite operation are reused: an amount/mode
                # edit needs no model run or effect job.
                self.assertIsNotNone(workflow.do_recombine())
                np.testing.assert_allclose(
                    self.read_composite(project),
                    np.full(self.shape, 0.4, np.float32),
                    atol=1 / 65535,
                    rtol=0,
                )

    def test_add_and_screen_match_independent_oracles_with_signed_residual(self):
        # N = min(source - separated_starless, 0) = -0.1: Add is reduced by
        # a*0.1, Screen ignores it and uses only the positive star layer.
        project = self.prepare_separated_project(
            "oracles",
            source=0.3,
            starless=0.4,
            stars=0.4,
            settings=replace(FINISH_DEFAULTS, star_amount=50.0, blend_mode=BLEND_ADD),
        )
        workflow = self.make_workflow(project)

        self.assertIsNotNone(workflow.do_recombine())
        expected_add = 0.4 + 0.5 * 0.4 + 0.5 * (0.3 - 0.4)
        np.testing.assert_allclose(
            self.read_composite(project), np.full(self.shape, expected_add, np.float32), atol=SAMPLE_TOLERANCE, rtol=0
        )

        project.update_settings(replace(project.get_settings(), blend_mode=BLEND_SCREEN))
        self.assertIsNotNone(workflow.do_recombine())
        expected_screen = 1.0 - (1.0 - 0.4) * (1.0 - 0.5 * 0.4)
        np.testing.assert_allclose(
            self.read_composite(project),
            np.full(self.shape, expected_screen, np.float32),
            atol=SAMPLE_TOLERANCE,
            rtol=0,
        )

    def test_reopen_shows_cached_separation_and_recombines_without_models(self):
        project = self.prepare_separated_project("reopen", source=0.5, starless=0.4, stars=0.1)
        app = self.make_app(project)
        app.workflow = FinishWorkflow(app)
        self.assertIsNotNone(app.workflow.do_recombine())
        app.saveProject()

        app.loadProject(project.project_file)
        reopened = app.project
        workflow = app.workflow
        self.assertIsNotNone(reopened.current_artifact_path(ROLE_SEPARATED_STARS))
        self.assertIsNotNone(reopened.current_artifact_path(ROLE_SEPARATED_STARLESS))
        # A composite saved before Step 10R is dropped on load; the cached
        # separation layers must recompose without rerunning models.
        reopened.invalidate_artifact_roles({ROLE_FINISHED_COMPOSITE})
        self.assertIsNone(reopened.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        # The four cards can preview the cached separation immediately; the
        # composite is recomposed explicitly when it is missing.
        operations = {output.operation for output in workflow.get_output_file_list()}
        self.assertIn("Starless", operations)
        self.assertIn("Stars", operations)
        self.assertNotIn("Composite", operations)

        with (
            patch.object(workflow, "do_run_starnet", side_effect=AssertionError("StarNet rerun")),
            patch.object(workflow, "_graxpert_session_for", side_effect=AssertionError("GraXpert session")),
        ):
            self.assertIsNotNone(workflow.do_recombine())
        np.testing.assert_allclose(
            self.read_composite(reopened),
            np.full(self.shape, 0.5, np.float32),
            atol=SAMPLE_TOLERANCE,
            rtol=0,
        )

    def test_finished_starless_change_recombines_from_new_plate_without_models(self):
        project = self.prepare_separated_project("plate_refresh", source=0.5, starless=0.4, stars=0.1)
        workflow = self.make_workflow(project)
        self.assertIsNotNone(workflow.do_recombine())

        self.write_finished_starless(project, 0.25)
        with (
            patch.object(workflow, "do_run_starnet", side_effect=AssertionError("StarNet rerun")),
            patch.object(workflow, "_graxpert_session_for", side_effect=AssertionError("GraXpert session")),
        ):
            self.assertIsNotNone(workflow.do_recombine())
        np.testing.assert_allclose(
            self.read_composite(project),
            np.full(self.shape, 0.35, np.float32),
            atol=SAMPLE_TOLERANCE,
            rtol=0,
        )

    def test_cancelled_and_stale_recombine_keep_the_previous_composite(self):
        project = self.prepare_separated_project("cancel", source=0.5, starless=0.4, stars=0.1)
        workflow = self.make_workflow(project)
        self.assertIsNotNone(workflow.do_recombine())
        composite = project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        self.assertIsNotNone(composite)
        previous = composite.read_bytes()

        with workflow.operation_session():
            workflow.app.activeOperation.requestInterrupt()
            self.assertIsNone(workflow.do_recombine())
        self.assertEqual(composite.read_bytes(), previous)
        self.assertFalse(list(project.get_output_dir().glob(".artifact-*")))

        real_recombine = workflow._recombine_into_transaction

        def stale_after_work(*args, **kwargs):
            result = real_recombine(*args, **kwargs)
            project.processing_revision += 1
            return result

        with patch.object(workflow, "_recombine_into_transaction", side_effect=stale_after_work):
            self.assertIsNone(workflow.do_recombine())
        self.assertEqual(composite.read_bytes(), previous)
        self.assertFalse(list(project.get_output_dir().glob(".artifact-*")))

    def test_export_reflects_current_star_settings_and_rejects_stale_composite(self):
        project = self.prepare_separated_project(
            "export",
            source=0.5,
            starless=0.4,
            stars=0.1,
            settings=replace(FINISH_DEFAULTS, star_amount=100.0, blend_mode=BLEND_ADD),
        )
        workflow = self.make_workflow(project)

        self.assertIsNotNone(workflow.do_recombine())
        full_export = workflow.do_export_composite(self.root / "full.tif")
        np.testing.assert_allclose(
            imread(full_export, to_rgb=True, as_float=True),
            np.full(self.shape, 0.5, np.float32),
            atol=SAMPLE_TOLERANCE,
            rtol=0,
        )

        project.update_settings(replace(project.get_settings(), star_amount=0.0))
        # The settings change invalidates the composite; export must not reuse it.
        with self.assertRaisesRegex(ValueError, "No current composite"):
            workflow.do_export_composite(self.root / "stale.tif")
        self.assertFalse((self.root / "stale.tif").exists())

        self.assertIsNotNone(workflow.do_recombine())
        zero_export = workflow.do_export_composite(self.root / "zero.tif")
        np.testing.assert_allclose(
            imread(zero_export, to_rgb=True, as_float=True),
            np.full(self.shape, 0.4, np.float32),
            atol=1 / 65535,
            rtol=0,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
