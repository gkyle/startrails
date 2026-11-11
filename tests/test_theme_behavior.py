"""Theme changes preserve input selection and edited settings."""

from PySide6.QtCore import Qt

from support import QtTestCase
from startrails.lib.file import InputFile
from startrails.ui.theme import is_dark, system_theme
from startrails.ui.ui_wrap import MainWindow


class ThemeTests(QtTestCase):
    def test_dark_stylesheet_maps_accent_border_color(self):
        from startrails.ui.theme import dark_stylesheet

        styled = dark_stylesheet("border-color: #0284c7; border: 1px solid #0284c7;")
        self.assertIn("border-color: #38bdf8;", styled)
        self.assertIn("border: 1px solid #38bdf8;", styled)

    def test_project_finish_resource_loads_without_filesystem(self):
        from PySide6.QtGui import QPixmap
        import startrails.ui.resources_rc  # noqa: F401

        pix = QPixmap(":/startrails/ui/project_finish.png")
        self.assertFalse(pix.isNull())
        self.assertGreater(pix.width(), 0)
        self.assertGreater(pix.height(), 0)

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
