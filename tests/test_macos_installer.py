"""Exercise macOS setup and installation without downloading dependencies."""

import hashlib
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from build.macos.prepare import build_app


ROOT = Path(__file__).resolve().parents[1]
MACOS_ARM = sys.platform == "darwin" and platform.machine() == "arm64"
RELEASE_ID = "0.1.1-0123456789ab"

UV_STUB = """#!/bin/bash
printf '%s\\n' "$*" >> "$STARTRAILS_TEST_CALLS"
case "$*" in
    --version) printf 'uv 0.0.0 (test)\\n' ;;
    *probeGPU.py*) printf mps ;;
    sync*) if [[ ${STARTRAILS_TEST_SYNC_FAIL:-0} == 1 ]]; then exit 12; fi ;;
    *check_runtime.py*)
        mkdir -p runtime/venv/bin
        cp "$STARTRAILS_TEST_PYTHON" runtime/venv/bin/python
        chmod +x runtime/venv/bin/python ;;
esac
"""
DEV_UV_STUB = """#!/bin/bash
printf '%s\\n' "$*" >> "$STARTRAILS_TEST_CALLS"
case "$*" in
    *probeGPU.py*) printf cpu ;;
esac
"""
PYTHON_STUB = """#!/bin/bash
printf '%s\\n' "$STARTRAILS_WORK_DIR" "$@" > "$STARTRAILS_TEST_LAUNCH"
"""
INSTALL_SETUP_STUB = """#!/bin/bash
printf '%s\\n' "$*" >> "$STARTRAILS_TEST_SETUP_CALLS"
if [[ ${STARTRAILS_TEST_SETUP_FAIL:-0} == 1 ]]; then exit 12; fi
cd "$(dirname "$0")/../.."
mkdir -p runtime/venv/bin
touch runtime/venv/bin/python
chmod +x runtime/venv/bin/python
"""
OPEN_STUB = """#!/bin/bash
printf '%s\\n' "$*" >> "$STARTRAILS_TEST_OPEN_CALLS"
"""


class MacAppMetadataTests(unittest.TestCase):
    def test_script_launcher_prefers_native_apple_silicon(self):
        with TemporaryDirectory(prefix="startrails_mac_app_") as temporary:
            stage = Path(temporary)
            build_app(stage, "0.1.1", "14.0")
            info_plist = stage / "StarTrails AI.app/Contents/Info.plist"
            with info_plist.open("rb") as stream:
                metadata = plistlib.load(stream)
            self.assertEqual(metadata["LSArchitecturePriority"], ["arm64"])


