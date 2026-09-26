"""Exercise real window widgets with an in-memory application interface."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import hashlib
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget
from test_ui_contract import ui_wrap
from startrails.lib.file import InputFile, OutputFile

QT_APP = QApplication.instance() or QApplication([])


class FakeApp:
    def __init__(self):
        self.inputs = []
        self.outputs = []
        self.gpuInfo = SimpleNamespace(getGpuPresent=lambda: False)
        self.saves = 0

    def getWindowSettings(self): return {}
    def getInputFileList(self): return self.inputs
    def getOutputFileList(self): return self.outputs
    def doInterruptOperation(self): pass
    def stackSuggestBatchSize(self, file, gpu): return 8, 1024**3, False
    def saveProject(self): self.saves += 1
    def removeInputFile(self, file): self.inputs.remove(file)
    def removeOutputFile(self, file): self.outputs.remove(file)
    def toggleExcludeFromStack(self, file): file.excludeFromStack = not file.excludeFromStack


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.app = FakeApp()
        self.window = ui_wrap.MainWindow(self.app)
        self.ui = self.window.ui
        QT_APP.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_empty_window_and_project_reset(self):
        self.assertFalse(self.ui.pushButton_fillGaps.isEnabled())
        self.assertFalse(self.ui.pushButton_stackImages.isEnabled())
        self.assertIsNone(self.window.findChild(QWidget, "frame_bottom"))
        self.assertIsNone(self.window.findChild(QWidget, "frame_right"))
        self.assertEqual(self.ui.op_queue.maxThreadCount(), 1)
        file = OutputFile("output", "missing-output", "Stacked")
        self.app.outputs.append(file)
        self.ui.slotRefreshOutputs(file)
        self.assertTrue(self.ui.pushButton_fillGaps.isEnabled())
        self.assertIs(self.ui.outputFiles.current_file(), file)
        self.app.outputs = []
        self.ui.resetProjectView()
        self.assertIsNone(self.ui.currentFile)
        self.assertIsNone(self.ui.canvas_main.file)
        self.assertFalse(self.ui.pushButton_fillGaps.isEnabled())
        self.assertEqual(self.ui.label_imageName.text(), "")

    def test_header_matches_pre_migration_form(self):
        path = Path(__file__).resolve().parents[1] / "src/startrails/ui/interface.ui"
        header = ET.parse(path).find('.//widget[@name="toolbar"]')
        canonical = ET.canonicalize(ET.tostring(header, encoding="unicode"), strip_text=True)
        # Canonical toolbar from efb6681: includes every widget/property/layout.
        self.assertEqual(hashlib.sha256(canonical.encode()).hexdigest(),
                         "d34fd643d1ffb93972001a1be7aa30eac07557d7309482436c732928f47b441e")

    def test_annotation_removal_exclusion_and_focus(self):
        first = InputFile("same.jpg", "a/same.jpg")
        second = InputFile("same.jpg", "b/same.jpg")
        self.app.inputs = [first, second]
        self.ui.slotRefreshInputs(first)
        second.streaksMasks.append([])
        first.streaksManualDeletedMasks.append([])
        self.ui.slotUpdateFile(first)
        self.ui.slotUpdateFile(second)
        self.assertTrue(self.ui.pushButton_exportMasks.isEnabled())
        self.assertTrue(self.ui.pushButton_exportTraining.isEnabled())
        self.ui.showFile(second)
        self.ui.slotExcludeFile(second)
        self.assertTrue(self.ui.inputFiles.ui.exclude.isChecked())
        self.ui.slotRemoveFile(second)
        self.assertEqual(self.ui.inputFiles.model.rowCount(), 1)
        self.assertIsNone(self.ui.currentFile)
        self.assertFalse(self.ui.pushButton_exportMasks.isEnabled())
        self.assertTrue(self.ui.pushButton_exportTraining.isEnabled())

    def test_worker_signals_update_gui_thread(self):
        file = InputFile("file", "missing")
        self.app.inputs = [file]
        self.ui.slotRefreshInputs()
        observed_threads = []
        from PySide6.QtCore import QThread
        self.ui.inputFiles.model.dataChanged.connect(lambda *args: observed_threads.append(QThread.currentThread()))
        def worker():
            file.streaksMasks.append([])
            self.ui.signals.updateFileButton.emit(file)
        self.ui.op_queue.start(ui_wrap.AsyncWorker(worker))
        self.assertTrue(self.ui.op_queue.waitForDone(3000))
        QT_APP.processEvents()
        self.assertEqual(observed_threads, [QT_APP.thread()])
        self.assertTrue(self.ui.pushButton_exportMasks.isEnabled())

    def test_detection_completion_refreshes_files_without_previews(self):
        files = [InputFile(str(i), f"missing-{i}") for i in range(25)]
        self.app.inputs = files
        self.ui.slotRefreshInputs()
        def worker():
            for file in files:
                file.streaksMasks.append([])
            self.ui.signals.refreshReadiness.emit()
        self.ui.op_queue.start(ui_wrap.AsyncWorker(worker))
        self.assertTrue(self.ui.op_queue.waitForDone(3000))
        QT_APP.processEvents()
        self.assertEqual(len(self.ui.inputFiles.model.mask_files), 25)
        self.assertEqual(self.ui.inputFiles.model.index(24, 1).data(), "A:1")
        self.assertTrue(self.ui.sidebar.stack.values()["streaksRemoved"])

    def test_preview_and_deleted_masks_control(self):
        import numpy as np
        self.ui.checkBox_showDeletedMasks.setChecked(True)
        self.assertTrue(self.ui.canvas_main.showDeletedMasks)
        updater = SimpleNamespace(update=lambda _: None)
        self.ui.slotIncrementProgressBar(updater, 2, 1, 1, False, np.zeros((16, 16, 3), dtype=np.uint8))
        self.assertEqual(self.ui.canvas_main.pixmap.width(), 16)


if __name__ == "__main__":
    unittest.main()
