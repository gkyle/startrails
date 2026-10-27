"""Release identity depends on the Windows payload and runtime pins."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from build.windows import prepare as windows_prepare


class WindowsPrepareTests(unittest.TestCase):
    def test_macos_toolchain_changes_do_not_replace_windows_release(self):
        with TemporaryDirectory(prefix="startrails_windows_prepare_") as temporary:
            root = Path(temporary)
            (root / "build").mkdir()
            (root / "src/startrails/ui/icons").mkdir(parents=True)
            (root / "src/startrails/windows.py").write_text('APP_USER_MODEL_ID = "StarTrails.Test"\n')
            (root / "src/startrails/ui/icons/startrails_windows.ico").write_bytes(b"icon")
            (root / "README.md").write_text("readme")
            (root / "LICENSE").write_text("license")
            (root / "pyproject.toml").write_text(
                '[project]\nname = "startrails"\nversion = "0.1.1"\nrequires-python = "==3.12.*"\n'
            )
            (root / "uv.lock").write_text("lock")
            toolchain_path = root / "build/toolchain.json"
            toolchain = {
                "python_version": "3.12.15",
                "uv_version": "0.13.5",
                "windows_x64_uv_archive_sha256": "windows-hash",
                "macos_min_version": "14.0",
                "macos_arm64_uv_archive_sha256": "mac-hash",
            }
            uv_dir = root / "uv"
            uv_dir.mkdir()
            uv = uv_dir / "uv.exe"
            uv.write_bytes(b"uv executable")
            for name in ("LICENSE-MIT", "LICENSE-APACHE"):
                (uv_dir / name).write_text(name)
            models = root / "StarTrailsAI-0.1.1-models.zip"
            with ZipFile(models, "w") as archive:
                archive.writestr("models/sky.safetensors", b"model")

            def staged_release(name):
                toolchain_path.write_text(json.dumps(toolchain), encoding="utf-8")
                return windows_prepare.prepare(root / name, uv, models, None)["release_id"]

            with (
                patch.object(windows_prepare, "ROOT", root),
                patch.object(windows_prepare, "copy_source_tree"),
            ):
                original = staged_release("first")
                toolchain["macos_min_version"] = "15.0"
                toolchain["macos_arm64_uv_archive_sha256"] = "new-mac-hash"
                self.assertEqual(staged_release("macos-change"), original)

                toolchain["python_version"] = "3.12.16"
                self.assertNotEqual(staged_release("python-change"), original)


if __name__ == "__main__":
    unittest.main()