@unittest.skipIf(sys.platform == "win32", "Unix setup script")
class MacSetupTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="startrails_mac_setup_")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "release 天空"
        (self.root / "src/setup").mkdir(parents=True)
        (self.root / "tools").mkdir()
        shutil.copy2(ROOT / "src/setup/setup.sh", self.root / "src/setup/setup.sh")
        self.uv = self.root / "tools/uv"
        self.uv.write_text(UV_STUB, encoding="utf-8")
        self.uv.chmod(0o755)
        self.python_stub = self.root / "python-stub"
        self.python_stub.write_text(PYTHON_STUB, encoding="utf-8")
        self.python_stub.chmod(0o755)
        (self.root / "release.conf").write_text(
            f"release_id='{RELEASE_ID}'\nuv_version='0.0.0'\npython_version='3.12.15'\n",
            encoding="utf-8",
        )
        (self.root / "uv.lock").write_text("test lock", encoding="utf-8")
        self.calls = self.root / "calls.txt"
        self.launch = self.root / "launch.txt"
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "STARTRAILS_TEST_CALLS": str(self.calls),
            "STARTRAILS_TEST_PYTHON": str(self.python_stub),
            "STARTRAILS_TEST_LAUNCH": str(self.launch),
        }
        self.env.pop("STARTRAILS_WORK_DIR", None)

    def run_setup(self, *arguments):
        return subprocess.run(
            ["/bin/bash", str(self.root / "src/setup/setup.sh"), "--packaged", *arguments],
            cwd=self.home,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_ready_launch_uses_prepared_python_without_uv(self):
        prepared = self.run_setup()
        self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
        calls = self.calls.read_text(encoding="utf-8")
        self.assertIn("probeGPU.py", calls)
        self.assertIn("sync --extra mps --locked --python 3.12.15", calls)
        project = self.home / "night sky.proj_denoise"
        project.touch()
        launched = self.run_setup("--launch", "--", project.name)
        self.assertEqual(launched.returncode, 0, launched.stdout + launched.stderr)
        self.assertEqual(self.calls.read_text(encoding="utf-8"), calls)
        self.assertEqual(
            self.launch.read_text(encoding="utf-8").splitlines(),
            [str(self.home / "Documents/Startrails"), "src/main.py", str(project.resolve())],
        )

    def test_missing_readiness_requires_repair_without_network_activity(self):
        result = self.run_setup("--launch")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needs repair", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_repair_rechecks_the_environment(self):
        self.assertEqual(self.run_setup().returncode, 0)
        before = self.calls.read_text(encoding="utf-8")
        self.assertEqual(self.run_setup("--repair").returncode, 0)
        after = self.calls.read_text(encoding="utf-8")
        self.assertEqual(after.count("probeGPU.py"), before.count("probeGPU.py") + 1)

    def test_failed_sync_does_not_mark_release_ready_and_can_retry(self):
        self.env["STARTRAILS_TEST_SYNC_FAIL"] = "1"
        failed = self.run_setup()
        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse((self.root / "runtime/ready.txt").exists())
        self.env.pop("STARTRAILS_TEST_SYNC_FAIL")
        retried = self.run_setup()
        self.assertEqual(retried.returncode, 0, retried.stdout + retried.stderr)
        self.assertTrue((self.root / "runtime/ready.txt").exists())


@unittest.skipIf(sys.platform == "win32", "Unix launch script")
class UnixDevelopmentLaunchTests(unittest.TestCase):
    def test_repository_wrapper_uses_shared_setup_and_preserves_project_path(self):
        with TemporaryDirectory(prefix="startrails_unix_launch_") as temporary:
            root = Path(temporary)
            (root / "src/setup").mkdir(parents=True)
            (root / "bin").mkdir()
            shutil.copy2(ROOT / "run.sh", root / "run.sh")
            shutil.copy2(ROOT / "src/setup/setup.sh", root / "src/setup/setup.sh")
            uv = root / "bin/uv"
            uv.write_text(DEV_UV_STUB, encoding="utf-8")
            uv.chmod(0o755)
            calls = root / "calls.txt"
            project = root / "night sky.proj_startrails"
            project.touch()
            result = subprocess.run(
                ["/bin/sh", str(root / "run.sh"), project.name],
                cwd=root,
                env={
                    **os.environ,
                    "PATH": f"{root / 'bin'}:{os.environ['PATH']}",
                    "STARTRAILS_TEST_CALLS": str(calls),
                },
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            commands = calls.read_text(encoding="utf-8")
            self.assertIn("sync --extra cpu", commands)
            self.assertIn(f"src/main.py {project.resolve()}", commands)


@unittest.skipUnless(MACOS_ARM, "macOS Apple Silicon installer")
class MacInstallerTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="startrails_mac_install_")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.home = self.root / "user with spaces 天空"
        self.home.mkdir()
        self.dmg = self.root / "StarTrails AI volume"
        self.payload = self.dmg / ".payload"
        (self.payload / "src/setup").mkdir(parents=True)
        (self.payload / "StarTrails AI.app/Contents/MacOS").mkdir(parents=True)
        (self.payload / "StarTrails AI.app/Contents/Resources").mkdir(parents=True)
        shutil.copy2(
            ROOT / "build/macos/launcher.sh", self.payload / "StarTrails AI.app/Contents/MacOS/StarTrails"
        )
        shutil.copy2(
            ROOT / "build/macos/common.sh", self.payload / "StarTrails AI.app/Contents/Resources/common.sh"
        )
        (self.payload / "src/setup/setup.sh").write_text(INSTALL_SETUP_STUB, encoding="utf-8")
        shutil.copy2(ROOT / "build/macos/common.sh", self.payload / "common.sh")
        shutil.copy2(ROOT / "build/macos/install.command", self.dmg / "Install StarTrails AI.command")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        open_stub = bin_dir / "open"
        open_stub.write_text(OPEN_STUB, encoding="utf-8")
        open_stub.chmod(0o755)
        self.setup_calls = self.root / "setup-calls.txt"
        self.open_calls = self.root / "open-calls.txt"
        self.models = self.root / "models.zip"
        with ZipFile(self.models, "w") as archive:
            archive.writestr("models/test.safetensors", "test model")
        model_hash = hashlib.sha256(self.models.read_bytes()).hexdigest()
        (self.payload / "release.conf").write_text(
            f"version='0.1.1'\nrelease_id='{RELEASE_ID}'\nmodels_sha256='{model_hash}'\n"
            "macos_min_version='14.0'\n"
            "models_url='https://example.invalid/models.zip'\n",
            encoding="utf-8",
        )
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STARTRAILS_TEST_SETUP_CALLS": str(self.setup_calls),
            "STARTRAILS_TEST_OPEN_CALLS": str(self.open_calls),
        }

    def install(self):
        return subprocess.run(
            ["/bin/bash", str(self.dmg / "Install StarTrails AI.command"), "--models-archive", str(self.models)],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_installs_release_and_launcher_in_user_directories(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        support = self.home / "Library/Application Support/StarTrails"
        self.assertEqual((support / "current").read_text(encoding="utf-8").strip(), RELEASE_ID)
        self.assertEqual(
            (support / "releases" / RELEASE_ID / "models/test.safetensors").read_text(encoding="utf-8"),
            "test model",
        )
        self.assertTrue((self.home / "Applications/StarTrails AI.app").is_dir())
        self.assertFalse((self.home / "Applications/Repair StarTrails AI.command").exists())
        self.assertFalse((self.home / "Applications/Uninstall StarTrails AI.command").exists())
        self.assertEqual(self.setup_calls.read_text(encoding="utf-8").splitlines(), ["--packaged"])
        self.assertEqual(
            self.open_calls.read_text(encoding="utf-8").splitlines(),
            [str(self.home / "Applications/StarTrails AI.app")],
        )
        launched = subprocess.run(
            ["/bin/bash", str(self.home / "Applications/StarTrails AI.app/Contents/MacOS/StarTrails")],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(launched.returncode, 0, launched.stdout + launched.stderr)

    def test_rerunning_installer_repairs_models_and_environment(self):
        self.assertEqual(self.install().returncode, 0)
        support = self.home / "Library/Application Support/StarTrails"
        release_dir = support / "releases" / RELEASE_ID
        (release_dir / "models/test.safetensors").write_text("damaged model", encoding="utf-8")
        (release_dir / "runtime/venv/bin/python").unlink()
        applications = self.home / "Applications"
        for name in ("Repair StarTrails AI.command", "Uninstall StarTrails AI.command"):
            (applications / name).write_text("old installer helper", encoding="utf-8")

        repaired = self.install()
        self.assertEqual(repaired.returncode, 0, repaired.stdout + repaired.stderr)
        self.assertIn("Repaired StarTrails AI", repaired.stdout)
        self.assertEqual((release_dir / "models/test.safetensors").read_text(encoding="utf-8"), "test model")
        self.assertTrue((release_dir / "runtime/venv/bin/python").exists())
        self.assertEqual(
            self.setup_calls.read_text(encoding="utf-8").splitlines(),
            ["--packaged", "--packaged --repair"],
        )
        self.assertEqual(
            self.open_calls.read_text(encoding="utf-8").splitlines(),
            [str(applications / "StarTrails AI.app")] * 2,
        )
        for name in ("Repair StarTrails AI.command", "Uninstall StarTrails AI.command"):
            self.assertFalse((applications / name).exists())

    def test_failed_repair_keeps_installed_app(self):
        self.assertEqual(self.install().returncode, 0)
        self.env["STARTRAILS_TEST_SETUP_FAIL"] = "1"
        failed = self.install()
        self.assertNotEqual(failed.returncode, 0)
        support = self.home / "Library/Application Support/StarTrails"
        self.assertEqual((support / "current").read_text(encoding="utf-8").strip(), RELEASE_ID)
        self.assertTrue((self.home / "Applications/StarTrails AI.app").is_dir())
        self.assertEqual(len(self.open_calls.read_text(encoding="utf-8").splitlines()), 1)

    def test_failed_upgrade_keeps_previous_launcher(self):
        support = self.home / "Library/Application Support/StarTrails"
        support.mkdir(parents=True)
        (support / "current").write_text("0.1.0-abcdefabcdef\n", encoding="utf-8")
        applications = self.home / "Applications"
        applications.mkdir()
        (applications / "StarTrails AI.app").mkdir()
        (applications / "StarTrails AI.app/old").touch()
        self.env["STARTRAILS_TEST_SETUP_FAIL"] = "1"
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((support / "current").read_text(encoding="utf-8"), "0.1.0-abcdefabcdef\n")
        self.assertTrue((applications / "StarTrails AI.app/old").exists())

    def test_modified_model_archive_is_rejected(self):
        with self.models.open("ab") as archive:
            archive.write(b"modified")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed SHA-256 verification", result.stderr)
        self.assertFalse((self.home / "Library/Application Support/StarTrails/current").exists())

    def test_trashing_app_preserves_projects_and_allows_reinstall(self):
        self.assertEqual(self.install().returncode, 0)
        project = self.home / "Documents/Startrails/projects/night.proj_denoise"
        project.parent.mkdir(parents=True)
        project.write_text("saved project", encoding="utf-8")
        app = self.home / "Applications/StarTrails AI.app"
        shutil.rmtree(app)
        self.assertEqual(project.read_text(encoding="utf-8"), "saved project")
        self.assertFalse(app.exists())
        self.assertTrue((self.home / "Library/Application Support/StarTrails").exists())
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(app.is_dir())
        self.assertEqual(self.setup_calls.read_text(encoding="utf-8").splitlines(), ["--packaged", "--packaged"])


if __name__ == "__main__":
    unittest.main()
