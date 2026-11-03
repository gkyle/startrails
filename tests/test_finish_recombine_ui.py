"""Focused offscreen UI unit and interaction tests for Recombine & Save controls (Step 10R)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from startrails.lib.finish.defaults import (
    DEFAULT_BLEND_MODE,
    DEFAULT_STAR_AMOUNT_PERCENT,
    FINISH_EXT,
    ROLE_FINISHED_COMPOSITE,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    FinishSettings,
)
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
        self.assertEqual(self.widget.lbl_star_amount_value.text(), "100%")
        self.assertEqual(self.widget.lbl_star_amount_title.text(), "Stars")
        self.assertEqual(self.widget.get_blend_mode(), DEFAULT_BLEND_MODE)

        self.widget.refresh_prerequisites(True)
        star_amount_sigs = []
        star_mode_sigs = []
        settings_sigs = []

        self.widget.star_amount_changed.connect(star_amount_sigs.append)
        self.widget.blend_mode_changed.connect(star_mode_sigs.append)
        self.widget.settings_changed.connect(lambda: settings_sigs.append(True))

        self.widget.slider_star_amount.setValue(70)
        self.assertEqual(star_amount_sigs, [70.0])
        self.assertEqual(self.widget.lbl_star_amount_value.text(), "70%")

        self.widget.combo_star_blend_mode.setCurrentIndex(1)  # screen
        self.assertEqual(star_mode_sigs, ["screen"])
        self.assertGreaterEqual(len(settings_sigs), 2)

    def test_programmatic_setters_block_signals(self):
        """Programmatic setters update controls without emitting signals."""
        self.widget.refresh_prerequisites(True)
        star_amount_sigs = []
        star_mode_sigs = []

        self.widget.star_amount_changed.connect(star_amount_sigs.append)
        self.widget.blend_mode_changed.connect(star_mode_sigs.append)

        self.widget.set_star_amount(50.0)
        self.widget.set_blend_mode("screen")

        self.assertEqual(self.widget.get_star_amount(), 50.0)
        self.assertEqual(self.widget.lbl_star_amount_value.text(), "50%")
        self.assertEqual(self.widget.get_blend_mode(), "screen")
        self.assertEqual(star_amount_sigs, [])
        self.assertEqual(star_mode_sigs, [])

    def test_blend_mode_setters_reject_unsupported_values(self):
        """Blend mode setters reject unsupported modes with ValueError."""
        with self.assertRaises(ValueError):
            self.widget.set_blend_mode("multiply")

    def test_set_from_project_populates_controls(self):
        """set_from_project correctly reads project settings and updates controls."""
        proj = FinishProject(project_file=str(self.root / f"temp{FINISH_EXT}"))
        settings = FinishSettings(star_amount=40.0, blend_mode="screen")
        proj.update_settings(settings)

        self.widget.set_from_project(proj)
        self.assertEqual(self.widget.get_star_amount(), 40.0)
        self.assertEqual(self.widget.lbl_star_amount_value.text(), "40%")
        self.assertEqual(self.widget.get_blend_mode(), "screen")

    def test_refresh_prerequisites_toggles_enabled_state(self):
        """refresh_prerequisites enables/disables amount slider and blend mode combo."""
        self.widget.refresh_prerequisites(False)
        self.assertFalse(self.widget.slider_star_amount.isEnabled())
        self.assertFalse(self.widget.combo_star_blend_mode.isEnabled())

        self.widget.refresh_prerequisites(True)
        self.assertTrue(self.widget.slider_star_amount.isEnabled())
        self.assertTrue(self.widget.combo_star_blend_mode.isEnabled())


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
        self.assertTrue(self.sidebar.slider_star_amount.isEnabled())


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
        self.project.separation_signature = "sep123"
        self.project.record_artifact(
            ROLE_SEPARATED_STARLESS, self.starless_path, options={"separation_signature": "sep123"}
        )
        self.project.record_artifact(ROLE_SEPARATED_STARS, self.stars_path, options={"separation_signature": "sep123"})

        self.composite_path = self.root / "composite.tif"
        imwrite(self.composite_path, np.full((64, 64, 3), 25000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(
            ROLE_FINISHED_COMPOSITE, self.composite_path, options={"separation_signature": "sep123"}
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

            self.view.on_blend_mode_changed("screen")
            self.assertEqual(self.project.get_settings().blend_mode, "screen")

        self.assertEqual(len(saved_calls), 2)

    def test_zero_star_amount_persists_and_triggers_recombine(self):
        """0% Stars Amount updates project settings and debounces recombine."""
        self.view.on_star_amount_changed(0.0)
        self.assertEqual(self.project.get_settings().star_amount, 0.0)
        self.assertIsNotNone(self.view._recombine_timer)
        self.assertTrue(self.view._recombine_timer.isActive())

    def test_slider_change_schedules_debounced_worker_job(self):
        """Slider change triggers debounce timer before launching recombine worker job."""
        self.view.on_star_amount_changed(60.0)
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
        """When task queue rejects a duplicate task ID, view retries with debounce."""
        debounce_called = []
        with (
            patch.object(self.shell, "enqueue_task", return_value=False),
            patch.object(self.view, "_debounce_recombine", side_effect=lambda: debounce_called.append(True)),
        ):
            self.view._apply_interactive_recombine()

        self.assertEqual(debounce_called, [True])

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
        """Reopening project restores star amount and blend mode in sidebar controls."""
        self.project.update_settings(replace(self.project.get_settings(), star_amount=35.0, blend_mode="screen"))
        self.view.resetProjectView()

        self.assertEqual(self.sidebar.recombineSettings.get_star_amount(), 35.0)
        self.assertEqual(self.sidebar.recombineSettings.lbl_star_amount_value.text(), "35%")
        self.assertEqual(self.sidebar.recombineSettings.get_blend_mode(), "screen")


if __name__ == "__main__":
    import unittest

    unittest.main()
