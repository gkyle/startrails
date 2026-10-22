"""User settings are validated and captured when work is submitted."""

from types import SimpleNamespace
from threading import Thread
from unittest.mock import patch

from support import QtTestCase
from startrails.ui import ui_wrap
from startrails.lib.file import InputFile


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
