"""Exercise real window widgets with an in-memory application interface."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import hashlib
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QPoint, QPointF
from PySide6.QtGui import QPixmap, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
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

    def test_designer_forms_load(self):
        from PySide6.QtUiTools import QUiLoader
        loader = QUiLoader()
        directory = Path(__file__).resolve().parents[1] / "src/startrails/ui"
        for path in directory.glob("*.ui"):
            widget = loader.load(str(path))
            self.assertIsNotNone(widget, f"{path.name}: {loader.errorString()}")
            widget.deleteLater()

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
        self.assertTrue(second.excludeFromStack)
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
            self.ui.signals.fileMetadataChanged.emit(file)
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

    def test_canvas_annotations_update_counts_and_remain_editable(self):
        import numpy as np
        file = InputFile("image", "missing-image")
        self.app.inputs = [file]
        self.ui.slotRefreshInputs(file)
        canvas = self.ui.canvas_main
        pixmap = QPixmap(512, 512)
        pixmap.fill(Qt.black)
        canvas.setPixmap(pixmap)
        QT_APP.processEvents()

        def point(x, y):
            return QPoint(round(canvas.posX + x * canvas.scale), round(canvas.posY + y * canvas.scale))

        for vertices in (((100, 100), (200, 100), (200, 200)), ((250, 100), (350, 100), (350, 200))):
            for vertex in vertices:
                QTest.mouseClick(canvas, Qt.RightButton, pos=point(*vertex))
            QTest.mouseClick(canvas, Qt.LeftButton, pos=point(450, 450))
        self.assertEqual(self.ui.inputFiles.model.index(0, 1).data(), "M:2")
        before = file.streaksManualMasks[0].copy()
        start, end = point(170, 120), point(180, 130)
        QTest.mousePress(canvas, Qt.LeftButton, pos=start)
        move = QMouseEvent(QEvent.MouseMove, QPointF(end), QPointF(canvas.mapToGlobal(end)), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(canvas, move)
        QTest.mouseRelease(canvas, Qt.LeftButton, pos=end)
        self.assertFalse(np.array_equal(file.streaksManualMasks[0], before))
        QTest.mouseClick(canvas, Qt.LeftButton, Qt.ShiftModifier, point(180, 130))
        self.assertEqual(self.ui.inputFiles.model.index(0, 1).data(), "M:1")
        self.assertTrue(self.ui.pushButton_exportTraining.isEnabled())

    def test_keyboard_navigation_and_step_expansion(self):
        files = [InputFile("a", "a"), InputFile("b", "b")]
        self.app.inputs = files
        self.ui.slotRefreshInputs(files[0])
        view = self.ui.inputFiles.ui.files
        view.setFocus()
        QTest.keyClick(view, Qt.Key_Down)
        self.assertIs(self.ui.currentFile, files[1])
        toggle = self.ui.sidebar.stackCard.ui.toggle
        toggle.setFocus()
        QTest.keyClick(toggle, Qt.Key_Space)
        self.assertTrue(toggle.isChecked())

    def test_canvas_zoom_pan_and_brightest_frame_dispatch(self):
        file = InputFile("input", "input")
        stacked = OutputFile("stacked", "stacked", "Stacked")
        self.app.inputs = [file]
        self.app.outputs = [stacked]
        self.ui.slotRefreshInputs()
        self.ui.slotRefreshOutputs(stacked)
        canvas = self.ui.canvas_main
        pixmap = QPixmap(512, 512)
        pixmap.fill(Qt.black)
        canvas.setPixmap(pixmap)
        QT_APP.processEvents()
        local = QPoint(round(canvas.posX + 200 * canvas.scale), round(canvas.posY + 200 * canvas.scale))
        calls = []
        self.app.doFindBrightFrame = lambda x, y, basis, tick: calls.append((x, y, basis)) or file
        with patch.object(ui_wrap, "ProgressBarUpdater", return_value=SimpleNamespace(tick=lambda: None)):
            QTest.mouseClick(canvas, Qt.LeftButton, Qt.ShiftModifier, local)
            self.assertTrue(self.ui.op_queue.waitForDone(3000))
        QT_APP.processEvents()
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][2], stacked)
        self.assertLessEqual(abs(calls[0][0] - 200), 1)
        self.assertIs(self.ui.currentFile, file)
        self.assertIs(self.ui.inputFiles.current_file(), file)

        wheel = QWheelEvent(QPointF(local), QPointF(canvas.mapToGlobal(local)), QPoint(), QPoint(0, 120),
                            Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        QApplication.sendEvent(canvas, wheel)
        QTest.qWait(15)
        self.assertGreater(canvas.zoom_factor, 1)
        previous = canvas.posX, canvas.posY
        end = local + QPoint(20, 30)
        QTest.mousePress(canvas, Qt.LeftButton, pos=local)
        move = QMouseEvent(QEvent.MouseMove, QPointF(end), QPointF(canvas.mapToGlobal(end)), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(canvas, move)
        QTest.mouseRelease(canvas, Qt.LeftButton, pos=end)
        self.assertNotEqual((canvas.posX, canvas.posY), previous)
        QTest.mouseDClick(canvas, Qt.LeftButton, pos=end)
        self.assertEqual(canvas.zoom_factor, 1)


if __name__ == "__main__":
    unittest.main()
