"""Client for the StarTrails training data contribution service.

Adheres to the ingestion API specification in /home/kyle/code/training-web/API_SPEC.md.
Handles flat packaging, proof-of-work (PoW) challenge solving, deterministic
multipart encoding, and receipt handling.
"""

from collections.abc import Callable
import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.request
import uuid
import zipfile

DEFAULT_CONTRIB_API_BASE_URL: str = "https://contrib.kylescholz.com"
DEFAULT_CONTRIB_PROJECT: str = "startrails"
DEFAULT_CONTRIB_TRAINING_SET: str = "streaks"

MAX_UPLOAD_REQUEST_BYTES: int = 50 * 1024 * 1024  # 50 MiB
MAX_DECLARED_UNCOMPRESSED_BYTES: int = 250 * 1024 * 1024  # 250 MiB
MAX_ZIP_ENTRIES_COUNT: int = 3000
MAX_ENTRY_NAME_BYTES: int = 255
MAX_POW_DIFFICULTY_BITS: int = 32
DEFAULT_HTTP_TIMEOUT_SECONDS: int = 60

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class ContributionError(Exception):
    """Base exception for contribution pipeline errors."""


class PoWError(ContributionError):
    """Proof-of-work challenge retrieval or solving failure."""


class ArchiveError(ContributionError):
    """Generated contribution archive violates volume, count, or format rules."""


class UploadApiError(ContributionError):
    """Contribution service returned a non-success response."""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        detail: str,
        retry_after: int | None = None,
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail
        self.retry_after = retry_after
        message = f"HTTP {status_code} ({error_code}): {detail}"
        if retry_after is not None:
            message += f" (retry after {retry_after}s)"
        super().__init__(message)


def package_training_directory(source_dir: str) -> tuple[bytes, int]:
    """Package flat training crops and label files into an in-memory ZIP archive.

    Returns:
        (zip_bytes, file_count)

    Raises:
        ArchiveError: If the directory is empty, has too many files, nested folders,
                      or exceeds size limits.
    """
    if not os.path.isdir(source_dir):
        raise ArchiveError(f"Training directory does not exist: {source_dir}")

    entry_names = sorted(os.listdir(source_dir))
    if not entry_names:
        raise ArchiveError("No training crops were generated from streak corrections.")

    if len(entry_names) > MAX_ZIP_ENTRIES_COUNT:
        raise ArchiveError(
            f"Archive entry count {len(entry_names)} exceeds limit of {MAX_ZIP_ENTRIES_COUNT}."
        )

    zip_buffer = io.BytesIO()
    total_uncompressed_bytes = 0
    file_count = 0

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in entry_names:
            file_path = os.path.join(source_dir, name)
            if os.path.isdir(file_path):
                raise ArchiveError(f"Directory entry '{name}' found; training archives must be flat.")
            if not os.path.isfile(file_path):
                continue
            if "/" in name or "\\" in name or ".." in name:
                raise ArchiveError(f"Invalid entry name '{name}'; paths are not permitted.")
            if len(name.encode("utf-8")) > MAX_ENTRY_NAME_BYTES:
                raise ArchiveError(f"Entry name '{name}' exceeds {MAX_ENTRY_NAME_BYTES} bytes.")

            file_size = os.path.getsize(file_path)
            total_uncompressed_bytes += file_size
            if total_uncompressed_bytes > MAX_DECLARED_UNCOMPRESSED_BYTES:
                raise ArchiveError(
                    f"Uncompressed archive size exceeds limit of {MAX_DECLARED_UNCOMPRESSED_BYTES} bytes."
                )

            zf.write(file_path, arcname=name)
            file_count += 1

    if file_count == 0:
        raise ArchiveError("No files found in training export directory.")

    zip_bytes = zip_buffer.getvalue()
    if len(zip_bytes) > MAX_UPLOAD_REQUEST_BYTES:
        raise ArchiveError(
            f"Archive compressed size ({len(zip_bytes)} bytes) exceeds limit of {MAX_UPLOAD_REQUEST_BYTES} bytes."
        )

    return zip_bytes, file_count


def solve_pow(
    challenge: str,
    difficulty_bits: int,
    max_iterations: int = 10_000_000,
    is_cancelled: Callable[[], bool] | None = None,
) -> int:
    """Solve an advertised proof-of-work challenge off the UI thread.

    Finds the smallest integer `solution >= 0` such that SHA-256(challenge + ":" + solution)
    has at least `difficulty_bits` leading zero bits.
    """
    if not (1 <= difficulty_bits <= MAX_POW_DIFFICULTY_BITS):
        raise PoWError(f"Invalid PoW difficulty {difficulty_bits}; must be 1-{MAX_POW_DIFFICULTY_BITS} bits.")

    prefix = f"{challenge}:".encode("ascii")
    nonce = 0
    while nonce < max_iterations:
        if is_cancelled is not None and is_cancelled():
            raise ContributionError("PoW solving cancelled by user.")

        digest = hashlib.sha256(prefix + str(nonce).encode("ascii")).digest()
        if int.from_bytes(digest, "big") >> (256 - difficulty_bits) == 0:
            return nonce
        nonce += 1

    raise PoWError(f"Exceeded {max_iterations} attempts solving challenge.")


