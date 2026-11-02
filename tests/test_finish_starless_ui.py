"""Focused UI unit and interaction tests for Finish Starless controls (Step 8)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QObject
from startrails.lib.finish.defaults import (
    DEFAULT_DENOISE_SCOPE,
    DEFAULT_DENOISE_STRENGTH_PERCENT,
    DEFAULT_DETAIL_AMOUNT_PERCENT,
    DEFAULT_STRUCTURE_AMOUNT_PERCENT,
    FINISH_EXT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    SCOPE_SKY_ONLY,
    SCOPE_WHOLE_IMAGE,
)
from startrails.lib.image_io import imwrite
from startrails.lib.project_finish import FinishProject
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.sidebar_finish import SidebarFinish
from startrails.ui.steps_starless import FinishStarlessSettings
from startrails.ui.views.finish import FinishView
from startrails.workflow.finish import FinishWorkflow
from support import QtTestCase


class TestFinishStarlessSettings(QtTestCase):
    """Unit tests for the Step 3 FinishStarlessSettings card body widget."""

    def setUp(self):
        super().setUp()
        self.widget = FinishStarlessSettings()
        self.widget.show()
        self.addCleanup(self.widget.deleteLater)

    def test_default_control_values(self):
        """Initial widget state matches authoritative defaults."""
        self.assertEqual(self.widget.get_strength(), DEFAULT_DENOISE_STRENGTH_PERCENT)
        self.assertEqual(self.widget.lbl_strength_value.text(), f"{int(DEFAULT_DENOISE_STRENGTH_PERCENT)}%")
        self.assertEqual(self.widget.get_scope(), DEFAULT_DENOISE_SCOPE)
        self.assertTrue(self.widget.radio_sky_only.isChecked())
        self.assertFalse(self.widget.radio_whole_image.isChecked())
        self.assertEqual(self.widget.get_structure(), DEFAULT_STRUCTURE_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_structure_value.text(), f"{int(DEFAULT_STRUCTURE_AMOUNT_PERCENT)}%")
        self.assertEqual(self.widget.slider_structure.value(), 0)
        self.assertEqual(self.widget.get_detail(), DEFAULT_DETAIL_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_detail_value.text(), f"{int(DEFAULT_DETAIL_AMOUNT_PERCENT)}%")
        self.assertEqual(self.widget.slider_detail.value(), 0)
        self.assertFalse(self.widget.unconfigured_box.isHidden())
        self.assertTrue(self.widget.configured_box.isHidden())
        self.assertFalse(self.widget.btn_run_denoise.isEnabled())

    def test_strength_slider_interaction(self):
        """Dragging strength slider emits strength_changed and updates value label."""
        signals = []
        self.widget.strength_changed.connect(signals.append)

        self.widget.slider_strength.setValue(75)
        self.assertEqual(self.widget.lbl_strength_value.text(), "75%")
        self.assertEqual(self.widget.get_strength(), 75.0)
        self.assertEqual(signals, [75.0])

    def test_structure_slider_interaction(self):
        """Dragging structure slider emits structure_amount_changed, structure_changed, and settings_changed."""
        amount_signals = []
        alias_signals = []
        settings_signals = []
        self.widget.structure_amount_changed.connect(amount_signals.append)
        self.widget.structure_changed.connect(alias_signals.append)
        self.widget.settings_changed.connect(lambda: settings_signals.append(True))

        self.widget.slider_structure.setValue(45)
        self.assertEqual(self.widget.lbl_structure_value.text(), "45%")
        self.assertEqual(self.widget.get_structure(), 45.0)
        self.assertEqual(self.widget.get_structure_amount(), 45.0)
        self.assertEqual(amount_signals, [45.0])
        self.assertEqual(alias_signals, [45.0])
        self.assertEqual(settings_signals, [True])

    def test_detail_slider_interaction(self):
        """Dragging detail slider emits detail_amount_changed, detail_changed, and settings_changed."""
        amount_signals = []
        alias_signals = []
        settings_signals = []
        self.widget.detail_amount_changed.connect(amount_signals.append)
        self.widget.detail_changed.connect(alias_signals.append)
        self.widget.settings_changed.connect(lambda: settings_signals.append(True))

        self.widget.slider_detail.setValue(60)
        self.assertEqual(self.widget.lbl_detail_value.text(), "60%")
        self.assertEqual(self.widget.get_detail(), 60.0)
        self.assertEqual(self.widget.get_detail_amount(), 60.0)
        self.assertEqual(amount_signals, [60.0])
        self.assertEqual(alias_signals, [60.0])
        self.assertEqual(settings_signals, [True])

    def test_scope_radio_interaction(self):
        """Toggling scope radios updates state and emits scope_changed."""
        scopes = []
        self.widget.scope_changed.connect(scopes.append)

        self.widget.radio_whole_image.setChecked(True)
        self.assertEqual(self.widget.get_scope(), SCOPE_WHOLE_IMAGE)
        self.assertEqual(scopes, [SCOPE_WHOLE_IMAGE])

        self.widget.radio_sky_only.setChecked(True)
        self.assertEqual(self.widget.get_scope(), SCOPE_SKY_ONLY)
        self.assertEqual(scopes, [SCOPE_WHOLE_IMAGE, SCOPE_SKY_ONLY])

    def test_button_signals(self):
        """Action buttons emit explicit requested signals."""
        run_called = []
        reset_called = []
        self.widget.run_denoise_requested.connect(lambda: run_called.append(True))
        self.widget.reset_requested.connect(lambda: reset_called.append(True))

        self.widget.btn_run_denoise.setEnabled(True)
        self.widget.btn_run_denoise.click()
        self.widget.btn_reset.click()
        self.assertEqual(run_called, [True])
        self.assertEqual(reset_called, [True])

    def test_programmatic_setters_block_signals(self):
        """set_strength, set_scope, set_structure, and set_detail do not fire signals."""
        strength_sig = []
        scope_sig = []
        structure_sig = []
        detail_sig = []
        settings_sig = []
        self.widget.strength_changed.connect(strength_sig.append)
        self.widget.scope_changed.connect(scope_sig.append)
        self.widget.structure_changed.connect(structure_sig.append)
        self.widget.detail_changed.connect(detail_sig.append)
        self.widget.settings_changed.connect(lambda: settings_sig.append(True))

        self.widget.set_strength(80.0)
        self.widget.set_scope(SCOPE_WHOLE_IMAGE)
        self.widget.set_structure(35.0)
        self.widget.set_detail(75.0)

        self.assertEqual(self.widget.get_strength(), 80.0)
        self.assertEqual(self.widget.get_scope(), SCOPE_WHOLE_IMAGE)
        self.assertEqual(self.widget.get_structure(), 35.0)
        self.assertEqual(self.widget.get_structure_amount(), 35.0)
        self.assertEqual(self.widget.lbl_structure_value.text(), "35%")
        self.assertEqual(self.widget.get_detail(), 75.0)
        self.assertEqual(self.widget.get_detail_amount(), 75.0)
        self.assertEqual(self.widget.lbl_detail_value.text(), "75%")
        self.assertEqual(strength_sig, [])
        self.assertEqual(scope_sig, [])
        self.assertEqual(structure_sig, [])
        self.assertEqual(detail_sig, [])
        self.assertEqual(settings_sig, [])

        # Clamping behavior
        self.widget.set_structure_amount(-10.0)
        self.assertEqual(self.widget.get_structure(), 0.0)
        self.assertEqual(self.widget.lbl_structure_value.text(), "0%")
        self.widget.set_structure_amount(150.0)
        self.assertEqual(self.widget.get_structure(), 100.0)
        self.assertEqual(self.widget.lbl_structure_value.text(), "100%")

        self.widget.set_detail_amount(-20.0)
        self.assertEqual(self.widget.get_detail(), 0.0)
        self.assertEqual(self.widget.lbl_detail_value.text(), "0%")
        self.widget.set_detail_amount(120.0)
        self.assertEqual(self.widget.get_detail(), 100.0)
        self.assertEqual(self.widget.lbl_detail_value.text(), "100%")

    def test_reset_action_restores_all_defaults(self):
        """Clicking reset restores strength, scope, structure, and detail to defaults."""
        self.widget.set_strength(85.0)
        self.widget.set_scope(SCOPE_WHOLE_IMAGE)
        self.widget.set_structure(50.0)
        self.widget.set_detail(70.0)

        reset_emitted = []
        self.widget.reset_requested.connect(lambda: reset_emitted.append(True))
        self.widget.btn_reset.click()

        self.assertEqual(self.widget.get_strength(), DEFAULT_DENOISE_STRENGTH_PERCENT)
        self.assertEqual(self.widget.get_scope(), DEFAULT_DENOISE_SCOPE)
        self.assertEqual(self.widget.get_structure(), DEFAULT_STRUCTURE_AMOUNT_PERCENT)
        self.assertEqual(self.widget.get_detail(), DEFAULT_DETAIL_AMOUNT_PERCENT)
        self.assertEqual(self.widget.lbl_structure_value.text(), f"{int(DEFAULT_STRUCTURE_AMOUNT_PERCENT)}%")
        self.assertEqual(self.widget.lbl_detail_value.text(), f"{int(DEFAULT_DETAIL_AMOUNT_PERCENT)}%")
        self.assertEqual(reset_emitted, [True])

    def test_set_from_project_restores_structure_and_detail(self):
        """set_from_project updates structure and detail controls from project settings."""
        proj = FinishProject(project_file=str(self.root / f"temp{FINISH_EXT}"))
        settings = proj.get_settings()
        from dataclasses import replace

        proj.update_settings(replace(settings, structure_amount=33.0, detail_amount=66.0))

        self.widget.set_from_project(proj)
        self.assertEqual(self.widget.get_structure(), 33.0)
        self.assertEqual(self.widget.get_detail(), 66.0)
        self.assertEqual(self.widget.lbl_structure_value.text(), "33%")
        self.assertEqual(self.widget.lbl_detail_value.text(), "66%")

    def test_refresh_status_verified_cuda(self):
        """Verified CUDA policy displays provider info badge and enables Run Denoise."""
        status = {
            "policy": {"provider": "CUDAExecutionProvider", "variant": "cu133", "verified": True},
            "model_ready": True,
            "setup_error": None,
        }
        self.widget.refresh_status(status, has_prerequisites=True, has_endpoint=False)

        self.assertTrue(self.widget.unconfigured_box.isHidden())
        self.assertFalse(self.widget.configured_box.isHidden())
        self.assertIn("CUDA (GPU)", self.widget.lbl_provider_info.text())
        self.assertTrue(self.widget.btn_run_denoise.isEnabled())

    def test_refresh_status_verified_cpu(self):
        """Verified CPU policy displays CPU badge and enables Run Denoise."""
        status = {
            "policy": {"provider": "CPUExecutionProvider", "variant": "cpu", "verified": True},
            "model_ready": True,
            "setup_error": None,
        }
        self.widget.refresh_status(status, has_prerequisites=True, has_endpoint=False)

        self.assertTrue(self.widget.unconfigured_box.isHidden())
        self.assertFalse(self.widget.configured_box.isHidden())
        self.assertIn("CPU", self.widget.lbl_provider_info.text())
        self.assertTrue(self.widget.btn_run_denoise.isEnabled())

    def test_refresh_status_displays_fallback_and_configured_provider(self):
        """When execution_provider and fallback_reason are present, UI displays actual provider, fallback, and configured."""
        status = {
            "policy": {"provider": "CUDAExecutionProvider", "variant": "cu133", "verified": True},
            "model_ready": True,
            "setup_error": None,
            "execution_provider": "CPUExecutionProvider",
            "fallback_reason": "CUDA out of memory",
        }
        self.widget.refresh_status(status, has_prerequisites=True, has_endpoint=False)

        info_text = self.widget.lbl_provider_info.text()
        self.assertIn("CPU", info_text)
        self.assertIn("CUDA (GPU)", info_text)
        self.assertIn("CUDA out of memory", info_text)
        self.assertTrue(self.widget.unconfigured_box.isHidden())
        self.assertFalse(self.widget.configured_box.isHidden())
        self.assertTrue(self.widget.btn_run_denoise.isEnabled())

    def test_refresh_status_missing_model_disables_positive_strength_only(self):
        """Missing GraXpert model shows warning and disables positive strength, but 0% is usable."""
        status = {
            "policy": None,
            "model_ready": False,
            "setup_error": "Model file not found",
        }
        # Strength > 0 and model missing -> button disabled
        self.widget.set_strength(50.0)
        self.widget.refresh_status(status, has_prerequisites=True, has_endpoint=False)
        self.assertFalse(self.widget.unconfigured_box.isHidden())
        self.assertTrue(self.widget.configured_box.isHidden())
        self.assertFalse(self.widget.btn_run_denoise.isEnabled())

        # Zero-strength identity is safe even without GraXpert
        self.widget.set_strength(0.0)
        self.widget.refresh_status(status, has_prerequisites=True, has_endpoint=False)
        self.assertTrue(self.widget.btn_run_denoise.isEnabled())

    def test_cached_endpoint_enables_run_denoise_even_if_model_missing(self):
        """When a cached endpoint exists, Run Denoise is enabled and surfaces cached blending."""
        status = {
            "policy": None,
            "model_ready": False,
            "setup_error": "Model file missing",
        }
        self.widget.set_strength(60.0)
        self.widget.refresh_status(status, has_prerequisites=True, has_endpoint=True)

        self.assertFalse(self.widget.unconfigured_box.isHidden())
        self.assertIn("Cached denoise endpoint is available for blending", self.widget.lbl_unconf_msg.text())
        self.assertTrue(self.widget.btn_run_denoise.isEnabled())

    def test_refresh_status_missing_prerequisites_disables_button(self):
        """Missing prerequisites disables Run Denoise and adjustment sliders regardless of readiness."""
        status = {
            "policy": {"provider": "CUDAExecutionProvider", "verified": True},
            "model_ready": True,
            "setup_error": None,
        }
        self.widget.refresh_status(status, has_prerequisites=False, has_endpoint=False)
        self.assertFalse(self.widget.btn_run_denoise.isEnabled())
        self.assertFalse(self.widget.slider_strength.isEnabled())
        self.assertFalse(self.widget.radio_sky_only.isEnabled())
        self.assertFalse(self.widget.slider_structure.isEnabled())
        self.assertFalse(self.widget.slider_detail.isEnabled())

        # When prerequisites are present, sliders become enabled
        self.widget.refresh_status(status, has_prerequisites=True, has_endpoint=False)
        self.assertTrue(self.widget.slider_structure.isEnabled())
        self.assertTrue(self.widget.slider_detail.isEnabled())
        self.assertTrue(self.widget.slider_strength.isEnabled())


class TestSidebarFinishPrerequisites(QtTestCase):
    """Test SidebarFinish step 3 prerequisite status progression."""

    def setUp(self):
        super().setUp()
        self.proj_path = self.root / f"test_sidebar{FINISH_EXT}"
        self.project = FinishProject(project_file=str(self.proj_path))
        self.app = self.make_app(self.project)
        self.workflow = FinishWorkflow(self.app)
        self.app.workflow = self.workflow
        self.sidebar = SidebarFinish(app=self.app)
        self.sidebar.show()
        self.addCleanup(self.sidebar.deleteLater)

    def test_step3_card_initial_subtitle(self):
        """Initial starlessCard subtitle reflects AI denoise with Structure and Detail controls."""
        fresh_sidebar = SidebarFinish(app=self.app)
        self.addCleanup(fresh_sidebar.deleteLater)
        self.assertEqual(
            fresh_sidebar.starlessCard.ui.subtitle.text(),
            "AI denoise with Structure and Detail controls",
        )

    def test_step3_card_prerequisite_states(self):
        """Step 3 transitions: locked -> GraXpert setup required / ready -> done."""
        # 1. No source image -> locked
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.starlessCard.status, "locked")
        self.assertIn("Source image required", self.sidebar.starlessCard.ui.subtitle.text())

        # 2. Add source, no mask -> locked
        src_path = self.root / "src.tif"
        imwrite(src_path, np.full((512, 512, 3), 30000, dtype=np.uint16), bit_depth=16)
        self.project.set_source_image(src_path)
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.starlessCard.status, "locked")

        # 3. Add mask, no separated starless -> locked
        mask_path = self.root / "mask.png"
        imwrite(mask_path, np.full((512, 512), 255, dtype=np.uint8), bit_depth=8)
        self.project.record_artifact(ROLE_SKY_MASK, mask_path)
        self.sidebar.update_prerequisites(self.project)
        self.assertEqual(self.sidebar.starlessCard.status, "locked")
        self.assertIn("Separated starless required", self.sidebar.starlessCard.ui.subtitle.text())

        # 4. Add separated layers, GraXpert not verified -> setup required
        starless_p = self.root / "starless.tif"
        stars_p = self.root / "stars.tif"
        imwrite(starless_p, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        imwrite(stars_p, np.full((512, 512, 3), 10000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_SEPARATED_STARLESS, starless_p)
        self.project.record_artifact(ROLE_SEPARATED_STARS, stars_p)

        with patch.object(
            FinishWorkflow,
            "get_graxpert_status",
            return_value={"policy": None, "model_ready": False, "setup_error": "missing"},
        ):
            self.sidebar.update_prerequisites(self.project)
            self.assertEqual(self.sidebar.starlessCard.status, "ready")
            self.assertEqual(self.sidebar.starlessCard.ui.subtitle.text(), "GraXpert setup required")

        # 5. Add verified GraXpert -> ready
        with patch.object(
            FinishWorkflow,
            "get_graxpert_status",
            return_value={
                "policy": {"provider": "CUDAExecutionProvider", "verified": True},
                "model_ready": True,
                "setup_error": None,
            },
        ):
            self.sidebar.update_prerequisites(self.project)
            self.assertEqual(self.sidebar.starlessCard.status, "ready")
            self.assertEqual(self.sidebar.starlessCard.ui.subtitle.text(), "Ready to finish starless")

        # 6. The inference cache alone does not finish the current settings.
        denoised_p = self.root / "denoised.tif"
        imwrite(denoised_p, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, denoised_p)
        with patch.object(
            FinishWorkflow,
            "get_graxpert_status",
            return_value={
                "policy": {"provider": "CUDAExecutionProvider", "verified": True},
                "model_ready": True,
                "setup_error": None,
            },
        ):
            self.sidebar.update_prerequisites(self.project)
            self.assertEqual(self.sidebar.starlessCard.status, "ready")
            self.assertEqual(self.sidebar.starlessCard.ui.subtitle.text(), "Ready to update starless")

            finished_p = self.root / "finished.tif"
            imwrite(finished_p, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
            self.project.record_artifact(ROLE_FINISHED_STARLESS, finished_p)
            self.sidebar.update_prerequisites(self.project)
            self.assertEqual(self.sidebar.starlessCard.status, "done")
            self.assertEqual(self.sidebar.starlessCard.ui.subtitle.text(), "Starless finished")

            self.project.update_settings(replace(self.project.get_settings(), structure_amount=25.0))
            self.sidebar.update_prerequisites(self.project)
            self.assertIsNotNone(self.project.current_artifact_path(ROLE_DENOISED_STARLESS))
            self.assertEqual(self.sidebar.starlessCard.status, "ready")
            self.assertEqual(self.sidebar.starlessCard.ui.subtitle.text(), "Ready to update starless")


class TestFinishViewStarlessInteraction(QtTestCase):
    """Integration and interaction tests for FinishView handling Finish Starless actions."""

    def setUp(self):
        super().setUp()
        self.proj_path = self.root / f"test_view{FINISH_EXT}"
        self.project = FinishProject(project_file=str(self.proj_path))
        self.app = self.make_app(self.project)
        self.workflow = FinishWorkflow(self.app)
        self.app.workflow = self.workflow

        # Create source image & valid mask
        self.source_path = self.root / "source.tif"
        imwrite(self.source_path, np.full((512, 512, 3), 30000, dtype=np.uint16), bit_depth=16)
        self.project.set_source_image(self.source_path)

        self.mask_path = self.root / "mask.png"
        imwrite(self.mask_path, np.full((512, 512), 255, dtype=np.uint8), bit_depth=8)
        self.project.record_artifact(ROLE_SKY_MASK, self.mask_path)

        self.starless_path = self.root / "starless.tif"
        self.stars_path = self.root / "stars.tif"
        imwrite(self.starless_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        imwrite(self.stars_path, np.full((512, 512, 3), 10000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_SEPARATED_STARLESS, self.starless_path)
        self.project.record_artifact(ROLE_SEPARATED_STARS, self.stars_path)

        self.canvas = CanvasLabel()
        self.canvas.resize(600, 600)
        self.addCleanup(self.canvas.deleteLater)

        class Shell(QObject):
            def __init__(self, canvas):
                super().__init__()
                self.canvas_main = canvas
                self.progressBar = None
                self.label_progressBar = None

            def enqueue_task(self, task_id, title, total, desc, work):
                work()
                return True

        self.shell = Shell(self.canvas)
        self.addCleanup(self.shell.deleteLater)

        self.view = FinishView(self.app, self.shell)
        self.addCleanup(self.view.teardown)
        self.sidebar = self.view.build_sidebar(None)
        self.view.bind()
        self.view.resetProjectView()

    def test_explicit_run_denoise_updates_settings_runs_workflow_and_shows_preview(self):
        """Clicking Run Denoise snapshots settings, saves project, runs denoise, recombines, and previews."""
        denoised_artifact = self.root / "denoised_starless.tif"
        imwrite(denoised_artifact, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)

        composite_artifact = self.root / "composite.tif"
        imwrite(composite_artifact, np.full((512, 512, 3), 30000, dtype=np.uint16), bit_depth=16)

        def mock_denoise(**kwargs):
            self.project.record_artifact(ROLE_DENOISED_STARLESS, denoised_artifact)
            self.project.record_artifact(ROLE_FINISHED_STARLESS, denoised_artifact)
            return np.zeros((512, 512, 3), dtype=np.float32), denoised_artifact

        def mock_recombine(**kwargs):
            self.project.record_artifact(ROLE_FINISHED_COMPOSITE, composite_artifact)
            return np.zeros((512, 512, 3), dtype=np.float32), composite_artifact

        # Set UI values
        self.sidebar.starlessSettings.set_strength(70.0)
        self.sidebar.starlessSettings.set_scope(SCOPE_WHOLE_IMAGE)
        self.sidebar.starlessSettings.set_structure(35.0)
        self.sidebar.starlessSettings.set_detail(55.0)

        # Set zoom to verify preservation
        self.canvas.zoom_factor = 2.0
        self.canvas.posX = 40
        self.canvas.posY = -20

        with (
            patch.object(
                FinishWorkflow,
                "get_graxpert_status",
                return_value={
                    "policy": {"provider": "CUDAExecutionProvider", "verified": True},
                    "model_ready": True,
                    "setup_error": None,
                },
            ),
            patch.object(FinishWorkflow, "do_denoise_starless", side_effect=mock_denoise) as mock_d,
            patch.object(FinishWorkflow, "do_recombine", side_effect=mock_recombine) as mock_r,
            patch.object(FinishWorkflow, "save_project") as mock_save,
        ):
            self.sidebar.starlessSettings.btn_run_denoise.click()
            self.qt.processEvents()

            mock_d.assert_called_once()
            mock_r.assert_called_once()
            mock_save.assert_called()

        # Check persisted project settings
        settings = self.project.get_settings()
        self.assertEqual(settings.denoise_strength, 70.0)
        self.assertEqual(settings.denoise_scope, SCOPE_WHOLE_IMAGE)
        self.assertEqual(settings.structure_amount, 35.0)
        self.assertEqual(settings.detail_amount, 55.0)

        # Canvas displays the finished starless file, preserving zoom/pan
        self.assertIsNotNone(self.canvas.file)
        self.assertEqual(Path(self.canvas.file.path), denoised_artifact.resolve())
        self.assertAlmostEqual(self.canvas.zoom_factor, 2.0)
        self.assertEqual((self.canvas.posX, self.canvas.posY), (40, -20))

    def test_strength_change_with_cached_endpoint_debounces_recompute(self):
        """Slider change when cached endpoint exists debounces and recomputes without inference."""
        endpoint_path = self.root / "endpoint.tif"
        imwrite(endpoint_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, endpoint_path)

        recompute_called = []

        def mock_denoise(**kwargs):
            recompute_called.append(True)
            return np.zeros((512, 512, 3), dtype=np.float32), endpoint_path

        with (
            patch.object(FinishWorkflow, "do_denoise_starless", side_effect=mock_denoise),
            patch.object(FinishWorkflow, "do_recombine", return_value=(np.zeros((512, 512, 3)), Path("c.tif"))),
        ):
            # Change slider to 85%
            self.sidebar.starlessSettings.slider_strength.setValue(85)
            # Before timer fires, recompute not yet called
            self.assertEqual(recompute_called, [])

            # Trigger timer
            self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_called, [True])

        self.assertEqual(self.project.get_settings().denoise_strength, 85.0)

    def test_strength_change_without_endpoint_does_not_infer_unless_zero(self):
        """Changing strength without cached endpoint does not implicitly run inference when strength > 0."""
        # Ensure no cached endpoint
        self.assertIsNone(self.project.current_artifact_path(ROLE_DENOISED_STARLESS))

        recompute_called = []

        def mock_denoise(**kwargs):
            recompute_called.append(True)
            return None

        with patch.object(FinishWorkflow, "do_denoise_starless", side_effect=mock_denoise):
            # Move slider to 40% (positive, no endpoint -> no inference)
            self.sidebar.starlessSettings.slider_strength.setValue(40)
            if self.view._denoise_timer is not None:
                self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_called, [])
            self.assertEqual(self.project.get_settings().denoise_strength, 40.0)

            # Move slider to 0% (zero-strength identity is safe without endpoint)
            self.sidebar.starlessSettings.slider_strength.setValue(0)
            self.assertIsNotNone(self.view._denoise_timer)
            self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_called, [True])
            self.assertEqual(self.project.get_settings().denoise_strength, 0.0)

    def test_reset_action_restores_defaults(self):
        """Reset button restores standard defaults and recomputes if endpoint was present."""
        endpoint_path = self.root / "endpoint.tif"
        imwrite(endpoint_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, endpoint_path)

        # Set nondefault values
        self.sidebar.starlessSettings.set_strength(90.0)
        self.sidebar.starlessSettings.set_scope(SCOPE_WHOLE_IMAGE)
        self.sidebar.starlessSettings.set_structure(45.0)
        self.sidebar.starlessSettings.set_detail(65.0)

        recompute_called = []
        with (
            patch.object(FinishWorkflow, "do_denoise_starless", side_effect=lambda **kw: recompute_called.append(True)),
            patch.object(FinishWorkflow, "do_recombine"),
        ):
            self.sidebar.starlessSettings.btn_reset.click()
            self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()

        settings = self.project.get_settings()
        self.assertEqual(settings.denoise_strength, DEFAULT_DENOISE_STRENGTH_PERCENT)
        self.assertEqual(settings.denoise_scope, DEFAULT_DENOISE_SCOPE)
        self.assertEqual(settings.structure_amount, DEFAULT_STRUCTURE_AMOUNT_PERCENT)
        self.assertEqual(settings.detail_amount, DEFAULT_DETAIL_AMOUNT_PERCENT)
        self.assertEqual(self.sidebar.starlessSettings.get_strength(), DEFAULT_DENOISE_STRENGTH_PERCENT)
        self.assertEqual(self.sidebar.starlessSettings.get_scope(), DEFAULT_DENOISE_SCOPE)
        self.assertEqual(self.sidebar.starlessSettings.get_structure(), DEFAULT_STRUCTURE_AMOUNT_PERCENT)
        self.assertEqual(self.sidebar.starlessSettings.get_detail(), DEFAULT_DETAIL_AMOUNT_PERCENT)
        self.assertEqual(recompute_called, [True])

    def test_structure_change_with_cached_endpoint_debounces_recompute(self):
        """Structure slider change when cached endpoint exists debounces and recomputes without inference."""
        endpoint_path = self.root / "endpoint.tif"
        imwrite(endpoint_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, endpoint_path)

        # Pre-set zoom/pan on canvas to verify preservation
        self.canvas.zoom_factor = 2.5
        self.canvas.posX = 15
        self.canvas.posY = -30

        recompute_called = []

        def mock_denoise(**kwargs):
            recompute_called.append(True)
            return np.zeros((512, 512, 3), dtype=np.float32), endpoint_path

        with (
            patch.object(FinishWorkflow, "do_denoise_starless", side_effect=mock_denoise),
            patch.object(FinishWorkflow, "do_recombine", return_value=(np.zeros((512, 512, 3)), Path("c.tif"))),
        ):
            # Change structure slider to 40%
            self.sidebar.starlessSettings.slider_structure.setValue(40)
            self.assertEqual(recompute_called, [])
            self.assertTrue(self.view._denoise_timer.isActive())

            # Trigger debounced timer
            self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_called, [True])

        self.assertEqual(self.project.get_settings().structure_amount, 40.0)
        self.assertAlmostEqual(self.canvas.zoom_factor, 2.5)
        self.assertEqual((self.canvas.posX, self.canvas.posY), (15, -30))

    def test_detail_change_with_cached_endpoint_debounces_recompute(self):
        """Detail slider change when cached endpoint exists debounces and recomputes without inference."""
        endpoint_path = self.root / "endpoint.tif"
        imwrite(endpoint_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, endpoint_path)

        recompute_called = []

        def mock_denoise(**kwargs):
            recompute_called.append(True)
            return np.zeros((512, 512, 3), dtype=np.float32), endpoint_path

        with (
            patch.object(FinishWorkflow, "do_denoise_starless", side_effect=mock_denoise),
            patch.object(FinishWorkflow, "do_recombine", return_value=(np.zeros((512, 512, 3)), Path("c.tif"))),
        ):
            # Change detail slider to 65%
            self.sidebar.starlessSettings.slider_detail.setValue(65)
            self.assertEqual(recompute_called, [])
            self.assertTrue(self.view._denoise_timer.isActive())

            # Trigger debounced timer
            self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_called, [True])

        self.assertEqual(self.project.get_settings().detail_amount, 65.0)

    def test_structure_and_detail_rapid_changes_coalesce_to_single_update(self):
        """Rapid slider updates coalesce within 100 ms and trigger only a single preview update."""
        endpoint_path = self.root / "endpoint.tif"
        imwrite(endpoint_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, endpoint_path)

        recompute_calls = []

        def mock_denoise(**kwargs):
            recompute_calls.append(True)
            return np.zeros((512, 512, 3), dtype=np.float32), endpoint_path

        with (
            patch.object(FinishWorkflow, "do_denoise_starless", side_effect=mock_denoise),
            patch.object(FinishWorkflow, "do_recombine", return_value=(np.zeros((512, 512, 3)), Path("c.tif"))),
        ):
            # Rapid sequential slider adjustments
            self.sidebar.starlessSettings.slider_structure.setValue(20)
            self.sidebar.starlessSettings.slider_structure.setValue(35)
            self.sidebar.starlessSettings.slider_detail.setValue(50)

            # Recompute should not have run yet during rapid interaction
            self.assertEqual(recompute_calls, [])
            self.assertTrue(self.view._denoise_timer.isActive())

            # Single coalesced debounce timeout
            self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_calls, [True])

        # Final settings are persisted
        self.assertEqual(self.project.get_settings().structure_amount, 35.0)
        self.assertEqual(self.project.get_settings().detail_amount, 50.0)

    def test_latest_preview_retried_when_previous_preview_is_still_queued(self):
        """The queue's duplicate-ID rejection must not lose the final slider settings."""
        queued = {}
        applied = []

        def enqueue(task_id, title, total, desc, work):
            if task_id in queued:
                return False
            queued[task_id] = work
            return True

        def run_queued():
            task_id, work = next(iter(queued.items()))
            try:
                work()
            finally:
                del queued[task_id]

        def finish(**kwargs):
            applied.append(self.project.get_settings())
            return None

        def dispatch_timer():
            # Consume the single-shot timeout without depending on wall time.
            self.view._denoise_timer.stop()
            self.view._denoise_timer.timeout.emit()

        with (
            patch.object(self.shell, "enqueue_task", side_effect=enqueue),
            patch.object(self.workflow, "do_denoise_starless", side_effect=finish),
        ):
            self.sidebar.starlessSettings.slider_strength.setValue(0)
            self.sidebar.starlessSettings.slider_structure.setValue(20)
            dispatch_timer()
            self.assertEqual(len(queued), 1)

            self.sidebar.starlessSettings.slider_structure.setValue(60)
            self.sidebar.starlessSettings.slider_detail.setValue(40)
            dispatch_timer()
            self.assertEqual(len(queued), 1)
            self.assertTrue(self.view._denoise_timer.isActive())

            run_queued()  # The old job's revision guard rejects it.
            self.assertEqual(applied, [])
            dispatch_timer()
            run_queued()
            self.assertEqual(len(applied), 1)
            self.assertEqual(applied[0].denoise_strength, 0.0)
            self.assertEqual(applied[0].structure_amount, 60.0)
            self.assertEqual(applied[0].detail_amount, 40.0)
            self.assertFalse(self.view._denoise_timer.isActive())

    def test_structure_detail_change_without_endpoint_does_not_infer_unless_zero(self):
        """Without cached endpoint, structure/detail changes do not run inference when strength > 0, but do when strength == 0."""
        self.assertIsNone(self.project.current_artifact_path(ROLE_DENOISED_STARLESS))
        self.assertEqual(self.project.get_settings().denoise_strength, DEFAULT_DENOISE_STRENGTH_PERCENT)  # 50.0

        recompute_called = []

        def mock_denoise(**kwargs):
            recompute_called.append(True)
            return None

        with patch.object(FinishWorkflow, "do_denoise_starless", side_effect=mock_denoise):
            # Change structure to 30% (positive strength, no endpoint -> no inference)
            self.sidebar.starlessSettings.slider_structure.setValue(30)
            if self.view._denoise_timer is not None and self.view._denoise_timer.isActive():
                self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_called, [])
            self.assertEqual(self.project.get_settings().structure_amount, 30.0)

            # Change detail to 45% (positive strength, no endpoint -> no inference)
            self.sidebar.starlessSettings.slider_detail.setValue(45)
            if self.view._denoise_timer is not None and self.view._denoise_timer.isActive():
                self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_called, [])
            self.assertEqual(self.project.get_settings().detail_amount, 45.0)

            # Now set denoise strength to 0.0 (zero-strength identity is safe without endpoint)
            self.sidebar.starlessSettings.slider_strength.setValue(0)
            self.assertIsNotNone(self.view._denoise_timer)
            self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_called, [True])
            recompute_called.clear()

            # Now with strength == 0, structure adjustment triggers debounced preview update
            self.sidebar.starlessSettings.slider_structure.setValue(55)
            self.assertTrue(self.view._denoise_timer.isActive())
            self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_called, [True])
            self.assertEqual(self.project.get_settings().structure_amount, 55.0)

            # And detail adjustment triggers debounced preview update
            recompute_called.clear()
            self.sidebar.starlessSettings.slider_detail.setValue(70)
            self.assertTrue(self.view._denoise_timer.isActive())
            self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()
            self.assertEqual(recompute_called, [True])
            self.assertEqual(self.project.get_settings().detail_amount, 70.0)

    def test_stale_job_guard_for_structure_change(self):
        """Stale background result from structure adjustment is discarded if revision changes."""
        endpoint_path = self.root / "endpoint.tif"
        imwrite(endpoint_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, endpoint_path)

        def worker_that_advances_revision():
            self.project.invalidate_results()
            return np.zeros((512, 512, 3)), endpoint_path

        initial_canvas_file = self.canvas.file

        with (
            patch.object(FinishWorkflow, "do_denoise_starless", side_effect=worker_that_advances_revision),
            patch.object(FinishWorkflow, "do_recombine"),
        ):
            self.sidebar.starlessSettings.slider_structure.setValue(50)
            self.view._denoise_timer.timeout.emit()
            self.qt.processEvents()

        # Canvas file should not have been updated to the stale output
        self.assertEqual(self.canvas.file, initial_canvas_file)

    def test_run_denoise_with_cached_endpoint_succeeds_even_when_graxpert_unavailable(self):
        """If an endpoint is cached, on_run_denoise proceeds with reblending even if model is unavailable."""
        endpoint_path = self.root / "endpoint.tif"
        imwrite(endpoint_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, endpoint_path)

        recompute_called = []
        with (
            patch.object(
                FinishWorkflow,
                "get_graxpert_status",
                return_value={"policy": None, "model_ready": False, "setup_error": "Model missing"},
            ),
            patch.object(FinishWorkflow, "do_denoise_starless", side_effect=lambda **kw: recompute_called.append(True)),
            patch.object(FinishWorkflow, "do_recombine"),
        ):
            self.sidebar.starlessSettings.set_strength(60.0)
            self.sidebar.starlessSettings.btn_run_denoise.click()
            self.qt.processEvents()

        self.assertEqual(recompute_called, [True])

    def test_stale_job_guard_rejects_outdated_results(self):
        """If project revision changes before background task finishes, stale result is dropped."""
        endpoint_path = self.root / "endpoint.tif"
        imwrite(endpoint_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, endpoint_path)

        def worker_that_advances_revision():
            # Simulate another operation or edit advancing processing_revision mid-task
            self.project.invalidate_results()
            return np.zeros((512, 512, 3)), endpoint_path

        initial_canvas_file = self.canvas.file

        with (
            patch.object(
                FinishWorkflow,
                "get_graxpert_status",
                return_value={
                    "policy": {"provider": "CUDAExecutionProvider", "verified": True},
                    "model_ready": True,
                    "setup_error": None,
                },
            ),
            patch.object(FinishWorkflow, "do_denoise_starless", side_effect=worker_that_advances_revision),
        ):
            self.view.on_run_denoise()
            self.qt.processEvents()

        # Canvas file should not have been updated to the stale output
        self.assertEqual(self.canvas.file, initial_canvas_file)

    def test_update_ready_states_invokes_graxpert_invalidation(self):
        """updateReadyStates calls invalidate_if_graxpert_changed and clears stale outputs."""
        endpoint_path = self.root / "endpoint.tif"
        imwrite(endpoint_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, endpoint_path)

        invalidation_calls = []

        def mock_invalidate_graxpert():
            invalidation_calls.append(True)
            self.project.invalidate_denoise_descendants()
            return True

        with patch.object(FinishWorkflow, "invalidate_if_graxpert_changed", side_effect=mock_invalidate_graxpert):
            self.view.updateReadyStates()

        self.assertEqual(invalidation_calls, [True])
        output_operations = [f.operation for f in self.sidebar.outputFiles.model.files]
        self.assertNotIn("Denoised", output_operations)
        self.assertNotIn("Finished Starless", output_operations)

    def test_update_ready_states_invokes_starless_filter_invalidation(self):
        """updateReadyStates calls invalidate_if_starless_filter_changed alongside denoise invalidation."""
        endpoint_path = self.root / "endpoint.tif"
        imwrite(endpoint_path, np.full((512, 512, 3), 20000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, endpoint_path)

        finished_path = self.root / "finished_starless.tif"
        imwrite(finished_path, np.full((512, 512, 3), 22000, dtype=np.uint16), bit_depth=16)
        self.project.record_artifact(ROLE_FINISHED_STARLESS, finished_path)

        invalidation_calls = []

        def mock_invalidate_filter():
            invalidation_calls.append(True)
            self.project.invalidate_artifact_roles({ROLE_FINISHED_STARLESS, ROLE_FINISHED_COMPOSITE})
            return True

        with patch.object(self.workflow, "invalidate_if_starless_filter_changed", mock_invalidate_filter, create=True):
            self.view.updateReadyStates()

        self.assertEqual(invalidation_calls, [True])
        output_operations = [f.operation for f in self.sidebar.outputFiles.model.files]
        self.assertNotIn("Finished Starless", output_operations)
        self.assertIsNotNone(self.project.current_artifact_path(ROLE_DENOISED_STARLESS))


__all__ = [
    "TestFinishStarlessSettings",
    "TestSidebarFinishPrerequisites",
    "TestFinishViewStarlessInteraction",
]
