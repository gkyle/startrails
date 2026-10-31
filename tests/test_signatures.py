"""Shared metadata identity, file integrity and processing-key contracts."""

import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from startrails.lib.signatures import compute_signature, read_file_identity, verify_file_integrity


class TestSignatures(unittest.TestCase):
    def test_mapping_order_is_ignored_but_dependencies_and_types_matter(self):
        payload = {"version": 1, "sources": ["a|b", "c"]}
        signature = compute_signature(payload)
        self.assertEqual(signature, compute_signature(dict(reversed(list(payload.items())))))
        for changed in (
            {"version": 2, "sources": ["a|b", "c"]},
            {"version": 1, "sources": ["a", "b|c"]},
            {"version": 1, "sources": ["c", "a|b"]},
            {"version": "1", "sources": ["a|b", "c"]},
        ):
            self.assertNotEqual(signature, compute_signature(changed))

    def test_nonfinite_settings_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError):
                compute_signature({"setting": value})

    def test_file_identity_tracks_metadata_and_propagates_missing_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "image.tif"
            path.write_bytes(b"first")
            first = read_file_identity(path)
            self.assertEqual(first.path, str(path.resolve()))
            self.assertEqual(first.size, len(b"first"))
            path.write_bytes(b"second")
            changed_mtime_ns = first.mtime_ns + 1_000_000_000
            os.utime(path, ns=(changed_mtime_ns, changed_mtime_ns))
            second = read_file_identity(path)
            self.assertNotEqual(first.size, second.size)
            self.assertEqual(second.mtime_ns, changed_mtime_ns)
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                read_file_identity(path)


class TestFileIntegrity(unittest.TestCase):
    def test_verify_file_integrity(self):
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.bin"
            content = b"StarTrails Finish Model Verification Test Payload"
            file_path.write_bytes(content)
            expected_hash = hashlib.sha256(content).hexdigest()
            expected_size = len(content)

            self.assertTrue(verify_file_integrity(file_path, expected_hash, expected_size))
            self.assertTrue(verify_file_integrity(file_path, expected_hash.upper(), expected_size))
            self.assertTrue(verify_file_integrity(file_path, expected_hash))

            # Corrupt size
            self.assertFalse(verify_file_integrity(file_path, expected_hash, expected_size + 1))
            # Corrupt hash
            self.assertFalse(verify_file_integrity(file_path, "0" * 64, expected_size))
            # Missing file
            self.assertFalse(verify_file_integrity(Path(tmpdir) / "nonexistent.bin", expected_hash))
