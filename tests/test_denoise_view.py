"""Project ownership of queued results, errors, and real background publication."""

from types import SimpleNamespace

import jsonpickle
import numpy as np
from PySide6.QtCore import QEventLoop, QObject, QTimer
from PySide6.QtWidgets import QLabel
from shiboken6 import isValid

from support import QtTestCase
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor
from startrails.lib.image_io import imread
from startrails.lib.project_denoise import DenoiseProject
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.ui_wrap import MainWindow
from startrails.ui.views.denoise import DenoiseView
from startrails.ui.workers_denoise import FinalCompositeSaveWorker

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
        np.testing.assert_allclose(
            imread(self.project.final_output_path, to_rgb=True, as_float=True), pixels, atol=0.5 / 65535 + 1e-7, rtol=0
        )
        self.assertFalse(list(self.project.get_output_dir().glob("tmp*")))

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
