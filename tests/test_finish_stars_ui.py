"""Focused offscreen UI unit and interaction tests for Finish Stars controls (Step 10)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from startrails.lib.finish.defaults import (
    DEFAULT_FAINT_STAR_AMOUNT_PERCENT,
    DEFAULT_FAINT_STAR_SUPPRESSION,
    DEFAULT_ROUND_STARS_AMOUNT_PERCENT,
    DEFAULT_ROUND_STARS_ENABLED,
    DEFAULT_STAR_AMOUNT_PERCENT,
    DEFAULT_STAR_GLOW_AMOUNT_PERCENT,
    DEFAULT_STAR_GLOW_ENABLED,
    DEFAULT_STAR_GLOW_RADIUS_PX,
    FINISH_EXT,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    FinishSettings,
)
from startrails.lib.image_io import imwrite
from startrails.lib.project_finish import FinishProject
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.sidebar_finish import SidebarFinish
from startrails.ui.steps_stars import FinishStarsSettings
from startrails.ui.views.finish import FinishView
from startrails.workflow.finish import FinishWorkflow
from support import QtTestCase


class TestFinishStarsSettings(QtTestCase):
    """Unit tests for the Step 4 FinishStarsSettings card body widget."""

    def setUp(self):
        super().setUp()
        self.widget = FinishStarsSettings()
        self.widget.show()
        self.addCleanup(self.widget.deleteLater)

    def test_default_control_values(self):
        """Initial widget state matches authoritative defaults."""
        self.assertEqual(self.widget.get_star_amount(), DEFAULT_STAR_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_star_amount_value.text(), f"{int(DEFAULT_STAR_AMOUNT_PERCENT)}%")

        self.assertEqual(self.widget.get_round_stars_enabled(), DEFAULT_ROUND_STARS_ENABLED)
        self.assertFalse(self.widget.check_round_stars.isChecked())
        self.assertEqual(self.widget.get_round_stars_amount(), DEFAULT_ROUND_STARS_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_round_stars_value.text(), f"{int(DEFAULT_ROUND_STARS_AMOUNT_PERCENT)}%")

        self.assertEqual(self.widget.get_faint_star_suppression(), DEFAULT_FAINT_STAR_SUPPRESSION)
        self.assertFalse(self.widget.check_faint_suppression.isChecked())
        self.assertEqual(self.widget.get_faint_star_amount(), DEFAULT_FAINT_STAR_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_faint_suppression_value.text(), f"{int(DEFAULT_FAINT_STAR_AMOUNT_PERCENT)}%")

        self.assertEqual(self.widget.get_star_glow_enabled(), DEFAULT_STAR_GLOW_ENABLED)
        self.assertFalse(self.widget.check_star_glow.isChecked())
        self.assertEqual(self.widget.get_star_glow_amount(), DEFAULT_STAR_GLOW_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_glow_amount_value.text(), f"{int(DEFAULT_STAR_GLOW_AMOUNT_PERCENT)}%")
        self.assertEqual(self.widget.get_star_glow_radius_px(), DEFAULT_STAR_GLOW_RADIUS_PX)
        self.assertEqual(self.widget.lbl_glow_radius_value.text(), f"{int(DEFAULT_STAR_GLOW_RADIUS_PX)} px")

        self.assertEqual(self.widget.get_preview_layer(), "composite")
        self.assertTrue(self.widget.radio_preview_composite.isChecked())
        self.assertFalse(self.widget.radio_preview_stars.isChecked())

        # Sliders disabled initially (prerequisites not met)
        self.assertFalse(self.widget.slider_round_stars.isEnabled())
        self.assertFalse(self.widget.slider_faint_suppression.isEnabled())
        self.assertFalse(self.widget.slider_glow_amount.isEnabled())
        self.assertFalse(self.widget.slider_glow_radius.isEnabled())
        self.assertFalse(self.widget.slider_star_amount.isEnabled())

        # Clear compact help text present
        help_text = self.widget.lbl_help.text()
        self.assertIn("Rounding is cosmetic and applies to isolated stars only", help_text)
        self.assertIn("Crowded, saturated, or border stars may be skipped", help_text)
        self.assertIn("close unresolved pairs cannot be reliably distinguished", help_text)

    def test_interactive_controls_emit_signals(self):
        """User toggles and slider moves emit expected signals and update labels."""
        self.widget.refresh_prerequisites(True)

        star_amount_sigs = []
        round_enabled_sigs = []
        round_amount_sigs = []
        faint_enabled_sigs = []
        faint_amount_sigs = []
        glow_enabled_sigs = []
        glow_amount_sigs = []
        glow_radius_sigs = []
        settings_sigs = []
        preview_sigs = []

        self.widget.star_amount_changed.connect(star_amount_sigs.append)
        self.widget.round_stars_enabled_changed.connect(round_enabled_sigs.append)
        self.widget.round_stars_amount_changed.connect(round_amount_sigs.append)
        self.widget.faint_star_suppression_changed.connect(faint_enabled_sigs.append)
        self.widget.faint_star_amount_changed.connect(faint_amount_sigs.append)
        self.widget.star_glow_enabled_changed.connect(glow_enabled_sigs.append)
        self.widget.star_glow_amount_changed.connect(glow_amount_sigs.append)
        self.widget.star_glow_radius_px_changed.connect(glow_radius_sigs.append)
        self.widget.settings_changed.connect(lambda: settings_sigs.append(True))
        self.widget.preview_layer_changed.connect(preview_sigs.append)

        # 1. Round Stars toggle and slider
        self.widget.check_round_stars.setChecked(True)
        self.assertEqual(round_enabled_sigs, [True])
        self.assertTrue(self.widget.slider_round_stars.isEnabled())

        self.widget.slider_round_stars.setValue(75)
        self.assertEqual(round_amount_sigs, [75.0])
        self.assertEqual(self.widget.lbl_round_stars_value.text(), "75%")

        # 2. Faint Suppression toggle and slider
        self.widget.check_faint_suppression.setChecked(True)
        self.assertEqual(faint_enabled_sigs, [True])
        self.assertTrue(self.widget.slider_faint_suppression.isEnabled())

        self.widget.slider_faint_suppression.setValue(40)
        self.assertEqual(faint_amount_sigs, [40.0])
        self.assertEqual(self.widget.lbl_faint_suppression_value.text(), "40%")

        # 3. Glow toggle, amount and radius
        self.widget.check_star_glow.setChecked(True)
        self.assertEqual(glow_enabled_sigs, [True])
        self.assertTrue(self.widget.slider_glow_amount.isEnabled())
        self.assertTrue(self.widget.slider_glow_radius.isEnabled())

        self.widget.slider_glow_amount.setValue(30)
        self.assertEqual(glow_amount_sigs, [30.0])
        self.assertEqual(self.widget.lbl_glow_amount_value.text(), "30%")

        self.widget.slider_glow_radius.setValue(22)
        self.assertEqual(glow_radius_sigs, [22.0])
        self.assertEqual(self.widget.lbl_glow_radius_value.text(), "22 px")

        # 4. Global Stars Amount slider
        self.widget.slider_star_amount.setValue(65)
        self.assertEqual(star_amount_sigs, [65.0])
        self.assertEqual(self.widget.lbl_star_amount_value.text(), "65%")

        # 5. Preview layer radio
        self.widget.radio_preview_stars.setChecked(True)
        self.assertEqual(preview_sigs, ["stars"])
        self.widget.radio_preview_composite.setChecked(True)
        self.assertEqual(preview_sigs, ["stars", "composite"])

        # Multiple settings_changed emissions occurred
        self.assertGreater(len(settings_sigs), 5)

    def test_programmatic_setters_block_signals(self):
        """Setters update widget values and labels without emitting signals."""
        self.widget.refresh_prerequisites(True)

        star_amount_sigs = []
        round_enabled_sigs = []
        round_amount_sigs = []
        settings_sigs = []

        self.widget.star_amount_changed.connect(star_amount_sigs.append)
        self.widget.round_stars_enabled_changed.connect(round_enabled_sigs.append)
        self.widget.round_stars_amount_changed.connect(round_amount_sigs.append)
        self.widget.settings_changed.connect(lambda: settings_sigs.append(True))

        self.widget.set_round_stars_enabled(True)
        self.widget.set_round_stars_amount(80.0)
        self.widget.set_faint_star_suppression(True)
        self.widget.set_faint_star_amount(25.0)
        self.widget.set_star_glow_enabled(True)
        self.widget.set_star_glow_amount(45.0)
        self.widget.set_star_glow_radius_px(20.0)
        self.widget.set_star_amount(50.0)
        self.widget.set_preview_layer("stars")

        self.assertTrue(self.widget.get_round_stars_enabled())
        self.assertEqual(self.widget.get_round_stars_amount(), 80.0)
        self.assertEqual(self.widget.lbl_round_stars_value.text(), "80%")
        self.assertTrue(self.widget.get_faint_star_suppression())
        self.assertEqual(self.widget.get_faint_star_amount(), 25.0)
        self.assertEqual(self.widget.lbl_faint_suppression_value.text(), "25%")
        self.assertTrue(self.widget.get_star_glow_enabled())
        self.assertEqual(self.widget.get_star_glow_amount(), 45.0)
        self.assertEqual(self.widget.lbl_glow_amount_value.text(), "45%")
        self.assertEqual(self.widget.get_star_glow_radius_px(), 20.0)
        self.assertEqual(self.widget.lbl_glow_radius_value.text(), "20 px")
        self.assertEqual(self.widget.get_star_amount(), 50.0)
        self.assertEqual(self.widget.lbl_star_amount_value.text(), "50%")
        self.assertEqual(self.widget.get_preview_layer(), "stars")

        # Zero signals emitted from setters
        self.assertEqual(star_amount_sigs, [])
        self.assertEqual(round_enabled_sigs, [])
        self.assertEqual(round_amount_sigs, [])
        self.assertEqual(settings_sigs, [])

    def test_reset_action_restores_defaults(self):
        """Clicking Reset restores all 8 settings to FinishSettings defaults."""
        self.widget.refresh_prerequisites(True)
        self.widget.set_round_stars_enabled(True)
        self.widget.set_round_stars_amount(90.0)
        self.widget.set_faint_star_suppression(True)
        self.widget.set_faint_star_amount(70.0)
        self.widget.set_star_glow_enabled(True)
        self.widget.set_star_glow_amount(80.0)
        self.widget.set_star_glow_radius_px(35.0)
        self.widget.set_star_amount(30.0)
        self.widget.set_preview_layer("stars")

        reset_emitted = []
        self.widget.reset_requested.connect(lambda: reset_emitted.append(True))
        self.widget.btn_reset.click()

        self.assertEqual(reset_emitted, [True])
        self.assertEqual(self.widget.get_round_stars_enabled(), DEFAULT_ROUND_STARS_ENABLED)
        self.assertEqual(self.widget.get_round_stars_amount(), DEFAULT_ROUND_STARS_AMOUNT_PERCENT)
        self.assertEqual(self.widget.get_faint_star_suppression(), DEFAULT_FAINT_STAR_SUPPRESSION)
        self.assertEqual(self.widget.get_faint_star_amount(), DEFAULT_FAINT_STAR_AMOUNT_PERCENT)
        self.assertEqual(self.widget.get_star_glow_enabled(), DEFAULT_STAR_GLOW_ENABLED)
        self.assertEqual(self.widget.get_star_glow_amount(), DEFAULT_STAR_GLOW_AMOUNT_PERCENT)
        self.assertEqual(self.widget.get_star_glow_radius_px(), DEFAULT_STAR_GLOW_RADIUS_PX)
        self.assertEqual(self.widget.get_star_amount(), DEFAULT_STAR_AMOUNT_PERCENT)
        self.assertEqual(self.widget.get_preview_layer(), "composite")

    def test_set_from_project_populates_controls(self):
        """set_from_project correctly reads project settings and updates controls."""
        proj = FinishProject(project_file=str(self.root / f"temp{FINISH_EXT}"))
        settings = FinishSettings(
            round_stars_enabled=True,
            round_stars_amount=60.0,
            faint_star_suppression=True,
            faint_star_amount=40.0,
            star_glow_enabled=True,
            star_glow_amount=25.0,
            star_glow_radius_px=18.0,
            star_amount=85.0,
        )
        proj.update_settings(settings)

        self.widget.set_from_project(proj)
        self.assertTrue(self.widget.get_round_stars_enabled())
        self.assertEqual(self.widget.get_round_stars_amount(), 60.0)
        self.assertTrue(self.widget.get_faint_star_suppression())
        self.assertEqual(self.widget.get_faint_star_amount(), 40.0)
        self.assertTrue(self.widget.get_star_glow_enabled())
        self.assertEqual(self.widget.get_star_glow_amount(), 25.0)
        self.assertEqual(self.widget.get_star_glow_radius_px(), 18.0)
        self.assertEqual(self.widget.get_star_amount(), 85.0)


class TestSidebarFinishStarsPrerequisites(QtTestCase):
    """Test SidebarFinish Step 4 prerequisite status progression and readiness."""

    def setUp(self):
        super().setUp()
        self.proj_path = self.root / f"test_sidebar_stars{FINISH_EXT}"
        self.project = FinishProject(project_file=str(self.proj_path))
        self.app = self.make_app(self.project)
        self.workflow = FinishWorkflow(self.app)
        self.app.workflow = self.workflow
        self.sidebar = SidebarFinish(app=self.app)
        self.sidebar.show()
        self.addCleanup(self.sidebar.deleteLater)

    def test_step4_card_initial_subtitle(self):
        """Step 4 card initial subtitle describes rounding, suppression, and glow."""
        self.assertEqual(
            self.sidebar.starsCard.ui.subtitle.text(),
            "Star rounding, faint-star suppression, and glow",
        )

    def test_step4_card_prerequisite_states(self):
        """Step 4 transitions: locked -> ready -> done."""
        # 1. No source image -> locked
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.starsCard.status, "locked")
        self.assertIn("Source image required", self.sidebar.starsCard.ui.subtitle.text())

        # 2. Add source, no mask -> locked
        src_path = self.root / "src.tif"
        imwrite(src_path, np.full((64, 64, 3), 30000, dtype=np.uint16), bit_depth=16)
        self.project.set_source_image(src_path)
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.starsCard.status, "locked")
        self.assertIn("Separated stars required", self.sidebar.starsCard.ui.subtitle.text())

        # 3. Add mask, no separated stars -> locked
        mask_path = self.root / "mask.png"
        imwrite(mask_path, np.full((64, 64), 255, dtype=np.uint8), bit_depth=8)
        self.project.record_artifact(ROLE_SKY_MASK, mask_path)
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.starsCard.status, "locked")
        self.assertIn("Separated stars required", self.sidebar.starsCard.ui.subtitle.text())

        # 4. Add separated layers -> ready (neutral defaults, effects off)
        starless_p = self.root / "starless.tif"
        stars_p = self.root / "stars.tif"
        imwrite(starless_p, np.full((64, 64, 3), 20000, dtype=np.uint16), bit_depth=16)
        imwrite(stars_p, np.full((64, 64, 3), 10000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_SEPARATED_STARLESS, starless_p)
        self.project.record_artifact(ROLE_SEPARATED_STARS, stars_p)

        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.starsCard.status, "ready")
        self.assertEqual(self.sidebar.starsCard.ui.subtitle.text(), "Ready to finish stars")

        # 5. Enable an effect with pending settings (no finished artifact yet) -> ready with pending status
        self.project.update_settings(
            replace(self.project.get_settings(), round_stars_enabled=True, round_stars_amount=50.0)
        )
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.starsCard.status, "ready")
        self.assertEqual(self.sidebar.starsCard.ui.subtitle.text(), "Ready to update stars")

        # 6. Publish finished stars artifact -> done
        finished_p = self.root / "finished_stars.tif"
        imwrite(finished_p, np.full((64, 64, 3), 12000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_FINISHED_STARS, finished_p)
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.starsCard.status, "done")
        self.assertEqual(self.sidebar.starsCard.ui.subtitle.text(), "Stars finished")

        # 7. Changing an effect setting invalidates finished stars -> back to ready with pending status
        self.project.update_settings(
            replace(self.project.get_settings(), star_glow_enabled=True, star_glow_amount=30.0)
        )
        self.sidebar.update_prerequisites(self.project)
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_STARS))
        self.assertEqual(self.sidebar.starsCard.status, "ready")
        self.assertEqual(self.sidebar.starsCard.ui.subtitle.text(), "Ready to update stars")


class TestFinishViewStarsInteraction(QtTestCase):
    """Integration and interaction tests for FinishView handling Finish Stars actions."""

    def setUp(self):
        super().setUp()
        self.proj_path = self.root / f"test_view_stars{FINISH_EXT}"
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
        self.view.bind()
        self.view.resetProjectView()
        self.addCleanup(self.view.teardown)

    def test_settings_changes_persist_and_save_project(self):
        """Slider/toggle interactions persist to project once and call save_project."""
        saved_calls = []
        with patch.object(self.workflow, "save_project", side_effect=lambda: saved_calls.append(True)):
            # Global star amount
            self.view.on_star_amount_changed(80.0)
            self.assertEqual(self.project.get_settings().star_amount, 80.0)

            # Round stars toggle and amount
            self.view.on_round_stars_enabled_changed(True)
            self.assertTrue(self.project.get_settings().round_stars_enabled)
            self.view.on_round_stars_amount_changed(70.0)
            self.assertEqual(self.project.get_settings().round_stars_amount, 70.0)

            # Faint suppression toggle and amount
            self.view.on_faint_star_suppression_changed(True)
            self.assertTrue(self.project.get_settings().faint_star_suppression)
            self.view.on_faint_star_amount_changed(35.0)
            self.assertEqual(self.project.get_settings().faint_star_amount, 35.0)

            # Star glow toggle, amount and radius
            self.view.on_star_glow_enabled_changed(True)
            self.assertTrue(self.project.get_settings().star_glow_enabled)
            self.view.on_star_glow_amount_changed(45.0)
            self.assertEqual(self.project.get_settings().star_glow_amount, 45.0)
            self.view.on_star_glow_radius_px_changed(25.0)
            self.assertEqual(self.project.get_settings().star_glow_radius_px, 25.0)

        self.assertEqual(len(saved_calls), 8)

    def test_global_amount_reuses_current_finished_stars_without_rerunning_effects(self):
        """Changing star amount is composition-only: calls do_recombine, never do_finish_stars."""
        # Establish finished stars artifact
        finished_p = self.root / "finished_stars.tif"
        imwrite(finished_p, np.full((64, 64, 3), 12000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_FINISHED_STARS, finished_p)

        finish_stars_called = []
        recombine_called = []

        with (
            patch.object(self.workflow, "do_finish_stars", side_effect=lambda **kw: finish_stars_called.append(True)),
            patch.object(self.workflow, "do_recombine", side_effect=lambda **kw: recombine_called.append(True)),
        ):
            # Trigger preview for star amount
            self.view._apply_interactive_stars()
            QApplication.processEvents()

        # Recombine was called; do_finish_stars was NOT called
        self.assertEqual(finish_stars_called, [])
        self.assertEqual(recombine_called, [True])

    def test_effects_enabled_call_finish_stars_then_recombine(self):
        """When star effects are enabled and no artifact exists, calls do_finish_stars then do_recombine."""
        self.project.update_settings(
            replace(self.project.get_settings(), round_stars_enabled=True, round_stars_amount=60.0)
        )
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_STARS))

        finish_stars_called = []
        recombine_called = []

        def fake_finish_stars(**kwargs):
            finish_stars_called.append(True)
            finished_p = self.root / "finished_stars.tif"
            imwrite(finished_p, np.full((64, 64, 3), 12000, dtype=np.uint16), bit_depth=16)
            self.project.publish_finished_stars(
                finished_p,
                separation_signature=self.project.separation_signature,
                expected_revision=self.project.processing_revision,
                star_effect_version=1,
                settings=self.project.get_settings(),
            )
            return MagicMock(path=str(finished_p), basename=finished_p.name)

        with (
            patch.object(self.workflow, "do_finish_stars", side_effect=fake_finish_stars),
            patch.object(self.workflow, "do_recombine", side_effect=lambda **kw: recombine_called.append(True)),
        ):
            self.view._apply_interactive_stars()
            QApplication.processEvents()

        self.assertEqual(finish_stars_called, [True])
        self.assertEqual(recombine_called, [True])

    def test_neutral_fallback_recombines_without_calling_finish_stars(self):
        """When all star effects are disabled/neutral, recombines directly from separated stars."""
        self.project.update_settings(
            replace(
                self.project.get_settings(),
                round_stars_enabled=False,
                faint_star_suppression=False,
                star_glow_enabled=False,
            )
        )
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_STARS))

        finish_stars_called = []
        recombine_called = []

        with (
            patch.object(self.workflow, "do_finish_stars", side_effect=lambda **kw: finish_stars_called.append(True)),
            patch.object(self.workflow, "do_recombine", side_effect=lambda **kw: recombine_called.append(True)),
        ):
            self.view._apply_interactive_stars()
            QApplication.processEvents()

        self.assertEqual(finish_stars_called, [])
        self.assertEqual(recombine_called, [True])

    def test_star_amount_zero_recombines_without_requiring_effect_artifact(self):
        """0% star amount does not require finished stars artifact to recombine."""
        self.project.update_settings(
            replace(
                self.project.get_settings(),
                star_amount=0.0,
                round_stars_enabled=True,
                round_stars_amount=50.0,
            )
        )
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_STARS))

        finish_stars_called = []
        recombine_called = []

        with (
            patch.object(self.workflow, "do_finish_stars", side_effect=lambda **kw: finish_stars_called.append(True)),
            patch.object(self.workflow, "do_recombine", side_effect=lambda **kw: recombine_called.append(True)),
        ):
            self.view._apply_interactive_stars()
            QApplication.processEvents()

        # At 0%, effects are not required
        self.assertEqual(finish_stars_called, [])
        self.assertEqual(recombine_called, [True])

    def test_duplicate_task_rejection_retries_via_debounce(self):
        """When task queue rejects a duplicate task ID, view retries with debounce."""
        debounce_called = []
        with (
            patch.object(self.shell, "enqueue_task", return_value=False),
            patch.object(self.view, "_debounce_stars_preview", side_effect=lambda: debounce_called.append(True)),
        ):
            self.view._apply_interactive_stars()

        self.assertEqual(debounce_called, [True])

    def test_preview_layer_switch_preserves_view(self):
        """Switching preview layer displays corresponding file on canvas preserving view."""
        finished_p = self.root / "finished_stars.tif"
        imwrite(finished_p, np.full((64, 64, 3), 12000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_FINISHED_STARS, finished_p)

        show_file_calls = []
        with patch.object(
            self.view,
            "showFile",
            side_effect=lambda f, preserve_view=None, reload=False: show_file_calls.append((f.path, preserve_view)),
        ):
            self.view.on_stars_preview_layer_changed("stars")
            self.assertEqual(show_file_calls[-1], (str(finished_p), True))

            self.view.on_stars_preview_layer_changed("composite")
            self.assertEqual(show_file_calls[-1], (str(self.composite_path), True))

    def test_switching_stars_only_with_pending_effects_schedules_finishing(self):
        """Switching to Stars Only with pending effects schedules finishing and labels pending accurately."""
        # Enable effect but do not publish artifact yet
        self.project.update_settings(
            replace(self.project.get_settings(), round_stars_enabled=True, round_stars_amount=50.0)
        )
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_STARS))

        shown_files = []
        with patch.object(
            self.view,
            "showFile",
            side_effect=lambda f, preserve_view=None, reload=False: shown_files.append(f),
        ):
            self.view.on_stars_preview_layer_changed("stars")

        self.assertTrue(len(shown_files) > 0)
        self.assertEqual(shown_files[-1].operation, "Stars (pending effects)")
        self.assertTrue(self.view._stars_timer is not None and self.view._stars_timer.isActive())

    def test_pre_global_stars_only_at_amount0_builds_effects(self):
        """In Stars Only preview, effects are generated and displayed even when global star amount is 0%."""
        self.project.update_settings(
            replace(
                self.project.get_settings(),
                star_amount=0.0,
                round_stars_enabled=True,
                round_stars_amount=60.0,
            )
        )
        self.sidebar.starsSettings.set_preview_layer("stars")

        finish_stars_called = []

        def fake_finish_stars(**kwargs):
            finish_stars_called.append(True)
            finished_p = self.root / "finished_stars.tif"
            imwrite(finished_p, np.full((64, 64, 3), 12000, dtype=np.uint16), bit_depth=16)
            self.project.publish_finished_stars(
                finished_p,
                separation_signature=self.project.separation_signature,
                expected_revision=self.project.processing_revision,
                star_effect_version=1,
                settings=self.project.get_settings(),
            )
            return MagicMock(path=str(finished_p), basename=finished_p.name)

        shown_files = []
        with (
            patch.object(self.workflow, "do_finish_stars", side_effect=fake_finish_stars),
            patch.object(self.workflow, "do_recombine", return_value=None),
            patch.object(
                self.view, "showFile", side_effect=lambda f, preserve_view=None, reload=False: shown_files.append(f)
            ),
        ):
            self.view._apply_interactive_stars()
            QApplication.processEvents()

        self.assertEqual(finish_stars_called, [True])
        self.assertTrue(len(shown_files) > 0)
        self.assertEqual(shown_files[-1].operation, "Finished Stars")
        self.assertEqual(Path(shown_files[-1].path).name, "finished_stars.tif")

    def test_stale_worker_result_rejected_after_revision_change(self):
        """Worker completion callbacks are dropped when project revision increments during run."""
        self.view.showFile(MagicMock(path=str(self.composite_path)))
        initial_file = getattr(self.canvas, "file", None)

        def delayed_worker():
            # Bump revision before result posts/delivers
            self.project.update_settings(replace(self.project.get_settings(), star_amount=40.0))

        delivered_done = []
        guard = self.view._result_guard()
        post_result = self.view._get_post_result()

        delayed_worker()
        post_result(lambda: delivered_done.append(True))
        QApplication.processEvents()

        self.assertFalse(guard())
        self.assertEqual(delivered_done, [])

    def test_stale_worker_result_rejected_after_project_switch(self):
        """Worker completion callbacks are dropped if the active project is replaced."""
        delivered_done = []
        post_result = self.view._get_post_result()
        guard = self.view._result_guard()

        # Switch project before delivery
        other_project = FinishProject(project_file=str(self.root / f"other{FINISH_EXT}"))
        self.app.project = other_project

        post_result(lambda: delivered_done.append(True))
        QApplication.processEvents()

        self.assertFalse(guard())
        self.assertEqual(delivered_done, [])

    def test_latest_preview_retry_after_busy_queue(self):
        """When an in-flight task blocks enqueue, debounce retry runs with the latest settings."""
        executed_amounts = []
        is_queue_busy = True

        def fake_enqueue(task_id, title, total, desc, work):
            if is_queue_busy:
                return False
            work()
            return True

        def fake_finish(**kwargs):
            executed_amounts.append(self.project.get_settings().round_stars_amount)
            finished_p = self.root / "finished_stars.tif"
            imwrite(finished_p, np.full((64, 64, 3), 12000, dtype=np.uint16), bit_depth=16)
            self.project.record_artifact(ROLE_FINISHED_STARS, finished_p)
            return MagicMock(path=str(finished_p), basename=finished_p.name)

        self.project.update_settings(
            replace(self.project.get_settings(), round_stars_enabled=True, round_stars_amount=30.0)
        )
        self.shell.enqueue_task = fake_enqueue

        with (
            patch.object(self.workflow, "do_finish_stars", side_effect=fake_finish),
            patch.object(self.workflow, "do_recombine", return_value=(np.zeros((64, 64, 3)), self.composite_path)),
        ):
            # First attempt: queue is busy, triggers debounce
            self.view._apply_interactive_stars()
            self.assertEqual(executed_amounts, [])
            self.assertTrue(self.view._stars_timer.isActive())

            # While waiting, user updates slider to 85%
            self.project.update_settings(replace(self.project.get_settings(), round_stars_amount=85.0))

            # In-flight task finishes, freeing queue
            is_queue_busy = False

            # Timer fires retry
            self.view._stars_timer.timeout.emit()
            QApplication.processEvents()

        # Job executed with latest setting (85%), not initial (30%)
        self.assertEqual(executed_amounts, [85.0])

    def test_failed_recombine_does_not_claim_success_in_composite_mode(self):
        """In composite mode, failed recombination does not trigger on_done or update canvas."""
        shown_files = []
        with (
            patch.object(self.workflow, "do_recombine", return_value=None),
            patch.object(
                self.view, "showFile", side_effect=lambda f, preserve_view=None, reload=False: shown_files.append(f)
            ),
        ):
            self.view._apply_interactive_stars()
            QApplication.processEvents()

        self.assertEqual(shown_files, [])

    def test_reset_action_reverts_settings_and_updates_sidebar(self):
        """Reset reverts all star settings in project and updates sidebar widget."""
        self.project.update_settings(
            replace(
                self.project.get_settings(),
                round_stars_enabled=True,
                round_stars_amount=90.0,
                faint_star_suppression=True,
                faint_star_amount=80.0,
                star_glow_enabled=True,
                star_glow_amount=70.0,
                star_glow_radius_px=30.0,
                star_amount=40.0,
            )
        )
        self.sidebar.starsSettings.set_from_project(self.project)

        self.view.on_reset_stars()
        settings = self.project.get_settings()

        self.assertEqual(settings.star_amount, DEFAULT_STAR_AMOUNT_PERCENT)
        self.assertEqual(settings.round_stars_enabled, DEFAULT_ROUND_STARS_ENABLED)
        self.assertEqual(settings.round_stars_amount, DEFAULT_ROUND_STARS_AMOUNT_PERCENT)
        self.assertEqual(settings.faint_star_suppression, DEFAULT_FAINT_STAR_SUPPRESSION)
        self.assertEqual(settings.faint_star_amount, DEFAULT_FAINT_STAR_AMOUNT_PERCENT)
        self.assertEqual(settings.star_glow_enabled, DEFAULT_STAR_GLOW_ENABLED)
        self.assertEqual(settings.star_glow_amount, DEFAULT_STAR_GLOW_AMOUNT_PERCENT)
        self.assertEqual(settings.star_glow_radius_px, DEFAULT_STAR_GLOW_RADIUS_PX)

        self.assertEqual(self.sidebar.starsSettings.get_star_amount(), DEFAULT_STAR_AMOUNT_PERCENT)
        self.assertEqual(self.sidebar.starsSettings.get_round_stars_enabled(), DEFAULT_ROUND_STARS_ENABLED)


if __name__ == "__main__":
    import unittest

    unittest.main()
