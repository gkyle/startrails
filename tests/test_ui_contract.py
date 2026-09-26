"""Small UI contract checks; no ML models, project writes, or GPU required."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QPushButton

# The window only needs an App interface. Avoid importing processing backends here.
app_module = ModuleType("startrails.app")
app_module.App = object
with patch.dict("sys.modules", {"startrails.app": app_module}):
    from startrails.ui import ui_wrap

from startrails.lib.file import InputFile, OutputFile
from startrails.ui.signals import AsyncWorker

QT_APP = QApplication.instance() or QApplication([])


class RecordingQueue:
    def __init__(self):
        self.workers = []

    def start(self, worker):
        self.workers.append(worker)


class DispatchContractTests(unittest.TestCase):
    def make_ui(self, files):
        app = SimpleNamespace(getWindowSettings=lambda: {}, getInputFileList=lambda: files)
        ui = ui_wrap.Ui_AppWindow(app)
        for name in ("stackImages", "removeStreaks", "exportMasks", "exportTraining"):
            setattr(ui, "pushButton_" + name, QPushButton())
        return ui

    def test_readiness_does_not_require_detection(self):
        file = InputFile("input.jpg", "input.jpg")
        ui = self.make_ui([])
        ui.updateReadyStates()
        self.assertFalse(ui.pushButton_stackImages.isEnabled())
        ui.app.getInputFileList = lambda: [file]
        ui.updateReadyStates()
        self.assertTrue(ui.pushButton_stackImages.isEnabled())
        self.assertTrue(ui.pushButton_removeStreaks.isEnabled())
        self.assertFalse(ui.pushButton_exportMasks.isEnabled())
        file.streaksManualMasks.append([[0, 0], [1, 1]])
        ui.updateReadyStates()
        self.assertTrue(ui.pushButton_exportMasks.isEnabled())
        self.assertTrue(ui.pushButton_exportTraining.isEnabled())

    def test_fill_resolves_selection_when_worker_runs(self):
        ui = self.make_ui([])
        ui.op_queue = RecordingQueue()
        ui.progressBar = ui.label_progressBar = None
        ui.signals = SimpleNamespace(drawOutputFileList=SimpleNamespace(emit=lambda _: None))
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
