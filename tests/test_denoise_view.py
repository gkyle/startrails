"""Project ownership of queued results, errors, and real background publication."""

from pathlib import Path
from types import SimpleNamespace
from io import StringIO
from unittest.mock import patch

import jsonpickle
import numpy as np
from PySide6.QtCore import QEventLoop, QObject, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel
from shiboken6 import isValid

from support import QtTestCase
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor
from startrails.lib.file import DenoiseInputFile
from startrails.lib.image_io import imread, imwrite
from startrails.lib.project_denoise import DenoiseProject
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.sidebar_denoise import SidebarDenoise
from startrails.ui.ui_wrap import MainWindow
from startrails.ui.views.denoise import DenoiseView
from startrails.ui.workers_denoise import FinalCompositeSaveWorker
from startrails.ui.progress import ProgressBarUpdater
from startrails.op.denoise.align_stars import AlignStars

WORKER_TIMEOUT_MS = 5000


class DenoiseViewTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.project = DenoiseProject(str(self.root / "first.proj_denoise"))
        self.app = self.make_app(self.project)
        self.shell = QObject()
        self.shell.canvas_main = CanvasLabel()
        self.addCleanup(self.shell.deleteLater)
        self.view = DenoiseView(self.app, self.shell)
        self.addCleanup(self.dispose_view)

    def dispose_view(self):
        if isValid(self.view):
            self.view.teardown()
            if isValid(self.view):
                self.view.wait_for_workers()

    def finish_worker(self, worker):
        if isValid(worker):
            worker.cancel()
            self.assertTrue(worker.wait(WORKER_TIMEOUT_MS), "Background save did not stop within its deadline")

    def test_sidebar_controls_follow_step_expansion(self):
        sidebar = SidebarDenoise(app=self.app)
        self.addCleanup(sidebar.deleteLater)
        sidebar.show()
        for step in ("sky", "align", "stack", "tune"):
            card = getattr(sidebar, step + "Card")
            settings = getattr(sidebar, step + "Settings")
            card.setStatus("ready")
            for expanded in (True, False):
                with self.subTest(step=step, expanded=expanded):
                    card.setExpanded(expanded)
                    self.qt.processEvents()
                    self.assertEqual(settings.isVisible(), expanded)

    def test_alignment_displays_preparation_and_cached_dark_work_before_frame_progress(self):
        shape = (8, 10, 3)
        light = imwrite(self.root / "light.tif", np.full(shape, 5000, np.uint16))
        darks = [
            imwrite(self.root / f"dark{i}.tif", np.full(shape, value, np.uint16))
            for i, value in enumerate((1000, 1001))
        ]
        config = DenoiseProject(
            str(self.root / "align.proj_denoise"),
            star_images=[light],
            noise_images=darks,
            use_gpu=False,
            taper_mask_edges=False,
        )
        window = MainWindow(self.make_app(config))
        ui = window.ui
        # A running task keeps the overlay visible until its worker finishes.
        ui.current_running_task = "alignStars"
        self.addCleanup(setattr, ui, "current_running_task", None)
        for cached in (False, True):
            with self.subTest(cached=cached):
                updater = ProgressBarUpdater(ui.progressBar, ui.label_progressBar, total=1, file=StringIO())
                self.addCleanup(updater.close)
                visible = []

                def observe(total, increment, count, done, data):
                    ui.slotIncrementProgressBar(updater, total, increment, count, done, data)
                    if data:
                        visible.append(
                            (
                                count,
                                ui.progressOverlay.label_progressBar.text(),
                                ui.progressBar.maximum(),
                                ui.progressOverlay.label_progressPercent.text(),
                            )
                        )

                aligner = AlignStars()
                aligner.addObserver(observe)
                result = aligner.align(config, warp_frames=False)
                preparing = [event for event in visible if event[0] == 0]
                self.assertTrue(preparing)
                self.assertTrue(all(maximum == 0 and percent == "Working" for _, _, maximum, percent in preparing))
                if cached:
                    self.assertTrue(
                        any("Loading cached master dark" in description for _, description, _, _ in preparing)
                    )
                else:
                    self.assertTrue(any("Reading dark frame 2/2" in description for _, description, _, _ in preparing))
                    self.assertTrue(
                        any("Combining dark frames: 100%" in description for _, description, _, _ in preparing)
                    )
                self.assertTrue(any("Reading reference frame" in description for _, description, _, _ in preparing))
                self.assertEqual(visible[-1][0], 1)
                self.assertEqual(visible[-1][2:], (100, "100%"))
                np.testing.assert_allclose(result.base_calibrated, (5000 - 1000.5) / 65535, atol=1e-7, rtol=0)

    def test_queued_result_cannot_publish_after_project_switch(self):
        published = []
        self.view._post_result(self.view._generation, lambda: published.append(True))
        self.app.project = DenoiseProject(str(self.root / "second.proj_denoise"))
        self.view.reset_project_view()
        self.qt.processEvents()
        self.assertEqual(published, [])
        self.assertTrue(self.shell.canvas_main.pixmap.isNull())

    def test_stale_save_discards_staging_and_preserves_destination(self):
        destination, staged = self.root / "final.tif", self.root / "stage.tif"
        destination.write_bytes(b"valid")
        staged.write_bytes(b"obsolete")
        worker = FinalCompositeSaveWorker(None, {}, destination, self.view._final_save_request_id)
        self.addCleanup(worker.deleteLater)
        worker.project = self.project
        worker.generation = self.view._generation
        self.view._final_save_worker = worker
        self.app.project = DenoiseProject(str(self.root / "second.proj_denoise"))
        self.view._on_final_save_finished(staged, worker.request_id)
        self.assertFalse(staged.exists())
        self.assertEqual(destination.read_bytes(), b"valid")

    def test_queued_error_is_visible_and_input_changes_discard_queued_work(self):
        queued = []
        self.shell.enqueue_task = lambda *args: queued.append(args[-1])
        error_label = QLabel()
        self.view.stack_settings = SimpleNamespace(ui=SimpleNamespace(error=error_label))

        def fail():
            raise OSError("disk full")

        self.view._enqueue_task("stackDenoise", "Stack", 1, "Stack", fail)
        queued.pop()()
        self.qt.processEvents()
        self.assertIn("disk full", error_label.text())
        self.assertFalse(error_label.isHidden())
        executed = []
        self.view._enqueue_task("stackDenoise", "Stack", 1, "Stack", lambda: executed.append(True))
        self.project.invalidate_results()
        queued.pop()()
        self.qt.processEvents()
        self.assertEqual(executed, [])

    def test_background_save_publishes_pixels_and_finishes_without_sleep_polling(self):
        pixels = np.full((16, 20, 3), [0.2, 0.4, 0.6], np.float32)
        mask = np.ones(pixels.shape[:2], np.float32)
        self.view.last_compositor = HorizonCompositor(pixels, pixels, mask, mask)
        sidebar = SidebarDenoise(app=self.app)
        self.addCleanup(sidebar.deleteLater)
        self.view.sidebar = sidebar
        self.view.update_ready_states()
        self.assertEqual(sidebar.tuneCard._status, "ready")
        self.view._dispatch_async_save_final_composite()
        worker = self.view._final_save_worker
        self.addCleanup(self.finish_worker, worker)
        loop = QEventLoop()
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        worker.finished.connect(loop.quit)
        deadline.start(WORKER_TIMEOUT_MS)
        if not worker.isFinished():
            loop.exec()
        deadline.stop()
        self.qt.processEvents()
        self.assertFalse(worker.isRunning() if isValid(worker) else False)
        self.assertIsNotNone(self.project.final_output_path)
        self.assertEqual(sidebar.tuneCard._status, "done")
        np.testing.assert_allclose(
            imread(self.project.final_output_path, to_rgb=True, as_float=True), pixels, atol=0.5 / 65535 + 1e-7, rtol=0
        )
        self.assertFalse(list(self.project.get_output_dir().glob("tmp*")))

    def test_stack_success_schedules_default_tune_autosave(self):
        from startrails.lib.denoise.mask import MaskHandler

        self.project.star_files = [DenoiseInputFile("star.tif", str(self.root / "star.tif"))]
        mask_path = self.project.artifact_path("mask")
        MaskHandler.save_brush_mask(np.ones((4, 4), dtype=np.float32), mask_path)
        self.project.mask_path = str(mask_path)
        sidebar = SidebarDenoise(app=self.app)
        self.addCleanup(sidebar.deleteLater)
        self.view.sidebar = sidebar
        self.view.bind()
        sidebar.stackCard.setExpanded(True)
        self.assertTrue(sidebar.stackCard.is_expanded)
        config = SimpleNamespace(
            stack_method="mean", sigma_clip_threshold=2.0, sigma_clip_iterations=2,
            compress_intermediate_tiffs=False, use_gpu=False, output_path=None,
        )
        pixels = np.zeros((4, 4, 3), np.float32)
        mask = np.ones((4, 4), np.float32)
        compositor = HorizonCompositor(pixels, pixels, mask, mask)
        self.view._output_saved = True
        self.shell.canvas_main = None
        with (
            patch.object(self.view, "_snapshot_config", return_value=config),
            patch.object(self.view, "_enqueue_task", side_effect=lambda *args: args[-1]()),
            patch.object(self.view, "_post_result", side_effect=lambda _, callback: callback()),
            patch.object(self.view, "_schedule_horizon_tuning") as schedule_save,
            patch.object(self.app.workflow, "has_cached_alignment", return_value=True),
            patch.object(self.app.workflow, "do_stack_denoise", return_value=compositor),
        ):
            self.view.do_stack_action()
        self.assertIs(self.view.last_compositor, compositor)
        self.assertFalse(self.view._output_saved)
        self.assertTrue(sidebar.stackCard.is_expanded)
        self.assertFalse(sidebar.tuneCard.is_expanded)
        schedule_save.assert_called_once_with(save=True)

    def test_saved_output_state_restores_only_while_file_exists(self):
        final_output = self.root / "saved_final.tif"
        final_output.write_bytes(b"saved")
        self.project.final_output_path = str(final_output)
        self.view.reset_project_view()
        self.assertTrue(self.view._output_saved)
        final_output.unlink()
        self.view.reset_project_view()
        self.assertFalse(self.view._output_saved)

    def test_window_switches_modes_and_back_without_reusing_old_project(self):
        window = MainWindow(self.make_app())
        self.assertEqual(window.ui.active_view.mode_name, "startrails")
        path = self.root / "denoise.proj_denoise"
        path.write_text(jsonpickle.encode(self.project), encoding="utf-8")
        original = window.ui.app.project
        window.ui.app.loadProject(str(path))
        window.ui.switch_to_project_mode()
        self.assertEqual(window.ui.active_view.mode_name, "denoise")
        self.assertIn("Denoise", window.windowTitle())
        window.ui.app.project = original
        window.ui.app.workflow = window.ui.app._create_workflow(original)
        window.ui.switch_to_project_mode()
        self.assertEqual(window.ui.active_view.mode_name, "startrails")

    def _setup_completed_denoise_sidebar(self):
        shape = (16, 20, 3)
        star_path = self.root / "star_input.tif"
        imwrite(star_path, np.full(shape, 0.2, dtype=np.float32), convertBGR=True)
        self.project.star_files = [DenoiseInputFile(star_path.name, str(star_path))]
        self.project.reference_file = self.project.star_files[0]

        out_dir = self.project.get_output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        mask_path = self.project.artifact_path("mask")
        from startrails.lib.denoise.mask import MaskHandler

        mask = np.zeros(shape[:2], dtype=np.float32)
        mask[:8, :] = 1.0
        MaskHandler.save_brush_mask(mask, mask_path)
        self.project.mask_path = str(mask_path)
        self.project.homographies = {str(star_path): np.eye(3).tolist()}
        self.project.alignment_signature = self.project.source_signature()

        sky_stack = np.full(shape, 0.6, dtype=np.float32)
        ground_stack = np.full(shape, 0.4, dtype=np.float32)
        sky_path = self.project.artifact_path("sky_stack")
        ground_path = self.project.artifact_path("ground_stack")
        imwrite(sky_path, sky_stack, convertBGR=True)
        imwrite(ground_path, ground_stack, convertBGR=True)
        self.project.sky_stack_path = str(sky_path)
        self.project.ground_stack_path = str(ground_path)

        grad_mask = np.zeros(shape[:2], dtype=np.float32)
        grad_path = self.project.artifact_path("gradient_mask")
        MaskHandler.save_mask(grad_mask, grad_path)
        self.project.gradient_mask_path = str(grad_path)

        compositor = HorizonCompositor(sky_stack, ground_stack, grad_mask, mask)
        base_comp_path = out_dir / "base_composite.tif"
        imwrite(base_comp_path, compositor.base_composite, convertBGR=True)
        self.project.output_path = str(out_dir / f"{self.project.get_project_stem()}.tif")
        self.project.record_stacks()

        final_path = out_dir / f"{self.project.get_project_stem()}_final.tif"
        imwrite(final_path, np.full(shape, 0.85, dtype=np.float32), convertBGR=True)
        self.project.final_output_path = str(final_path)

        sidebar = SidebarDenoise(app=self.app)
        self.addCleanup(sidebar.deleteLater)
        self.view.sidebar = sidebar
        self.view.bind()
        self.view.reset_project_view()
        sidebar.show()
        self.shell.canvas_main.show()
        self.qt.processEvents()
        return sidebar, star_path, base_comp_path, final_path

    def _canvas_center_rgb(self):
        img = self.shell.canvas_main.pixmap.toImage()
        c = QColor(img.pixel(img.width() // 2, img.height() // 2))
        return c.red(), c.green(), c.blue()

    def test_step3_before_after_toggles_input_and_stacked_composite(self):
        sidebar, star_path, base_comp_path, _ = self._setup_completed_denoise_sidebar()

        # Hidden while collapsed even when done.
        self.assertEqual(sidebar.stackCard.status, "done")
        self.assertFalse(sidebar.stackCard.ui.previewToggle.isVisible())

        # Expanding Step 3 displays the stacked sky+ground composite ("after") and shows the eye chip.
        sidebar.stackCard.setExpanded(True)
        self.qt.processEvents()
        self.assertFalse(sidebar.starFiles.ui.toggle.isChecked())
        self.assertFalse(sidebar.outputFiles.ui.toggle.isChecked())
        self.assertTrue(sidebar.stackCard.ui.previewToggle.isVisible())
        self.assertFalse(sidebar.stackCard.ui.previewToggle.isChecked())
        self.assertEqual(Path(self.shell.canvas_main.file.path).resolve(), base_comp_path.resolve())
        self.assertFalse(self.shell.canvas_main.is_mask_edit_mode())
        after_rgb = self._canvas_center_rgb()

        # Toggling before shows the clean input image without expanding collapsed file sections.
        sidebar.stackCard.ui.previewToggle.click()
        self.qt.processEvents()
        self.assertTrue(sidebar.stackCard.ui.previewToggle.isChecked())
        self.assertFalse(sidebar.starFiles.ui.toggle.isChecked())
        self.assertFalse(sidebar.outputFiles.ui.toggle.isChecked())
        self.assertEqual(Path(self.shell.canvas_main.file.path).resolve(), star_path.resolve())
        self.assertFalse(self.shell.canvas_main.is_mask_edit_mode())
        before_rgb = self._canvas_center_rgb()
        self.assertLess(before_rgb[0], after_rgb[0])

        # Toggling again restores the stacked composite ("after") without expanding file sections.
        sidebar.stackCard.ui.previewToggle.click()
        self.qt.processEvents()
        self.assertFalse(sidebar.stackCard.ui.previewToggle.isChecked())
        self.assertFalse(sidebar.starFiles.ui.toggle.isChecked())
        self.assertFalse(sidebar.outputFiles.ui.toggle.isChecked())
        self.assertEqual(Path(self.shell.canvas_main.file.path).resolve(), base_comp_path.resolve())
        self.assertEqual(self._canvas_center_rgb(), after_rgb)

        # Collapsing while showing "before" resets the toggle and restores the stacked composite.
        sidebar.stackCard.ui.previewToggle.click()
        self.qt.processEvents()
        self.assertEqual(Path(self.shell.canvas_main.file.path).resolve(), star_path.resolve())
        sidebar.stackCard.setExpanded(False)
        self.qt.processEvents()
        self.assertFalse(sidebar.stackCard.ui.previewToggle.isVisible())
        self.assertFalse(sidebar.stackCard.ui.previewToggle.isChecked())
        self.assertEqual(Path(self.shell.canvas_main.file.path).resolve(), base_comp_path.resolve())

    def test_step4_before_after_toggles_stacked_and_final_composite(self):
        sidebar, _, base_comp_path, final_path = self._setup_completed_denoise_sidebar()

        # Hidden while collapsed even when done.
        self.assertEqual(sidebar.tuneCard.status, "done")
        self.assertFalse(sidebar.tuneCard.ui.previewToggle.isVisible())

        # Expanding Step 4 displays the final composite ("after") and shows the eye chip.
        sidebar.tuneCard.setExpanded(True)
        self.qt.processEvents()
        self.assertFalse(sidebar.outputFiles.ui.toggle.isChecked())
        self.assertTrue(sidebar.tuneCard.ui.previewToggle.isVisible())
        self.assertFalse(sidebar.tuneCard.ui.previewToggle.isChecked())
        self.assertEqual(Path(self.shell.canvas_main.file.path).resolve(), final_path.resolve())
        final_rgb = self._canvas_center_rgb()

        # Toggling before shows the stacked composite ("before") with no horizon overlay or section expansion.
        sidebar.tuneCard.ui.previewToggle.click()
        self.qt.processEvents()
        self.assertTrue(sidebar.tuneCard.ui.previewToggle.isChecked())
        self.assertFalse(sidebar.outputFiles.ui.toggle.isChecked())
        self.assertEqual(Path(self.shell.canvas_main.file.path).resolve(), base_comp_path.resolve())
        self.assertEqual(self.shell.canvas_main._horizon_overlay_patches, [])
        stacked_rgb = self._canvas_center_rgb()
        self.assertLess(stacked_rgb[0], final_rgb[0])

        # Stale horizon overlay patches arriving while viewing "before" are ignored.
        patch_arr = np.full((4, 4, 3), 1.0, dtype=np.float32)
        self.view._on_horizon_patches_ready([(patch_arr, (0, 0, 4, 4))], self.view._horizon_request_id)
        self.assertEqual(self.shell.canvas_main._horizon_overlay_patches, [])

        # Toggling again restores the final composite ("after") without expanding file sections.
        sidebar.tuneCard.ui.previewToggle.click()
        self.qt.processEvents()
        self.assertFalse(sidebar.tuneCard.ui.previewToggle.isChecked())
        self.assertFalse(sidebar.outputFiles.ui.toggle.isChecked())
        self.assertEqual(Path(self.shell.canvas_main.file.path).resolve(), final_path.resolve())
        self.assertEqual(self._canvas_center_rgb(), final_rgb)

        # Collapsing while showing "before" resets the toggle and restores the final composite.
        sidebar.tuneCard.ui.previewToggle.click()
        self.qt.processEvents()
        self.assertEqual(Path(self.shell.canvas_main.file.path).resolve(), base_comp_path.resolve())
        sidebar.tuneCard.setExpanded(False)
        self.qt.processEvents()
        self.assertFalse(sidebar.tuneCard.ui.previewToggle.isVisible())
        self.assertFalse(sidebar.tuneCard.ui.previewToggle.isChecked())
        self.assertEqual(Path(self.shell.canvas_main.file.path).resolve(), final_path.resolve())
