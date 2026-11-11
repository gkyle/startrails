"""Tests for Finish Step 3: GraXpert starless denoising, endpoint caching, and interactive strength/scope."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import jsonpickle
import numpy as np
from PySide6.QtCore import QObject

from startrails.lib.finish.composition import blend_denoise, compute_denoise_endpoint_signature
from startrails.lib.finish.defaults import (
    FINISH_EXT,
    ROLE_DENOISE_ENDPOINT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    SCOPE_SKY_ONLY,
    SCOPE_WHOLE_IMAGE,
)
from startrails.lib.finish.starless_filters import STARLESS_FILTER_VERSION, sharpen_starless
from startrails.lib.image_io import imread, imwrite
from startrails.lib.project_finish import FinishProject
from startrails.op.finish.graxpert_denoise import GraXpertDenoise
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.sidebar_finish import SidebarFinish
from startrails.ui.views.finish import FinishView
from startrails.workflow.finish import FinishWorkflow
from support import QtTestCase


class TestFinishDenoise(QtTestCase):
    def setUp(self):
        super().setUp()
        self.rng = np.random.default_rng(42)
        self.proj_path = self.root / f"test_denoise{FINISH_EXT}"
        self.project = FinishProject(project_file=str(self.proj_path))
        self.app = self.make_app(self.project)
        self.workflow = FinishWorkflow(self.app)
        self.app.workflow = self.workflow
        self.enterContext(
            patch.object(
                self.workflow,
                "get_star_removal_status",
                return_value={"configured": True, "model_ready": True, "version": "1.0.0", "device": "cpu"},
            )
        )

    def create_synthetic_image(self, name: str = "source.tif", shape: tuple[int, int] = (512, 512)) -> Path:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        pixels = self.rng.integers(5000, 55000, (*shape, 3), dtype=np.uint16)
        imwrite(target, pixels, convertBGR=False, bit_depth=16)
        return target

    @staticmethod
    def create_gradient_mask(shape: tuple[int, int] = (512, 512)) -> np.ndarray:
        height, width = shape
        mask = np.zeros((height, width), dtype=np.float32)
        mask[: height // 2, :] = 1.0
        mask[height // 2 : height // 2 + 10, :] = 0.5
        return mask

    @staticmethod
    def make_fake_nox_session(scale: float = 0.8) -> MagicMock:
        session = MagicMock()
        session.remove_stars.side_effect = lambda image, **kwargs: (image * scale).astype(np.float32)
        return session

    def prepare_separated_project(self) -> Path:
        source_path = self.create_synthetic_image("night_sky.tif")
        self.workflow.do_import_source(source_path)
        self.workflow.save_mask(self.create_gradient_mask())

        with patch.object(self.workflow, "_nox_session_for", return_value=self.make_fake_nox_session(0.8)):
            self.assertIsNotNone(self.workflow.do_separate_stars(chroma_postfilter=False))
        return source_path

    def test_end_to_end_denoise_endpoint_caching_and_strength_blending(self):
        """Denoise runs inference once, caches endpoint, and strength/scope reuse it."""
        self.prepare_separated_project()
        self.project.update_settings(replace(self.project.get_settings(), structure_amount=0.0, detail_amount=0.0))

        inference_calls = 0

        def fake_denoise_inference(image, progress_bar=None, should_interrupt=None):
            nonlocal inference_calls
            inference_calls += 1
            # Return smoother/reduced noise version
            return np.full_like(image, 0.45, dtype=np.float32)

        fake_session = MagicMock()
        fake_session.denoise_full_strength.side_effect = fake_denoise_inference

        with patch.object(self.workflow, "_graxpert_session_for", return_value=fake_session):
            # Step 1: Run denoise at 50% strength and sky_only with neutral sharpening.
            result = self.workflow.do_denoise_starless()
            self.assertIsNotNone(result)
            self.assertEqual(inference_calls, 1)

            endpoint_p = self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT)
            denoised_p = self.project.current_artifact_path(ROLE_DENOISED_STARLESS)
            finished_p = self.project.current_artifact_path(ROLE_FINISHED_STARLESS)
            self.assertIsNotNone(endpoint_p)
            self.assertIsNotNone(denoised_p)
            self.assertIsNotNone(finished_p)
            self.assertTrue(endpoint_p.is_file())
            self.assertTrue(denoised_p.is_file())
            self.assertTrue(finished_p.is_file())

            endpoint_pixels = imread(endpoint_p, to_rgb=True, as_float=True)
            np.testing.assert_allclose(endpoint_pixels, 0.45, atol=1e-3)
            np.testing.assert_allclose(
                imread(denoised_p, to_rgb=True, as_float=True),
                imread(finished_p, to_rgb=True, as_float=True),
                atol=1 / 65535,
            )

            # Step 2: Change strength to 80% and run again
            settings = self.project.get_settings()
            self.project.update_settings(replace(settings, denoise_strength=80.0))
            result2 = self.workflow.do_denoise_starless()
            self.assertIsNotNone(result2)
            # Critical: inference was NOT called again; endpoint was reused!
            self.assertEqual(inference_calls, 1)

            finished_pixels = imread(finished_p, to_rgb=True, as_float=True)
            base_pixels = imread(
                self.project.current_artifact_path(ROLE_SEPARATED_STARLESS), to_rgb=True, as_float=True
            )
            mask = self.workflow.get_current_mask()
            expected = blend_denoise(base_pixels, endpoint_pixels, mask, 80.0, SCOPE_SKY_ONLY)
            np.testing.assert_allclose(finished_pixels, expected, atol=1e-3)
            np.testing.assert_allclose(
                imread(denoised_p, to_rgb=True, as_float=True),
                expected,
                atol=1e-3,
            )

            # Step 3: Change scope to whole_image
            settings = self.project.get_settings()
            self.project.update_settings(replace(settings, denoise_scope=SCOPE_WHOLE_IMAGE))
            result3 = self.workflow.do_denoise_starless()
            self.assertIsNotNone(result3)
            self.assertEqual(inference_calls, 1)

            finished_whole = imread(finished_p, to_rgb=True, as_float=True)
            expected_whole = blend_denoise(base_pixels, endpoint_pixels, mask, 80.0, SCOPE_WHOLE_IMAGE)
            np.testing.assert_allclose(finished_whole, expected_whole, atol=1e-3)

    def test_zero_strength_does_not_require_graxpert_model(self):
        """Zero strength produces finished starless without invoking GraXpert."""
        self.prepare_separated_project()
        settings = self.project.get_settings()
        self.project.update_settings(
            replace(settings, denoise_strength=0.0, structure_amount=0.0, detail_amount=0.0)
        )

        with patch.object(self.workflow, "_graxpert_session_for", side_effect=RuntimeError("no model")):
            result = self.workflow.do_denoise_starless()

        self.assertIsNotNone(result)
        finished_p = self.project.current_artifact_path(ROLE_FINISHED_STARLESS)
        denoised_p = self.project.current_artifact_path(ROLE_DENOISED_STARLESS)
        separated_p = self.project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        self.assertIsNotNone(finished_p)
        self.assertIsNotNone(denoised_p)
        self.assertIsNone(self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT))
        finished = imread(finished_p, to_rgb=True, as_float=True)
        denoised = imread(denoised_p, to_rgb=True, as_float=True)
        separated = imread(separated_p, to_rgb=True, as_float=True)
        np.testing.assert_allclose(finished, separated, atol=1e-4)
        np.testing.assert_allclose(denoised, separated, atol=1e-4)

    def test_separation_change_invalidates_denoise_endpoint(self):
        """Re-running separation invalidates the denoise endpoint and finished starless."""
        self.prepare_separated_project()

        fake_session = MagicMock()
        fake_session.denoise_full_strength.return_value = np.full((512, 512, 3), 0.5, dtype=np.float32)

        with patch.object(self.workflow, "_graxpert_session_for", return_value=fake_session):
            self.workflow.do_denoise_starless()

        self.assertIsNotNone(self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT))
        self.assertIsNotNone(self.project.current_artifact_path(ROLE_DENOISED_STARLESS))
        self.assertIsNotNone(self.project.current_artifact_path(ROLE_FINISHED_STARLESS))

        # Re-running separation must invalidate all denoise artifacts
        with patch.object(self.workflow, "_nox_session_for", return_value=self.make_fake_nox_session(0.7)):
            self.workflow.do_separate_stars(stride=128, chroma_postfilter=False)

        self.assertIsNone(self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT))
        self.assertIsNone(self.project.current_artifact_path(ROLE_DENOISED_STARLESS))
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_STARLESS))

    def test_project_reopen_preserves_valid_denoise_endpoint(self):
        """Saving and reopening project preserves the cached denoise endpoint and finished layer."""
        self.prepare_separated_project()

        fake_session = MagicMock()
        fake_session.denoise_full_strength.return_value = np.full((512, 512, 3), 0.5, dtype=np.float32)

        with patch.object(self.workflow, "_graxpert_session_for", return_value=fake_session):
            self.workflow.do_denoise_starless()

        endpoint_before = self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT)
        denoised_before = self.project.current_artifact_path(ROLE_DENOISED_STARLESS)
        finished_before = self.project.current_artifact_path(ROLE_FINISHED_STARLESS)
        self.assertIsNotNone(endpoint_before)
        self.assertIsNotNone(denoised_before)
        self.assertIsNotNone(finished_before)

        # Reopen project from disk
        reloaded = jsonpickle.decode(self.proj_path.read_text(encoding="utf-8"))
        endpoint_after = reloaded.current_artifact_path(ROLE_DENOISE_ENDPOINT)
        denoised_after = reloaded.current_artifact_path(ROLE_DENOISED_STARLESS)
        finished_after = reloaded.current_artifact_path(ROLE_FINISHED_STARLESS)

        self.assertEqual(endpoint_before, endpoint_after)
        self.assertEqual(denoised_before, denoised_after)
        self.assertEqual(finished_before, finished_after)

    def test_ui_denoise_card_status_and_prerequisites(self):
        """Card status updates appropriately as project moves from unseparated to separated and denoised."""
        source_path = self.create_synthetic_image("test_ui.tif")
        self.workflow.do_import_source(source_path)

        canvas = CanvasLabel()
        self.addCleanup(canvas.deleteLater)

        shell = QObject()
        shell.canvas_main = canvas
        shell.progressBar = None
        shell.label_progressBar = None
        self.addCleanup(shell.deleteLater)

        view = FinishView(self.app, shell)
        self.addCleanup(view.teardown)
        sidebar = view.build_sidebar(canvas)
        view.bind()

        # Before separation: card 3 (starlessCard) must be locked
        view.updateReadyStates()
        self.assertEqual(sidebar.starlessCard.status, "locked")
        self.assertEqual(sidebar.starlessCard.ui.subtitle.text(), "Prerequisite: Separated starless required")

        # Define sky region
        self.workflow.save_mask(self.create_gradient_mask())
        view.updateReadyStates()
        self.assertEqual(sidebar.starlessCard.status, "locked")
        self.assertEqual(sidebar.starlessCard.ui.subtitle.text(), "Prerequisite: Separated starless required")

        # Separate stars
        with patch.object(self.workflow, "_nox_session_for", return_value=self.make_fake_nox_session(0.8)):
            self.workflow.do_separate_stars(chroma_postfilter=False)

        view.updateReadyStates()
        self.assertEqual(sidebar.starlessCard.status, "ready")
        self.assertEqual(sidebar.starlessCard.ui.subtitle.text(), "Ready to finish starless")
        self.assertTrue(sidebar.starlessSettings.check_enable_denoise.isEnabled())
        self.assertTrue(sidebar.starlessSettings.check_enable_sharpen.isEnabled())

        # Test slider updates settings
        sidebar.starlessSettings.slider_denoise_strength.setValue(72)
        self.assertEqual(self.project.get_settings().denoise_strength, 72.0)
        self.assertEqual(sidebar.starlessSettings.spin_strength.value(), 72)

        # Test scope radio updates settings
        sidebar.starlessSettings.radio_whole_image.setChecked(True)
        self.assertEqual(self.project.get_settings().denoise_scope, SCOPE_WHOLE_IMAGE)

    def test_workflow_applies_structure_and_detail_to_denoised_plate(self):
        """Sharpening reruns from the denoised plate and persists both amounts."""
        self.prepare_separated_project()
        separated_p = self.project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        mask = self.workflow.get_current_mask()
        base = imread(separated_p, to_rgb=True, as_float=True)

        settings = self.project.get_settings()
        self.project.update_settings(replace(settings, denoise_strength=0.0, structure_amount=100.0, detail_amount=0.0))
        self.assertIsNotNone(self.workflow.do_denoise_starless())
        denoised_p = self.project.current_artifact_path(ROLE_DENOISED_STARLESS)
        finished_p = self.project.current_artifact_path(ROLE_FINISHED_STARLESS)
        denoised = imread(denoised_p, to_rgb=True, as_float=True)
        np.testing.assert_allclose(denoised, base, atol=1e-4)
        structure_output = imread(finished_p, to_rgb=True, as_float=True)
        np.testing.assert_allclose(
            structure_output,
            sharpen_starless(denoised, mask, 100.0, 0.0),
            atol=1.5 / 65535,
        )
        options = self.project.artifact_manifest[ROLE_FINISHED_STARLESS]["options"]
        self.assertEqual(options["structure_amount"], 100.0)
        self.assertEqual(options["detail_amount"], 0.0)

        self.project.update_settings(replace(self.project.get_settings(), structure_amount=0.0, detail_amount=100.0))
        self.assertIsNotNone(self.workflow.do_denoise_starless())
        detail_output = imread(self.project.current_artifact_path(ROLE_FINISHED_STARLESS), to_rgb=True, as_float=True)
        # A second run starts from the denoised plate, not the first sharpened result.
        np.testing.assert_allclose(
            detail_output,
            sharpen_starless(denoised, mask, 0.0, 100.0),
            atol=1.5 / 65535,
        )
        self.assertGreater(float(np.max(np.abs(detail_output - structure_output))), 0.0)
        options = self.project.artifact_manifest[ROLE_FINISHED_STARLESS]["options"]
        self.assertEqual(options["structure_amount"], 0.0)
        self.assertEqual(options["detail_amount"], 100.0)

    def test_structure_change_reuses_cached_denoised_plate_and_endpoint(self):
        """Structure/Detail edits sharpen the retained denoised plate without re-blending."""
        self.prepare_separated_project()
        fake_session = MagicMock()
        fake_session.denoise_full_strength.return_value = np.full((512, 512, 3), 0.45, dtype=np.float32)
        real_imread = imread
        read_paths: list[Path] = []

        def tracking_imread(path, *args, **kwargs):
            read_paths.append(Path(path).resolve())
            return real_imread(path, *args, **kwargs)

        with (
            patch.object(self.workflow, "_graxpert_session_for", return_value=fake_session),
            patch("startrails.workflow.finish.imread", side_effect=tracking_imread),
            patch("startrails.workflow.finish.blend_denoise", wraps=blend_denoise) as blend_mock,
        ):
            self.project.update_settings(
                replace(
                    self.project.get_settings(),
                    denoise_strength=50.0,
                    denoise_scope=SCOPE_SKY_ONLY,
                    structure_amount=100.0,
                    detail_amount=0.0,
                )
            )
            self.assertIsNotNone(self.workflow.do_denoise_starless())
            denoised_p = self.project.current_artifact_path(ROLE_DENOISED_STARLESS)
            endpoint_p = self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT)
            self.assertIsNotNone(denoised_p)
            self.assertIsNotNone(endpoint_p)
            denoised_bytes = denoised_p.read_bytes()
            endpoint_bytes = endpoint_p.read_bytes()
            denoised_pixels = imread(denoised_p, to_rgb=True, as_float=True)
            self.assertEqual(blend_mock.call_count, 1)

            read_paths.clear()
            self.project.update_settings(
                replace(self.project.get_settings(), structure_amount=40.0, detail_amount=60.0)
            )
            self.assertIsNotNone(self.workflow.do_denoise_starless())

        self.assertEqual(fake_session.denoise_full_strength.call_count, 1)
        self.assertEqual(blend_mock.call_count, 1)
        self.assertEqual(read_paths, [])
        self.assertEqual(self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT), endpoint_p)
        self.assertEqual(self.project.current_artifact_path(ROLE_DENOISED_STARLESS), denoised_p)
        self.assertEqual(denoised_p.read_bytes(), denoised_bytes)
        self.assertEqual(endpoint_p.read_bytes(), endpoint_bytes)
        np.testing.assert_allclose(
            imread(
                self.project.current_artifact_path(ROLE_FINISHED_STARLESS),
                to_rgb=True,
                as_float=True,
            ),
            sharpen_starless(denoised_pixels, self.workflow.get_current_mask(), 40.0, 60.0),
            atol=1.5 / 65535,
        )

    def test_workflow_sharpens_after_cached_denoise_blend_without_reinference(self):
        """Sharpening is applied to B + a*W*(D-B) and reuses the cached endpoint."""
        self.prepare_separated_project()
        separated_p = self.project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        mask = self.workflow.get_current_mask()
        base = imread(separated_p, to_rgb=True, as_float=True)
        denoised = np.full_like(base, 0.45)

        fake_session = MagicMock()
        fake_session.denoise_full_strength.return_value = denoised
        with patch.object(self.workflow, "_graxpert_session_for", return_value=fake_session):
            self.project.update_settings(
                replace(
                    self.project.get_settings(),
                    denoise_strength=50.0,
                    denoise_scope=SCOPE_SKY_ONLY,
                    structure_amount=100.0,
                    detail_amount=0.0,
                )
            )
            self.assertIsNotNone(self.workflow.do_denoise_starless())
            blended = blend_denoise(base, denoised, mask, 50.0, SCOPE_SKY_ONLY)
            np.testing.assert_allclose(
                imread(self.project.current_artifact_path(ROLE_FINISHED_STARLESS), to_rgb=True, as_float=True),
                sharpen_starless(blended, mask, 100.0, 0.0),
                atol=1.5 / 65535,
            )

            self.project.update_settings(
                replace(self.project.get_settings(), structure_amount=40.0, detail_amount=60.0)
            )
            self.assertIsNotNone(self.workflow.do_denoise_starless())
            self.assertEqual(fake_session.denoise_full_strength.call_count, 1)
            np.testing.assert_allclose(
                imread(self.project.current_artifact_path(ROLE_FINISHED_STARLESS), to_rgb=True, as_float=True),
                sharpen_starless(blended, mask, 40.0, 60.0),
                atol=1.5 / 65535,
            )

            # Disabling denoise implicitly disables post-denoise sharpening: do_denoise_starless does
            # not call GraXpert or overwrite the cached denoised/finished plates, and returns Starless.
            self.project.update_settings(replace(self.project.get_settings(), enable_starless_denoise=False))
            self.assertIsNotNone(self.project.current_artifact_path(ROLE_DENOISED_STARLESS))
            self.assertIsNotNone(self.project.current_artifact_path(ROLE_FINISHED_STARLESS))
            result = self.workflow.do_denoise_starless()
            self.assertIsNotNone(result)
            self.assertEqual(result.operation, "Starless")
            self.assertEqual(fake_session.denoise_full_strength.call_count, 1)
            np.testing.assert_allclose(
                imread(self.project.current_artifact_path(ROLE_FINISHED_STARLESS), to_rgb=True, as_float=True),
                sharpen_starless(blended, mask, 40.0, 60.0),
                atol=1.5 / 65535,
            )
            np.testing.assert_allclose(
                imread(self.project.current_artifact_path(ROLE_DENOISED_STARLESS), to_rgb=True, as_float=True),
                blended,
                atol=1.5 / 65535,
            )

    def test_recombine_respects_independent_starless_toggles(self):
        """Recombination selects finished, denoised, or separated plate from the toggles."""
        self.prepare_separated_project()
        self.project.update_settings(replace(self.project.get_settings(), star_amount=0.0, structure_amount=20.0))
        separated_p = self.project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        self.assertIsNotNone(separated_p)
        separated_pixels = imread(separated_p, to_rgb=True, as_float=True)

        denoised_p = self.project.artifact_path(ROLE_DENOISED_STARLESS, for_write=True)
        imwrite(denoised_p, np.full((512, 512, 3), 0.30, np.float32), convertBGR=False, bit_depth=16)
        self.project.record_artifact(ROLE_DENOISED_STARLESS, denoised_p)
        finished_p = self.project.artifact_path(ROLE_FINISHED_STARLESS, for_write=True)
        imwrite(finished_p, np.full((512, 512, 3), 0.25, np.float32), convertBGR=False, bit_depth=16)
        finished_options = {
            "separation_signature": self.project.separation_signature,
            "starless_filter_version": STARLESS_FILTER_VERSION,
        }
        self.project.record_artifact(ROLE_FINISHED_STARLESS, finished_p, options=finished_options)

        # Post-denoise sharpening applies only when denoise is enabled; otherwise fall back to separated starless.
        expectations = (
            (True, True, 0.25, ROLE_FINISHED_STARLESS),
            (True, False, 0.30, ROLE_DENOISED_STARLESS),
            (False, False, None, ROLE_SEPARATED_STARLESS),
            (False, True, None, ROLE_SEPARATED_STARLESS),
        )
        for enable_denoise, enable_sharpen, expected, expected_role in expectations:
            with self.subTest(enable_denoise=enable_denoise, enable_sharpen=enable_sharpen):
                self.project.update_settings(
                    replace(
                        self.project.get_settings(),
                        enable_starless_denoise=enable_denoise,
                        enable_starless_sharpen=enable_sharpen,
                    )
                )
                self.assertIsNotNone(self.project.current_artifact_path(ROLE_DENOISED_STARLESS))
                self.assertIsNotNone(self.project.current_artifact_path(ROLE_FINISHED_STARLESS))
                with self.assertRaisesRegex(ValueError, "No current composite"):
                    self.workflow.do_export_composite(self.root / "stale_toggle.tif")
                self.assertIsNotNone(self.workflow.do_recombine())

                composite = imread(
                    self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE),
                    to_rgb=True,
                    as_float=True,
                )
                if expected is None:
                    np.testing.assert_allclose(composite, separated_pixels, atol=1.5 / 65535)
                else:
                    np.testing.assert_allclose(composite, expected, atol=1.5 / 65535)

                options = self.project.artifact_manifest[ROLE_FINISHED_COMPOSITE]["options"]
                self.assertEqual(options["enable_starless_denoise"], enable_denoise)
                self.assertEqual(options["enable_starless_sharpen"], enable_sharpen)
                self.assertEqual(self.workflow.active_starless_role(), expected_role)

    def test_repeated_denoise_adjustments_reuse_decoded_plates(self):
        """Cached endpoint adjustments do not decode the separated or endpoint plates again."""
        self.prepare_separated_project()
        fake_session = MagicMock()
        fake_session.denoise_full_strength.return_value = np.full((512, 512, 3), 0.45, dtype=np.float32)
        real_imread = imread
        read_paths: list[Path] = []

        def tracking_imread(path, *args, **kwargs):
            read_paths.append(Path(path).resolve())
            return real_imread(path, *args, **kwargs)

        with (
            patch.object(self.workflow, "_graxpert_session_for", return_value=fake_session),
            patch("startrails.workflow.finish.imread", side_effect=tracking_imread),
        ):
            self.assertIsNotNone(self.workflow.do_denoise_starless())
            separated_p = self.project.current_artifact_path(ROLE_SEPARATED_STARLESS)
            endpoint_p = self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT)
            self.assertIsNotNone(separated_p)
            self.assertIsNotNone(endpoint_p)
            self.assertIn(separated_p, read_paths)
            # The newly computed endpoint is cached directly instead of decoded back.
            self.assertNotIn(endpoint_p, read_paths)

            read_paths.clear()
            self.project.update_settings(replace(self.project.get_settings(), denoise_strength=80.0))
            self.assertIsNotNone(self.workflow.do_denoise_starless())
            self.project.update_settings(replace(self.project.get_settings(), denoise_scope=SCOPE_WHOLE_IMAGE))
            self.assertIsNotNone(self.workflow.do_denoise_starless())

        self.assertEqual(fake_session.denoise_full_strength.call_count, 1)
        self.assertNotIn(separated_p, read_paths)
        self.assertNotIn(endpoint_p, read_paths)
        self.assertEqual(read_paths, [])

    def test_filter_version_change_invalidates_finished_descendants_only(self):
        """A new sharpening algorithm rebuilds the finished plate from the cached endpoint."""
        self.prepare_separated_project()
        fake_session = MagicMock()
        fake_session.denoise_full_strength.return_value = np.full((512, 512, 3), 0.45, dtype=np.float32)
        with patch.object(self.workflow, "_graxpert_session_for", return_value=fake_session):
            self.project.update_settings(
                replace(
                    self.project.get_settings(),
                    denoise_strength=50.0,
                    denoise_scope=SCOPE_SKY_ONLY,
                    structure_amount=100.0,
                    detail_amount=50.0,
                )
            )
            self.assertIsNotNone(self.workflow.do_denoise_starless())
            self.assertIsNotNone(self.workflow.do_recombine())
            export_path = self.create_synthetic_image("version_export.tif")
            self.project.record_export(export_path)

            endpoint = self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT)
            denoised = self.project.current_artifact_path(ROLE_DENOISED_STARLESS)
            self.assertIsNotNone(endpoint)
            self.assertIsNotNone(denoised)
            self.assertIsNotNone(self.project.current_artifact_path(ROLE_FINISHED_STARLESS))
            self.assertIsNotNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
            self.assertIsNotNone(self.project.current_export_path())
            self.assertFalse(self.workflow.invalidate_if_starless_filter_changed())
            self.assertEqual(fake_session.denoise_full_strength.call_count, 1)

            self.project.artifact_manifest[ROLE_FINISHED_STARLESS]["options"]["starless_filter_version"] = 0
            self.assertTrue(self.workflow.invalidate_if_starless_filter_changed())
            self.assertEqual(self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT), endpoint)
            self.assertEqual(self.project.current_artifact_path(ROLE_DENOISED_STARLESS), denoised)
            self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_STARLESS))
            self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
            self.assertIsNone(self.project.current_export_path())

            self.assertIsNotNone(self.workflow.do_denoise_starless())
            self.assertEqual(fake_session.denoise_full_strength.call_count, 1)
            self.assertEqual(
                self.project.artifact_manifest[ROLE_FINISHED_STARLESS]["options"]["starless_filter_version"],
                STARLESS_FILTER_VERSION,
            )

    def test_stale_filter_version_rejected_at_recombine_and_export_boundaries(self):
        """Direct consume calls reject a stale finished plate and keep the endpoint."""
        self.prepare_separated_project()
        fake_session = MagicMock()
        fake_session.denoise_full_strength.return_value = np.full((512, 512, 3), 0.45, dtype=np.float32)
        with patch.object(self.workflow, "_graxpert_session_for", return_value=fake_session):
            self.project.update_settings(
                replace(
                    self.project.get_settings(),
                    denoise_strength=50.0,
                    denoise_scope=SCOPE_SKY_ONLY,
                    structure_amount=100.0,
                    detail_amount=0.0,
                )
            )
            self.assertIsNotNone(self.workflow.do_denoise_starless())
            self.assertIsNotNone(self.workflow.do_recombine())
            self.project.record_export(self.create_synthetic_image("stale_export.tif"))
            endpoint = self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT)
            denoised = self.project.current_artifact_path(ROLE_DENOISED_STARLESS)
            self.assertIsNotNone(endpoint)
            self.assertIsNotNone(denoised)
            self.assertEqual(fake_session.denoise_full_strength.call_count, 1)

            self.project.artifact_manifest[ROLE_FINISHED_STARLESS]["options"]["starless_filter_version"] = 0
            self.assertIsNone(self.workflow.do_recombine())
            self.assertEqual(self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT), endpoint)
            self.assertEqual(self.project.current_artifact_path(ROLE_DENOISED_STARLESS), denoised)
            self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_STARLESS))
            self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
            self.assertIsNone(self.project.current_export_path())

            # Rebuild at the current version, then verify export rejects a stale plate too.
            self.assertIsNotNone(self.workflow.do_denoise_starless())
            self.assertIsNotNone(self.workflow.do_recombine())
            self.project.record_export(self.create_synthetic_image("stale_export_2.tif"))
            self.assertEqual(fake_session.denoise_full_strength.call_count, 1)
            self.project.artifact_manifest[ROLE_FINISHED_STARLESS]["options"]["starless_filter_version"] = 0
            with self.assertRaisesRegex(ValueError, "No current composite"):
                self.workflow.do_export_composite(self.root / "never_written.tif")
            self.assertEqual(self.project.current_artifact_path(ROLE_DENOISE_ENDPOINT), endpoint)
            self.assertEqual(self.project.current_artifact_path(ROLE_DENOISED_STARLESS), denoised)
            self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_STARLESS))
            self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
            self.assertIsNone(self.project.current_export_path())

    def test_stale_graxpert_model_rejected_at_recombine_and_export_boundaries(self):
        """Direct consumers cannot publish plates built from an obsolete denoise model."""
        self.prepare_separated_project()
        fake_session = MagicMock()
        fake_session.denoise_full_strength.return_value = np.full((512, 512, 3), 0.45, dtype=np.float32)
        with patch.object(self.workflow, "_graxpert_session_for", return_value=fake_session):
            for consumer in ("recombine", "export"):
                with self.subTest(consumer=consumer):
                    self.assertIsNotNone(self.workflow.do_denoise_starless())
                    self.assertIsNotNone(self.workflow.do_recombine())
                    self.project.denoise_model_identity = "obsolete-model"

                    if consumer == "recombine":
                        self.assertIsNone(self.workflow.do_recombine())
                    else:
                        destination = self.root / "obsolete-export.tif"
                        with self.assertRaisesRegex(ValueError, "No current composite"):
                            self.workflow.do_export_composite(destination)
                        self.assertFalse(destination.exists())

                    for role in (
                        ROLE_DENOISE_ENDPOINT,
                        ROLE_DENOISED_STARLESS,
                        ROLE_FINISHED_STARLESS,
                        ROLE_FINISHED_COMPOSITE,
                    ):
                        self.assertIsNone(self.project.current_artifact_path(role))
                    self.assertIsNotNone(self.project.current_artifact_path(ROLE_SEPARATED_STARLESS))

    def test_progress_does_not_complete_before_sharpening_finishes(self):
        """Inference completion is mapped to a partial phase, not task completion."""
        self.prepare_separated_project()
        fake_session = MagicMock()

        def fake_denoise(image, progress_bar=None, should_interrupt=None):
            if progress_bar is not None:
                progress_bar(2, 1, 1, False, {"desc": "Denoising tile 1/2..."})
                progress_bar(2, 1, 2, True, {"desc": "Denoising tile 2/2..."})
            return np.full_like(image, 0.45)

        fake_session.denoise_full_strength.side_effect = fake_denoise
        events = []

        def record_progress(total, increment, count, done, data=None):
            events.append((total, increment, count, done, data))

        with patch.object(self.workflow, "_graxpert_session_for", return_value=fake_session):
            self.project.update_settings(
                replace(
                    self.project.get_settings(),
                    denoise_strength=50.0,
                    denoise_scope=SCOPE_SKY_ONLY,
                    structure_amount=100.0,
                    detail_amount=0.0,
                )
            )
            self.assertIsNotNone(self.workflow.do_denoise_starless(progress_bar=record_progress))
            self.assertTrue(events)
            self.assertTrue(all(not event[3] for event in events[:-1]))
            self.assertTrue(events[-1][3])
            self.assertEqual(events[-1][2], 100)
            self.assertEqual(events[-1][4]["desc"], "Starless finishing complete.")

            self.project.update_settings(
                replace(self.project.get_settings(), structure_amount=40.0, detail_amount=60.0)
            )
            cached_events = []
            self.assertIsNotNone(
                self.workflow.do_denoise_starless(
                    progress_bar=lambda *args: cached_events.append(args),
                )
            )
            self.assertEqual(fake_session.denoise_full_strength.call_count, 1)
            self.assertTrue(cached_events)
            self.assertTrue(all(not event[3] for event in cached_events[:-1]))
            self.assertTrue(cached_events[-1][3])
            self.assertEqual(cached_events[0][2], 90)
            self.assertFalse(cached_events[0][3])
