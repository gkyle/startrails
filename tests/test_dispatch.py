"""User settings are validated and captured when work is submitted."""

from types import SimpleNamespace
from concurrent.futures import CancelledError
from threading import Thread
from unittest.mock import patch

from support import QtTestCase
from startrails.ui import ui_wrap
from startrails.lib.file import InputFile
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.signals import Signals
from PySide6.QtWidgets import QLabel, QProgressBar


class RecordingQueue:
    def __init__(self):
        self.workers = []

    def start(self, worker):
        self.workers.append(worker)


class DispatchTests(QtTestCase):
    def make_ui(self, files):
        app = SimpleNamespace(
            getWindowSettings=lambda: {},
            getInputFileList=lambda: files,
            stackSuggestBatchSize=lambda file, gpu: (8, 1024**3, False),
        )
        ui = ui_wrap.Ui_AppWindow(app)
        ui.sidebar = ui_wrap.Sidebar(app)
        ui.inputFiles = ui.sidebar.inputs
        ui.inputFiles.set_files(files)
        ui.pushButton_stackImages = ui.sidebar.stack.ui.run
        ui.pushButton_removeStreaks = ui.sidebar.detect.ui.run
        ui.pushButton_exportMasks = ui.sidebar.tools.ui.masks
        ui.pushButton_exportTraining = ui.sidebar.exports.ui.training
        ui.pushButton_contribute = getattr(ui.sidebar.exports.ui, "contribute", None)
        ui.checkBox_showDeletedMasks = ui.sidebar.exports.ui.showDeletedMasks
        ui.pushButton_fillGaps = ui.sidebar.fill.ui.run
        self.addCleanup(ui.deleteLater)
        return ui

    def test_readiness_does_not_require_detection(self):
        file = InputFile("input.jpg", "input.jpg")
        ui = self.make_ui([])
        self.assertEqual(ui.sidebar.toolsCard.title, "Contribute and Export")
        self.assertEqual(ui.sidebar.toolsCard.subtitle, "Export artifacts")
        self.assertFalse(ui.sidebar.toolsCard.has_number)
        self.assertIsNone(getattr(ui.sidebar.review.ui, "training", None))
        self.assertIsNone(getattr(ui.sidebar.review.ui, "contribute", None))
        self.assertIsNotNone(getattr(ui.sidebar.tools.ui, "training", None))
        self.assertIsNotNone(getattr(ui.sidebar.tools.ui, "contribute", None))
        ui.updateReadyStates()
        self.assertFalse(ui.pushButton_stackImages.isEnabled())
        self.assertEqual(ui.sidebar.toolsCard.ui.number.text(), "")
        self.assertEqual(ui.sidebar.toolsCard.ui.number.property("stepStatus"), "neutral")
        ui.app.getInputFileList = lambda: [file]
        ui.inputFiles.set_files([file])
        ui.updateReadyStates()
        self.assertTrue(ui.pushButton_stackImages.isEnabled())
        self.assertTrue(ui.pushButton_removeStreaks.isEnabled())
        self.assertFalse(ui.pushButton_exportMasks.isEnabled())
        self.assertFalse(ui.pushButton_exportTraining.isEnabled())
        if ui.pushButton_contribute is not None:
            self.assertFalse(ui.pushButton_contribute.isEnabled())
        self.assertEqual(ui.sidebar.toolsCard.ui.number.text(), "")
        self.assertEqual(ui.sidebar.toolsCard.ui.number.property("stepStatus"), "neutral")
        file.streaksManualMasks.append([[0, 0], [1, 1]])
        ui.inputFiles.model.update_file(file)
        ui.updateReadyStates()
        self.assertTrue(ui.pushButton_exportMasks.isEnabled())
        self.assertTrue(ui.pushButton_exportTraining.isEnabled())
        if ui.pushButton_contribute is not None:
            self.assertTrue(ui.pushButton_contribute.isEnabled())
        self.assertEqual(ui.sidebar.toolsCard.ui.number.text(), "!")
        self.assertEqual(ui.sidebar.toolsCard.ui.number.property("stepStatus"), "ready")

    def test_progress_works_without_console_and_keeps_frame_counts(self):
        bar = QProgressBar()
        label = QLabel()
        self.addCleanup(bar.deleteLater)
        self.addCleanup(label.deleteLater)
        with patch("sys.stdout", None), patch("sys.stderr", None):
            with ProgressBarUpdater(bar, label, total=2, desc="Detecting streaks") as updater:
                updater.update(1)
                self.assertEqual(updater.n, 1)
                self.assertEqual(bar.value(), 50)
                self.assertEqual(label.text(), "Detecting streaks")
                updater.update(1)
                self.assertEqual(updater.n, 2)
                self.assertEqual(bar.value(), 100)

    def test_worker_failure_is_logged_reported_and_allows_retry(self):
        ui = self.make_ui([])
        ui.op_queue = RecordingQueue()
        ui.signals = Signals(ui)
        ui.signals.task_failed.connect(ui._show_task_error)

        def fail():
            raise RuntimeError("Model could not be loaded")

        with patch("startrails.ui.ui_wrap.QMessageBox.warning") as warning:
            ui.enqueue_task("detectStreaks", "Detect Streaks", 1, "", fail)
            with self.assertLogs("startrails.ui.ui_wrap", level="ERROR") as records:
                worker = Thread(target=ui.op_queue.workers[0].run)
                worker.start()
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive())
            self.assertFalse(warning.called)
            self.qt.processEvents()
            self.assertIn("Model could not be loaded", "\n".join(records.output))
            warning.assert_called_once()
            self.assertIn("Model could not be loaded", warning.call_args.args[2])
            self.assertFalse(ui.enqueued_tasks)
            self.assertIsNone(ui.current_running_task)
            self.assertTrue(ui.enqueue_task("detectStreaks", "Detect Streaks", 1, "", lambda: None))

    def test_cancelled_worker_is_not_reported_as_failure(self):
        ui = self.make_ui([])
        ui.op_queue = RecordingQueue()
        ui.signals = Signals(ui)
        ui.signals.task_failed.connect(ui._show_task_error)

        def cancel():
            raise CancelledError()

        with patch("startrails.ui.ui_wrap.QMessageBox.warning") as warning:
            ui.enqueue_task("detectStreaks", "Detect Streaks", 1, "", cancel)
            ui.op_queue.workers[0].run()
            self.qt.processEvents()
            warning.assert_not_called()
            self.assertFalse(ui.enqueued_tasks)

    def test_settings_are_captured_per_submission(self):
        file = InputFile("input.jpg", "input.jpg")
        ui = self.make_ui([file])
        ui.op_queue = RecordingQueue()
        ui.progressBar = ui.label_progressBar = None
        ui.signals = SimpleNamespace(
            start_task_progress=SimpleNamespace(emit=lambda *args: None),
            finish_task_progress=SimpleNamespace(emit=lambda *args: None),
            drawOutputFileList=SimpleNamespace(emit=lambda _: None),
            refreshReadiness=SimpleNamespace(emit=lambda: None),
        )
        calls = []
        ui.app.doDetectStreaks = lambda tick, **settings: calls.append(("detect", settings))
        ui.app.doStack = lambda remove, tick, **settings: calls.append(("stack", remove, settings))
        ui.sidebar.detect.ui.confidence.setValue(0.45)
        ui.doDetectStreaks()
        # Duplicate submission is ignored while task is already enqueued
        ui.doDetectStreaks()
        self.assertEqual(len(ui.op_queue.workers), 1)

        with patch.object(ui_wrap, "ProgressBarUpdater", return_value=SimpleNamespace(tick=lambda: None)):
            ui.op_queue.workers[0].work()

        ui.sidebar.detect.ui.confidence.setValue(0.8)
        ui.doDetectStreaks()
        ui.sidebar.stack.ui.batchSize.setValue(6)
        ui.doStack()
        ui.sidebar.stack.ui.batchSize.setValue(17)
        self.assertEqual(len(ui.op_queue.workers), 3)
        with patch.object(ui_wrap, "ProgressBarUpdater", return_value=SimpleNamespace(tick=lambda: None)):
            for worker in ui.op_queue.workers[1:]:
                worker.work()
        self.assertEqual(calls[0][1]["confThreshold"], 0.45)
        self.assertEqual(calls[1][1]["confThreshold"], 0.8)
        self.assertFalse(calls[2][1])
        self.assertEqual(calls[2][2]["batchSize"], 6)

    def test_invalid_settings_do_not_enqueue(self):
        ui = self.make_ui([InputFile("input.jpg", "input.jpg")])
        ui.op_queue = RecordingQueue()
        ui.sidebar.detect.ui.confidence.lineEdit().setText("")
        ui.doDetectStreaks()
        ui.sidebar.stack.ui.batchSize.lineEdit().setText("")
        ui.doStack()
        self.assertEqual(ui.op_queue.workers, [])

    def test_contribute_training_dispatch(self):
        from support import qt_app
        from startrails.ui.views.startrails import StarTrailsView

        file = InputFile("input.jpg", "input.jpg")
        ui = self.make_ui([file])
        ui.op_queue = RecordingQueue()
        ui.progressBar = ui.label_progressBar = None
        ui.signals = SimpleNamespace(
            start_task_progress=SimpleNamespace(emit=lambda *args: None),
            finish_task_progress=SimpleNamespace(emit=lambda *args: None),
        )
        contribute_calls = []
        ui.app.doContributeTrainingStreaks = lambda tick, **kwargs: (
            contribute_calls.append(kwargs) or {"status": "accepted", "submission_id": "sub-123", "file_count": 2, "size_bytes": 500}
        )

        with patch("startrails.ui.contribute_dialog.ContributeCorrectionsDialog.exec", return_value=1), \
             patch("startrails.ui.contribute_dialog.ContributeCorrectionsDialog.values", return_value=("user@example.com", "My test notes")):
            ui.doContributeTrainingStreaks()

        self.assertEqual(len(ui.op_queue.workers), 1)
        with patch.object(ui_wrap, "ProgressBarUpdater", return_value=SimpleNamespace(tick=lambda: None)), \
             patch.object(StarTrailsView, "_notify_contribution_result") as mock_notify:
            worker_thread = Thread(target=ui.op_queue.workers[0].work)
            worker_thread.start()
            worker_thread.join()
            qt_app().processEvents()

        self.assertEqual(len(contribute_calls), 1)
        self.assertEqual(contribute_calls[0]["user_email"], "user@example.com")
        self.assertEqual(contribute_calls[0]["user_comments"], "My test notes")
        mock_notify.assert_called_once()
