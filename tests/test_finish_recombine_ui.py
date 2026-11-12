"""Focused offscreen UI unit and interaction tests for Recombine & Save controls (Step 10R)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import numpy as np
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from startrails.lib.file import OutputFile
from startrails.lib.finish.defaults import (
    DEFAULT_BLEND_MODE,
    DEFAULT_STAR_AMOUNT_PERCENT,
    DEFAULT_STAR_THRESHOLD_PERCENT,
    FINISH_EXT,
    ROLE_FINISHED_COMPOSITE,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    FinishSettings,
)
from startrails.lib.finish.nox import DEFAULT_STRIDE, nox_model_identity
from startrails.lib.finish.separation import compute_separation_signature
from startrails.lib.image_io import imwrite
from startrails.lib.project_finish import FinishProject
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.sidebar_finish import FinishRecombineSettings, SidebarFinish
from startrails.ui.views.finish import FinishView
from startrails.workflow.finish import FinishWorkflow
from support import QtTestCase


class TestFinishRecombineSettings(QtTestCase):
    """Unit tests for the Step 4 Recombine & Save controls widget."""

    def setUp(self):
        super().setUp()
        self.widget = FinishRecombineSettings()
        self.widget.show()
        self.addCleanup(self.widget.deleteLater)

    def test_default_values_and_signals(self):
        """Initial widget state matches recombine defaults and emits signals on interaction."""
        self.assertEqual(self.widget.get_star_amount(), DEFAULT_STAR_AMOUNT_PERCENT)
        self.assertEqual(self.widget.spin_star_amount.text(), "100%")
        self.assertEqual(self.widget.spin_star_amount.value(), 100)
        self.assertEqual(self.widget.lbl_star_amount_title.text(), "Stars:")
        self.assertEqual(self.widget.get_star_threshold(), DEFAULT_STAR_THRESHOLD_PERCENT)
        self.assertEqual(self.widget.spin_star_threshold.text(), "0%")
        self.assertEqual(self.widget.spin_star_threshold.value(), 0)
        self.assertEqual(self.widget.lbl_star_threshold_title.text(), "Faint-star cutoff:")
        self.assertEqual(self.widget.slider_star_threshold.maximum(), 50)
        self.assertEqual(self.widget.slider_star_threshold.pageStep(), 5)
        self.assertEqual(self.widget.spin_star_threshold.maximum(), 100)
        self.assertEqual(self.widget.get_blend_mode(), DEFAULT_BLEND_MODE)

        self.widget.refresh_prerequisites(True)
        star_amount_sigs = []
        star_threshold_sigs = []
        star_mode_sigs = []
        settings_sigs = []

        self.widget.star_amount_changed.connect(star_amount_sigs.append)
        self.widget.star_threshold_changed.connect(star_threshold_sigs.append)
        self.widget.blend_mode_changed.connect(star_mode_sigs.append)
        self.widget.settings_changed.connect(lambda: settings_sigs.append(True))

        self.widget.slider_star_amount.setValue(70)
        self.assertEqual(star_amount_sigs, [70.0])
        self.assertEqual(self.widget.spin_star_amount.value(), 70)

        self.widget.spin_star_amount.setValue(65)
        self.assertEqual(star_amount_sigs, [70.0, 65.0])
        self.assertEqual(self.widget.slider_star_amount.value(), 65)

        self.widget.slider_star_threshold.setValue(25)
        self.assertEqual(star_threshold_sigs, [25.0])
        self.assertEqual(self.widget.spin_star_threshold.value(), 25)

        self.widget.spin_star_threshold.setValue(30)
        self.assertEqual(star_threshold_sigs, [25.0, 30.0])
        self.assertEqual(self.widget.slider_star_threshold.value(), 30)

        self.widget.combo_star_blend_mode.setCurrentIndex(1)  # screen
        self.assertEqual(star_mode_sigs, ["screen"])
        self.assertGreaterEqual(len(settings_sigs), 5)

    def test_programmatic_setters_block_signals(self):
        """Programmatic setters update controls without emitting signals."""
        self.widget.refresh_prerequisites(True)
        star_amount_sigs = []
        star_threshold_sigs = []
        star_mode_sigs = []

        self.widget.star_amount_changed.connect(star_amount_sigs.append)
        self.widget.star_threshold_changed.connect(star_threshold_sigs.append)
        self.widget.blend_mode_changed.connect(star_mode_sigs.append)

        self.widget.set_star_amount(50.0)
        self.widget.set_star_threshold(35.0)
        self.widget.set_blend_mode("screen")

        self.assertEqual(self.widget.get_star_amount(), 50.0)
        self.assertEqual(self.widget.spin_star_amount.value(), 50)
        self.assertEqual(self.widget.get_star_threshold(), 35.0)
        self.assertEqual(self.widget.spin_star_threshold.value(), 35)
        self.assertEqual(self.widget.get_blend_mode(), "screen")
        self.assertEqual(star_amount_sigs, [])
        self.assertEqual(star_threshold_sigs, [])
        self.assertEqual(star_mode_sigs, [])

    def test_blend_mode_setters_reject_unsupported_values(self):
        """Blend mode setters reject unsupported modes with ValueError."""
        with self.assertRaises(ValueError):
            self.widget.set_blend_mode("multiply")

    def test_set_from_project_populates_controls(self):
        """set_from_project correctly reads project settings and updates controls."""
        proj = FinishProject(project_file=str(self.root / f"temp{FINISH_EXT}"))
        settings = FinishSettings(star_amount=40.0, star_threshold=15.0, blend_mode="screen")
        proj.update_settings(settings)

        self.widget.set_from_project(proj)
        self.assertEqual(self.widget.get_star_amount(), 40.0)
        self.assertEqual(self.widget.spin_star_amount.value(), 40)
        self.assertEqual(self.widget.get_star_threshold(), 15.0)
        self.assertEqual(self.widget.spin_star_threshold.value(), 15)
        self.assertEqual(self.widget.get_blend_mode(), "screen")

    def test_threshold_above_slider_range_keeps_exact_value_until_slider_changes(self):
        project = FinishProject(project_file=str(self.root / f"high_threshold{FINISH_EXT}"))
        project.update_settings(replace(project.get_settings(), star_threshold=75.0))
        changes = []
        self.widget.star_threshold_changed.connect(changes.append)

        self.widget.set_from_project(project)
        self.assertEqual(self.widget.get_star_threshold(), 75.0)
        self.assertEqual(self.widget.spin_star_threshold.value(), 75)
        self.assertEqual(self.widget.slider_star_threshold.value(), 50)
        self.assertEqual(changes, [])

        self.widget.spin_star_threshold.setValue(100)
        self.assertEqual(self.widget.get_star_threshold(), 100.0)
        self.assertEqual(changes, [100.0])

        self.widget.slider_star_threshold.setValue(49)
        self.assertEqual(self.widget.get_star_threshold(), 49.0)
        self.assertEqual(self.widget.spin_star_threshold.value(), 49)
        self.assertEqual(changes, [100.0, 49.0])

    def test_refresh_prerequisites_toggles_enabled_state(self):
        """refresh_prerequisites enables/disables amount and threshold sliders/spinners and blend mode combo."""
        self.widget.refresh_prerequisites(False)
        self.assertFalse(self.widget.slider_star_amount.isEnabled())
        self.assertFalse(self.widget.spin_star_amount.isEnabled())
        self.assertFalse(self.widget.slider_star_threshold.isEnabled())
        self.assertFalse(self.widget.spin_star_threshold.isEnabled())
        self.assertFalse(self.widget.combo_star_blend_mode.isEnabled())

        self.widget.refresh_prerequisites(True)
        self.assertTrue(self.widget.slider_star_amount.isEnabled())
        self.assertTrue(self.widget.spin_star_amount.isEnabled())
        self.assertTrue(self.widget.slider_star_threshold.isEnabled())
        self.assertTrue(self.widget.spin_star_threshold.isEnabled())
        self.assertTrue(self.widget.combo_star_blend_mode.isEnabled())

    def test_export_layers_controls(self):
        """Export Layers button operates correctly with signals and prerequisites."""
        export_sigs = []
        self.widget.export_layers_requested.connect(lambda: export_sigs.append(True))

        # Enable prerequisites to test click
        self.widget.refresh_prerequisites(True)
        self.assertTrue(self.widget.btn_export_layers.isEnabled())

        # Click export layers
        self.widget.btn_export_layers.click()
        self.assertEqual(export_sigs, [True])

        # refresh_prerequisites(False) disables controls
        self.widget.refresh_prerequisites(False)
        self.assertFalse(self.widget.btn_export_layers.isEnabled())

        # refresh_prerequisites(True) re-enables controls
        self.widget.refresh_prerequisites(True)
        self.assertTrue(self.widget.btn_export_layers.isEnabled())

        # Tooltip explains positive-only, negative correction, and reconstruction
        tooltip = self.widget.btn_export_layers.toolTip()
        self.assertIn("positive-only", tooltip)
        self.assertIn("negative correction", tooltip)
        self.assertIn("reconstruct", tooltip)


class TestSidebarFinishRecombinePrerequisites(QtTestCase):
    """Test SidebarFinish Recombine & Save step prerequisite status progression and readiness."""

    def setUp(self):
        super().setUp()
        self.proj_path = self.root / f"test_sidebar_recombine{FINISH_EXT}"
        self.project = FinishProject(project_file=str(self.proj_path))
        self.app = self.make_app(self.project)
        self.workflow = FinishWorkflow(self.app)
        self.app.workflow = self.workflow
        self.sidebar = SidebarFinish(app=self.app)
        self.sidebar.show()
        self.addCleanup(self.sidebar.deleteLater)

    def test_recombine_card_initial_subtitle_and_number(self):
        """Recombine card is step 4 of 4 and subtitle describes blending layers and export."""
        self.assertEqual(len(self.sidebar._step_cards), 4)
        self.assertEqual(self.sidebar.recombineCard.ui.number.text(), "4")
        self.assertEqual(
            self.sidebar.recombineCard.ui.subtitle.text(),
            "Blend layers and export image",
        )

    def test_recombine_card_prerequisite_states(self):
        """Step 4 transitions: locked -> ready."""
        # 1. No source image -> locked
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.recombineCard.status, "locked")
        self.assertIn("Source image required", self.sidebar.recombineCard.ui.subtitle.text())
        self.assertFalse(self.sidebar.btn_save_output.isEnabled())

        # 2. Add source, no mask -> locked
        src_path = self.root / "src.tif"
        imwrite(src_path, np.full((64, 64, 3), 30000, dtype=np.uint16), bit_depth=16)
        self.project.set_source_image(src_path)
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.recombineCard.status, "locked")
        self.assertIn("Sky region required", self.sidebar.recombineCard.ui.subtitle.text())
        self.assertFalse(self.sidebar.btn_save_output.isEnabled())

        # 3. Add mask, no separated layers -> locked
        mask_path = self.root / "mask.png"
        imwrite(mask_path, np.full((64, 64), 255, dtype=np.uint8), bit_depth=8)
        self.project.record_artifact(ROLE_SKY_MASK, mask_path)
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.recombineCard.status, "locked")
        self.assertIn("Separated layers required", self.sidebar.recombineCard.ui.subtitle.text())
        self.assertFalse(self.sidebar.btn_save_output.isEnabled())

        # 4. Add separated layers -> ready
        starless_p = self.root / "starless.tif"
        stars_p = self.root / "stars.tif"
        imwrite(starless_p, np.full((64, 64, 3), 20000, dtype=np.uint16), bit_depth=16)
        imwrite(stars_p, np.full((64, 64, 3), 10000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_SEPARATED_STARLESS, starless_p)
        self.project.record_artifact(ROLE_SEPARATED_STARS, stars_p)

        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.recombineCard.status, "ready")
        self.assertEqual(self.sidebar.recombineCard.ui.subtitle.text(), "Ready to recombine")
        self.assertTrue(self.sidebar.btn_save_output.isEnabled())
        self.assertTrue(self.sidebar.btn_export_layers.isEnabled())
        self.assertTrue(self.sidebar.slider_star_amount.isEnabled())

        # 5. Record composite -> done ("Composite saved")
        comp_p = self.root / "composite.tif"
        imwrite(comp_p, np.full((64, 64, 3), 24000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_FINISHED_COMPOSITE, comp_p)
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.recombineCard.status, "done")
        self.assertEqual(self.sidebar.recombineCard.ui.subtitle.text(), "Composite saved")

        # 6. Record export -> done ("Finished image saved")
        export_p = self.root / "exported.tif"
        imwrite(export_p, np.full((64, 64, 3), 25000, dtype=np.uint16), bit_depth=16)
        self.project.record_export(export_p)
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.recombineCard.status, "done")
        self.assertEqual(self.sidebar.recombineCard.ui.subtitle.text(), "Finished image saved")
        self.assertTrue(self.sidebar.btn_save_output.isEnabled())
        self.assertTrue(self.sidebar.btn_export_layers.isEnabled())


class TestFinishViewRecombineInteraction(QtTestCase):
    """Integration and interaction tests for FinishView handling Recombine actions."""

    def setUp(self):
        super().setUp()
        self.proj_path = self.root / f"test_view_recombine{FINISH_EXT}"
        self.project = FinishProject(project_file=str(self.proj_path))
        self.app = self.make_app(self.project)
        self.workflow = FinishWorkflow(self.app)
        self.app.workflow = self.workflow

        # Create source image & valid mask
        self.source_path = self.root / "source.tif"
        imwrite(self.source_path, np.full((64, 64, 3), 30000, dtype=np.uint16), bit_depth=16)
        self.project.set_source_image(self.source_path)

        self.mask_path = self.root / "mask.png"
        imwrite(self.mask_path, np.full((64, 64), 255, dtype=np.uint8), bit_depth=8)
        self.project.record_artifact(ROLE_SKY_MASK, self.mask_path)

        self.starless_path = self.root / "starless.tif"
        self.stars_path = self.root / "stars.tif"
        imwrite(self.starless_path, np.full((64, 64, 3), 20000, dtype=np.uint16), bit_depth=16)
        imwrite(self.stars_path, np.full((64, 64, 3), 10000, dtype=np.uint16), bit_depth=16)
        self.composite_path = self.root / "composite.tif"
        imwrite(self.composite_path, np.full((64, 64, 3), 25000, dtype=np.uint16), bit_depth=16)
        sep_options = {
            "stride": DEFAULT_STRIDE,
            "chroma_postfilter": self.project.chroma_postfilter,
            "mask_feather_radius_px": self.project.mask_feather_radius_px,
        }
        mask_id = str(self.project.artifact_manifest[ROLE_SKY_MASK].get("file", ""))
        model_id = nox_model_identity()
        self.separation_signature = compute_separation_signature(
            source_id=self.project.source_file.sourceId,
            mask_id=mask_id,
            model_identity=model_id,
            stride=sep_options["stride"],
            chroma_postfilter=sep_options["chroma_postfilter"],
            mask_feather_radius_px=sep_options["mask_feather_radius_px"],
        )
        self.project.publish_separation(
            self.starless_path,
            self.stars_path,
            signature=self.separation_signature,
            model_identity=model_id,
            expected_revision=self.project.processing_revision,
            composite_path=self.composite_path,
            options=sep_options,
        )

        self.canvas = CanvasLabel()
        self.canvas.resize(400, 400)
        self.addCleanup(self.canvas.deleteLater)

        class Shell(QObject):
            def __init__(self, canvas):
                super().__init__()
                self.canvas_main = canvas
                self.progressBar = None
                self.label_progressBar = None
                self.enqueued_tasks = []

            def enqueue_task(self, task_id, title, total, desc, work):
                self.enqueued_tasks.append(task_id)
                work()
                return True

        self.shell = Shell(self.canvas)
        self.view = FinishView(self.app, self.shell)
        self.sidebar = self.view.build_sidebar(None)
        self.sidebar.show()
        self.addCleanup(self.sidebar.deleteLater)
        self.view.bind()
        self.view.resetProjectView()
        self.addCleanup(self.view.teardown)

    def test_settings_changes_persist_and_save_project(self):
        """Settings interactions persist to project once and call save_project."""
        saved_calls = []
        with patch.object(self.workflow, "save_project", side_effect=lambda: saved_calls.append(True)):
            self.view.on_star_amount_changed(80.0)
            self.assertEqual(self.project.get_settings().star_amount, 80.0)

            self.view.on_star_threshold_changed(25.0)
            self.assertEqual(self.project.get_settings().star_threshold, 25.0)

            self.view.on_blend_mode_changed("screen")
            self.assertEqual(self.project.get_settings().blend_mode, "screen")

        self.assertEqual(len(saved_calls), 3)

    def test_zero_star_amount_persists_and_triggers_recombine(self):
        """0% Stars Amount updates project settings and debounces recombine."""
        self.view.on_star_amount_changed(0.0)
        self.assertEqual(self.project.get_settings().star_amount, 0.0)
        self.assertIsNotNone(self.view._recombine_timer)
        self.assertTrue(self.view._recombine_timer.isActive())

    def test_debounced_worker_recombine_executes_outside_gui(self):
        """Debounce timer timeout executes do_recombine and updates output composite."""
        self.shell.enqueued_tasks.clear()
        recombine_calls = []

        def fake_recombine(**kwargs):
            recombine_calls.append(True)
            return (np.zeros((64, 64, 3)), self.composite_path)

        with patch.object(self.workflow, "do_recombine", side_effect=fake_recombine):
            self.view.on_star_amount_changed(50.0)
            self.assertEqual(recombine_calls, [])

            # Trigger debounce timer
            self.view._recombine_timer.timeout.emit()
            QApplication.processEvents()

            self.assertEqual(recombine_calls, [True])
            self.assertIn("finish_recombine_preview", self.shell.enqueued_tasks)

    def test_mask_editing_mode_blocks_preview_canvas_update(self):
        """When mask edit mode is active, late recombine worker completion does NOT overwrite canvas."""
        self.canvas.set_mask_edit_mode(True)
        self.assertTrue(self.canvas.is_mask_edit_mode())

        canvas_set_calls = []
        with patch.object(self.canvas, "setFromNumpyArray", side_effect=lambda *a, **k: canvas_set_calls.append(a)):
            with patch.object(self.workflow, "do_recombine", return_value=(np.zeros((64, 64, 3)), self.composite_path)):
                self.view.on_star_amount_changed(40.0)
                self.view._recombine_timer.timeout.emit()
                QApplication.processEvents()

        self.assertEqual(canvas_set_calls, [])
        self.assertTrue(self.canvas.is_mask_edit_mode())

    def test_rapid_slider_changes_coalesce_to_single_worker_job(self):
        """Rapid slider updates coalesce within 100 ms debounce timer."""
        recombine_calls = []

        with patch.object(
            self.workflow,
            "do_recombine",
            side_effect=lambda **kw: recombine_calls.append(True) or (np.zeros((64, 64, 3)), self.composite_path),
        ):
            self.view.on_star_amount_changed(30.0)
            self.view.on_star_amount_changed(40.0)
            self.view.on_star_amount_changed(50.0)

            self.assertEqual(recombine_calls, [])
            self.assertTrue(self.view._recombine_timer.isActive())

            self.view._recombine_timer.timeout.emit()
            QApplication.processEvents()

            self.assertEqual(recombine_calls, [True])
            self.assertEqual(self.project.get_settings().star_amount, 50.0)

    def test_stale_worker_result_rejected_after_revision_change(self):
        """Worker completion callbacks are dropped when project revision increments during run."""
        post_result = self.view._get_post_result()
        guard = self.view._result_guard()

        # Bump revision before delivery
        self.project.update_settings(replace(self.project.get_settings(), star_amount=40.0))

        delivered_done = []
        post_result(lambda: delivered_done.append(True))
        QApplication.processEvents()

        self.assertFalse(guard())
        self.assertEqual(delivered_done, [])

    def test_stale_worker_result_rejected_after_project_switch(self):
        """Worker completion callbacks are dropped if the active project is replaced."""
        post_result = self.view._get_post_result()
        guard = self.view._result_guard()

        other_project = FinishProject(project_file=str(self.root / f"other{FINISH_EXT}"))
        self.app.project = other_project

        delivered_done = []
        post_result(lambda: delivered_done.append(True))
        QApplication.processEvents()

        self.assertFalse(guard())
        self.assertEqual(delivered_done, [])

    def test_duplicate_task_rejection_retries_via_debounce(self):
        """A rejected preview is recomputed once the queue accepts work again."""
        with patch.object(self.workflow, "do_recombine", wraps=self.workflow.do_recombine) as recombine:
            with patch.object(self.shell, "enqueue_task", return_value=False):
                self.view.on_star_amount_changed(0.0)
                self.view._recombine_timer.timeout.emit()
                recombine.assert_not_called()

            self.view._recombine_timer.timeout.emit()
            QApplication.processEvents()
            self.assertEqual(recombine.call_count, 1)

        result = self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        self.assertIsNotNone(result)
        # With no stars added, the output is the separated starless plate.
        from startrails.lib.image_io import imread

        np.testing.assert_array_equal(imread(result), imread(self.starless_path))

    def test_save_enabled_after_composition_edits_and_recombines_fullres(self):
        """Save button remains enabled after composition-only edits and recombines before exporting."""
        self.view.on_star_amount_changed(80.0)
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertTrue(self.sidebar.btn_save_output.isEnabled())

        save_dest = str(self.root / "exported.tif")
        recombine_called = []
        export_called = []

        with (
            patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=(save_dest, "TIFF (*.tif)")),
            patch.object(
                self.workflow,
                "do_recombine",
                side_effect=lambda **kw: recombine_called.append(True) or (np.zeros((64, 64, 3)), self.composite_path),
            ),
            patch.object(
                self.workflow,
                "do_export_composite",
                side_effect=lambda output_path: export_called.append(output_path) or Path(output_path),
            ),
            patch("PySide6.QtWidgets.QMessageBox.information"),
        ):
            self.view.on_save_output()

        self.assertEqual(recombine_called, [True])
        self.assertEqual(export_called, [save_dest])

    def test_save_cancelled_avoids_export(self):
        """User cancelling save file dialog avoids launching export task."""
        with (
            patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=("", "")),
            patch.object(self.workflow, "do_export_composite") as mock_export,
        ):
            self.view.on_save_output()
            mock_export.assert_not_called()

    def test_zoom_pan_preserved_on_recombine_completion(self):
        """Canvas zoom and pan are preserved when composite completes and refreshes."""
        self.canvas.zoom_factor = 3.0
        self.canvas.posX = 50
        self.canvas.posY = -25

        with patch.object(
            self.workflow,
            "do_recombine",
            return_value=(np.zeros((64, 64, 3)), self.composite_path),
        ):
            self.view.on_star_amount_changed(65.0)
            self.view._recombine_timer.timeout.emit()
            QApplication.processEvents()

        self.assertAlmostEqual(self.canvas.zoom_factor, 3.0)
        self.assertEqual((self.canvas.posX, self.canvas.posY), (50, -25))

    def test_reopen_project_restores_recombine_settings(self):
        """Reopening project restores star amount, threshold, and blend mode in sidebar controls."""
        self.project.update_settings(
            replace(self.project.get_settings(), star_amount=35.0, star_threshold=18.0, blend_mode="screen")
        )
        self.view.resetProjectView()

        self.assertEqual(self.sidebar.recombineSettings.get_star_amount(), 35.0)
        self.assertEqual(self.sidebar.recombineSettings.spin_star_amount.value(), 35)
        self.assertEqual(self.sidebar.recombineSettings.get_star_threshold(), 18.0)
        self.assertEqual(self.sidebar.recombineSettings.spin_star_threshold.value(), 18)
        self.assertEqual(self.sidebar.recombineSettings.get_blend_mode(), "screen")

    def test_recombine_slider_drag_holds_off_worker_until_release(self):
        """While stars slider is held down (isSliderDown=True), recombine worker is held off until release."""
        recombine_calls = []

        def fake_recombine(**kwargs):
            recombine_calls.append(True)
            return (np.zeros((64, 64, 3)), self.composite_path)

        slider = self.sidebar.recombineSettings.slider_star_amount
        with patch.object(self.workflow, "do_recombine", side_effect=fake_recombine):
            # 1. Mouse down / active drag
            slider.setSliderDown(True)
            slider.setValue(45)
            QApplication.processEvents()

            # Spinner updated immediately
            self.assertEqual(self.sidebar.recombineSettings.spin_star_amount.value(), 45)
            # Settings NOT yet committed, worker NOT executed
            self.assertEqual(self.project.get_settings().star_amount, DEFAULT_STAR_AMOUNT_PERCENT)
            self.assertEqual(recombine_calls, [])

            # Even if timer was somehow started or timeout emits mid-drag, worker is held off
            if self.view._recombine_timer is not None and self.view._recombine_timer.isActive():
                self.view._recombine_timer.timeout.emit()
                QApplication.processEvents()
                self.assertEqual(recombine_calls, [])

            # 2. Release slider
            slider.setSliderDown(False)
            slider.sliderReleased.emit()
            QApplication.processEvents()

            # Settings updated, debounce timer active
            self.assertEqual(self.project.get_settings().star_amount, 45.0)
            self.assertTrue(self.view._recombine_timer.isActive())
            self.assertEqual(self.view._recombine_timer.interval(), 200)

            # Timer fires after release
            self.view._recombine_timer.timeout.emit()
            QApplication.processEvents()
            self.assertEqual(recombine_calls, [True])

    def test_expanding_step4_card_triggers_recombination_when_composite_missing(self):
        """Expanding Step 4 card triggers recombination when composite is not current."""
        # Invalidate composite
        self.project.invalidate_artifact_roles({ROLE_FINISHED_COMPOSITE})
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.view.updateReadyStates()

        recombine_calls = []

        def fake_recombine(**kwargs):
            recombine_calls.append(True)
            self.project.record_artifact(
                ROLE_FINISHED_COMPOSITE,
                self.composite_path,
                options={"separation_signature": self.separation_signature},
            )
            return (np.zeros((64, 64, 3)), self.composite_path)

        with patch.object(self.workflow, "do_recombine", side_effect=fake_recombine):
            # Expand recombine card
            self.sidebar.recombineCard.setExpanded(True)
            QApplication.processEvents()

            self.assertIsNotNone(self.view._recombine_timer)
            self.assertTrue(self.view._recombine_timer.isActive())

            # Fire debounce timer
            self.view._recombine_timer.timeout.emit()
            QApplication.processEvents()

            self.assertEqual(recombine_calls, [True])
            self.assertIsNotNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
            self.assertEqual(Path(self.canvas.file.path).resolve(), self.composite_path.resolve())

    def test_selection_sync_between_input_and_output_files_and_mask_mode(self):
        """Selecting an output file clears inputFiles; viewing source outside Step 1 does NOT show green mask overlay."""
        # 1. In Step 1 (skyCard expanded), viewing source shows mask overlay for editing
        self.sidebar.skyCard.setExpanded(True)
        self.view.showFile(self.project.source_file)
        QApplication.processEvents()
        self.assertTrue(self.canvas.is_mask_edit_mode())

        # 2. Select Output File (Composite in Step 4) -> disables mask edit mode
        self.sidebar.skyCard.setExpanded(False)
        self.sidebar.recombineCard.setExpanded(True)
        comp_file = OutputFile(basename=self.composite_path.name, path=str(self.composite_path), operation="Composite")
        self.sidebar.outputFiles.showFile.emit(comp_file)
        QApplication.processEvents()

        self.assertTrue(self.sidebar.outputFiles.ui.files.currentIndex().isValid())
        self.assertFalse(self.sidebar.inputFiles.ui.files.currentIndex().isValid())
        self.assertFalse(self.canvas.is_mask_edit_mode())

        # 3. Select Input File while in Step 4 -> shows clean Original without green mask overlay
        self.sidebar.inputFiles.showFile.emit(self.project.source_file)
        QApplication.processEvents()

        self.assertTrue(self.sidebar.inputFiles.ui.files.currentIndex().isValid())
        self.assertFalse(self.sidebar.outputFiles.ui.files.currentIndex().isValid())
        self.assertFalse(self.canvas.is_mask_edit_mode())

        # 4. Select Output File again -> returns to Composite with mask overlay off
        self.sidebar.outputFiles.showFile.emit(comp_file)
        QApplication.processEvents()

        self.assertTrue(self.sidebar.outputFiles.ui.files.currentIndex().isValid())
        self.assertFalse(self.sidebar.inputFiles.ui.files.currentIndex().isValid())
        self.assertFalse(self.canvas.is_mask_edit_mode())

    def test_export_layers_action_success_cancel_and_error(self):
        """Export layers prompts for directory, calls workflow.do_export_layers, and handles errors."""
        export_dir = self.root / "exported_layers"
        exported_map = {
            ROLE_SEPARATED_STARLESS: export_dir / "starless.tif",
            ROLE_SEPARATED_STARS: export_dir / "stars.tif",
        }

        # 1. Success path
        self.shell.enqueued_tasks.clear()
        with (
            patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value=str(export_dir)),
            patch.object(self.workflow, "do_export_layers", return_value=exported_map) as mock_exp,
            patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
        ):
            self.sidebar.btn_export_layers.click()
            QApplication.processEvents()

            mock_exp.assert_called_once_with(output_dir=str(export_dir), progress_bar=ANY)
            self.assertIn("finish_export_layers", self.shell.enqueued_tasks)
            mock_info.assert_called_once()
            self.assertIn("Layers Exported", mock_info.call_args[0])

        # 2. Cancel path (empty directory selection)
        with (
            patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value=""),
            patch.object(self.workflow, "do_export_layers") as mock_exp,
        ):
            self.sidebar.btn_export_layers.click()
            QApplication.processEvents()
            mock_exp.assert_not_called()

        # 3. Error path (exception raised in task)
        self.sidebar.recombineCard.setExpanded(True)
        with (
            patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value=str(export_dir)),
            patch.object(self.workflow, "do_export_layers", side_effect=RuntimeError("Export device disconnected")),
        ):
            self.sidebar.btn_export_layers.click()
            QApplication.processEvents()

            self.assertFalse(self.sidebar.recombineSettings.lbl_status.isHidden())
            self.assertIn("Export device disconnected", self.sidebar.recombineSettings.lbl_status.text())

    def test_export_layers_prerequisite_validation(self):
        """Export layers validates source image and separated layers before showing dialog."""
        # 1. Missing separated layers
        self.project.invalidate_artifact_roles({ROLE_SEPARATED_STARLESS})
        with (
            patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory") as mock_dialog,
            patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
        ):
            self.view.on_export_layers()
            mock_dialog.assert_not_called()
            mock_info.assert_called_once()
            self.assertEqual(mock_info.call_args[0][1], "Export Layers")
            self.assertEqual(mock_info.call_args[0][2], "Separate stars before exporting layers.")

        # 2. Missing source image
        self.project.clear_source_image()
        with (
            patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory") as mock_dialog,
            patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
        ):
            self.view.on_export_layers()
            mock_dialog.assert_not_called()
            mock_info.assert_called_once()
            self.assertIn("source image first", mock_info.call_args[0][2])

    def test_step4_status_progression_after_composite_and_save_export(self):
        """Step 4 transitions from 'ready' -> 'done' when composite exists, and 'Finished image saved' on export."""
        self.project.invalidate_artifact_roles({ROLE_FINISHED_COMPOSITE})
        self.view.updateReadyStates()
        self.assertEqual(self.sidebar.recombineCard.status, "ready")
        self.assertEqual(self.sidebar.recombineCard.ui.subtitle.text(), "Ready to recombine")

        self.project.record_artifact(ROLE_FINISHED_COMPOSITE, self.composite_path)
        self.view.updateReadyStates()
        self.assertEqual(self.sidebar.recombineCard.status, "done")
        self.assertEqual(self.sidebar.recombineCard.ui.subtitle.text(), "Composite saved")

        export_path = self.root / "final_image.tif"
        imwrite(export_path, np.full((64, 64, 3), 30000, dtype=np.uint16), bit_depth=16)
        self.project.record_export(export_path)

        self.view.updateReadyStates()
        self.assertEqual(self.sidebar.recombineCard.status, "done")
        self.assertEqual(self.sidebar.recombineCard.ui.subtitle.text(), "Finished image saved")

    def test_step4_before_after_chip_visibility_and_preview(self):
        """Step 4 eye chip appears only when expanded and done, toggling input image (before) and composite (after)."""
        self.sidebar.show()

        # Without composite/export, Step 4 is ready -> chip stays hidden even when expanded.
        self.project.invalidate_artifact_roles({ROLE_FINISHED_COMPOSITE})
        self.view.updateReadyStates()
        with patch.object(self.view, "_debounce_recombine"):
            self.sidebar.recombineCard.setExpanded(True)
        self.assertEqual(self.sidebar.recombineCard.status, "ready")
        self.assertFalse(self.sidebar.recombineCard.ui.previewToggle.isVisible())
        self.sidebar.recombineCard.setExpanded(False)

        # Record composite -> Step 4 is done, hidden while collapsed.
        self.project.record_artifact(ROLE_FINISHED_COMPOSITE, self.composite_path)
        self.view.updateReadyStates()
        self.assertEqual(self.sidebar.recombineCard.status, "done")
        self.assertFalse(self.sidebar.recombineCard.ui.previewToggle.isVisible())

        # Expand Step 4 -> chip appears and defaults to composite ("after").
        self.sidebar.recombineCard.setExpanded(True)
        QApplication.processEvents()
        self.assertTrue(self.sidebar.recombineCard.ui.previewToggle.isVisible())
        self.assertFalse(self.sidebar.recombineCard.ui.previewToggle.isChecked())
        self.assertEqual(Path(self.canvas.file.path).resolve(), self.composite_path.resolve())

        # Click chip -> switches canvas cleanly to the input source image ("before") without expanding collapsed lists.
        self.sidebar.inputFiles.setExpanded(False)
        self.sidebar.outputFiles.setExpanded(False)
        self.sidebar.recombineCard.ui.previewToggle.click()
        QApplication.processEvents()
        self.assertTrue(self.sidebar.recombineCard.ui.previewToggle.isChecked())
        self.assertFalse(self.sidebar.inputFiles.ui.toggle.isChecked())
        self.assertFalse(self.sidebar.outputFiles.ui.toggle.isChecked())
        self.assertEqual(Path(self.canvas.file.path).resolve(), self.source_path.resolve())
        self.assertFalse(self.canvas.is_mask_edit_mode())

        # Click again -> switches back to the composite ("after") without expanding collapsed lists.
        self.sidebar.recombineCard.ui.previewToggle.click()
        QApplication.processEvents()
        self.assertFalse(self.sidebar.recombineCard.ui.previewToggle.isChecked())
        self.assertFalse(self.sidebar.inputFiles.ui.toggle.isChecked())
        self.assertFalse(self.sidebar.outputFiles.ui.toggle.isChecked())
        self.assertEqual(Path(self.canvas.file.path).resolve(), self.composite_path.resolve())

        # Collapse while in "before" hides the chip AND restores composite ("after") on the canvas.
        self.sidebar.recombineCard.ui.previewToggle.click()
        QApplication.processEvents()
        self.assertEqual(Path(self.canvas.file.path).resolve(), self.source_path.resolve())
        self.sidebar.recombineCard.setExpanded(False)
        QApplication.processEvents()
        self.assertFalse(self.sidebar.recombineCard.ui.previewToggle.isVisible())
        self.assertEqual(Path(self.canvas.file.path).resolve(), self.composite_path.resolve())
        self.sidebar.recombineCard.setExpanded(True)
        QApplication.processEvents()
        self.assertTrue(self.sidebar.recombineCard.ui.previewToggle.isVisible())
        self.assertFalse(self.sidebar.recombineCard.ui.previewToggle.isChecked())
        self.assertEqual(Path(self.canvas.file.path).resolve(), self.composite_path.resolve())


if __name__ == "__main__":
    import unittest

    unittest.main()
