"""Project ownership of queued results, errors, and real background publication."""

from types import SimpleNamespace
from io import StringIO
from unittest.mock import patch

import jsonpickle
import numpy as np
from PySide6.QtCore import QEventLoop, QObject, QTimer
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
        self.project.star_files = [DenoiseInputFile("star.tif", str(self.root / "star.tif"))]
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