def build_multipart_payload(
    fields: dict[str, str | None],
    file_bytes: bytes,
    file_part_name: str = "file",
    filename: str = "bundle.zip",
    boundary: str | None = None,
) -> tuple[bytes, str]:
    """Build a deterministic multipart/form-data body and Content-Type header."""
    if boundary is None:
        boundary = "----StarTrailsBoundary" + uuid.uuid4().hex

    body = io.BytesIO()
    for name, value in fields.items():
        if value is None or value == "":
            continue
        body.write(f"--{boundary}\r\n".encode("ascii"))
        body.write(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii")
        )
        body.write(str(value).encode("utf-8") + b"\r\n")

    body.write(f"--{boundary}\r\n".encode("ascii"))
    body.write(
        f'Content-Disposition: form-data; name="{file_part_name}"; filename="{filename}"\r\n'.encode("ascii")
    )
    body.write(b"Content-Type: application/zip\r\n\r\n")
    body.write(file_bytes + b"\r\n")
    body.write(f"--{boundary}--\r\n".encode("ascii"))

    raw = body.getvalue()
    content_type = f"multipart/form-data; boundary={boundary}"
    return raw, content_type


class ContributionClient:
    """Client for negotiating PoW and submitting training data bundles."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int = DEFAULT_HTTP_TIMEOUT_SECONDS,
    ):
        if base_url is not None:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = os.environ.get("CONTRIB_API_BASE_URL", DEFAULT_CONTRIB_API_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_challenge(self) -> dict:
        """Request a fresh proof-of-work challenge token."""
        url = f"{self.base_url}/api/v1/challenge"
        req = urllib.request.Request(url, headers={"Cache-Control": "no-store"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            retry_after = err.headers.get("Retry-After")
            retry_val = int(retry_after) if retry_after and retry_after.isdigit() else None
            try:
                body = json.loads(err.read().decode("utf-8"))
                error_code = body.get("error", "http_error")
                detail = body.get("detail", str(err))
            except Exception:
                error_code = "http_error"
                detail = str(err)
            raise UploadApiError(err.code, error_code, detail, retry_val) from err
        except OSError as err:
            raise ContributionError(f"Could not reach contribution server: {err}") from err

        if data.get("algorithm") != "sha256":
            raise PoWError(f"Unsupported PoW algorithm: {data.get('algorithm')}")

        return data

    def upload_contribution(
        self,
        body_bytes: bytes,
        content_type: str,
        challenge: str,
        solution: int,
        idempotency_key: str | None = None,
    ) -> dict:
        """POST an admitted multipart body with PoW headers to /api/v1/contributions."""
        if len(body_bytes) > MAX_UPLOAD_REQUEST_BYTES:
            raise ArchiveError(
                f"Total request payload ({len(body_bytes)} bytes) exceeds limit of {MAX_UPLOAD_REQUEST_BYTES} bytes."
            )

        if idempotency_key is None:
            idempotency_key = str(uuid.uuid4())

        digest = hashlib.sha256(body_bytes).hexdigest()
        headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(body_bytes)),
            "Idempotency-Key": idempotency_key,
            "X-Content-SHA256": digest,
            "X-PoW-Challenge": challenge,
            "X-PoW-Solution": str(solution),
            "Cache-Control": "no-store",
        }

        url = f"{self.base_url}/api/v1/contributions"
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                receipt = json.loads(resp.read().decode("utf-8"))
                return receipt
        except urllib.error.HTTPError as err:
            retry_after = err.headers.get("Retry-After")
            retry_val = int(retry_after) if retry_after and retry_after.isdigit() else None
            try:
                body = json.loads(err.read().decode("utf-8"))
                error_code = body.get("error", "http_error")
                detail = body.get("detail", str(err))
            except Exception:
                error_code = "http_error"
                detail = str(err)
            raise UploadApiError(err.code, error_code, detail, retry_val) from err
        except OSError as err:
            raise ContributionError(f"Contribution upload failed: {err}") from err

    def submit_bundle(
        self,
        zip_bytes: bytes,
        project: str = DEFAULT_CONTRIB_PROJECT,
        training_set: str = DEFAULT_CONTRIB_TRAINING_SET,
        app_version: str | None = None,
        model_version: str | None = None,
        user_email: str | None = None,
        user_comments: str | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> dict:
        """End-to-end package, challenge solve, and upload."""
        if user_email:
            user_email = user_email.strip()
            if not EMAIL_PATTERN.fullmatch(user_email):
                raise ContributionError("Invalid contact email format.")

        fields = {
            "project": project,
            "training_set": training_set,
            "app_version": app_version,
            "model_version": model_version,
            "user_email": user_email if user_email else None,
            "user_comments": user_comments.strip() if user_comments else None,
        }

        body_bytes, content_type = build_multipart_payload(fields, zip_bytes)

        if is_cancelled is not None and is_cancelled():
            raise ContributionError("Operation cancelled.")

        challenge_data = self.get_challenge()
        token = challenge_data["challenge"]
        bits = int(challenge_data["difficulty_bits"])

        if is_cancelled is not None and is_cancelled():
            raise ContributionError("Operation cancelled.")

        solution = solve_pow(token, bits, is_cancelled=is_cancelled)

        if is_cancelled is not None and is_cancelled():
            raise ContributionError("Operation cancelled.")

        return self.upload_contribution(body_bytes, content_type, token, solution)
