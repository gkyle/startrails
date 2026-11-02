"""Workflow and project integration tests for Step 10 star effects.

These tests exercise publication, invalidation, cancellation and recombination
semantics. The numerical star-effects implementation is substituted at its
operation boundary, so this suite stays independent of the prototype algorithm.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from support import QtTestCase

from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.finish.defaults import (
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_FINISHED_STARS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    FinishSettings,
)
from startrails.lib.finish.star_effects import STAR_EFFECT_VERSION
from startrails.lib.finish.starless_filters import STARLESS_FILTER_VERSION
from startrails.lib.image_io import imread, imwrite
from startrails.lib.project_finish import FinishProject, STAR_EFFECT_SETTING_NAMES
from startrails.op.finish import finish_stars as finish_stars_operation
from startrails.workflow.finish import FinishWorkflow


class TestFinishStars(QtTestCase):
    shape = (8, 12, 3)

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
        return project

    def make_workflow(self, project: FinishProject) -> FinishWorkflow:
        app = self.make_app(project)
        workflow = FinishWorkflow(app)
        app.workflow = workflow
        return workflow

    def record_finished_starless(self, project: FinishProject, value: float = 0.3) -> Path:
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

    def write_finished_stars(self, project: FinishProject, value: float = 0.25) -> Path:
        path = self.write_image(project.artifact_path(ROLE_FINISHED_STARS, for_write=True), value)
        self.assertTrue(
            project.publish_finished_stars(
                path,
                separation_signature=project.separation_signature,
                expected_revision=project.processing_revision,
                star_effect_version=STAR_EFFECT_VERSION,
                settings=project.get_settings(),
            )
        )
        return path

    def record_composite_and_export(self, project: FinishProject, value: float = 0.2) -> tuple[Path, Path]:
        composite = self.write_image(project.artifact_path(ROLE_FINISHED_COMPOSITE, for_write=True), value)
        project.record_artifact(
            ROLE_FINISHED_COMPOSITE,
            composite,
            options={"separation_signature": project.separation_signature},
        )
        export = self.write_image(self.root / "user_export.tif", value)
        project.record_export(export)
        return composite, export

    def fake_star_effects(
        self,
        result: np.ndarray,
        *,
        on_progress=None,
        settings_seen: list | None = None,
        source_seen: list | None = None,
    ):
        def apply(stars, sky_mask, settings, *, source, should_interrupt=None, progress_callback=None):
            if settings_seen is not None:
                settings_seen.append(settings)
            if source_seen is not None:
                source_seen.append(source)
            if progress_callback is not None:
                progress_callback(0, 3, "Detecting stars...")
                progress_callback(1, 3, "Correcting stars...")
                progress_callback(3, 3, "Applying glow...")
            if on_progress is not None:
                on_progress(stars, sky_mask, settings)
            return np.asarray(result, dtype=np.float32)

        return apply

    def test_publish_finished_stars_records_only_effect_identity_and_invalidates_derived_outputs(self):
        project = self.prepare_separated_project("publish")
        project.update_settings(
            replace(
                project.get_settings(),
                star_amount=37.0,
                faint_star_suppression=True,
                faint_star_amount=15.0,
                round_stars_enabled=True,
                round_stars_amount=60.0,
                star_glow_enabled=True,
                star_glow_amount=20.0,
                star_glow_radius_px=9.0,
            )
        )
        signature = project.separation_signature
        finished_starless = self.record_finished_starless(project)
        denoised = self.write_image(project.artifact_path(ROLE_DENOISED_STARLESS, for_write=True), 0.29)
        project.record_artifact(ROLE_DENOISED_STARLESS, denoised, options={"separation_signature": signature})
        self.record_composite_and_export(project)

        settings = project.get_settings()
        revision = project.processing_revision
        finished = self.write_image(project.artifact_path(ROLE_FINISHED_STARS, for_write=True), 0.25)
        self.assertTrue(
            project.publish_finished_stars(
                finished,
                separation_signature=signature,
                expected_revision=revision,
                star_effect_version=STAR_EFFECT_VERSION,
                settings=settings,
            )
        )

        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARS), finished)
        options = project.artifact_manifest[ROLE_FINISHED_STARS]["options"]
        self.assertEqual(options["separation_signature"], signature)
        self.assertEqual(options["star_effect_version"], STAR_EFFECT_VERSION)
        for name in STAR_EFFECT_SETTING_NAMES:
            self.assertEqual(options[name], getattr(settings, name))
        self.assertNotIn("star_amount", options)
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertIsNone(project.current_export_path())
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARLESS), finished_starless)
        self.assertEqual(project.current_artifact_path(ROLE_DENOISED_STARLESS), denoised)

        # Effect results belong to the separation that produced their stars.
        project.separation_signature = "different-separation"
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARS))
        project.separation_signature = signature

        # A stale job cannot replace the published result.
        self.assertFalse(
            project.publish_finished_stars(
                finished,
                separation_signature=signature,
                expected_revision=revision - 1,
                star_effect_version=STAR_EFFECT_VERSION,
                settings=replace(settings, round_stars_amount=10.0),
            )
        )
        self.assertEqual(project.artifact_manifest[ROLE_FINISHED_STARS]["options"]["round_stars_amount"], 60.0)

    def test_global_star_amount_preserves_effects_while_effect_settings_invalidate_them(self):
        project = self.prepare_separated_project("settings")
        project.update_settings(
            replace(
                project.get_settings(),
                star_amount=80.0,
                round_stars_enabled=True,
                round_stars_amount=60.0,
            )
        )
        finished = self.write_finished_stars(project)
        finished_starless = self.record_finished_starless(project)
        self.record_composite_and_export(project)

        project.update_settings(replace(project.get_settings(), star_amount=25.0))
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARS), finished)
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertIsNone(project.current_export_path())
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARLESS), finished_starless)

        self.record_composite_and_export(project)
        project.update_settings(replace(project.get_settings(), round_stars_amount=10.0))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARS))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertIsNone(project.current_export_path())
        self.assertIsNotNone(project.current_artifact_path(ROLE_SEPARATED_STARS))
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARLESS), finished_starless)

    def test_do_finish_stars_publishes_lossless_result_with_progress(self):
        project = self.prepare_separated_project("finish_stars")
        project.update_settings(
            replace(
                project.get_settings(),
                round_stars_enabled=True,
                round_stars_amount=50.0,
                star_glow_enabled=True,
                star_glow_amount=10.0,
            )
        )
        workflow = self.make_workflow(project)
        expected = np.clip(np.full(self.shape, 0.1, np.float32) * 0.5 + 0.05, 0.0, 1.0)
        settings_seen: list[FinishSettings] = []
        source_seen: list[np.ndarray] = []
        observed = []
        published_at_done = []

        def observe(total, increment, count, done, data):
            observed.append((total, increment, count, done, data))
            if done:
                published_at_done.append(project.current_artifact_path(ROLE_FINISHED_STARS) is not None)

        apply = self.fake_star_effects(expected, settings_seen=settings_seen, source_seen=source_seen)
        with patch.object(finish_stars_operation, "apply_star_effects", side_effect=apply):
            result = workflow.do_finish_stars(progress_bar=observe)

        self.assertIsNotNone(result)
        self.assertEqual(result.operation, "Finished Stars")
        finished = project.current_artifact_path(ROLE_FINISHED_STARS)
        self.assertEqual(finished, Path(result.path))
        self.assertEqual(imread(finished).dtype, np.uint16)
        np.testing.assert_allclose(
            imread(finished, to_rgb=True, as_float=True),
            expected,
            atol=0.5 / 65535 + np.finfo(np.float32).eps,
            rtol=0,
        )
        options = project.artifact_manifest[ROLE_FINISHED_STARS]["options"]
        self.assertEqual(options["star_effect_version"], STAR_EFFECT_VERSION)
        self.assertEqual(options["round_stars_amount"], 50.0)
        self.assertNotIn("star_amount", options)
        self.assertEqual(settings_seen, [project.get_settings()])
        self.assertEqual(len(source_seen), 1)
        np.testing.assert_allclose(
            source_seen[0],
            np.full(self.shape, 0.5, np.float32),
            atol=1 / 65535,
            rtol=0,
        )

        # Inner effect completion stops at 99; the task reports 100/done only
        # after the TIFF and project record are published.
        self.assertEqual(observed[-1][0], 100)
        self.assertEqual(observed[-1][2], 100)
        self.assertTrue(observed[-1][3])
        self.assertTrue(all(not entry[3] for entry in observed[:-1]))
        self.assertLessEqual(max(entry[2] for entry in observed[:-1]), 99)
        self.assertEqual(published_at_done, [True])
        self.assertIn(
            "Applying glow...",
            [entry[4]["desc"] for entry in observed if entry[4] is not None],
        )

    def test_do_finish_stars_cancels_and_rejects_stale_revisions_without_publishing(self):
        project = self.prepare_separated_project("cancel")
        project.update_settings(replace(project.get_settings(), round_stars_enabled=True, round_stars_amount=50.0))
        workflow = self.make_workflow(project)
        finished = project.artifact_path(ROLE_FINISHED_STARS, for_write=True)

        with workflow.operation_session():
            workflow.app.activeOperation.requestInterrupt()
            self.assertIsNone(workflow.do_finish_stars())
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARS))
        self.assertFalse(finished.exists())
        self.assertFalse(list(project.get_output_dir().glob(".artifact-*")))

        apply = self.fake_star_effects(np.full(self.shape, 0.15, np.float32))
        with patch.object(finish_stars_operation, "apply_star_effects", side_effect=apply):
            self.assertIsNotNone(workflow.do_finish_stars())
        previous = finished.read_bytes()

        def invalidate_while_running(*_args, **_kwargs):
            project.invalidate_artifact_roles(set())
            return np.full(self.shape, 0.5, np.float32)

        with patch.object(finish_stars_operation, "apply_star_effects", side_effect=invalidate_while_running):
            self.assertIsNone(workflow.do_finish_stars())
        self.assertEqual(finished.read_bytes(), previous)
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARS), finished)
        self.assertFalse(list(project.get_output_dir().glob(".artifact-*")))

    def test_recombine_uses_effect_result_and_separated_negative_residual(self):
        shape = self.shape
        project = self.prepare_separated_project(
            "recombine",
            source=np.full(shape, 0.4, np.float32),
            starless=np.full(shape, 0.5, np.float32),
            stars=np.full(shape, 0.1, np.float32),
        )
        project.update_settings(
            replace(project.get_settings(), star_amount=100.0, round_stars_enabled=True, round_stars_amount=40.0)
        )
        self.record_finished_starless(project, value=0.3)
        self.write_finished_stars(project, value=0.2)
        workflow = self.make_workflow(project)

        self.assertIsNotNone(workflow.do_recombine())
        composite = project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        self.assertIsNotNone(composite)
        # 0.3 finished starless + 0.2 finished stars + (0.4 - 0.5) negative residual.
        # Using the finished plate for N would yield 0.6; using separated stars would yield 0.3.
        np.testing.assert_allclose(
            imread(composite, to_rgb=True, as_float=True),
            np.full(shape, 0.4, np.float32),
            atol=3 / 65535,
            rtol=0,
        )

        project.update_settings(replace(project.get_settings(), star_amount=0.0))
        self.assertIsNotNone(project.current_artifact_path(ROLE_FINISHED_STARS))
        self.assertIsNotNone(workflow.do_recombine())
        np.testing.assert_allclose(
            imread(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), to_rgb=True, as_float=True),
            np.full(shape, 0.3, np.float32),
            atol=1 / 65535,
            rtol=0,
        )

    def test_neutral_step7_fallback_remains_but_enabled_effects_require_a_result(self):
        shape = self.shape
        project = self.prepare_separated_project(
            "neutral",
            source=np.full(shape, 0.5, np.float32),
            starless=np.full(shape, 0.4, np.float32),
            stars=np.full(shape, 0.1, np.float32),
        )
        workflow = self.make_workflow(project)

        self.assertIsNotNone(workflow.do_recombine())
        neutral_composite = project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        np.testing.assert_allclose(
            imread(neutral_composite, to_rgb=True, as_float=True),
            np.full(shape, 0.5, np.float32),
            atol=2 / 65535,
            rtol=0,
        )

        project.update_settings(replace(project.get_settings(), round_stars_enabled=True, round_stars_amount=50.0))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertIsNone(workflow.do_recombine())
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))

        # A neutral composite recorded outside do_recombine must not bypass the guard.
        composite_path = self.write_image(project.artifact_path(ROLE_FINISHED_COMPOSITE, for_write=True), 0.5)
        project.record_artifact(
            ROLE_FINISHED_COMPOSITE,
            composite_path,
            options={"separation_signature": project.separation_signature},
        )
        output_path = self.root / "blocked_export.tif"
        with self.assertRaisesRegex(ValueError, "finished-stars"):
            workflow.do_export_composite(output_path)
        self.assertFalse(output_path.exists())

    def test_zero_amount_effect_toggles_are_neutral_and_do_not_require_a_result(self):
        shape = self.shape
        project = self.prepare_separated_project(
            "neutral_toggles",
            source=np.full(shape, 0.5, np.float32),
            starless=np.full(shape, 0.4, np.float32),
            stars=np.full(shape, 0.1, np.float32),
        )
        project.update_settings(
            replace(
                project.get_settings(),
                star_amount=100.0,
                faint_star_suppression=True,
                faint_star_amount=0.0,
                round_stars_enabled=True,
                round_stars_amount=0.0,
                star_glow_enabled=True,
                star_glow_amount=0.0,
            )
        )
        workflow = self.make_workflow(project)

        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARS))
        self.assertIsNotNone(workflow.do_recombine())
        composite = project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        np.testing.assert_allclose(
            imread(composite, to_rgb=True, as_float=True),
            np.full(shape, 0.5, np.float32),
            atol=2 / 65535,
            rtol=0,
        )
        output_path = self.root / "neutral_toggle_export.tif"
        self.assertTrue(workflow.do_export_composite(output_path).is_file())
        self.assertTrue(output_path.is_file())

    def test_zero_global_amount_recombines_and_exports_finished_starless_without_effects(self):
        shape = self.shape
        project = self.prepare_separated_project(
            "zero_amount",
            source=np.full(shape, 0.5, np.float32),
            starless=np.full(shape, 0.4, np.float32),
            stars=np.full(shape, 0.1, np.float32),
        )
        self.record_finished_starless(project, value=0.3)
        project.update_settings(
            replace(
                project.get_settings(),
                star_amount=0.0,
                round_stars_enabled=True,
                round_stars_amount=50.0,
                star_glow_enabled=True,
                star_glow_amount=25.0,
            )
        )
        workflow = self.make_workflow(project)

        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARS))
        self.assertIsNotNone(workflow.do_recombine())
        composite = project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        np.testing.assert_allclose(
            imread(composite, to_rgb=True, as_float=True),
            np.full(shape, 0.3, np.float32),
            atol=1 / 65535,
            rtol=0,
        )
        output_path = self.root / "zero_amount_export.tif"
        self.assertEqual(workflow.do_export_composite(output_path), output_path.resolve())
        np.testing.assert_allclose(
            imread(output_path, to_rgb=True, as_float=True),
            np.full(shape, 0.3, np.float32),
            atol=1 / 65535,
            rtol=0,
        )

    def test_stale_effect_version_is_rejected_at_consumption_boundaries(self):
        project = self.prepare_separated_project("version")
        project.update_settings(replace(project.get_settings(), round_stars_enabled=True, round_stars_amount=50.0))
        workflow = self.make_workflow(project)
        finished_starless = self.record_finished_starless(project)
        self.write_finished_stars(project)
        self.record_composite_and_export(project)

        self.assertFalse(workflow.invalidate_if_star_effects_changed())
        project.artifact_manifest[ROLE_FINISHED_STARS]["options"]["star_effect_version"] = STAR_EFFECT_VERSION + 1
        self.assertTrue(workflow.invalidate_if_star_effects_changed())
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARS))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertIsNone(project.current_export_path())
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARLESS), finished_starless)
        self.assertIsNotNone(project.current_artifact_path(ROLE_SEPARATED_STARS))
        self.assertFalse(workflow.invalidate_if_star_effects_changed())

        # Recombine rejects and invalidates a stale result before consuming it.
        self.write_finished_stars(project)
        self.record_composite_and_export(project)
        project.artifact_manifest[ROLE_FINISHED_STARS]["options"]["star_effect_version"] = STAR_EFFECT_VERSION + 1
        self.assertIsNone(workflow.do_recombine())
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARS))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertIsNone(project.current_export_path())

        # Export applies the same guard, so a stale composite is never encoded.
        self.write_finished_stars(project)
        self.record_composite_and_export(project)
        project.artifact_manifest[ROLE_FINISHED_STARS]["options"]["star_effect_version"] = STAR_EFFECT_VERSION + 1
        with self.assertRaisesRegex(ValueError, "No current composite"):
            workflow.do_export_composite(self.root / "stale_effect_export.tif")
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARS))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertIsNone(project.current_export_path())
        self.assertFalse((self.root / "stale_effect_export.tif").exists())


if __name__ == "__main__":
    unittest.main()
