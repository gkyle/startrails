import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import tracemalloc
import unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QAbstractItemModelTester, QSignalSpy
from PySide6.QtWidgets import QApplication, QWidget
from startrails.lib.file import InputFile, OutputFile
from startrails.ui.file_manager import FileModel, FileSection

QT_APP = QApplication.instance() or QApplication([])


class FileModelTests(unittest.TestCase):
    def test_identity_annotations_and_targeted_updates(self):
        model = FileModel()
        tester = QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Warning)
        first = InputFile("same.jpg", "a/same.jpg")
        second = InputFile("same.jpg", "b/same.jpg")
        model.set_files([first, second])
        updates = QSignalSpy(model.dataChanged)
        resets = QSignalSpy(model.modelReset)
        second.streaksManualDeletedMasks.append([])
        second.excludeFromStack = True
        model.update_file(second)
        self.assertEqual(updates.count(), 1)
        self.assertEqual(resets.count(), 0)
        self.assertEqual(updates.at(0)[0].row(), 1)
        self.assertEqual(model.data(model.index(1, 1)), "D:1 · Excluded")
        self.assertEqual(model.manual_files, {second})
        self.assertEqual(model.mask_files, set())
        first.streaksMasks.append([])
        model.update_file(first)
        self.assertEqual(model.mask_files, {first})
        self.assertIs(model.index_for_file(second).data(Qt.UserRole), second)
        model.remove_file(first)
        self.assertEqual(model.index_for_file(second).row(), 0)
        self.assertEqual(model.mask_files, set())

    def test_output_append_keeps_existing_index(self):
        model = FileModel()
        first = OutputFile("first", "first", "Stacked")
        second = OutputFile("second", "second", "FillGapsMask")
        model.set_files([first])
        resets = QSignalSpy(model.modelReset)
        model.sync_files([first, second])
        self.assertEqual(resets.count(), 0)
        self.assertEqual(model.data(model.index(1, 1)), "FillGapsMask")

    def test_focus_does_not_emit_preview_recursively(self):
        section = FileSection("Input Files", inputs=True)
        files = [InputFile("a", "a"), InputFile("b", "b")]
        section.set_files(files)
        previews = QSignalSpy(section.showFile)
        section.setExpanded(False)
        section.focus_file(files[1])
        self.assertTrue(section.ui.toggle.isChecked())
        self.assertIs(section.current_file(), files[1])
        self.assertEqual(previews.count(), 0)
        section.ui.files.setCurrentIndex(section.model.index(0, 0))
        self.assertEqual(previews.count(), 1)
        section.set_files([])
        self.assertIsNone(section.current_file())
        self.assertFalse(section.ui.remove.isEnabled())

    def test_large_lists_do_not_allocate_row_widgets(self):
        section = FileSection("Input Files", inputs=True)
        section.show()
        QT_APP.processEvents()
        widget_counts = []
        for count in (1000, 5000):
            records = [InputFile(f"image_{i}.jpg", f"missing/{i}.jpg") for i in range(count)]
            start = time.perf_counter()
            tracemalloc.start()
            section.set_files(records)
            QT_APP.processEvents()
            populate = time.perf_counter() - start
            start = time.perf_counter()
            section.focus_file(records[-1])
            records[-1].streaksMasks.append([])
            section.model.update_file(records[-1])
            QT_APP.processEvents()
            update = time.perf_counter() - start
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            widget_counts.append(len(section.findChildren(QWidget)))
            print(f"\n{count} files: populate {populate:.4f}s; focus/update {update:.4f}s; widgets {widget_counts[-1]}; traced peak {peak / 1024:.0f} KiB")
            self.assertEqual(section.model.rowCount(), count)
        self.assertEqual(widget_counts[0], widget_counts[1])
        section.close()


if __name__ == "__main__":
    unittest.main()
