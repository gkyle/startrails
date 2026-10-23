"""Regression coverage for cross-platform model release archives."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from build import release


class ModelArchiveTests(unittest.TestCase):
    def test_text_checkout_line_endings_do_not_change_archive_hash(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = root / "models"
            models.mkdir()
            weights = models / "model.safetensors"
            weights.write_bytes(b"model weights")
            metadata = models / "config.json"
            first = root / "first.zip"
            second = root / "second.zip"

            with patch.object(release, "ROOT", root):
                metadata.write_bytes(b'{\n  "name": "sky"\n}\n')
                release.create_models_archive(first)
                metadata.write_bytes(b'{\r\n  "name": "sky"\r\n}\r\n')
                release.create_models_archive(second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(second) as archive:
                self.assertEqual(archive.read("models/config.json"), b'{\n  "name": "sky"\n}\n')
                self.assertEqual(archive.read("models/model.safetensors"), b"model weights")

    def test_staging_copies_the_exact_archive_and_uses_its_uncompressed_size(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = root / "models"
            models.mkdir()
            (models / "sky.safetensors").write_bytes(b"weights")
            (models / "config.json").write_bytes(b'{\r\n  "name": "sky"\r\n}\r\n')
            archive = root / release.models_archive_name("0.1.1")
            output = root / "build"
            output.mkdir()

            with patch.object(release, "ROOT", root):
                release.create_models_archive(archive)
            staged, digest, models_size = release.stage_models_archive(archive, output, "0.1.1")

            self.assertEqual(staged.read_bytes(), archive.read_bytes())
            self.assertEqual(digest, hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(models_size, len(b"weights") + len(b'{\n  "name": "sky"\n}\n'))

    def test_staging_rejects_an_archive_from_another_version(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / release.models_archive_name("0.1.0")
            archive.touch()

            with self.assertRaisesRegex(ValueError, "Expected model archive named"):
                release.stage_models_archive(archive, root, "0.1.1")


if __name__ == "__main__":
    unittest.main()
