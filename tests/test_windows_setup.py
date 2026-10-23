"""Exercise packaged setup recovery without downloading application dependencies."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]

# Stand in for the native uv executable at the setup process boundary.
UV_STUB = r"""
using System;
using System.IO;

public class UvStub {
    public static int Main(string[] args) {
        string runtime = Path.Combine(Environment.CurrentDirectory, "runtime");
        string command = string.Join(" ", args);
        File.AppendAllText(Path.Combine(runtime, "calls.log"), command + "\n");
        if (command == "--version") {
            Console.WriteLine("uv 0.0.0");
        } else if (command.Contains("probeGPU.py")) {
            string attempted = Path.Combine(runtime, "probe-attempted");
            bool first = !File.Exists(attempted);
            File.WriteAllText(attempted, "");
            string failure = Environment.GetEnvironmentVariable("STARTRAILS_TEST_UV_FAILURE");
            if (first || failure == "persistent") {
                Console.Error.WriteLine("error: Failed to create Python minor version link directory");
                Console.Error.WriteLine(failure == "unrelated"
                    ? "cause: Access is denied. (os error 5)"
                    : "cause: The path cannot be traversed because it contains an untrusted mount point. (os error 448)");
                return 2;
            }
            Console.Error.WriteLine("GPU support checked.");
            Console.WriteLine("cpu");
        } else if (command.StartsWith("sync ") &&
                   Environment.GetEnvironmentVariable("STARTRAILS_TEST_UV_FAILURE") == "streaming") {
            Console.WriteLine("Installing test dependency...");
            Console.Error.WriteLine("Downloading test dependency...");
            // The test releases this barrier only after receiving the download output.
            DateTime deadline = DateTime.UtcNow.AddSeconds(10);
            while (!File.Exists(Path.Combine(runtime, "continue-sync"))) {
                if (DateTime.UtcNow >= deadline) return 23;
                System.Threading.Thread.Sleep(50);
            }
        } else if (command.Contains("check_runtime.py")) {
            string scripts = Path.Combine(runtime, "venv", "Scripts");
            Directory.CreateDirectory(scripts);
            File.WriteAllText(Path.Combine(scripts, "pythonw.exe"), "");
        }
        return 0;
    }
}
"""


@unittest.skipUnless(sys.platform == "win32", "Windows PowerShell setup")
class WindowsSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        directory = TemporaryDirectory(prefix="startrails_uv_stub_")
        cls.addClassCleanup(directory.cleanup)
        root = Path(directory.name)
        source = root / "uv.cs"
        source.write_text(UV_STUB, encoding="utf-8")
        cls.uv = root / "uv.exe"
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Add-Type -Path '"
                + str(source).replace("'", "''")
                + "' -OutputAssembly '"
                + str(cls.uv).replace("'", "''")
                + "' -OutputType ConsoleApplication -ErrorAction Stop",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def setUp(self):
        directory = TemporaryDirectory(prefix="startrails_setup_")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "src/setup").mkdir(parents=True)
        (self.root / "tools").mkdir()
        shutil.copy2(ROOT / "src/setup/setup.ps1", self.root / "src/setup/setup.ps1")
        shutil.copy2(self.uv, self.root / "tools/uv.exe")
        (self.root / "release.json").write_text(
            json.dumps({"release_id": "test", "uv_version": "0.0.0", "python_version": "3.12.15"}),
            encoding="utf-8",
        )
        (self.root / "uv.lock").write_text("test lockfile", encoding="utf-8")

        self.command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.root / "src/setup/setup.ps1"),
            "-Packaged",
        ]

    def run_setup(self, failure):
        return subprocess.run(
            self.command,
            cwd=self.root,
            env={**os.environ, "STARTRAILS_TEST_UV_FAILURE": failure},
            capture_output=True,
            text=True,
            timeout=60,
        )

    def probe_calls(self):
        return [line for line in (self.root / "runtime/calls.log").read_text().splitlines() if "probeGPU.py" in line]

    def test_optional_junction_failure_retries_and_prepares_environment(self):
        result = self.run_setup("recoverable")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.probe_calls()), 2)
        ready = json.loads((self.root / "runtime/ready.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(ready["torch_variant"], "cpu")
        self.assertIn("os error 448", (self.root / "runtime/setup.log").read_text(encoding="utf-8-sig"))

    def test_dependency_output_arrives_before_sync_finishes(self):
        with subprocess.Popen(
            self.command,
            cwd=self.root,
            env={**os.environ, "STARTRAILS_TEST_UV_FAILURE": "streaming"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ) as process:
            output = []
            for line in process.stdout:
                output.append(line)
                if "Downloading test dependency..." in line:
                    self.assertIsNone(process.poll())
                    (self.root / "runtime/continue-sync").touch()
                    break
            remaining, _ = process.communicate(timeout=20)
            output.append(remaining)
            self.assertEqual(process.returncode, 0, "".join(output))
            self.assertIn("Installing test dependency...", "".join(output))
            self.assertTrue((self.root / "runtime/ready.json").exists())

    def test_unrelated_failure_stops_without_retry(self):
        result = self.run_setup("unrelated")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.probe_calls()), 1)
        self.assertFalse((self.root / "runtime/ready.json").exists())
        self.assertIn("os error 5", result.stdout + result.stderr)

    def test_persistent_junction_failure_stops_after_one_retry(self):
        result = self.run_setup("persistent")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.probe_calls()), 2)
        self.assertFalse((self.root / "runtime/ready.json").exists())
        self.assertIn("os error 448", result.stdout + result.stderr)
