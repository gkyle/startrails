"""Real startup selection and actionable feedback at the modal-dialog boundary."""

from contextlib import chdir
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
from unittest import TestCase, skipUnless
from unittest.mock import patch

import jsonpickle

from support import QtTestCase
from main import create_main_window
from startrails.lib.project_denoise import DenoiseProject
from startrails.paths import WORK_DIR_ENV, configure_work_directory


class WindowsTaskbarTests(TestCase):
    @skipUnless(sys.platform == "win32", "Windows shell identity")
    def test_running_process_identifies_itself_as_startrails(self):
        # Isolate the process-wide shell setting from the test runner.
        script = textwrap.dedent("""
            import ctypes
            from startrails.windows import APP_USER_MODEL_ID, configure_taskbar_identity

            configure_taskbar_identity()
            get_app_id = ctypes.OleDLL("shell32").GetCurrentProcessExplicitAppUserModelID
            get_app_id.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
            get_app_id.restype = ctypes.HRESULT
            app_id = ctypes.c_wchar_p()
            get_app_id(ctypes.byref(app_id))
            free = ctypes.OleDLL("ole32").CoTaskMemFree
            free.argtypes = [ctypes.c_void_p]
            free.restype = None
            try:
                assert app_id.value == APP_USER_MODEL_ID, app_id.value
            finally:
                free(app_id)
        """)
        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class WorkingDirectoryTests(TestCase):
    def setUp(self):
        super().setUp()
        directory = TemporaryDirectory(prefix="startrails_startup_")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.enterContext(chdir(self.root))
        self.enterContext(patch.dict(os.environ))
        os.environ.pop(WORK_DIR_ENV, None)

    def test_unset_override_preserves_launch_directory(self):
        self.assertIsNone(configure_work_directory(None))
        self.assertEqual(Path.cwd(), self.root)

    def test_override_creates_directory_and_preserves_relative_project_argument(self):
        project = self.root / "existing.proj_startrails"
        project.write_text("existing project", encoding="utf-8")
        os.environ[WORK_DIR_ENV] = "Documents/Startrails space 天空"
        argument = configure_work_directory(project.name)
        self.assertEqual(Path.cwd(), self.root / os.environ[WORK_DIR_ENV])
        self.assertEqual(Path(argument).read_text(encoding="utf-8"), "existing project")
        Path("app.json").write_text("application state", encoding="utf-8")
        self.assertFalse((self.root / "app.json").exists())

    def test_invalid_override_reports_failure_without_changing_directory(self):
        existing_file = self.root / "file"
        existing_file.touch()
        for configured, error in (("", ValueError), (str(existing_file), FileExistsError)):
            with self.subTest(configured=configured):
                os.environ[WORK_DIR_ENV] = configured
                with self.assertRaises(error):
                    configure_work_directory(None)
                self.assertEqual(Path.cwd(), self.root)


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
