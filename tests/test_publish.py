"""The release sync requires explicit approval before changing GitHub assets."""

import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from build import publish


TAG = "v0.1.1"


def completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(["gh"], returncode, stdout, stderr)


class PublishTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="startrails_publish_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.artifact = self.root / "StarTrailsAI-0.1.1-models.zip"
        self.artifact.write_bytes(b"verified model archive")
        self.digest = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.calls = []
        self.uploaded_checksums = None
        self.release = None
        self.enterContext(patch.object(publish.shutil, "which", return_value="gh"))
        self.enterContext(patch.object(publish, "run_gh", side_effect=self.fake_gh))

    def fake_gh(self, *arguments, check=True):
        self.calls.append(arguments)
        if arguments[0] == "api":
            if arguments[1].endswith("/latest"):
                if getattr(self, "latest", False):
                    return completed(stdout=json.dumps({"tag_name": TAG}))
                return completed(stderr="gh: Not Found (HTTP 404)", returncode=1)
            if self.release is None:
                return completed(stderr="gh: Not Found (HTTP 404)", returncode=1)
            return completed(stdout=json.dumps(self.release))
        if arguments[:2] == ("release", "download"):
            output = Path(arguments[arguments.index("--dir") + 1]) / publish.CHECKSUM_NAME
            output.write_text(self.remote_checksums, encoding="utf-8")
        if arguments[:2] == ("release", "upload") and Path(arguments[3]).name == publish.CHECKSUM_NAME:
            self.uploaded_checksums = Path(arguments[3]).read_text(encoding="utf-8")
        return completed()

    def test_declining_sync_never_creates_or_uploads_a_release(self):
        with patch("builtins.input", return_value="no"):
            publish.sync_release("0.1.1", [self.artifact], create_release=True)

        self.assertEqual(self.calls, [])

    def test_missing_gh_leaves_local_artifacts_available(self):
        with (
            patch.object(publish.shutil, "which", return_value=None),
            patch("builtins.input", side_effect=AssertionError("unexpected prompt")),
        ):
            publish.sync_release("0.1.1", [self.artifact], create_release=True)

        self.assertTrue(self.artifact.is_file())
        self.assertEqual(self.calls, [])

    def test_new_release_has_no_latest_or_prerelease_label(self):
        with patch("builtins.input", side_effect=["yes", "yes"]):
            publish.sync_release("0.1.1", [self.artifact], create_release=True)

        created = next(args for args in self.calls if args[:2] == ("release", "create"))
        self.assertIn("--verify-tag", created)
        self.assertNotIn("--prerelease", created)
        self.assertIn("--latest=false", created)
        self.assertEqual(self.uploaded_checksums, f"{self.digest}  {self.artifact.name}\n")

    def test_declining_new_release_creation_leaves_the_tag_untouched(self):
        with patch("builtins.input", side_effect=["yes", "no"]):
            publish.sync_release("0.1.1", [self.artifact], create_release=True)

        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0], "api")

    def test_existing_asset_requires_separate_replacement_approval(self):
        self.release = {
            "assets": [{"name": self.artifact.name, "digest": "sha256:" + self.digest}],
            "draft": False,
        }
        with patch("builtins.input", side_effect=["yes", "no"]):
            publish.sync_release("0.1.1", [self.artifact], create_release=True)

        self.assertEqual(len(self.calls), 2)
        self.assertIsNone(self.uploaded_checksums)

    def test_declining_latest_conversion_leaves_release_unchanged(self):
        self.release = {"assets": [], "draft": False}
        self.latest = True
        with patch("builtins.input", side_effect=["yes", "no"]):
            publish.sync_release("0.1.1", [self.artifact], create_release=True)

        self.assertEqual(len(self.calls), 2)

    def test_approved_latest_conversion_precedes_asset_upload(self):
        self.release = {"assets": [], "draft": False}
        self.latest = True
        with patch("builtins.input", side_effect=["yes", "yes"]):
            publish.sync_release("0.1.1", [self.artifact], create_release=True)

        edit_index = next(i for i, args in enumerate(self.calls) if args[:2] == ("release", "edit"))
        upload_index = next(i for i, args in enumerate(self.calls) if args[:2] == ("release", "upload"))
        self.assertLess(edit_index, upload_index)
        self.assertIn("--prerelease", self.calls[edit_index])
        self.assertIn("--latest=false", self.calls[edit_index])

    def test_approved_existing_asset_is_replaced_with_updated_checksum(self):
        old_digest = "b" * 64
        self.release = {
            "assets": [
                {"name": self.artifact.name, "digest": "sha256:" + old_digest},
                {"name": publish.CHECKSUM_NAME},
            ],
            "draft": False,
        }
        self.remote_checksums = f"{old_digest}  {self.artifact.name}\n"
        with patch("builtins.input", side_effect=["yes", "yes", "yes"]):
            publish.sync_release("0.1.1", [self.artifact], create_release=True)

        artifact_upload = next(
            args for args in self.calls
            if args[:2] == ("release", "upload") and Path(args[3]).name == self.artifact.name
        )
        self.assertIn("--clobber", artifact_upload)
        self.assertEqual(self.uploaded_checksums, f"{self.digest}  {self.artifact.name}\n")

    def test_checksum_is_merged_and_replacement_is_approved_before_upload(self):
        previous_name = "StarTrailsAI-0.1.1-macos-arm64.dmg"
        previous_digest = "a" * 64
        self.release = {
            "assets": [
                {"name": previous_name, "digest": "sha256:" + previous_digest},
                {"name": publish.CHECKSUM_NAME},
            ],
            "draft": False,
        }
        self.remote_checksums = f"{previous_digest}  {previous_name}\n"
        with patch("builtins.input", side_effect=["yes", "yes"]):
            publish.sync_release("0.1.1", [self.artifact], create_release=False)

        self.assertEqual(
            self.uploaded_checksums,
            f"{previous_digest}  {previous_name}\n{self.digest}  {self.artifact.name}\n",
        )
        checksum_upload = next(
            args for args in self.calls
            if args[:2] == ("release", "upload") and Path(args[3]).name == publish.CHECKSUM_NAME
        )
        self.assertIn("--clobber", checksum_upload)

    def test_declining_checksum_replacement_prevents_partial_sync(self):
        self.release = {"assets": [{"name": publish.CHECKSUM_NAME}], "draft": False}
        self.remote_checksums = ""
        with patch("builtins.input", side_effect=["yes", "no"]):
            publish.sync_release("0.1.1", [self.artifact], create_release=False)

        self.assertFalse(any(args[:2] == ("release", "upload") for args in self.calls))

    def test_unknown_existing_asset_hash_prevents_incomplete_checksum(self):
        self.release = {"assets": [{"name": "old-installer.exe", "digest": None}], "draft": False}
        with patch("builtins.input", return_value="yes"):
            with self.assertRaisesRegex(RuntimeError, "lack a GitHub digest"):
                publish.sync_release("0.1.1", [self.artifact], create_release=False)

        self.assertFalse(any(args[:2] == ("release", "upload") for args in self.calls))

    def test_network_failure_is_not_treated_as_missing_release(self):
        with patch.object(publish, "run_gh", return_value=completed(stderr="connection failed", returncode=1)):
            with patch("builtins.input", return_value="yes"):
                with self.assertRaisesRegex(RuntimeError, "connection failed"):
                    publish.sync_release("0.1.1", [self.artifact], create_release=True)


if __name__ == "__main__":
    unittest.main()
