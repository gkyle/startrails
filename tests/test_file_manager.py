"""File identity, selection, preview signals, and timestamp sorting."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

from support import QtTestCase
from startrails.lib.file import InputFile, OutputFile
from startrails.ui.file_manager import FileModel, FileSection


class FileModelTests(QtTestCase):
    def test_identity_annotations_and_targeted_updates(self):
        model = FileModel()
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
        first.streaksMasks.append([])
        model.update_file(first)
        self.assertIs(model.index_for_file(second).data(Qt.UserRole), second)
        model.remove_file(first)
        self.assertEqual(model.index_for_file(second).row(), 0)

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
        self.assertEqual(section.model.rowCount(), 0)

    def test_click_on_already_selected_item_emits_show_file(self):
        section = FileSection("Input Files", inputs=True)
        f1 = InputFile("a.jpg", "a.jpg")
        f2 = InputFile("b.jpg", "b.jpg")
        section.set_files([f1, f2])

        # Select f1
        section.ui.files.setCurrentIndex(section.model.index(0, 0))
        previews = QSignalSpy(section.showFile)

        # Clicking on f1 when it is already selected must still emit showFile
        section.ui.files.clicked.emit(section.model.index(0, 0))
        self.assertEqual(previews.count(), 1)
        self.assertIs(previews.at(0)[0], f1)

        # Activating f1 (e.g. Return/Enter) must also emit showFile
        section.ui.files.activated.emit(section.model.index(0, 0))
        self.assertEqual(previews.count(), 2)
        self.assertIs(previews.at(1)[0], f1)

        section.close()
