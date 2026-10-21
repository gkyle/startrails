"""Theme changes preserve input selection and edited settings."""

from PySide6.QtCore import Qt

from support import QtTestCase
from startrails.lib.file import InputFile
from startrails.ui.theme import is_dark, system_theme
from startrails.ui.ui_wrap import MainWindow


class ThemeTests(QtTestCase):
    def test_scheme_changes_update_existing_window_without_losing_edits(self):
        theme = system_theme()
        previous = Qt.ColorScheme.Dark if theme.dark else Qt.ColorScheme.Light
        self.addCleanup(theme.apply_scheme, previous)
        app = self.make_app()
        file = InputFile("source.tif", str(self.root / "source.tif"))
        app.project.rawInputFiles = [file]
        window = MainWindow(app)
        window.ui.inputFiles.focus_file(file)
        window.ui.sidebar.detect.ui.confidence.setValue(0.63)
        for scheme in (Qt.ColorScheme.Dark, Qt.ColorScheme.Light):
            self.qt.styleHints().colorSchemeChanged.emit(scheme)
            self.qt.processEvents()
            self.assertEqual(is_dark(window.ui.inputFiles.ui.files.palette()), scheme == Qt.ColorScheme.Dark)
            self.assertIs(window.ui.inputFiles.current_file(), file)
            self.assertEqual(window.ui.sidebar.detect.ui.confidence.value(), 0.63)
