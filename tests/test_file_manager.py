"""File imports, identity, selection, and preview signals."""

from unittest.mock import patch

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QFileDialog, QMessageBox

from support import QtTestCase
from startrails.lib.file import InputFile, OutputFile
from startrails.lib.image_io import imwrite
from startrails.lib.project_denoise import DenoiseProject
from startrails.ui.file_manager import FileModel, FileSection
from startrails.ui.ui_wrap import MainWindow


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


class FileImportTests(QtTestCase):
    def make_import_window(self, target, existing):
        project = None if target == "inputs" else DenoiseProject(str(self.root / "test.proj_denoise"))
        app = self.make_app(project)
        if target == "inputs":
            lists = {"inputs": app.getInputFileList}
            if existing:
                app.addInputFiles([str(self.root / "star.tif")])
        else:
            lists = {"stars": app.workflow.get_star_files, "darks": app.workflow.get_noise_files}
            if existing:
                app.workflow.add_star_files([str(self.root / "star.tif")])
                app.workflow.add_noise_files([str(self.root / "dark.tif")])
        window = MainWindow(app)
        self.addCleanup(window.close)
        sidebar = window.ui.active_view.sidebar
        sections = (
            {"inputs": sidebar.inputs}
            if target == "inputs"
            else {
                "stars": sidebar.starFiles,
                "darks": sidebar.noiseFiles,
            }
        )
        return window, sections[target], lists

    def test_add_controls_replace_append_and_preserve_files_on_cancel(self):
        for name in ("star", "dark", "new"):
            imwrite(self.root / f"{name}.tif", np.zeros((4, 4, 3), np.uint16))
        new_path = str(self.root / "new.tif")
        yes, no = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
        cases = ((True, yes, [new_path]), (True, no, [new_path]), (True, yes, []), (False, no, [new_path]))
        for target in ("inputs", "stars", "darks"):
            for existing, reply, selected in cases:
                with self.subTest(target=target, existing=existing, reply=reply, selected=selected):
                    window, section, lists = self.make_import_window(target, existing)
                    before = {name: [str(file.path) for file in get_files()] for name, get_files in lists.items()}
                    with (
                        patch.object(QMessageBox, "question", return_value=reply) as question,
                        patch.object(QFileDialog, "getOpenFileNames", return_value=(selected, "")),
                    ):
                        section.ui.add.click()
                    self.assertEqual(question.call_count, int(existing))
                    expected = selected if reply == yes and selected else before[target] + selected
                    self.assertCountEqual([str(file.path) for file in lists[target]()], expected)
                    for name, get_files in lists.items():
                        if name != target:
                            self.assertEqual([str(file.path) for file in get_files()], before[name])
                    window.close()
