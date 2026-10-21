"""User settings are validated and captured when work is submitted."""

from types import SimpleNamespace
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
        ui.checkBox_showDeletedMasks = ui.sidebar.exports.ui.showDeletedMasks
        ui.pushButton_fillGaps = ui.sidebar.fill.ui.run
        self.addCleanup(ui.deleteLater)
        return ui

    def test_readiness_does_not_require_detection(self):
        file = InputFile("input.jpg", "input.jpg")
        ui = self.make_ui([])
        ui.updateReadyStates()
        self.assertFalse(ui.pushButton_stackImages.isEnabled())
        ui.app.getInputFileList = lambda: [file]
        ui.inputFiles.set_files([file])
        ui.updateReadyStates()
        self.assertTrue(ui.pushButton_stackImages.isEnabled())
        self.assertTrue(ui.pushButton_removeStreaks.isEnabled())
        self.assertFalse(ui.pushButton_exportMasks.isEnabled())
        file.streaksManualMasks.append([[0, 0], [1, 1]])
        ui.inputFiles.model.update_file(file)
        ui.updateReadyStates()
        self.assertTrue(ui.pushButton_exportMasks.isEnabled())
        self.assertTrue(ui.pushButton_exportTraining.isEnabled())

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
