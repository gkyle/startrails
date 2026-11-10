"""Regression coverage for cross-platform model release archives."""

import hashlib
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

from dataclasses import replace

from build import release, models as model_builder


class PublishedModelArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="startrails_models_download_")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        self.name = "StarTrailsAI-0.1.1-models.zip"
        self.archive = self.output / self.name
        self.contents = b"published model archive"
        digest = hashlib.sha256(self.contents).hexdigest()
        self.api_url = "https://api.github.com/repos/gkyle/startrails/releases/tags/v0.1.1"
        self.asset_url = "https://github.com/gkyle/startrails/releases/download/v0.1.1/" + self.name
        self.responses = {
            self.api_url: json.dumps({"assets": [{"name": self.name, "digest": "sha256:" + digest}]}).encode(),
            self.asset_url: self.contents,
        }

        def github_response(request, timeout):
            return BytesIO(self.responses[request.full_url])

        self.enterContext(patch.object(release, "urlopen", side_effect=github_response))

    def test_published_bytes_replace_stale_cache_and_verified_cache_is_reused(self):
        self.archive.write_bytes(b"previous local build")

        archive = release.download_models_archive(self.output, "0.1.1")

        self.assertEqual(archive, self.archive)
        self.assertEqual(archive.read_bytes(), self.contents)
        del self.responses[self.asset_url]
        self.assertEqual(release.download_models_archive(self.output, "0.1.1").read_bytes(), self.contents)

    def test_hash_mismatch_preserves_cache_and_removes_partial_download(self):
        self.archive.write_bytes(b"existing cache")
        self.responses[self.asset_url] = b"incorrect download"

        with self.assertRaisesRegex(ValueError, "failed GitHub SHA-256 verification"):
            release.download_models_archive(self.output, "0.1.1")

        self.assertEqual(self.archive.read_bytes(), b"existing cache")
        self.assertEqual(list(self.output.iterdir()), [self.archive])

    def test_unverifiable_published_asset_never_uses_cached_copy(self):
        self.archive.write_bytes(self.contents)
        for assets, error in (
            ([], "Publish"),
            ([{"name": self.name, "digest": None}], "GitHub SHA-256 digest"),
        ):
            with self.subTest(assets=assets):
                self.responses[self.api_url] = json.dumps({"assets": assets}).encode()
                with self.assertRaisesRegex(ValueError, error):
                    release.download_models_archive(self.output, "0.1.1")
                self.assertEqual(self.archive.read_bytes(), self.contents)


class ModelArchiveTests(unittest.TestCase):
    def test_source_bundle_copies_text_resources_and_skips_pycache(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative_path = Path("src/startrails/lib/finish/NOTICE.txt")
            source = root / relative_path
            source.parent.mkdir(parents=True)
            source.write_text("Model license notice", encoding="utf-8")
            pycache_file = root / "src/startrails/lib/finish/__pycache__/nox.cpython-312.pyc"
            pycache_file.parent.mkdir(parents=True)
            pycache_file.write_bytes(b"bytecode")
            stage = root / "release"
            with patch.object(release, "ROOT", root):
                release.copy_source_tree(stage)
            self.assertEqual((stage / relative_path).read_text(), "Model license notice")
            self.assertFalse((stage / "src/startrails/lib/finish/__pycache__/nox.cpython-312.pyc").exists())

    def test_graxpert_bundle_requires_verified_weights_and_all_notices(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            model_root, notices = root / "models", root / "notices"
            notices.mkdir()
            data = b"unmodified model"
            manifest = replace(
                model_builder.GRAXPERT_MANIFEST, sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data)
            )
            model = model_root / manifest.relative_path
            model.parent.mkdir(parents=True)
            with patch.object(model_builder, "GRAXPERT_MANIFEST", manifest):
                with self.assertRaisesRegex(ValueError, "unverified GraXpert model"):
                    model_builder.prepare_graxpert_bundle(model_root, notices)
                model.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "Missing GraXpert attribution/license"):
                    model_builder.prepare_graxpert_bundle(model_root, notices)
                for name in ("README.md", "LICENSE.html", "LICENSE.txt"):
                    (notices / name).write_text(name)
                model_builder.prepare_graxpert_bundle(model_root, notices)
            self.assertEqual(model.read_bytes(), data)
            for name in ("README.md", "LICENSE.html", "LICENSE.txt"):
                self.assertEqual((model.parent / name).read_bytes(), (notices / name).read_bytes())

    def test_checkout_platform_does_not_change_archive_hash(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = root / "models"
            models.mkdir()
            weights = models / "model.safetensors"
            weights.write_bytes(b"model weights")
            metadata = models / "config.json"
            graxpert = models / "graxpert"
            graxpert.mkdir()
            model_data = b"PyTorch weights\r\n\x00\xff"
            (graxpert / "graxpert-denoise-3.0.2-mixed-int4-int8.pt").write_bytes(model_data)
            notices = {
                "README.md": b"# Model attribution\n",
                "LICENSE.html": b"<p>License</p>\n",
                "LICENSE.txt": b"Model license\n",
            }
            first = root / "first.zip"
            second = root / "second.zip"

            windows_zip_system = 0
            unix_zip_system = 3
            for archive_path, newline, host_system in (
                (first, b"\n", windows_zip_system),
                (second, b"\r\n", unix_zip_system),
            ):
                # Simulate ZipInfo's OS-dependent default on either test host.
                def host_zip_info(filename, timestamp):
                    entry = ZipInfo(filename, timestamp)
                    entry.create_system = host_system
                    return entry

                metadata.write_bytes(b'{\n  "name": "sky"\n}\n'.replace(b"\n", newline))
                for name, content in notices.items():
                    (graxpert / name).write_bytes(content.replace(b"\n", newline))
                with (
                    patch.object(release, "ROOT", root),
                    patch.object(release, "ZipInfo", side_effect=host_zip_info),
                ):
                    release.create_models_archive(archive_path)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(second) as archive:
                self.assertEqual(archive.read("models/config.json"), b'{\n  "name": "sky"\n}\n')
                self.assertEqual(archive.read("models/model.safetensors"), b"model weights")
                self.assertEqual(archive.getinfo("models/config.json").create_system, unix_zip_system)
                self.assertEqual(
                    archive.read("models/graxpert/graxpert-denoise-3.0.2-mixed-int4-int8.pt"),
                    model_data,
                )
                for name, content in notices.items():
                    self.assertEqual(archive.read("models/graxpert/" + name), content)

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

    def test_archive_excludes_pycache_and_bytecode(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            models = root / "models"
            models.mkdir()
            (models / "model.safetensors").write_bytes(b"model weights")
            pycache = models / "__pycache__"
            pycache.mkdir()
            (pycache / "compiled.cpython-312.pyc").write_bytes(b"bytecode")
            archive = root / "models.zip"

            with patch.object(release, "ROOT", root):
                release.create_models_archive(archive)

            with ZipFile(archive) as zip_file:
                names = zip_file.namelist()
                self.assertIn("models/model.safetensors", names)
                self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))


if __name__ == "__main__":
    unittest.main()
