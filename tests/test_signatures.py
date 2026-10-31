"""Shared metadata identity and processing-key contracts."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from startrails.lib.signatures import compute_signature, read_file_identity


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
