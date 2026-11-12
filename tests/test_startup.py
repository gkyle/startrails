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
from startrails.app import App
from startrails.lib.project_startrails import Project
from startrails.lib.project_denoise import DenoiseProject
from startrails.lib.project_finish import FinishProject
from startrails.lib.project_type import DENOISE_EXT, FINISH_EXT, STARTRAILS_EXT
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

    def test_corrupt_or_wrong_type_starter_project_does_not_block_startup(self):
        projects_dir = self.root / "projects"
        projects_dir.mkdir()

        cases = (
            (
                f"default{FINISH_EXT}",
                "{not json",
                "selected.proj_startrails",
                Project(projectFile=str(projects_dir / "selected.proj_startrails")),
                Project,
            ),
            (
                f"default{FINISH_EXT}",
                jsonpickle.encode(Project(projectFile=str(projects_dir / f"default{FINISH_EXT}"))),
                "selected.proj_denoise",
                DenoiseProject(project_file=str(projects_dir / "selected.proj_denoise")),
                DenoiseProject,
            ),
            (
                f"default{DENOISE_EXT}",
                jsonpickle.encode(FinishProject(project_file=str(projects_dir / f"default{DENOISE_EXT}"))),
                "selected.proj_finish",
                FinishProject(project_file=str(projects_dir / "selected.proj_finish")),
                FinishProject,
            ),
        )

        for starter_name, starter_body, selected_name, selected_proj, expected_cls in cases:
            with self.subTest(starter=starter_name, selected=selected_name):
                starter_path = projects_dir / starter_name
                starter_path.write_text(starter_body, encoding="utf-8")

                selected_path = projects_dir / selected_name
                selected_path.write_text(jsonpickle.encode(selected_proj), encoding="utf-8")
                Path("app.json").write_text(jsonpickle.encode({"projectFile": str(selected_path)}), encoding="utf-8")

                try:
                    with (
                        patch("startrails.app.GPUInfo"),
                        self.assertLogs("startrails.app", level="WARNING") as logs,
                    ):
                        app = App()

                    self.assertIsInstance(app.project, expected_cls)
                    self.assertEqual(Path(app.project.projectFile).resolve(), selected_path.resolve())
                    self.assertEqual(starter_path.read_text(encoding="utf-8"), starter_body)
                    self.assertTrue(any(starter_name in line for line in logs.output))
                finally:
                    starter_path.unlink(missing_ok=True)

    def test_corrupt_selected_default_finish_recovers_without_overwriting(self):
        projects_dir = self.root / "projects"
        projects_dir.mkdir()
        starter_path = projects_dir / f"default{FINISH_EXT}"
        corrupt_body = "{corrupt finish project"
        starter_path.write_text(corrupt_body, encoding="utf-8")
        Path("app.json").write_text(jsonpickle.encode({"projectFile": str(starter_path)}), encoding="utf-8")

        with (
            patch("startrails.app.GPUInfo"),
            self.assertLogs("startrails.app", level="WARNING") as logs,
        ):
            app = App()

        self.assertIsInstance(app.project, Project)
        self.assertEqual(Path(app.project.projectFile), Path(f"projects/default{STARTRAILS_EXT}"))
        self.assertEqual(starter_path.read_text(encoding="utf-8"), corrupt_body)
        self.assertTrue(any(f"default{FINISH_EXT}" in line for line in logs.output))
