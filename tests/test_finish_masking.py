"""Tests for shared sky masking in Finish mode and isolation from Denoise mode."""

from pathlib import Path
from unittest.mock import patch

import jsonpickle
import numpy as np
from PySide6.QtCore import QObject

from support import QtTestCase
from startrails.lib.finish.defaults import (
    FINISH_EXT,
    ROLE_FINISHED_COMPOSITE,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
)
from startrails.lib.file import File
from startrails.lib.image_io import imwrite
from startrails.lib.project_denoise import DenoiseProject
from startrails.lib.project_finish import FinishProject
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.sidebar_denoise import SidebarDenoise
from startrails.ui.sky_mask_settings import SkyMaskSettings
from startrails.ui.views.denoise import DenoiseView
from startrails.ui.views.finish import FinishView
from startrails.workflow.finish import FinishWorkflow


class TestFinishMasking(QtTestCase):
    def create_synthetic_image(self, filename: str, bit_depth: int = 8, shape=(64, 64, 3)) -> Path:
        target = self.root / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(42)
        if bit_depth == 8:
            arr = rng.integers(0, 256, shape, dtype=np.uint8)
        elif bit_depth == 16:
            arr = rng.integers(0, 65536, shape, dtype=np.uint16)
        else:
            raise ValueError(f"Unsupported bit depth: {bit_depth}")
        imwrite(target, arr, bit_depth=bit_depth)
        return target

    def make_shell(self):
        shell = QObject()
        shell.canvas_main = CanvasLabel()
        shell.enqueued = []

        def enqueue_task(task_id, title, total, desc, work):
            shell.enqueued.append((task_id, title, desc))
            work()
            return True

        shell.enqueue_task = enqueue_task
        self.addCleanup(shell.deleteLater)
        self.addCleanup(shell.canvas_main.deleteLater)
        return shell

    def test_sky_mask_settings_controls_and_project_sync(self):
        proj_file = self.root / f"test{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))
        project.auto_mask_model = "segformer"
        project.mask_search_radius = 15
        project.mask_erosion_pixels = 8
        project.auto_mask_path = "/models/project_a_mask.pt"
        project.mask_foliage_protection = True

        app = self.make_app(project)
        settings = SkyMaskSettings(app=app)
        self.addCleanup(settings.deleteLater)

        self.assertEqual(settings.ui.modelType.currentText(), "SegFormer (ADE20K Pretrained)")
        self.assertEqual(settings.ui.searchRadius.value(), 15)
        self.assertEqual(settings.ui.erosionPixels.value(), 8)
        self.assertEqual(
            settings.values(),
            {
                "auto_mask_model": "segformer",
                "mask_search_radius": 15,
                "mask_erosion_pixels": 8,
            },
        )

        # Mutate widget controls and sync back
        settings.ui.modelType.setCurrentIndex(0)  # nightstack
        settings.ui.searchRadius.setValue(22)
        settings.ui.erosionPixels.setValue(3)

        self.assertEqual(project.auto_mask_model, "nightstack")
        self.assertEqual(project.mask_search_radius, 22)
        self.assertEqual(project.mask_erosion_pixels, 3)
        # Syncing another project must preserve its non-widget configuration.
        proj_b_file = self.root / f"test_b{FINISH_EXT}"
        project_b = FinishProject(project_file=str(proj_b_file))
        project_b.auto_mask_path = "/models/project_b_custom.pt"
        project_b.mask_foliage_protection = False
        project_b.mask_search_radius = 10
        project_b.mask_erosion_pixels = 5

        # Set controls to explicit 0 values
        settings.ui.modelType.setCurrentIndex(1)  # segformer
        settings.ui.searchRadius.setValue(0)     # 0 translates to None
        settings.ui.erosionPixels.setValue(0)    # explicit 0 erosion

        settings.sync_to_project(project_b)

        self.assertEqual(project_b.auto_mask_model, "segformer")
        self.assertIsNone(project_b.mask_search_radius)
        self.assertEqual(project_b.mask_erosion_pixels, 0)
        self.assertEqual(project_b.auto_mask_path, "/models/project_b_custom.pt")
        self.assertFalse(project_b.mask_foliage_protection)

        # Loading another project's controls preserves explicit zero values.
        settings.set_from_project(project_b)
        self.assertEqual(settings.ui.modelType.currentIndex(), 1)
        self.assertEqual(settings.ui.searchRadius.value(), 0)
        self.assertEqual(settings.ui.erosionPixels.value(), 0)

    def test_workflow_save_mask_geometry_validation_and_artifact_registration(self):
        proj_file = self.root / f"geo{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))
        source = self.create_synthetic_image("geo_source.tif", shape=(60, 80, 3))
        project.set_source_image(source)
        app = self.make_app(project)
        workflow = FinishWorkflow(app)

        # 1. Reject mismatched geometry
        bad_mask = np.ones((50, 50), dtype=np.float32)
        with self.assertRaises(ValueError) as cm:
            workflow.save_mask(bad_mask)
        self.assertIn("do not match source dimensions", str(cm.exception))

        for bad_mask in (np.ones((60, 80, 3)), np.full((60, 80), np.nan)):
            with self.subTest(shape=bad_mask.shape), self.assertRaises(ValueError):
                workflow.save_mask(bad_mask)

        # 2. Accept matching geometry (60, 80)
        valid_mask = np.zeros((60, 80), dtype=np.float32)
        valid_mask[:30, :] = 1.0
        written = workflow.save_mask(valid_mask)
        self.assertTrue(written.is_file())
        self.assertEqual(written.name, "sky_mask.png")

        # Verify publication and current artifact path
        current_p = project.current_artifact_path(ROLE_SKY_MASK)
        self.assertIsNotNone(current_p)
        self.assertEqual(current_p.resolve(), written.resolve())

        # Verify get_current_mask returns loaded array matching input
        loaded = workflow.get_current_mask()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.shape, (60, 80))
        np.testing.assert_allclose(loaded, valid_mask, atol=1.0 / 255.0)

    def test_all_sky_and_clear_mask_operations(self):
        proj_file = self.root / f"allsky{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))
        source = self.create_synthetic_image("allsky_source.tif", shape=(40, 50, 3))
        project.set_source_image(source)
        app = self.make_app(project)
        workflow = FinishWorkflow(app)

        # All sky mask (all 1.0)
        p_all = workflow.do_all_sky_mask()
        self.assertTrue(p_all.is_file())
        mask_all = workflow.get_current_mask()
        self.assertEqual(mask_all.shape, (40, 50))
        self.assertTrue(np.all(mask_all >= 0.99))

        # Clear mask (all 0.0)
        p_clear = workflow.do_clear_mask()
        self.assertTrue(p_clear.is_file())
        mask_clear = workflow.get_current_mask()
        self.assertEqual(mask_clear.shape, (40, 50))
        self.assertTrue(np.all(mask_clear <= 0.01))

    def test_mask_changes_invalidate_downstream_artifacts_only(self):
        proj_file = self.root / f"inval{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))
        source = self.create_synthetic_image("inval_source.tif", shape=(50, 50, 3))
        project.set_source_image(source)
        app = self.make_app(project)
        workflow = FinishWorkflow(app)

        # Set initial mask and simulate downstream artifacts
        initial_mask = np.ones((50, 50), dtype=np.float32)
        workflow.save_mask(initial_mask)

        starless = self.create_synthetic_image("inval.finish/starless.tif", shape=(50, 50, 3), bit_depth=16)
        stars = self.create_synthetic_image("inval.finish/stars.tif", shape=(50, 50, 3), bit_depth=16)
        composite = self.create_synthetic_image("inval.finish/composite.tif", shape=(50, 50, 3), bit_depth=16)
        project.record_artifact(ROLE_SEPARATED_STARLESS, starless)
        project.record_artifact(ROLE_SEPARATED_STARS, stars)
        project.record_artifact(ROLE_FINISHED_COMPOSITE, composite)

        self.assertIsNotNone(project.current_artifact_path(ROLE_SKY_MASK))
        self.assertIsNotNone(project.current_artifact_path(ROLE_SEPARATED_STARLESS))
        self.assertIsNotNone(project.current_artifact_path(ROLE_SEPARATED_STARS))
        self.assertIsNotNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))

        # Updating the mask should preserve the mask but discard downstream separation/composite
        new_mask = np.zeros((50, 50), dtype=np.float32)
        new_mask[10:20, :] = 1.0
        workflow.save_mask(new_mask)

        self.assertIsNotNone(project.current_artifact_path(ROLE_SKY_MASK))
        self.assertIsNone(project.current_artifact_path(ROLE_SEPARATED_STARLESS))
        self.assertIsNone(project.current_artifact_path(ROLE_SEPARATED_STARS))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_COMPOSITE))

    def test_painting_survives_reopening(self):
        proj_file = self.root / f"paint{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))
        source = self.create_synthetic_image("paint_source.tif", shape=(60, 60, 3))
        project.set_source_image(source)

        shell = self.make_shell()
        app = self.make_app(project)
        view = FinishView(app, shell)
        self.addCleanup(view.teardown)
        sidebar = view.build_sidebar(shell.canvas_main)
        self.addCleanup(sidebar.deleteLater)
        view.bind()
        view.resetProjectView()

        # Simulate brush painting on canvas
        painted_mask = np.zeros((60, 60), dtype=np.float32)
        painted_mask[5:15, 5:15] = 1.0
        shell.canvas_main.set_denoise_mask(painted_mask)
        shell.canvas_main.mask_brush_edited.emit()
        shell.canvas_main.mask_changed.emit()

        self.assertTrue(project.has_manual_sky_corrections)
        self.assertIsNotNone(project.current_artifact_path(ROLE_SKY_MASK))

        # Reopen project from serialized state
        encoded = jsonpickle.encode(project)
        reloaded_proj = jsonpickle.decode(encoded)
        self.assertIsInstance(reloaded_proj, FinishProject)
        self.assertTrue(reloaded_proj.has_manual_sky_corrections)

        reloaded_app = self.make_app(reloaded_proj)
        reloaded_shell = self.make_shell()
        reloaded_view = FinishView(reloaded_app, reloaded_shell)
        self.addCleanup(reloaded_view.teardown)
        reloaded_sidebar = reloaded_view.build_sidebar(reloaded_shell.canvas_main)
        self.addCleanup(reloaded_sidebar.deleteLater)
        reloaded_view.bind()
        reloaded_view.resetProjectView()

        # Verify painted mask survived reopening on canvas
        canvas_mask = reloaded_shell.canvas_main.get_denoise_mask()
        self.assertIsNotNone(canvas_mask)
        self.assertEqual(canvas_mask.shape, (60, 60))
        np.testing.assert_allclose(canvas_mask, painted_mask, atol=1.0 / 255.0)
        self.assertEqual(reloaded_sidebar.skyCard.status, "done")

    def test_detection_and_refinement_survive_reopening(self):
        proj_file = self.root / f"detect{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))
        project.auto_mask_path = "/models/custom_detect.pt"
        project.mask_foliage_protection = False
        source = self.create_synthetic_image("detect_source.tif", shape=(64, 64, 3))
        project.set_source_image(source)

        shell = self.make_shell()
        app = self.make_app(project)
        view = FinishView(app, shell)
        self.addCleanup(view.teardown)
        sidebar = view.build_sidebar(shell.canvas_main)
        self.addCleanup(sidebar.deleteLater)
        view.bind()
        view.resetProjectView()

        # Mock DetectSky and RefineMask operations
        mock_detect = np.full((64, 64), 0.8, dtype=np.float32)
        mock_refined = np.full((64, 64), 0.95, dtype=np.float32)

        with (
            patch("startrails.op.denoise.detect_sky.DetectSky.detect", return_value=mock_detect) as mock_detect_op,
            patch("startrails.op.denoise.refine_mask.RefineMask.refine", return_value=mock_refined) as mock_refine_op,
        ):
            # Trigger Detect Sky
            view.mask_controller.do_detect_sky()
            self.qt.processEvents()

            mock_detect_op.assert_called_once()
            self.assertEqual(mock_detect_op.call_args.kwargs["model_path"], "/models/custom_detect.pt")
            mock_refine_op.assert_called_once()
            self.assertFalse(mock_refine_op.call_args.kwargs["foliage_protection"])

            # Also verify direct do_refine_mask forwards foliage_protection=False
            mock_refine_op.reset_mock()
            view.mask_controller.do_refine_mask()
            self.qt.processEvents()
            mock_refine_op.assert_called_once()
            self.assertFalse(mock_refine_op.call_args.kwargs["foliage_protection"])

        self.assertIsNotNone(project.current_artifact_path(ROLE_SKY_MASK))
        self.assertEqual(sidebar.skyCard.status, "done")

        # Change refinement parameters in widget
        sidebar.skySettings.ui.searchRadius.setValue(18)
        sidebar.skySettings.ui.erosionPixels.setValue(7)
        self.assertEqual(project.mask_search_radius, 18)
        self.assertEqual(project.mask_erosion_pixels, 7)

        # Reopen the saved project, including settings changed after detection.
        reloaded_proj = jsonpickle.decode(proj_file.read_text())
        self.assertEqual(reloaded_proj.mask_search_radius, 18)
        self.assertEqual(reloaded_proj.mask_erosion_pixels, 7)

        reloaded_app = self.make_app(reloaded_proj)
        reloaded_shell = self.make_shell()
        reloaded_view = FinishView(reloaded_app, reloaded_shell)
        self.addCleanup(reloaded_view.teardown)
        reloaded_sidebar = reloaded_view.build_sidebar(reloaded_shell.canvas_main)
        self.addCleanup(reloaded_sidebar.deleteLater)
        reloaded_view.bind()
        reloaded_view.resetProjectView()

        self.assertEqual(reloaded_sidebar.skySettings.ui.searchRadius.value(), 18)
        self.assertEqual(reloaded_sidebar.skySettings.ui.erosionPixels.value(), 7)
        self.assertEqual(reloaded_sidebar.skyCard.status, "done")

    def test_source_replacement_invalidates_mask_correctly(self):
        proj_file = self.root / f"replace{FINISH_EXT}"
        project = FinishProject(project_file=str(proj_file))
        source1 = self.create_synthetic_image("source1.tif", shape=(60, 60, 3))
        project.set_source_image(source1)

        shell = self.make_shell()
        app = self.make_app(project)
        view = FinishView(app, shell)
        self.addCleanup(view.teardown)
        sidebar = view.build_sidebar(shell.canvas_main)
        self.addCleanup(sidebar.deleteLater)
        view.bind()
        view.resetProjectView()

        # Add valid mask
        valid_mask = np.ones((60, 60), dtype=np.float32)
        app.workflow.save_mask(valid_mask)
        view.resetProjectView()

        self.assertIsNotNone(project.current_artifact_path(ROLE_SKY_MASK))
        self.assertEqual(sidebar.skyCard.status, "done")

        # Replace source with source2
        source2 = self.create_synthetic_image("source2.tif", shape=(80, 80, 3))
        app.workflow.do_replace_source(source2)
        view.resetProjectView()

        # Mask must be invalidated
        self.assertIsNone(project.current_artifact_path(ROLE_SKY_MASK))
        self.assertFalse(project.has_manual_sky_corrections)
        self.assertEqual(sidebar.skyCard.status, "ready")
        self.assertEqual(sidebar.separateCard.status, "locked")
        self.assertIn("Sky region required", sidebar.separateCard.ui.subtitle.text())
        self.assertIsNone(shell.canvas_main.get_denoise_mask())

    def make_finish_view(self, name: str):
        project = FinishProject(project_file=str(self.root / f"{name}{FINISH_EXT}"))
        source = self.create_synthetic_image(f"{name}_source.tif", shape=(32, 40, 3))
        project.set_source_image(source)
        app = self.make_app(project)
        shell = self.make_shell()
        view = FinishView(app, shell)
        self.addCleanup(view.teardown)
        sidebar = view.build_sidebar(shell.canvas_main)
        self.addCleanup(sidebar.deleteLater)
        view.bind()
        view.resetProjectView()
        return app, shell, view, sidebar

    def test_delayed_detection_cannot_replace_newer_mask_or_source(self):
        for change in ("source", "painting", "project", "teardown"):
            with self.subTest(change=change):
                app, shell, view, sidebar = self.make_finish_view(change)
                old_project = app.project
                mask = np.ones((32, 40), dtype=np.float32)
                with (
                    patch("startrails.op.denoise.detect_sky.DetectSky.detect", return_value=mask),
                    patch("startrails.op.denoise.refine_mask.RefineMask.refine", return_value=mask),
                ):
                    view.mask_controller.do_detect_sky()
                # The worker finished, but Qt has not delivered its result yet.
                if change == "source":
                    source = self.create_synthetic_image("replacement.tif", shape=(32, 40, 3))
                    app.workflow.do_replace_source(source)
                    view.resetProjectView()
                elif change == "painting":
                    app.workflow.save_mask(np.zeros_like(mask))
                elif change == "project":
                    project = FinishProject(project_file=str(self.root / f"new{FINISH_EXT}"))
                    project.set_source_image(old_project.source_file.path)
                    app.project = project
                    app.workflow = FinishWorkflow(app)
                    view.resetProjectView()
                else:
                    view.teardown()
                self.qt.processEvents()
                if change == "painting":
                    self.assertFalse(app.workflow.get_current_mask().any())
                else:
                    self.assertIsNone(app.workflow.get_current_mask())
                    self.assertIsNone(old_project.current_artifact_path(ROLE_SKY_MASK))

    def test_clear_and_all_sky_use_source_geometry_and_publish_once(self):
        app, shell, view, sidebar = self.make_finish_view("fills")
        # Clear must work even before a mask has been initialized.
        for value, action in ((0, view.mask_controller.do_clear_mask), (1, view.mask_controller.do_full_frame_mask)):
            with self.subTest(value=value):
                preview = self.create_synthetic_image(f"preview{value}.tif", shape=(8, 10, 3))
                view.showFile(File(path=str(preview), basename=preview.name))
                revision = app.project.processing_revision
                action()
                self.assertEqual(app.project.processing_revision, revision + 1)
                loaded = app.workflow.get_current_mask()
                self.assertEqual(loaded.shape, (32, 40))
                self.assertTrue(np.all(loaded == value))
                self.assertEqual(shell.canvas_main.file.path, app.project.source_file.path)

    def test_save_as_mask_edit_keeps_original_input_unchanged(self):
        app, shell, view, sidebar = self.make_finish_view("original")
        original = app.workflow.do_all_sky_mask()
        original_bytes = original.read_bytes()
        app.project.relocate(str(self.root / f"copy{FINISH_EXT}"))
        self.assertEqual(app.project.current_artifact_path(ROLE_SKY_MASK), original)
        written = app.workflow.do_clear_mask()
        self.assertEqual(written, app.project.get_output_dir() / "sky_mask.png")
        self.assertNotEqual(written, original)
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertFalse(app.workflow.get_current_mask().any())

    def test_detection_configuration_corrections_and_error_delivery(self):
        app, shell, view, sidebar = self.make_finish_view("configuration")
        app.project.auto_mask_path = "custom-model.pt"
        app.project.mask_foliage_protection = False
        app.project.has_manual_sky_corrections = True
        mask = np.ones((32, 40), dtype=np.float32)
        with (
            patch("startrails.op.denoise.detect_sky.DetectSky.detect", return_value=mask) as detect,
            patch("startrails.op.denoise.refine_mask.RefineMask.refine", return_value=mask) as refine,
        ):
            view.mask_controller.do_detect_sky()
            self.qt.processEvents()
        self.assertEqual(detect.call_args.kwargs["model_path"], "custom-model.pt")
        self.assertFalse(refine.call_args.kwargs["foliage_protection"])
        reloaded = jsonpickle.decode(Path(app.project.project_file).read_text())
        self.assertFalse(reloaded.has_manual_sky_corrections)
        with patch("startrails.op.denoise.detect_sky.DetectSky.detect", side_effect=ValueError("Model failed")):
            view.mask_controller.do_detect_sky()
            self.qt.processEvents()
        self.assertEqual(sidebar.skySettings.ui.error.text(), "Failed: Model failed")

    def test_workflow_session_cancels_on_project_switch(self):
        app, shell, view, sidebar = self.make_finish_view("session")
        with app.workflow.operation_session():
            operation = app.activeOperation
            self.assertFalse(operation.shouldInterrupt())
            app.project = FinishProject()
            self.assertTrue(operation.shouldInterrupt())

    def test_canvas_and_callback_isolation_during_mode_switches(self):
        # Setup Denoise project & Finish project
        dn_proj = DenoiseProject(str(self.root / "mode.proj_denoise"))
        fn_proj = FinishProject(project_file=str(self.root / f"mode{FINISH_EXT}"))
        source = self.create_synthetic_image("mode_source.tif", shape=(60, 60, 3))
        fn_proj.set_source_image(source)

        shell = self.make_shell()

        # 1. Start in DenoiseView
        dn_app = self.make_app(dn_proj)
        dn_view = DenoiseView(dn_app, shell)
        dn_sidebar = SidebarDenoise(parent=shell.canvas_main, app=dn_app)
        self.addCleanup(dn_sidebar.deleteLater)
        dn_view.sidebar_widget = dn_sidebar
        dn_view.bind()

        # Set mask on canvas in Denoise mode
        dn_mask = np.full((60, 60), 0.5, dtype=np.float32)
        shell.canvas_main.set_denoise_mask(dn_mask)
        shell.canvas_main.set_mask_edit_mode(True)
        self.assertTrue(shell.canvas_main.maskEditMode)

        # 2. Switch away from DenoiseView to FinishView
        dn_view.teardown()

        # Verify teardown isolated canvas
        self.assertFalse(shell.canvas_main.maskEditMode)
        self.assertIsNone(shell.canvas_main.get_denoise_mask())

        # 3. Enter FinishView
        fn_app = self.make_app(fn_proj)
        fn_view = FinishView(fn_app, shell)
        self.addCleanup(fn_view.teardown)
        fn_sidebar = fn_view.build_sidebar(shell.canvas_main)
        self.addCleanup(fn_sidebar.deleteLater)
        fn_view.bind()
        fn_view.resetProjectView()

        # Paint on canvas in Finish mode
        fn_mask = np.ones((60, 60), dtype=np.float32)
        shell.canvas_main.set_denoise_mask(fn_mask)
        shell.canvas_main.mask_brush_edited.emit()
        shell.canvas_main.mask_changed.emit()

        # Verify Finish received and saved the mask, and Denoise was untouched
        self.assertIsNotNone(fn_proj.current_artifact_path(ROLE_SKY_MASK))
        self.assertTrue(fn_proj.has_manual_sky_corrections)
        self.assertFalse(hasattr(dn_proj, "has_manual_sky_corrections") and dn_proj.has_manual_sky_corrections)

        # 4. Switch away from FinishView
        fn_view.teardown()
        self.assertFalse(shell.canvas_main.maskEditMode)
        self.assertIsNone(shell.canvas_main.get_denoise_mask())

    def test_detect_sky_uses_active_workflow_after_project_switch(self):
        """Replacing app.project/app.workflow on an active FinishView still runs Detect Sky."""
        proj1 = FinishProject(project_file=str(self.root / f"first{FINISH_EXT}"))
        app = self.make_app(proj1)
        app.workflow = FinishWorkflow(app)
        shell = self.make_shell()

        view = FinishView(app, shell)
        self.addCleanup(view.teardown)
        sidebar = view.build_sidebar(shell.canvas_main)
        self.addCleanup(sidebar.deleteLater)
        view.bind()
        view.resetProjectView()

        # Simulate creating/opening a new Finish project without rebuilding FinishView
        proj2_path = self.root / f"second{FINISH_EXT}"
        app.newProject(str(proj2_path))
        src_path = self.create_synthetic_image("switched_sky.tif", shape=(60, 60, 3))
        app.workflow.do_import_source(src_path)
        view.resetProjectView()

        expected_mask = np.full((60, 60), 0.75, dtype=np.float32)
        with (
            patch(
                "startrails.op.denoise.detect_sky.AutoSkyDetector.detect",
                return_value=expected_mask,
            ) as mock_detect,
            patch(
                "startrails.op.denoise.refine_mask.MaskRefiner.refine",
                return_value=expected_mask,
            ) as mock_refine,
        ):
            sidebar.btn_detect_sky.click()
            self.qt.processEvents()

        mock_detect.assert_called_once()
        mock_refine.assert_called_once()
        saved_mask = app.workflow.get_current_mask()
        self.assertIsNotNone(saved_mask)
        np.testing.assert_allclose(saved_mask, expected_mask, atol=1.0 / 255.0)

    def test_step1_eye_chip_toggles_mask_overlay(self):
        """Step 1 eye chip appears when expanded and done, toggling the canvas mask overlay on and off."""
        app, shell, view, sidebar = self.make_finish_view("overlay_chip")
        shell.canvas_main.show()
        sidebar.show()
        self.qt.processEvents()

        # Before a mask is defined, Step 1 starts ready with overlay disabled and chip hidden.
        self.assertEqual(sidebar.skyCard.status, "ready")
        self.assertFalse(sidebar.skyCard.ui.previewToggle.isVisible())
        self.assertFalse(shell.canvas_main.is_mask_edit_mode())

        # Save a mask -> Step 1 is done, still collapsed -> chip remains hidden until expanded.
        mask = np.ones((32, 40), dtype=np.float32)
        app.workflow.save_mask(mask)
        view.updateReadyStates()
        self.assertEqual(sidebar.skyCard.status, "done")
        self.assertFalse(sidebar.skyCard.ui.previewToggle.isVisible())

        # Expanding Step 1 shows the open-eye chip and turns the mask overlay ON.
        sidebar.skyCard.setExpanded(True)
        self.qt.processEvents()
        self.assertTrue(sidebar.skyCard.ui.previewToggle.isVisible())
        self.assertFalse(sidebar.skyCard.ui.previewToggle.isChecked())
        self.assertFalse(sidebar.skyCard.ui.previewToggle.property("showingBefore"))
        self.assertTrue(shell.canvas_main.is_mask_edit_mode())

        # Clicking the eye chip switches to eye-off and hides the mask overlay.
        sidebar.skyCard.ui.previewToggle.click()
        self.qt.processEvents()
        self.assertTrue(sidebar.skyCard.ui.previewToggle.isChecked())
        self.assertTrue(sidebar.skyCard.ui.previewToggle.property("showingBefore"))
        self.assertFalse(shell.canvas_main.is_mask_edit_mode())

        # Clicking again restores open eye and shows the mask overlay.
        sidebar.skyCard.ui.previewToggle.click()
        self.qt.processEvents()
        self.assertFalse(sidebar.skyCard.ui.previewToggle.isChecked())
        self.assertFalse(sidebar.skyCard.ui.previewToggle.property("showingBefore"))
        self.assertTrue(shell.canvas_main.is_mask_edit_mode())

        # Collapsing Step 1 from eye-off resets state, hides the chip, and turns overlay off.
        sidebar.skyCard.ui.previewToggle.click()
        self.qt.processEvents()
        self.assertFalse(shell.canvas_main.is_mask_edit_mode())
        sidebar.skyCard.setExpanded(False)
        self.qt.processEvents()
        self.assertFalse(sidebar.skyCard.ui.previewToggle.isVisible())
        self.assertFalse(sidebar.skyCard.ui.previewToggle.isChecked())
        self.assertFalse(shell.canvas_main.is_mask_edit_mode())


__all__ = ["TestFinishMasking"]
