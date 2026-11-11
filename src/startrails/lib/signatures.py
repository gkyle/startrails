"""File metadata identities and deterministic processing signatures.

Callers own dependency selection, versioning and missing-file policy. Metadata
identities detect ordinary file changes; they are not hashes of file contents.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FileIdentity:
    path: str
    size: int
    mtime_ns: int
    ctime_ns: int


def read_file_identity(path: Path | str) -> FileIdentity:
    """Read resolved file metadata, propagating filesystem errors to the caller."""
    resolved = Path(path).resolve()
    stat = resolved.stat()
    return FileIdentity(str(resolved), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def compute_signature(payload: dict[str, Any]) -> str:
    """Hash a JSON-compatible mapping, independent of dictionary insertion order.

    Callers include operation/version fields when needed. List order remains
    significant. Preserve the serialization used by existing Denoise caches.
    """
    encoded = json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
