"""Regression coverage for cross-platform model release archives."""

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


if __name__ == "__main__":
    unittest.main()
