"""Workflow regressions for single-layer Finish recombination and layer export.

Covers the lasting contracts: zero/neutral Stars Amount, Add/Screen oracles with
the signed separation residual, reopening cached separation and recomposing
without models, cancellation/stale publication, exporting the current composite,
source-matching layer exports, and refreshing starless plates from cached
endpoint data when the starless controls change.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np

from support import QtTestCase

from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.finish.composition import compute_denoise_endpoint_signature
from startrails.lib.finish.defaults import (
    BLEND_ADD,
    BLEND_SCREEN,
    FINISH_DEFAULTS,
    ROLE_DENOISE_ENDPOINT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    SCOPE_WHOLE_IMAGE,
    FinishSettings,
)
from startrails.lib.finish.graxpert import graxpert_model_identity
from startrails.lib.finish.starless_filters import STARLESS_FILTER_VERSION
from startrails.lib.image_io import imread, imwrite
from startrails.lib.project_finish import LAYER_EXPORT_SUFFIXES, FinishProject
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

    def write_source(self, path: Path, *, bit_depth: int, value: float = 0.5) -> Path:
        pixels = np.full(self.shape, value, np.float32)
        path.parent.mkdir(parents=True, exist_ok=True)
        imwrite(path, pixels, bit_depth=bit_depth)
        return path

    def record_layer(
        self,
        project: FinishProject,
        role: str,
        value: float,
        *,
        options: dict | None = None,
    ) -> Path:
        path = self.write_image(project.artifact_path(role, for_write=True), value)
        project.record_artifact(role, path, options=options)
        return path

    def save_sky_mask(self, project: FinishProject, value: float = 1.0) -> Path:
        path = project.get_output_dir() / "sky_mask.png"
        MaskHandler.save_mask(np.full(self.shape[:2], value, np.float32), path)
        project.record_artifact(ROLE_SKY_MASK, path)
        return path

    def prepare_layer_export_project(self, name: str, suffix: str, bit_depth: int) -> FinishProject:
        project = FinishProject(project_file=str(self.root / f"{name}.proj_finish"))
        project.set_source_image(self.write_source(self.root / f"{name}{suffix}", bit_depth=bit_depth))
        starless = self.write_image(project.artifact_path(ROLE_SEPARATED_STARLESS, for_write=True), 0.4)
        stars = self.write_image(project.artifact_path(ROLE_SEPARATED_STARS, for_write=True), 0.1)
        self.assertTrue(
            project.publish_separation(
                starless,
                stars,
                signature=f"{name}-separation",
                model_identity="nox-model",
                expected_revision=project.processing_revision,
            )
        )
        self.record_layer(project, ROLE_DENOISED_STARLESS, 0.35)
        self.record_layer(
            project,
            ROLE_FINISHED_STARLESS,
            0.3,
            options={"starless_filter_version": STARLESS_FILTER_VERSION},
        )
        return project

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
                model_identity="nox-model",
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
            patch.object(workflow, "_nox_session_for", side_effect=AssertionError("Nox session")),
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
            patch.object(workflow, "_nox_session_for", side_effect=AssertionError("Nox session")),
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

    def test_layer_exports_match_source_format_and_bit_depth(self):
        """Layer exports mirror the source codec/depth and use role-specific names."""
        cases = (
            ("layers_jpeg", ".jpg", 8),
            ("layers_tiff8", ".tif", 8),
            ("layers_tiff16", ".tif", 16),
        )
        for name, suffix, bit_depth in cases:
            with self.subTest(source=name):
                project = self.prepare_layer_export_project(name, suffix, bit_depth)
                workflow = self.make_workflow(project)
                expected_dtype = np.uint8 if bit_depth == 8 else np.uint16
                expected_names = {role: f"{name}{tail}{suffix}" for role, tail in LAYER_EXPORT_SUFFIXES.items()}

                exported = workflow.do_export_layers()
                self.assertEqual(set(exported), set(LAYER_EXPORT_SUFFIXES))
                for role, path in exported.items():
                    self.assertEqual(path.name, expected_names[role])
                    self.assertEqual(imread(path, as_float=False).dtype, expected_dtype)

                single_dir = self.root / f"{name}_single"
                for role, tail in LAYER_EXPORT_SUFFIXES.items():
                    with self.subTest(role=role):
                        target = single_dir / f"{name}{tail}{suffix}"
                        result = workflow.do_export_layer(role, target)
                        self.assertEqual(result, target.resolve())
                        self.assertEqual(imread(result, as_float=False).dtype, expected_dtype)

    def test_layer_exports_roll_back_on_cancellation(self):
        """Cancelling mid-write rolls back every staged layer without publishing."""
        project = self.prepare_layer_export_project("layer_cancel", ".tif", 16)
        workflow = self.make_workflow(project)
        output_dir = self.root / "cancelled_layers"
        real_imwrite = imwrite

        def cancel_after_write(path, *args, **kwargs):
            written = real_imwrite(path, *args, **kwargs)
            workflow.app.activeOperation.requestInterrupt()
            return written

        with workflow.operation_session():
            with patch("startrails.workflow.finish.imwrite", side_effect=cancel_after_write):
                with self.assertRaisesRegex(ValueError, "cancelled"):
                    workflow.do_export_layers(output_dir)
        self.assertFalse(output_dir.exists() and any(output_dir.iterdir()))

        single_target = self.root / "cancelled_layer.tif"
        with workflow.operation_session():
            with patch("startrails.workflow.finish.imwrite", side_effect=cancel_after_write):
                with self.assertRaisesRegex(ValueError, "cancelled"):
                    workflow.do_export_layer(ROLE_SEPARATED_STARLESS, single_target)
        self.assertFalse(single_target.exists())
        self.assertFalse(list(self.root.glob(".artifact-*")))

    def test_layer_exports_refuse_publication_after_revision_change(self):
        """A revision change during writing rolls back layer exports without recording artifacts."""
        real_imwrite = imwrite

        def make_stale_writer(target_project: FinishProject):
            def stale_after_write(path, *args, **kwargs):
                written = real_imwrite(path, *args, **kwargs)
                target_project.processing_revision += 1
                return written

            return stale_after_write

        project = self.prepare_layer_export_project("layer_stale", ".tif", 16)
        workflow = self.make_workflow(project)
        manifest_before = copy.deepcopy(project.artifact_manifest)
        single_target = self.root / "stale_layer.tif"
        with patch("startrails.workflow.finish.imwrite", side_effect=make_stale_writer(project)):
            with self.assertRaisesRegex(ValueError, "Project changed"):
                workflow.do_export_layer(ROLE_SEPARATED_STARLESS, single_target)
        self.assertFalse(single_target.exists())
        self.assertEqual(project.artifact_manifest, manifest_before)

        batch_project = self.prepare_layer_export_project("layer_stale_batch", ".tif", 16)
        batch_workflow = self.make_workflow(batch_project)
        batch_manifest_before = copy.deepcopy(batch_project.artifact_manifest)
        batch_dir = self.root / "stale_layers"
        with patch("startrails.workflow.finish.imwrite", side_effect=make_stale_writer(batch_project)):
            with self.assertRaisesRegex(ValueError, "Project changed"):
                batch_workflow.do_export_layers(batch_dir, roles=[ROLE_SEPARATED_STARLESS])
        self.assertFalse(batch_dir.exists() and any(batch_dir.iterdir()))
        self.assertEqual(batch_project.artifact_manifest, batch_manifest_before)

    def test_layer_exports_reject_stale_settings_snapshots_consistently(self):
        """Batch layer validation enforces the same freshness rule as a single export."""
        project = self.prepare_layer_export_project("layer_mismatch", ".tif", 16)
        denoised_path = project.artifact_path(ROLE_DENOISED_STARLESS)
        project.record_artifact(
            ROLE_DENOISED_STARLESS,
            denoised_path,
            options={"denoise_strength": 5.0, "denoise_scope": project.denoise_scope},
        )
        workflow = self.make_workflow(project)

        with self.assertRaisesRegex(ValueError, "does not match"):
            workflow.do_export_layer(ROLE_DENOISED_STARLESS, self.root / "mismatch_layer.tif")
        with self.assertRaisesRegex(ValueError, "does not match"):
            workflow.do_export_layers(self.root / "mismatch_layers")
        self.assertFalse((self.root / "mismatch_layer.tif").exists())

    def test_jpeg_composite_export_uses_lossless_intermediate(self):
        """A JPEG source exports from composite.tif, never from a prior JPEG export."""
        name = "jpeg_intermediate"
        project = FinishProject(project_file=str(self.root / f"{name}.proj_finish"))
        project.set_source_image(self.write_source(self.root / f"{name}.jpg", bit_depth=8))
        workflow = self.make_workflow(project)
        settings = project.get_settings()
        composite_options = {
            "star_amount": settings.star_amount,
            "star_threshold": settings.star_threshold,
            "blend_mode": settings.blend_mode,
            "enable_starless_denoise": settings.enable_starless_denoise,
            "enable_starless_sharpen": settings.enable_starless_sharpen,
        }
        composite_path = self.write_image(project.artifact_path(ROLE_FINISHED_COMPOSITE, for_write=True), 0.2)
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite_path, options=composite_options)

        first_export = workflow.do_export_composite(self.root / "jpeg_first.jpg")
        self.assertEqual(imread(first_export, as_float=False).dtype, np.uint8)
        np.testing.assert_allclose(imread(first_export, to_rgb=True, as_float=True), 0.2, atol=2 / 255)

        # Replace the 16-bit intermediate with a value no previous export holds.
        self.write_image(composite_path, 0.8)
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite_path, options=composite_options)
        read_paths: list[Path] = []
        real_imread = imread

        def tracking_imread(path, *args, **kwargs):
            read_paths.append(Path(path).resolve())
            return real_imread(path, *args, **kwargs)

        with patch("startrails.workflow.finish.imread", side_effect=tracking_imread):
            second_export = workflow.do_export_composite(self.root / "jpeg_second.jpg")

        self.assertIn(composite_path.resolve(), read_paths)
        self.assertNotIn(first_export.resolve(), read_paths)
        np.testing.assert_allclose(imread(second_export, to_rgb=True, as_float=True), 0.8, atol=2 / 255)

    def test_recombine_refreshes_starless_from_cached_endpoint_without_graxpert(self):
        """Changed starless sliders rebuild the plate from the cached endpoint."""
        project = self.prepare_separated_project(
            "endpoint_refresh",
            source=0.3,
            starless=0.4,
            stars=0.1,
        )
        self.save_sky_mask(project)
        model_identity = graxpert_model_identity()
        endpoint_signature = compute_denoise_endpoint_signature(project.separation_signature, model_identity)
        endpoint_path = self.write_image(project.artifact_path(ROLE_DENOISE_ENDPOINT, for_write=True), 0.6)
        project.record_artifact(
            ROLE_DENOISE_ENDPOINT,
            endpoint_path,
            options={
                "separation_signature": project.separation_signature,
                "denoise_signature": endpoint_signature,
            },
        )
        project.denoise_signature = endpoint_signature
        project.denoise_model_identity = model_identity
        project.update_settings(
            replace(
                project.get_settings(),
                denoise_strength=50.0,
                denoise_scope=SCOPE_WHOLE_IMAGE,
                enable_starless_denoise=True,
                enable_starless_sharpen=True,
                structure_amount=0.0,
                detail_amount=0.0,
                star_amount=100.0,
                blend_mode=BLEND_ADD,
            )
        )
        workflow = self.make_workflow(project)

        with patch.object(workflow, "_graxpert_session_for", side_effect=AssertionError("GraXpert inference")):
            self.assertIsNotNone(workflow.do_recombine())
            # denoised = 0.4 + 0.5 * (0.6 - 0.4) = 0.5; composite = 0.5 + 0.1 - 0.1.
            np.testing.assert_allclose(
                self.read_composite(project), np.full(self.shape, 0.5, np.float32), atol=SAMPLE_TOLERANCE
            )

            project.update_settings(
                replace(
                    project.get_settings(),
                    denoise_strength=25.0,
                    structure_amount=60.0,
                )
            )
            self.assertIsNotNone(workflow.do_recombine())

        # denoised = 0.4 + 0.25 * (0.6 - 0.4) = 0.45; constant plates sharpen unchanged.
        expected = np.full(self.shape, 0.45, np.float32)
        np.testing.assert_allclose(self.read_composite(project), expected, atol=SAMPLE_TOLERANCE)
        options = project.artifact_manifest[ROLE_FINISHED_COMPOSITE]["options"]
        self.assertEqual(options["starless_role"], ROLE_FINISHED_STARLESS)
        finished_options = project.artifact_manifest[ROLE_FINISHED_STARLESS]["options"]
        self.assertEqual(finished_options["structure_amount"], 60.0)
        self.assertEqual(finished_options["denoise_strength"], 25.0)
        exported = workflow.do_export_composite(self.root / "endpoint_refresh.tif")
        np.testing.assert_allclose(imread(exported, to_rgb=True, as_float=True), expected, atol=SAMPLE_TOLERANCE)

    def test_star_threshold_filters_stars_and_invalidates_only_composite(self):
        """Star threshold suppresses isolated weak stars, keeps bright star halos, and guards stale export."""
        stars = np.zeros(self.shape, dtype=np.float32)
        stars[:, :10, :] = 0.15
        stars[:, 20:24, :] = 0.15
        stars[:, 24:, :] = 0.60
        project = self.prepare_separated_project(
            "threshold",
            source=np.clip(0.2 + stars, 0.0, 1.0),
            starless=0.2,
            stars=stars,
            settings=replace(FINISH_DEFAULTS, star_amount=100.0, star_threshold=30.0, blend_mode=BLEND_ADD),
        )
        finished_path = self.write_finished_starless(project, 0.2)
        workflow = self.make_workflow(project)
        self.assertIsNotNone(workflow.do_recombine())

        composite = self.read_composite(project)
        np.testing.assert_allclose(composite[:, :10, :], 0.2, atol=SAMPLE_TOLERANCE)
        np.testing.assert_allclose(composite[:, 20:24, :], 0.35, atol=SAMPLE_TOLERANCE)
        np.testing.assert_allclose(composite[:, 24:, :], 0.8, atol=SAMPLE_TOLERANCE)
        self.assertEqual(project.artifact_manifest[ROLE_FINISHED_COMPOSITE]["options"]["star_threshold"], 30.0)

        project.update_settings(replace(project.get_settings(), star_threshold=10.0))
        self.assertEqual(project.current_artifact_path(ROLE_FINISHED_STARLESS), finished_path)
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        with self.assertRaisesRegex(ValueError, "No current composite"):
            workflow.do_export_composite(self.root / "stale_threshold.tif")


if __name__ == "__main__":
    import unittest

    unittest.main()
