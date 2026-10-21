"""All-or-nothing publication preserves prior outputs and removes owned staging."""

from concurrent.futures import CancelledError
import os
from threading import Event
from unittest.mock import patch

from support import IsolatedTestCase
from startrails.lib.artifacts import ArtifactTransaction


class ArtifactTests(IsolatedTestCase):
    def test_success_publishes_all_files_and_cleans_staging(self):
        first, second = self.root / "first.tif", self.root / "second.png"
        first.write_bytes(b"old")
        with ArtifactTransaction() as transaction:
            transaction.stage(first).write_bytes(b"new first")
            transaction.stage(second).write_bytes(b"new second")
            self.assertEqual(first.read_bytes(), b"old")
            self.assertFalse(second.exists())
            transaction.commit()
        self.assertEqual(first.read_bytes(), b"new first")
        self.assertEqual(second.read_bytes(), b"new second")
        self.assertEqual(set(self.root.iterdir()), {first, second})

    def test_partial_publication_failure_restores_destinations(self):
        first, second = self.root / "first.tif", self.root / "second.tif"
        first.write_bytes(b"old first")
        second.write_bytes(b"old second")
        replace = os.replace
        with ArtifactTransaction() as transaction:
            transaction.stage(first).write_bytes(b"new first")
            staged_second = transaction.stage(second)
            staged_second.write_bytes(b"new second")

            def fail_second(source, destination):
                if source == staged_second:
                    raise OSError("simulated disk failure")
                return replace(source, destination)

            with patch("startrails.lib.artifacts.os.replace", side_effect=fail_second):
                with self.assertRaisesRegex(OSError, "disk failure"):
                    transaction.commit()
        self.assertEqual(first.read_bytes(), b"old first")
        self.assertEqual(second.read_bytes(), b"old second")
        self.assertEqual(set(self.root.iterdir()), {first, second})

    def test_cancelled_or_unwritten_transaction_preserves_previous_output(self):
        destination = self.root / "output.tif"
        destination.write_bytes(b"previous")
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                event = Event()
                with ArtifactTransaction(event.is_set) as transaction:
                    staged = transaction.stage(destination)
                    if cancel:
                        staged.write_bytes(b"partial")
                        event.set()
                    with self.assertRaises(CancelledError if cancel else OSError):
                        transaction.commit()
                self.assertEqual(destination.read_bytes(), b"previous")
                self.assertEqual(list(self.root.iterdir()), [destination])
