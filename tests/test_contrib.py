"""Tests for the training data contribution client and PoW solver."""

import io
import json
import os
import tempfile
import urllib.error
from unittest import TestCase
from unittest.mock import MagicMock, patch
import zipfile

from startrails.lib.contrib import (
    ArchiveError,
    ContributionClient,
    ContributionError,
    PoWError,
    UploadApiError,
    build_multipart_payload,
    package_training_directory,
    solve_pow,
)


class ContribTests(TestCase):
    def test_solve_pow_vector(self):
        """Verify PoW solver matches the API_SPEC.md reproducible test vector."""
        challenge = (
            "v1:1792683130:1792683430:16:00112233445566778899aabbccddeeff:"
            "9875d222cf202d841e857a02ae216ccc7d76b12bda28d8053079fb0526924f37"
        )
        solution = solve_pow(challenge, 16)
        self.assertEqual(solution, 83090)

    def test_solve_pow_cancellation(self):
        """Verify solver terminates early when cancelled."""
        challenge = "v1:1792683130:1792683430:16:00112233445566778899aabbccddeeff:fake"
        with self.assertRaises(ContributionError):
            solve_pow(challenge, 16, is_cancelled=lambda: True)

    def test_solve_pow_invalid_difficulty(self):
        with self.assertRaises(PoWError):
            solve_pow("ch", 0)
        with self.assertRaises(PoWError):
            solve_pow("ch", 33)

    def test_package_training_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Empty directory raises ArchiveError
            with self.assertRaises(ArchiveError):
                package_training_directory(temp_dir)

            # Add sample files
            f1 = os.path.join(temp_dir, "streaks-img1-0-0-0.jpg")
            f2 = os.path.join(temp_dir, "streaks-img1-0-0-0.txt")
            with open(f1, "wb") as f:
                f.write(b"jpeg-bytes")
            with open(f2, "wb") as f:
                f.write(b"0 0.1 0.2 0.3 0.4\n")

            zip_bytes, count = package_training_directory(temp_dir)
            self.assertEqual(count, 2)
            self.assertGreater(len(zip_bytes), 0)

            # Verify flat ZIP structure
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                self.assertEqual(
                    sorted(zf.namelist()),
                    ["streaks-img1-0-0-0.jpg", "streaks-img1-0-0-0.txt"],
                )

    def test_package_training_directory_rejects_subdirectories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sub = os.path.join(temp_dir, "subfolder")
            os.mkdir(sub)
            with self.assertRaises(ArchiveError):
                package_training_directory(temp_dir)

    def test_build_multipart_payload(self):
        fields = {
            "project": "startrails",
            "training_set": "streaks",
            "app_version": "0.1.1",
            "user_email": "test@example.com",
            "user_comments": "Sample comments",
        }
        file_bytes = b"fake-zip-bundle-data"
        raw, content_type = build_multipart_payload(
            fields, file_bytes, boundary="----TestBoundary123"
        )

        self.assertIn("multipart/form-data; boundary=----TestBoundary123", content_type)
        self.assertIn(b'name="project"\r\n\r\nstartrails\r\n', raw)
        self.assertIn(b'name="training_set"\r\n\r\nstreaks\r\n', raw)
        self.assertIn(b'name="app_version"\r\n\r\n0.1.1\r\n', raw)
        self.assertIn(b'name="user_email"\r\n\r\ntest@example.com\r\n', raw)
        self.assertIn(b'name="user_comments"\r\n\r\nSample comments\r\n', raw)
        self.assertIn(b'name="file"; filename="bundle.zip"', raw)
        self.assertIn(file_bytes, raw)
        self.assertTrue(raw.endswith(b"------TestBoundary123--\r\n"))

    def test_client_get_challenge_success(self):
        client = ContributionClient(base_url="https://test.contrib.local")
        resp_data = {
            "challenge": "v1:1792683130:1792683430:16:00112233445566778899aabbccddeeff:9875d222cf202d841e857a02ae216ccc7d76b12bda28d8053079fb0526924f37",
            "algorithm": "sha256",
            "difficulty_bits": 16,
            "expires_at_utc": "2026-10-22T15:37:10Z",
        }

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(resp_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get_challenge()
            self.assertEqual(result["algorithm"], "sha256")
            self.assertEqual(result["difficulty_bits"], 16)

    def test_client_upload_error_handling(self):
        client = ContributionClient(base_url="https://test.contrib.local")

        headers = {"Retry-After": "30"}
        error_body = json.dumps({"error": "rate_limited", "detail": "Too many requests"}).encode("utf-8")
        http_error = urllib.error.HTTPError(
            url="https://test.contrib.local/api/v1/challenge",
            code=429,
            msg="Too Many Requests",
            hdrs=headers,
            fp=io.BytesIO(error_body),
        )

        with patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaises(UploadApiError) as ctx:
                client.get_challenge()
            self.assertEqual(ctx.exception.status_code, 429)
            self.assertEqual(ctx.exception.error_code, "rate_limited")
            self.assertEqual(ctx.exception.retry_after, 30)

    def test_client_submit_bundle_end_to_end(self):
        client = ContributionClient(base_url="https://test.contrib.local")

        challenge_json = json.dumps({
            "challenge": "v1:1792683130:1792683430:16:00112233445566778899aabbccddeeff:9875d222cf202d841e857a02ae216ccc7d76b12bda28d8053079fb0526924f37",
            "algorithm": "sha256",
            "difficulty_bits": 16,
            "expires_at_utc": "2026-10-22T15:37:10Z",
        }).encode("utf-8")

        receipt_json = json.dumps({
            "status": "accepted",
            "submission_id": "9f8a3c4e-1234-4678-90ab-cdef12345678",
            "project": "startrails",
            "training_set": "streaks",
            "file_count": 2,
            "size_bytes": 1024,
            "received_at_utc": "2026-10-22T15:37:11Z",
        }).encode("utf-8")

        def mock_urlopen(req, timeout=60):
            mock = MagicMock()
            if "/challenge" in req.full_url:
                mock.read.return_value = challenge_json
            elif "/contributions" in req.full_url:
                self.assertEqual(req.headers["X-pow-solution"], "83090")
                self.assertIn("Idempotency-key", req.headers)
                mock.read.return_value = receipt_json
            mock.__enter__.return_value = mock
            return mock

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            receipt = client.submit_bundle(
                zip_bytes=b"dummy-zip-bytes",
                user_email="contributor@example.com",
                user_comments="Streaks with reflections",
            )
            self.assertEqual(receipt["status"], "accepted")
            self.assertEqual(receipt["submission_id"], "9f8a3c4e-1234-4678-90ab-cdef12345678")

    def test_client_submit_bundle_rejects_invalid_email(self):
        client = ContributionClient(base_url="https://test.contrib.local")
        with self.assertRaises(ContributionError):
            client.submit_bundle(zip_bytes=b"bytes", user_email="not-an-email")
