"""Check the signed-release entry point without downloading build dependencies."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL_TIMEOUT_SECONDS = 30


@unittest.skipUnless(sys.platform == "win32", "Windows PowerShell release")
class WindowsReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="startrails_release_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repository $files"
        self.scripts = self.root / "build/windows"
        self.scripts.mkdir(parents=True)
        for name in ("release.ps1", "build.ps1"):
            shutil.copy2(ROOT / "build/windows" / name, self.scripts / name)
        self.working_directory = Path(temporary.name) / "elsewhere"
        self.working_directory.mkdir()

    def run_release(self, signing_command, *arguments, settings=None):
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith(("WINDOWS_SIGN", "WINDOWS_AZURE_CLI_"))
        }
        environment.update(settings or {})
        if signing_command is not None:
            environment["WINDOWS_SIGN_COMMAND"] = signing_command
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.scripts / "release.ps1"),
                *arguments,
            ],
            cwd=self.working_directory,
            env=environment,
            capture_output=True,
            text=True,
            timeout=POWERSHELL_TIMEOUT_SECONDS,
        )

    def test_release_rejects_missing_or_blank_signing_before_building(self):
        for environment, arguments in (
            (None, ()),
            ("   ", ()),
            ("configured signer $f", ("-SignCommand", "   ")),
        ):
            with self.subTest(environment=environment, arguments=arguments):
                result = self.run_release(environment, *arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("WINDOWS_SIGN_COMMAND", result.stderr)

    def test_release_accepts_signing_configuration_and_propagates_build_failure(self):
        missing_archive = str(self.root / "missing models.zip")
        for environment, arguments in (
            ("configured signer $f", ()),
            (None, ("-SignCommand", "explicit signer $f")),
        ):
            with self.subTest(environment=environment, arguments=arguments):
                result = self.run_release(environment, "-ModelsArchive", missing_archive, *arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Model archive not found:", result.stderr)
                self.assertIn("missing models.zip", result.stderr)

    def test_custom_signer_precedence_is_parameter_then_environment_then_dotenv(self):
        # Replace the expensive toolchain boundary to observe the resolved signing command.
        (self.scripts / "build.ps1").write_text(
            "param([string]$SignCommand)\n"
            "[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'signer.txt'), $SignCommand)\n",
            encoding="utf-8",
        )
        (self.root / ".env").write_text("WINDOWS_SIGN_COMMAND='file signer $f'\n", encoding="utf-8")
        for environment, arguments, expected in (
            (None, (), "file signer $f"),
            ("environment signer $f", (), "environment signer $f"),
            ("environment signer $f", ("-SignCommand", "parameter signer $f"), "parameter signer $f"),
        ):
            with self.subTest(expected=expected):
                result = self.run_release(environment, *arguments)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((self.scripts / "signer.txt").read_text(), expected)

    def test_dotenv_generates_metadata_literally_and_environment_overrides_file(self):
        marker = self.root / "should not execute.txt"
        profile = f"$(Set-Content -LiteralPath '{marker}' -Value executed)"
        settings = {
            "WINDOWS_SIGNING_ENDPOINT": "https://signing.example.invalid",
            "WINDOWS_SIGNING_ACCOUNT": "file-account",
            "WINDOWS_SIGNING_PROFILE": profile,
            "WINDOWS_SIGNTOOL_PATH": "SDK tools/signtool.exe",
            "WINDOWS_SIGNING_DLIB_PATH": "Signing tools/Azure.CodeSigning.Dlib.dll",
            "WINDOWS_AZURE_CLI_PATH": "CLI tools/az.cmd",
        }
        for name in ("WINDOWS_SIGNTOOL_PATH", "WINDOWS_SIGNING_DLIB_PATH", "WINDOWS_AZURE_CLI_PATH"):
            path = self.root / settings[name]
            path.parent.mkdir()
            path.touch()
        (self.root / ".env").write_text(
            "# Shared with the macOS release script\nMACOS_SIGNING_IDENTITY='unused'\n"
            + "\n".join(f'export {name}="{value}"' for name, value in settings.items())
            + "\n",
            encoding="utf-8",
        )
        metadata = self.root / "out/windows/signing.json"
        metadata.parent.mkdir(parents=True)
        metadata.write_text('{"obsolete": true}', encoding="utf-8")

        result = self.run_release(
            None,
            "-ModelsArchive",
            str(self.root / "missing.zip"),
            settings={"WINDOWS_SIGNING_ACCOUNT": "environment-account"},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Model archive not found:", result.stderr)
        self.assertEqual(
            json.loads(metadata.read_text(encoding="utf-8")),
            {
                "Endpoint": "https://signing.example.invalid",
                "CodeSigningAccountName": "environment-account",
                "CertificateProfileName": profile,
            },
        )
        self.assertFalse(marker.exists())

    def test_unclosed_dotenv_quotes_fail_without_echoing_the_value(self):
        (self.root / ".env").write_text("WINDOWS_SIGN_COMMAND='private incomplete value\n", encoding="utf-8")
        result = self.run_release(None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unclosed quote for WINDOWS_SIGN_COMMAND", result.stderr)
        self.assertNotIn("private incomplete value", result.stdout + result.stderr)

    def test_tools_are_discovered_from_path_or_standard_installations(self):
        program_files = self.root / "Program Files"
        sdk_program_files = self.root / "Program Files x86"
        local_app_data = self.root / "Local App Data"
        paths = (
            program_files / "Microsoft SDKs/Azure/CLI2/wbin/az.cmd",
            sdk_program_files / "Windows Kits/10/bin/10.0.26100.0/x64/signtool.exe",
            local_app_data / "Microsoft/MicrosoftArtifactSigningClientTools/Azure.CodeSigning.Dlib.dll",
        )
        for path in paths:
            path.parent.mkdir(parents=True)
            path.touch()
        (self.root / ".env").write_text(
            "WINDOWS_SIGNING_ENDPOINT=https://signing.example.invalid\n"
            "WINDOWS_SIGNING_ACCOUNT=file-account\n"
            "WINDOWS_SIGNING_PROFILE=file-profile\n",
            encoding="utf-8",
        )
        system_path = str(Path(os.environ["SystemRoot"]) / "System32")
        environment = {
            "ProgramFiles": str(program_files),
            "ProgramFiles(x86)": str(sdk_program_files),
            "LOCALAPPDATA": str(local_app_data),
            "PATH": system_path,
        }
        command_directory = self.root / "Commands"
        command_directory.mkdir()
        for name in ("signtool.exe", "az.cmd"):
            (command_directory / name).touch()

        for location in ("standard installation", "PATH"):
            with self.subTest(location=location):
                if location == "PATH":
                    environment.update(
                        {
                            "PATH": str(command_directory) + os.pathsep + system_path,
                            "ProgramFiles": str(self.root / "no CLI installation"),
                            "ProgramFiles(x86)": str(self.root / "no SDK installation"),
                        }
                    )
                result = self.run_release(None, "-ModelsArchive", str(self.root / "missing.zip"), settings=environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Model archive not found:", result.stderr)
                self.assertTrue((self.root / "out/windows/signing.json").exists())


if __name__ == "__main__":
    unittest.main()
