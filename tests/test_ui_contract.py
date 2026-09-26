"""Small UI contract checks; no ML models, project writes, or GPU required."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

# The window only needs an App interface. Avoid importing processing backends here.
app_module = ModuleType("startrails.app")
app_module.App = object
previous_app_module = sys.modules.get("startrails.app")
sys.modules["startrails.app"] = app_module
try:
    from startrails.ui import ui_wrap
finally:
    if previous_app_module is None:
        del sys.modules["startrails.app"]
    else:
        sys.modules["startrails.app"] = previous_app_module

from startrails.lib.file import InputFile, OutputFile
from startrails.ui.signals import AsyncWorker

QT_APP = QApplication.instance() or QApplication([])
# The Windows offscreen platform has no system font database. Register fonts for
# realistic layout checks; native application font selection is unchanged.
if sys.platform == "win32" and not QFontDatabase.families():
    for filename in ("segoeui.ttf", "segoeuib.ttf", "arial.ttf", "arialbd.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + filename)
    QT_APP.setFont(QFont("Segoe UI", 9))


class RecordingQueue:
    def __init__(self):
        self.workers = []

    def start(self, worker):
        self.workers.append(worker)


class DispatchContractTests(unittest.TestCase):
    def make_ui(self, files):
        app = SimpleNamespace(getWindowSettings=lambda: {}, getInputFileList=lambda: files,
                              stackSuggestBatchSize=lambda file, gpu: (8, 1024**3, False))
        ui = ui_wrap.Ui_AppWindow(app)
        ui.sidebar = ui_wrap.Sidebar(app)
        ui.inputFiles = ui.sidebar.inputs
        ui.inputFiles.set_files(files)
        ui.pushButton_stackImages = ui.sidebar.stack.ui.run
        ui.pushButton_removeStreaks = ui.sidebar.detect.ui.run
        ui.pushButton_exportMasks = ui.sidebar.exports.ui.masks
        ui.pushButton_exportTraining = ui.sidebar.exports.ui.training
        ui.pushButton_fillGaps = ui.sidebar.fill.ui.run
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

    def test_fill_resolves_selection_when_worker_runs(self):
        ui = self.make_ui([])
        ui.op_queue = RecordingQueue()
        ui.progressBar = ui.label_progressBar = None
        ui.signals = SimpleNamespace(drawOutputFileList=SimpleNamespace(emit=lambda _: None),
                                     refreshReadiness=SimpleNamespace(emit=lambda: None))
        ui.updateReadyStates = lambda: None
        first = OutputFile("first", "first", "Stacked")
        second = OutputFile("second", "second", "Stacked")
        calls = []
        ui.app.doFillGaps = lambda file, tick: calls.append(file) or file
        ui.currentFile = first
        ui.doFillGaps()
        ui.currentFile = second
        with patch.object(ui_wrap, "ProgressBarUpdater", return_value=SimpleNamespace(tick=lambda: None)):
            ui.op_queue.workers[0].work()
        self.assertEqual(calls, [second])

    def test_settings_are_captured_per_submission(self):
        file = InputFile("input.jpg", "input.jpg")
        ui = self.make_ui([file])
        ui.op_queue = RecordingQueue()
        ui.progressBar = ui.label_progressBar = None
        ui.signals = SimpleNamespace(drawOutputFileList=SimpleNamespace(emit=lambda _: None),
                                     refreshReadiness=SimpleNamespace(emit=lambda: None))
        calls = []
        ui.app.doDetectStreaks = lambda tick, **settings: calls.append(("detect", settings))
        ui.app.doStack = lambda remove, tick, **settings: calls.append(("stack", remove, settings))
        ui.sidebar.detect.ui.confidence.setValue(0.45)
        ui.doDetectStreaks()
        ui.sidebar.detect.ui.confidence.setValue(0.8)
        ui.doDetectStreaks()
        ui.sidebar.stack.ui.batchSize.setValue(6)
        ui.doStack()
        ui.sidebar.stack.ui.batchSize.setValue(17)
        self.assertEqual(len(ui.op_queue.workers), 3)
        with patch.object(ui_wrap, "ProgressBarUpdater", return_value=SimpleNamespace(tick=lambda: None)):
            for worker in ui.op_queue.workers:
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

    def test_cancel_does_not_clear_pending_jobs(self):
        ui = self.make_ui([])
        ui.op_queue = RecordingQueue()
        ui.op_queue.start(object())
        calls = []
        ui.app.doInterruptOperation = lambda: calls.append("interrupt")
        ui.doCancelOp()
        self.assertEqual(calls, ["interrupt"])
        self.assertEqual(len(ui.op_queue.workers), 1)

    def test_worker_pool_remains_serial(self):
        pool = QThreadPool()
        pool.setMaxThreadCount(1)
        started = threading.Event()
        release = threading.Event()
        calls = []

        def first():
            calls.append("first start")
            started.set()
            release.wait(3)
            calls.append("first end")

        pool.start(AsyncWorker(first))
        try:
            self.assertTrue(started.wait(3))
            pool.start(AsyncWorker(lambda: calls.append("second")))
            self.assertEqual(calls, ["first start"])
        finally:
            release.set()
            self.assertTrue(pool.waitForDone(3000))
        self.assertEqual(calls, ["first start", "first end", "second"])


if __name__ == "__main__":
    unittest.main()
