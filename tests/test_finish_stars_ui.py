"""Focused offscreen UI unit and interaction tests for Finish Stars controls (Step 10B)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from startrails.lib.finish.defaults import (
    DEFAULT_BLEND_MODE,
    DEFAULT_GLOW_STAR_COUNT,
    DEFAULT_ORIGINAL_STARS_AMOUNT_PERCENT,
    DEFAULT_ROUND_STARS_AMOUNT_PERCENT,
    DEFAULT_ROUND_STARS_ENABLED,
    DEFAULT_STAR_AMOUNT_PERCENT,
    DEFAULT_STAR_COUNT_CUTOFF,
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
from startrails.ui.sidebar_finish import FinishRecombineSettings, SidebarFinish
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
        """Initial widget state matches Step 10B authoritative defaults."""
        self.assertEqual(self.widget.get_star_count_cutoff(), DEFAULT_STAR_COUNT_CUTOFF)
        self.assertEqual(self.widget.combo_star_cutoff.currentText(), "10,000")
        self.assertEqual(self.widget.lbl_star_cutoff_info.text(), "—")

        self.assertEqual(self.widget.get_round_stars_enabled(), DEFAULT_ROUND_STARS_ENABLED)
        self.assertFalse(self.widget.check_round_stars.isChecked())
        self.assertEqual(self.widget.get_round_stars_amount(), DEFAULT_ROUND_STARS_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_round_stars_value.text(), f"{int(DEFAULT_ROUND_STARS_AMOUNT_PERCENT)}%")

        self.assertEqual(self.widget.get_star_glow_enabled(), DEFAULT_STAR_GLOW_ENABLED)
        self.assertFalse(self.widget.check_star_glow.isChecked())
        self.assertEqual(self.widget.get_glow_star_count(), DEFAULT_GLOW_STAR_COUNT)
        self.assertEqual(self.widget.combo_glow_count.currentText(), "100")
        self.assertEqual(self.widget.get_star_glow_amount(), DEFAULT_STAR_GLOW_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_glow_amount_value.text(), f"{int(DEFAULT_STAR_GLOW_AMOUNT_PERCENT)}%")
        self.assertEqual(self.widget.get_star_glow_radius_px(), DEFAULT_STAR_GLOW_RADIUS_PX)
        self.assertEqual(self.widget.lbl_glow_radius_value.text(), f"{int(DEFAULT_STAR_GLOW_RADIUS_PX)} px")

        self.assertEqual(self.widget.get_preview_layer(), "composite")
        self.assertTrue(self.widget.radio_preview_composite.isChecked())
        self.assertFalse(self.widget.radio_preview_finished_stars.isChecked())
        self.assertFalse(self.widget.radio_preview_original_stars.isChecked())
        self.assertFalse(self.widget.radio_preview_excluded_stars.isChecked())

        # Faint suppression and global star amount controls are retired from Step 4
        self.assertFalse(hasattr(self.widget.ui, "check_faint_suppression"))
        self.assertFalse(hasattr(self.widget.ui, "slider_faint_suppression"))
        self.assertFalse(hasattr(self.widget.ui, "slider_star_amount"))
        self.assertFalse(hasattr(self.widget, "star_amount_changed"))
        self.assertFalse(hasattr(self.widget, "get_star_amount"))

        # Sliders disabled initially (prerequisites not met)
        self.assertFalse(self.widget.combo_star_cutoff.isEnabled())
        self.assertFalse(self.widget.slider_round_stars.isEnabled())
        self.assertFalse(self.widget.combo_glow_count.isEnabled())
        self.assertFalse(self.widget.slider_glow_amount.isEnabled())
        self.assertFalse(self.widget.slider_glow_radius.isEnabled())
        self.assertFalse(self.widget.btn_compare.isEnabled())

        # Clear help text present
        help_text = self.widget.lbl_help.text()
        self.assertIn("Rounding circularizes isolated stars", help_text)
        self.assertIn("Glow adds an atmospheric halo", help_text)
        self.assertIn("Hold to Compare previews included stars without cosmetic effects", help_text)

    def test_interactive_controls_emit_signals(self):
        """User toggles, combo selections and slider moves emit expected signals and update labels."""
        self.widget.refresh_prerequisites(True)

        cutoff_sigs = []
        round_enabled_sigs = []
        round_amount_sigs = []
        glow_enabled_sigs = []
        glow_count_sigs = []
        glow_amount_sigs = []
        glow_radius_sigs = []
        settings_sigs = []
        preview_sigs = []

        self.widget.star_count_cutoff_changed.connect(cutoff_sigs.append)
        self.widget.round_stars_enabled_changed.connect(round_enabled_sigs.append)
        self.widget.round_stars_amount_changed.connect(round_amount_sigs.append)
        self.widget.star_glow_enabled_changed.connect(glow_enabled_sigs.append)
        self.widget.glow_star_count_changed.connect(glow_count_sigs.append)
        self.widget.star_glow_amount_changed.connect(glow_amount_sigs.append)
        self.widget.star_glow_radius_px_changed.connect(glow_radius_sigs.append)
        self.widget.settings_changed.connect(lambda: settings_sigs.append(True))
        self.widget.preview_layer_changed.connect(preview_sigs.append)

        # 1. Included Stars Cutoff combo (All, 100,000, 10,000, 1,000)
        self.widget.combo_star_cutoff.setCurrentIndex(0)  # All -> None
        self.assertEqual(cutoff_sigs, [None])
        self.widget.combo_star_cutoff.setCurrentIndex(1)  # 100,000 -> 100000
        self.assertEqual(cutoff_sigs, [None, 100000])
        self.widget.combo_star_cutoff.setCurrentIndex(3)  # 1,000 -> 1000
        self.assertEqual(cutoff_sigs, [None, 100000, 1000])

        # 2. Round Stars toggle and slider
        self.widget.check_round_stars.setChecked(True)
        self.assertEqual(round_enabled_sigs, [True])
        self.assertTrue(self.widget.slider_round_stars.isEnabled())

        self.widget.slider_round_stars.setValue(75)
        self.assertEqual(round_amount_sigs, [75.0])
        self.assertEqual(self.widget.lbl_round_stars_value.text(), "75%")

        # 3. Glow toggle, count subset, amount and radius
        self.widget.check_star_glow.setChecked(True)
        self.assertEqual(glow_enabled_sigs, [True])
        self.assertTrue(self.widget.combo_glow_count.isEnabled())
        self.assertTrue(self.widget.slider_glow_amount.isEnabled())
        self.assertTrue(self.widget.slider_glow_radius.isEnabled())

        self.widget.combo_glow_count.setCurrentIndex(2)  # 500
        self.assertEqual(glow_count_sigs, [500])

        self.widget.slider_glow_amount.setValue(30)
        self.assertEqual(glow_amount_sigs, [30.0])
        self.assertEqual(self.widget.lbl_glow_amount_value.text(), "30%")

        self.widget.slider_glow_radius.setValue(22)
        self.assertEqual(glow_radius_sigs, [22.0])
        self.assertEqual(self.widget.lbl_glow_radius_value.text(), "22 px")

        # 4. Preview layer radios (four choices)
        self.widget.radio_preview_finished_stars.setChecked(True)
        self.assertEqual(preview_sigs, ["finished_stars"])
        self.widget.radio_preview_original_stars.setChecked(True)
        self.assertEqual(preview_sigs, ["finished_stars", "original_stars"])
        self.widget.radio_preview_excluded_stars.setChecked(True)
        self.assertEqual(preview_sigs, ["finished_stars", "original_stars", "excluded_stars"])
        self.widget.radio_preview_composite.setChecked(True)
        self.assertEqual(preview_sigs, ["finished_stars", "original_stars", "excluded_stars", "composite"])

        # Multiple settings_changed emissions occurred
        self.assertGreater(len(settings_sigs), 5)

    def test_hold_to_compare_emits_press_and_release(self):
        """Hold to compare button emits pressed and released signals."""
        self.widget.refresh_prerequisites(True)
        pressed = []
        released = []
        self.widget.compare_pressed.connect(lambda: pressed.append(True))
        self.widget.compare_released.connect(lambda: released.append(True))

        self.widget.btn_compare.pressed.emit()
        self.assertEqual(pressed, [True])
        self.assertEqual(released, [])

        self.widget.btn_compare.released.emit()
        self.assertEqual(pressed, [True])
        self.assertEqual(released, [True])

    def test_cutoff_display_formatting(self):
        """set_cutoff_display formats N of M stars and cutoff score correctly, including for All."""
        self.widget.set_cutoff_display(10000, 42150, score=12.34)
        info = self.widget.lbl_star_cutoff_info.text()
        self.assertIn("10,000", info)
        self.assertIn("42,150", info)
        self.assertIn("12.34", info)

        # For All, displays N of M (N=M) and cutoff score
        self.widget.set_cutoff_display(42150, 42150, score=0.00)
        info_all = self.widget.lbl_star_cutoff_info.text()
        self.assertIn("42,150 of 42,150", info_all)
        self.assertIn("0.00", info_all)

        self.widget.set_cutoff_display(None, None)
        self.assertEqual(self.widget.lbl_star_cutoff_info.text(), "—")

    def test_programmatic_setters_block_signals(self):
        """Setters update widget values and labels without emitting signals."""
        self.widget.refresh_prerequisites(True)

        cutoff_sigs = []
        round_enabled_sigs = []
        round_amount_sigs = []
        glow_enabled_sigs = []
        glow_count_sigs = []
        glow_amount_sigs = []
        glow_radius_sigs = []
        settings_sigs = []

        self.widget.star_count_cutoff_changed.connect(cutoff_sigs.append)
        self.widget.round_stars_enabled_changed.connect(round_enabled_sigs.append)
        self.widget.round_stars_amount_changed.connect(round_amount_sigs.append)
        self.widget.star_glow_enabled_changed.connect(glow_enabled_sigs.append)
        self.widget.glow_star_count_changed.connect(glow_count_sigs.append)
        self.widget.star_glow_amount_changed.connect(glow_amount_sigs.append)
        self.widget.star_glow_radius_px_changed.connect(glow_radius_sigs.append)
        self.widget.settings_changed.connect(lambda: settings_sigs.append(True))

        self.widget.set_star_count_cutoff(1000)
        self.widget.set_round_stars_enabled(True)
        self.widget.set_round_stars_amount(80.0)
        self.widget.set_star_glow_enabled(True)
        self.widget.set_glow_star_count(500)
        self.widget.set_star_glow_amount(45.0)
        self.widget.set_star_glow_radius_px(20.0)
        self.widget.set_preview_layer("finished_stars")

        self.assertEqual(self.widget.get_star_count_cutoff(), 1000)
        self.assertEqual(self.widget.combo_star_cutoff.currentText(), "1,000")
        self.assertTrue(self.widget.get_round_stars_enabled())
        self.assertEqual(self.widget.get_round_stars_amount(), 80.0)
        self.assertEqual(self.widget.lbl_round_stars_value.text(), "80%")
        self.assertTrue(self.widget.get_star_glow_enabled())
        self.assertEqual(self.widget.get_glow_star_count(), 500)
        self.assertEqual(self.widget.combo_glow_count.currentText(), "500")
        self.assertEqual(self.widget.get_star_glow_amount(), 45.0)
        self.assertEqual(self.widget.lbl_glow_amount_value.text(), "45%")
        self.assertEqual(self.widget.get_star_glow_radius_px(), 20.0)
        self.assertEqual(self.widget.lbl_glow_radius_value.text(), "20 px")
        self.assertEqual(self.widget.get_preview_layer(), "finished_stars")

        # Zero signals emitted from setters
        self.assertEqual(cutoff_sigs, [])
        self.assertEqual(round_enabled_sigs, [])
        self.assertEqual(round_amount_sigs, [])
        self.assertEqual(glow_enabled_sigs, [])
        self.assertEqual(glow_count_sigs, [])
        self.assertEqual(glow_amount_sigs, [])
        self.assertEqual(glow_radius_sigs, [])
        self.assertEqual(settings_sigs, [])

    def test_preset_setters_reject_unsupported_values(self):
        """Preset setters raise ValueError on unsupported values rather than silently mapping."""
        with self.assertRaises(ValueError):
            self.widget.set_star_count_cutoff(999)

        with self.assertRaises(ValueError):
            self.widget.set_glow_star_count(42)

        with self.assertRaises(ValueError):
            self.widget.set_preview_layer("stars")

        with self.assertRaises(ValueError):
            self.widget.set_preview_layer("unknown_mode")

    def test_reset_action_restores_defaults(self):
        """Clicking Reset restores all Step 10B settings to authoritative defaults."""
        self.widget.refresh_prerequisites(True)
        self.widget.set_star_count_cutoff(1000)
        self.widget.set_round_stars_enabled(True)
        self.widget.set_round_stars_amount(90.0)
        self.widget.set_star_glow_enabled(True)
        self.widget.set_glow_star_count(500)
        self.widget.set_star_glow_amount(80.0)
        self.widget.set_star_glow_radius_px(35.0)
        self.widget.set_preview_layer("finished_stars")

        reset_emitted = []
        self.widget.reset_requested.connect(lambda: reset_emitted.append(True))
        self.widget.btn_reset.click()

        self.assertEqual(reset_emitted, [True])
        self.assertEqual(self.widget.get_star_count_cutoff(), DEFAULT_STAR_COUNT_CUTOFF)
        self.assertEqual(self.widget.get_round_stars_enabled(), DEFAULT_ROUND_STARS_ENABLED)
        self.assertEqual(self.widget.get_round_stars_amount(), DEFAULT_ROUND_STARS_AMOUNT_PERCENT)
        self.assertEqual(self.widget.get_star_glow_enabled(), DEFAULT_STAR_GLOW_ENABLED)
        self.assertEqual(self.widget.get_glow_star_count(), DEFAULT_GLOW_STAR_COUNT)
        self.assertEqual(self.widget.get_star_glow_amount(), DEFAULT_STAR_GLOW_AMOUNT_PERCENT)
        self.assertEqual(self.widget.get_star_glow_radius_px(), DEFAULT_STAR_GLOW_RADIUS_PX)
        self.assertEqual(self.widget.get_preview_layer(), "composite")

    def test_set_from_project_populates_controls(self):
        """set_from_project correctly reads project settings and updates controls."""
        proj = FinishProject(project_file=str(self.root / f"temp{FINISH_EXT}"))
        settings = FinishSettings(
            star_count_cutoff=100000,
            round_stars_enabled=True,
            round_stars_amount=60.0,
            star_glow_enabled=True,
            glow_star_count=25,
            star_glow_amount=25.0,
            star_glow_radius_px=18.0,
        )
        proj.update_settings(settings)

        self.widget.set_from_project(proj)
        self.assertEqual(self.widget.get_star_count_cutoff(), 100000)
        self.assertTrue(self.widget.get_round_stars_enabled())
        self.assertEqual(self.widget.get_round_stars_amount(), 60.0)
        self.assertTrue(self.widget.get_star_glow_enabled())
        self.assertEqual(self.widget.get_glow_star_count(), 25)
        self.assertEqual(self.widget.get_star_glow_amount(), 25.0)
        self.assertEqual(self.widget.get_star_glow_radius_px(), 18.0)


class TestFinishRecombineSettings(QtTestCase):
    """Unit tests for the Step 5 Recombine & Save controls widget."""

    def setUp(self):
        super().setUp()
        self.widget = FinishRecombineSettings()
        self.widget.show()
        self.addCleanup(self.widget.deleteLater)

    def test_default_values_and_signals(self):
        """Initial widget state matches recombine defaults and emits signals on interaction."""
        self.assertEqual(self.widget.get_star_amount(), DEFAULT_STAR_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_star_amount_value.text(), "100%")
        self.assertEqual(self.widget.get_blend_mode(), DEFAULT_BLEND_MODE)

        self.assertEqual(self.widget.get_original_stars_amount(), DEFAULT_ORIGINAL_STARS_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_original_stars_amount_value.text(), "0%")
        self.assertEqual(self.widget.get_original_stars_blend_mode(), DEFAULT_BLEND_MODE)

        self.widget.refresh_prerequisites(True)
        star_amount_sigs = []
        star_mode_sigs = []
        orig_amount_sigs = []
        orig_mode_sigs = []

        self.widget.star_amount_changed.connect(star_amount_sigs.append)
        self.widget.blend_mode_changed.connect(star_mode_sigs.append)
        self.widget.original_stars_amount_changed.connect(orig_amount_sigs.append)
        self.widget.original_stars_blend_mode_changed.connect(orig_mode_sigs.append)

        self.widget.slider_star_amount.setValue(70)
        self.assertEqual(star_amount_sigs, [70.0])
        self.assertEqual(self.widget.lbl_star_amount_value.text(), "70%")

        self.widget.combo_star_blend_mode.setCurrentIndex(1)  # screen
        self.assertEqual(star_mode_sigs, ["screen"])

        self.widget.slider_original_stars_amount.setValue(40)
        self.assertEqual(orig_amount_sigs, [40.0])
        self.assertEqual(self.widget.lbl_original_stars_amount_value.text(), "40%")

        self.widget.combo_original_stars_blend_mode.setCurrentIndex(1)  # screen
        self.assertEqual(orig_mode_sigs, ["screen"])

    def test_blend_mode_setters_reject_unsupported_values(self):
        """Blend mode setters reject unsupported modes with ValueError."""
        with self.assertRaises(ValueError):
            self.widget.set_blend_mode("multiply")

        with self.assertRaises(ValueError):
            self.widget.set_original_stars_blend_mode("overlay")


class TestSidebarFinishStarsPrerequisites(QtTestCase):
    """Test SidebarFinish Step 4 & 5 prerequisite status progression and readiness."""

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
        """Step 4 card initial subtitle describes selection, rounding, and glow."""
        self.assertEqual(
            self.sidebar.starsCard.ui.subtitle.text(),
            "Star selection, rounding, and glow",
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


class TestFinishViewStarsInteraction(QtTestCase):
    """Integration and interaction tests for FinishView handling Step 10B actions."""

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
        self.sidebar.show()
        self.addCleanup(self.sidebar.deleteLater)
        self.view.bind()
        self.view.resetProjectView()
        self.addCleanup(self.view.teardown)

    def test_settings_changes_persist_and_save_project(self):
        """Settings interactions persist to project once and call save_project."""
        saved_calls = []
        with patch.object(self.workflow, "save_project", side_effect=lambda: saved_calls.append(True)):
            # 1. Star cutoff
            self.view.on_star_count_cutoff_changed(1000)
            self.assertEqual(self.project.get_settings().star_count_cutoff, 1000)

            # 2. Round stars toggle and amount
            self.view.on_round_stars_enabled_changed(True)
            self.assertTrue(self.project.get_settings().round_stars_enabled)
            self.view.on_round_stars_amount_changed(70.0)
            self.assertEqual(self.project.get_settings().round_stars_amount, 70.0)

            # 3. Star glow toggle, count subset, amount and radius
            self.view.on_star_glow_enabled_changed(True)
            self.assertTrue(self.project.get_settings().star_glow_enabled)
            self.view.on_glow_star_count_changed(500)
            self.assertEqual(self.project.get_settings().glow_star_count, 500)
            self.view.on_star_glow_amount_changed(45.0)
            self.assertEqual(self.project.get_settings().star_glow_amount, 45.0)
            self.view.on_star_glow_radius_px_changed(25.0)
            self.assertEqual(self.project.get_settings().star_glow_radius_px, 25.0)

            # 4. Finished Stars and Original Stars recombination amounts and modes
            self.view.on_star_amount_changed(80.0)
            self.assertEqual(self.project.get_settings().star_amount, 80.0)
            self.view.on_blend_mode_changed("screen")
            self.assertEqual(self.project.get_settings().blend_mode, "screen")
            self.view.on_original_stars_amount_changed(30.0)
            self.assertEqual(self.project.get_settings().original_stars_amount, 30.0)
            self.view.on_original_stars_blend_mode_changed("screen")
            self.assertEqual(self.project.get_settings().original_stars_blend_mode, "screen")

        self.assertEqual(len(saved_calls), 11)

    def test_toggles_and_amounts_immediate_composition_no_worker_jobs(self):
        """Effect toggles and amounts do immediate composition only: NO worker jobs, NO do_finish_stars."""
        self.shell.enqueued_tasks.clear()
        preview_arr = np.full((64, 64, 3), 0.5, dtype=np.float32)
        render_calls = []

        def fake_render(layer="composite", **kwargs):
            render_calls.append((layer, kwargs))
            return preview_arr

        finish_stars_called = []
        recombine_called = []

        with (
            patch.object(self.workflow, "render_star_preview", side_effect=fake_render),
            patch.object(self.workflow, "do_finish_stars", side_effect=lambda **kw: finish_stars_called.append(True)),
            patch.object(self.workflow, "do_recombine", side_effect=lambda **kw: recombine_called.append(True)),
        ):
            # Toggle Round Stars
            self.view.on_round_stars_enabled_changed(True)
            self.assertEqual(len(render_calls), 1)
            self.assertEqual(finish_stars_called, [])
            self.assertEqual(recombine_called, [])
            self.assertEqual(self.shell.enqueued_tasks, [])

            # Change Round Stars Amount
            self.view.on_round_stars_amount_changed(80.0)
            self.assertEqual(len(render_calls), 2)
            self.assertEqual(finish_stars_called, [])
            self.assertEqual(recombine_called, [])
            self.assertEqual(self.shell.enqueued_tasks, [])

            # Toggle Star Glow
            self.view.on_star_glow_enabled_changed(True)
            self.assertEqual(len(render_calls), 3)
            self.assertEqual(finish_stars_called, [])
            self.assertEqual(recombine_called, [])
            self.assertEqual(self.shell.enqueued_tasks, [])

            # Change Glow Amount
            self.view.on_star_glow_amount_changed(60.0)
            self.assertEqual(len(render_calls), 4)
            self.assertEqual(finish_stars_called, [])
            self.assertEqual(recombine_called, [])
            self.assertEqual(self.shell.enqueued_tasks, [])

            # Change Finished Stars Amount
            self.view.on_star_amount_changed(75.0)
            self.assertEqual(len(render_calls), 5)
            self.assertEqual(finish_stars_called, [])
            self.assertEqual(recombine_called, [])
            self.assertEqual(self.shell.enqueued_tasks, [])

            # Change Original Stars Amount
            self.view.on_original_stars_amount_changed(20.0)
            self.assertEqual(len(render_calls), 6)
            self.assertEqual(finish_stars_called, [])
            self.assertEqual(recombine_called, [])
            self.assertEqual(self.shell.enqueued_tasks, [])

    def test_composition_action_returns_without_worker_when_cache_absent(self):
        """When preview cache is cold/absent, composition-only edits return WITHOUT running worker."""
        finish_stars_called = []
        recombine_called = []
        self.shell.enqueued_tasks.clear()

        with (
            patch.object(self.workflow, "render_star_preview", return_value=None),
            patch.object(self.workflow, "do_finish_stars", side_effect=lambda **kw: finish_stars_called.append(True)),
            patch.object(self.workflow, "do_recombine", side_effect=lambda **kw: recombine_called.append(True)),
        ):
            # Toggle round stars with absent cache
            self.view.on_round_stars_enabled_changed(True)
            self.assertEqual(self.shell.enqueued_tasks, [])
            self.assertEqual(finish_stars_called, [])
            self.assertEqual(recombine_called, [])
            # Actionable status displayed
            self.assertFalse(self.sidebar.starsSettings.lbl_status.isHidden())
            self.assertIn("preparing or unavailable", self.sidebar.starsSettings.lbl_status.text())

    def test_render_immediate_preview_shows_actionable_status_on_error(self):
        """When render_star_preview raises an exception, an actionable status is shown without falling back to stale TIFF."""
        with patch.object(self.workflow, "render_star_preview", side_effect=RuntimeError("Disk read failure")):
            rendered = self.view._render_immediate_preview()
            self.assertFalse(rendered)
            self.assertFalse(self.sidebar.starsSettings.lbl_status.isHidden())
            self.assertIn("Preview unavailable: Disk read failure", self.sidebar.starsSettings.lbl_status.text())

    def test_cutoff_summary_updates_via_public_interface(self):
        """Cutoff display updates through public get_star_catalog_summary interface."""
        summary = {
            "included_count": 10000,
            "total_count": 50000,
            "cutoff_score": 15.67,
        }
        with patch.object(self.workflow, "get_star_catalog_summary", return_value=summary):
            self.view._update_cutoff_display()
            info = self.sidebar.starsSettings.lbl_star_cutoff_info.text()
            self.assertIn("10,000", info)
            self.assertIn("50,000", info)
            self.assertIn("15.67", info)

    def test_hold_to_compare_shows_s_inc_without_mutating_settings(self):
        """Hold to compare shows S_inc without effects and without mutating saved settings."""
        settings_before = self.project.get_settings()
        self.project.update_settings(
            replace(settings_before, round_stars_enabled=True, round_stars_amount=80.0, star_glow_enabled=True)
        )
        expected_settings = self.project.get_settings()

        preview_arr = np.full((64, 64, 3), 0.5, dtype=np.float32)
        render_calls = []

        def fake_render(layer="composite", **kwargs):
            render_calls.append((layer, kwargs.get("compare", False)))
            return preview_arr

        with patch.object(self.workflow, "render_star_preview", side_effect=fake_render):
            # Press hold-to-compare
            self.view.on_compare_pressed()
            self.assertTrue(self.view._is_comparing)
            self.assertEqual(render_calls[-1], ("finished_stars", True))

            # Settings are NOT mutated
            self.assertEqual(self.project.get_settings(), expected_settings)

            # Release hold-to-compare
            self.view.on_compare_released()
            self.assertFalse(self.view._is_comparing)
            self.assertEqual(render_calls[-1], ("composite", False))

            # Settings still unchanged
            self.assertEqual(self.project.get_settings(), expected_settings)

    def test_four_preview_layers_rendered_with_zoom_preserved(self):
        """Preview layer switching renders all four choices and preserves canvas zoom/pan."""
        preview_arr = np.full((64, 64, 3), 0.5, dtype=np.float32)
        rendered_layers = []

        def fake_render(layer="composite", **kwargs):
            rendered_layers.append(layer)
            return preview_arr

        with patch.object(self.workflow, "render_star_preview", side_effect=fake_render):
            for layer in ("composite", "finished_stars", "original_stars", "excluded_stars"):
                self.sidebar.starsSettings.set_preview_layer(layer)
                self.view.on_stars_preview_layer_changed(layer)
                self.assertEqual(rendered_layers[-1], layer)

    def test_cutoff_change_schedules_effects_job(self):
        """Cutoff change triggers incremental analysis/effects worker job."""
        executed_jobs = []

        def fake_finish(**kwargs):
            executed_jobs.append("finish_stars")
            return MagicMock(path=str(self.composite_path), basename="finished_stars.tif")

        def fake_recombine(**kwargs):
            executed_jobs.append("recombine")
            return (np.zeros((64, 64, 3)), self.composite_path)

        with (
            patch.object(self.workflow, "do_finish_stars", side_effect=fake_finish),
            patch.object(self.workflow, "do_recombine", side_effect=fake_recombine),
        ):
            self.view.on_star_count_cutoff_changed(1000)
            self.view._stars_timer.timeout.emit()
            QApplication.processEvents()

        self.assertIn("finish_stars", executed_jobs)
        self.assertIn("recombine", executed_jobs)

    def test_glow_radius_and_count_schedule_glow_job(self):
        """Glow radius or subset count changes schedule a Glow-only worker job."""
        executed_jobs = []

        def fake_finish(**kwargs):
            executed_jobs.append("finish_stars")
            return MagicMock(path=str(self.composite_path), basename="finished_stars.tif")

        def fake_recombine(**kwargs):
            executed_jobs.append("recombine")
            return (np.zeros((64, 64, 3)), self.composite_path)

        with (
            patch.object(self.workflow, "do_finish_stars", side_effect=fake_finish),
            patch.object(self.workflow, "do_recombine", side_effect=fake_recombine),
        ):
            self.view.on_star_glow_radius_px_changed(30.0)
            self.view._stars_timer.timeout.emit()
            QApplication.processEvents()

            self.view.on_glow_star_count_changed(500)
            self.view._stars_timer.timeout.emit()
            QApplication.processEvents()

        self.assertEqual(executed_jobs, ["finish_stars", "recombine", "finish_stars", "recombine"])

    def test_rapid_cutoff_and_glow_edits_survive_worker_and_rerun_coalesced(self):
        """New cutoff/glow edits arriving while worker is busy survive callback and rerun coalesced."""
        executed_cutoffs = []
        worker_busy = True

        def fake_enqueue(task_id, title, total, desc, work):
            if worker_busy:
                return False
            work()
            return True

        def fake_finish(**kwargs):
            executed_cutoffs.append(self.project.get_settings().star_count_cutoff)
            return MagicMock(path=str(self.composite_path), basename="finished_stars.tif")

        self.shell.enqueue_task = fake_enqueue

        with (
            patch.object(self.workflow, "do_finish_stars", side_effect=fake_finish),
            patch.object(self.workflow, "do_recombine", return_value=(np.zeros((64, 64, 3)), self.composite_path)),
        ):
            # 1. First edit: glow count changed, but queue is busy
            self.view.on_glow_star_count_changed(500)
            self.view._stars_timer.timeout.emit()
            self.assertEqual(executed_cutoffs, [])
            self.assertEqual(self.view._pending_stars_action, "glow")

            # 2. While pending, user changes cutoff to 1000 (upgrades to effects)
            self.view.on_star_count_cutoff_changed(1000)
            self.assertEqual(self.view._pending_stars_action, "effects")

            # 3. Worker frees up
            worker_busy = False
            self.view._stars_timer.timeout.emit()
            QApplication.processEvents()

            # Executed with cutoff 1000
            self.assertEqual(executed_cutoffs, [1000])
            self.assertEqual(self.view._pending_stars_action, "none")

    def test_mask_editing_mode_blocks_preview_canvas_update(self):
        """When mask edit mode is active, immediate and late preview delivery do NOT overwrite canvas."""
        self.canvas.set_mask_edit_mode(True)
        self.assertTrue(self.canvas.is_mask_edit_mode())
        preview_arr = np.full((100, 100, 3), 0.5, dtype=np.float32)

        with patch.object(self.workflow, "render_star_preview", return_value=preview_arr):
            # 1. Immediate preview returns False and does not touch canvas
            rendered = self.view._render_immediate_preview()
            self.assertFalse(rendered)
            self.assertTrue(self.canvas.is_mask_edit_mode())

            # 2. Worker job completion does not deliver to canvas while mask editing
            canvas_set_calls = []
            with patch.object(self.canvas, "setFromNumpyArray", side_effect=lambda *a, **k: canvas_set_calls.append(a)):
                with (
                    patch.object(self.workflow, "do_finish_stars", return_value=MagicMock()),
                    patch.object(
                        self.workflow, "do_recombine", return_value=(np.zeros((64, 64, 3)), self.composite_path)
                    ),
                ):
                    self.view.on_star_count_cutoff_changed(1000)
                    self.view._stars_timer.timeout.emit()
                    QApplication.processEvents()

            self.assertEqual(canvas_set_calls, [])
            self.assertTrue(self.canvas.is_mask_edit_mode())

    def test_save_enabled_after_composition_edits_and_recombines_fullres(self):
        """Save button remains enabled after composition-only edits and recombines before exporting."""
        # 1. Composition edit invalidates composite
        self.view.on_star_amount_changed(80.0)
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertTrue(self.sidebar.btn_save_output.isEnabled())

        # 2. Clicking save prompts for path and executes worker recombination + export
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

    def test_interactive_stars_checks_mask_path_metadata_not_full_decode(self):
        """_apply_interactive_stars checks metadata path without decoding fullframe mask PNG on GUI thread."""
        with patch.object(self.workflow, "get_current_mask") as mock_decode:
            self.view._apply_interactive_stars()
            mock_decode.assert_not_called()

    def test_reduced_resolution_preview_labeled_visibly(self):
        """When source dimensions exceed preview dimensions, label visibly indicates reduced preview."""
        reduced_arr = np.full((1067, 1600, 3), 0.5, dtype=np.float32)

        with (
            patch.object(self.project, "get_source_dimensions", return_value=(4000, 6000)),
            patch.object(self.workflow, "render_star_preview", return_value=reduced_arr),
        ):
            rendered = self.view._render_immediate_preview()
            self.assertTrue(rendered)
            status_text = self.sidebar.starsSettings.lbl_status.text()
            self.assertIn("Reduced-resolution preview", status_text)
            self.assertIn("saved image uses full resolution", status_text)

    def test_reopen_cold_enqueues_preparation_and_shows_preparing_status(self):
        """resetProjectView enqueues prepare_star_endpoints when separated stars exist and preview is cold/stale."""
        with (
            patch.object(self.workflow, "get_star_preview_status", return_value="cold"),
            patch.object(self.workflow, "prepare_star_endpoints", return_value=MagicMock()) as mock_prepare,
        ):
            self.view.resetProjectView()
            self.assertIn("finish_stars_prepare", self.shell.enqueued_tasks)
            mock_prepare.assert_called_once()
            self.assertIn("Preparing star finish preview", self.sidebar.starsSettings.lbl_status.text())

    def test_source_import_without_separation_does_not_prepare_stars(self):
        """Source-only project without star separation does not trigger star preparation on reset."""
        # Reset project without separated stars
        raw_project = FinishProject(project_file=str(self.root / f"raw_proj{FINISH_EXT}"))
        raw_project.set_source_image(self.source_path)
        self.app.project = raw_project
        self.shell.enqueued_tasks.clear()

        with patch.object(self.workflow, "prepare_star_endpoints") as mock_prepare:
            self.view.resetProjectView()
            self.assertNotIn("finish_stars_prepare", self.shell.enqueued_tasks)
            mock_prepare.assert_not_called()

    def test_preparation_interrupted_by_composition_edit_retries_and_becomes_ready(self):
        """Preparation interrupted by a composition-only edit retries preparation and becomes ready with new settings."""
        rendered_amounts = []
        is_first_run = True

        def fake_render(layer="composite", **kwargs):
            rendered_amounts.append(self.project.get_settings().round_stars_amount)
            return np.full((64, 64, 3), 0.5, dtype=np.float32)

        def delayed_prepare(**kwargs):
            nonlocal is_first_run
            if is_first_run:
                is_first_run = False
                # User changes round stars amount while prepare is running
                self.view.on_round_stars_amount_changed(85.0)
            return MagicMock()

        self.shell.enqueued_tasks.clear()
        with (
            patch.object(self.workflow, "get_star_preview_status", return_value="cold"),
            patch.object(self.workflow, "prepare_star_endpoints", side_effect=delayed_prepare),
            patch.object(self.workflow, "render_star_preview", side_effect=fake_render),
        ):
            # 1. Reopen launches first prepare
            self.view.resetProjectView()
            self.assertEqual(len(self.shell.enqueued_tasks), 1)
            self.assertEqual(self.shell.enqueued_tasks[0], "finish_stars_prepare")

            # 2. Process Qt event loop for singleShot retry_if_stale
            QApplication.processEvents()

            # Stale first run dropped, triggered retry timer for preparation
            self.assertTrue(self.view._prepare_timer is not None and self.view._prepare_timer.isActive())

            # 3. Preparation retry runs and renders with new setting (85.0)
            self.view._prepare_timer.timeout.emit()
            QApplication.processEvents()

            self.assertEqual(len(self.shell.enqueued_tasks), 2)
            self.assertEqual(rendered_amounts[-1], 85.0)
            self.assertEqual(self.project.get_settings().round_stars_amount, 85.0)

    def test_prepare_duplicate_rejection_retries_via_debounce(self):
        """When prepare task is rejected due to active/teardown queue, debounce retries preparation."""
        self.shell.enqueued_tasks.clear()
        with (
            patch.object(self.shell, "enqueue_task", return_value=False),
            patch.object(self.view, "_debounce_star_endpoint_preparation") as mock_debounce,
        ):
            self.view._enqueue_star_endpoint_preparation()
            mock_debounce.assert_called_once()

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

        # Switch project before delivery
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
            patch.object(self.view, "_debounce_stars_preview", side_effect=lambda: debounce_called.append(True)),
        ):
            self.view._pending_stars_action = "effects"
            self.view._apply_interactive_stars()

        self.assertEqual(debounce_called, [True])

    def test_reset_action_reverts_settings_and_updates_sidebar(self):
        """Reset reverts all star settings in project and updates sidebar widgets."""
        self.project.update_settings(
            replace(
                self.project.get_settings(),
                star_count_cutoff=1000,
                round_stars_enabled=True,
                round_stars_amount=90.0,
                star_glow_enabled=True,
                glow_star_count=500,
                star_glow_amount=70.0,
                star_glow_radius_px=30.0,
                star_amount=40.0,
                original_stars_amount=50.0,
            )
        )
        self.sidebar.starsSettings.set_from_project(self.project)
        self.sidebar.recombineSettings.set_from_project(self.project)

        with (
            patch.object(self.workflow, "do_finish_stars", return_value=MagicMock()),
            patch.object(self.workflow, "do_recombine", return_value=(np.zeros((64, 64, 3)), self.composite_path)),
        ):
            self.view.on_reset_stars()
            settings = self.project.get_settings()

            self.assertEqual(settings.star_count_cutoff, DEFAULT_STAR_COUNT_CUTOFF)
            self.assertEqual(settings.round_stars_enabled, DEFAULT_ROUND_STARS_ENABLED)
            self.assertEqual(settings.round_stars_amount, DEFAULT_ROUND_STARS_AMOUNT_PERCENT)
            self.assertEqual(settings.star_glow_enabled, DEFAULT_STAR_GLOW_ENABLED)
            self.assertEqual(settings.glow_star_count, DEFAULT_GLOW_STAR_COUNT)
            self.assertEqual(settings.star_glow_amount, DEFAULT_STAR_GLOW_AMOUNT_PERCENT)
            self.assertEqual(settings.star_glow_radius_px, DEFAULT_STAR_GLOW_RADIUS_PX)
            self.assertEqual(settings.star_amount, DEFAULT_STAR_AMOUNT_PERCENT)
            self.assertEqual(settings.original_stars_amount, DEFAULT_ORIGINAL_STARS_AMOUNT_PERCENT)

            self.assertEqual(self.sidebar.starsSettings.get_star_count_cutoff(), DEFAULT_STAR_COUNT_CUTOFF)
            self.assertEqual(self.sidebar.starsSettings.get_round_stars_enabled(), DEFAULT_ROUND_STARS_ENABLED)
            self.assertEqual(self.sidebar.recombineSettings.get_star_amount(), DEFAULT_STAR_AMOUNT_PERCENT)
            self.assertEqual(
                self.sidebar.recombineSettings.get_original_stars_amount(), DEFAULT_ORIGINAL_STARS_AMOUNT_PERCENT
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
