"""Real startup selection and actionable feedback at the modal-dialog boundary."""

from unittest.mock import patch

import jsonpickle

from support import QtTestCase
from main import create_main_window
from startrails.lib.project_denoise import DenoiseProject


class StartupTests(QtTestCase):
    def test_valid_project_opens_while_no_argument_shows_selection(self):
        path = self.root / "valid.proj_denoise"
        path.write_text(jsonpickle.encode(DenoiseProject(str(path))), encoding="utf-8")
        for argument in (None, str(path)):
            with self.subTest(argument=argument), patch("main.QMessageBox.warning") as warning:
                app = self.make_app()
                window = create_main_window(app, argument)
                self.assertEqual(window.project_overlay.isVisible(), argument is None)
                if argument:
                    self.assertIsInstance(app.project, DenoiseProject)
                    self.assertEqual(app.project.project_file, str(path))
                warning.assert_not_called()
                window.close()

    def test_missing_or_invalid_project_reports_error_and_shows_selection(self):
        invalid = self.root / "invalid.proj_denoise"
        invalid.write_text("not a project", encoding="utf-8")
        for path in (self.root / "missing.proj_denoise", invalid):
            with self.subTest(path=path), patch("main.QMessageBox.warning") as warning:
                app = self.make_app()
                previous = app.project
                window = create_main_window(app, str(path))
                self.assertTrue(window.project_overlay.isVisible())
                self.assertIs(app.project, previous)
                self.assertEqual(warning.call_count, 1)
                self.assertIn(str(path), warning.call_args.args[2])
                window.close()
