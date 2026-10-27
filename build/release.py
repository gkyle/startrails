"""Files shared by platform release builders."""

import hashlib
import json
from pathlib import Path
import re
import shutil
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".py", ".ps1", ".sh", ".ui", ".qrc", ".qss", ".svg", ".png"}
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_CREATOR_SYSTEM_UNIX = 3
RELEASE_HASH_PREFIX_LENGTH = 12
MODEL_METADATA_SUFFIXES = {".json", ".xml", ".yaml", ".yml"}
GITHUB_REPOSITORY = "gkyle/startrails"
DOWNLOAD_TIMEOUT_SECONDS = 60


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def copy_source_tree(stage: Path) -> None:
    for source in sorted((ROOT / "src").rglob("*")):
        if source.is_file() and source.suffix in SOURCE_SUFFIXES and "__pycache__" not in source.parts:
            destination = stage / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def models_archive_name(version: str) -> str:
    return f"StarTrailsAI-{version}-models.zip"


def models_archive_url(version: str, base_url: str | None) -> str:
    base_url = base_url or f"https://github.com/{GITHUB_REPOSITORY}/releases/download/v{version}"
    parsed_url = urlparse(base_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc or any(char in base_url for char in "\r\n\"';"):
        raise ValueError("ModelBaseUrl must be an HTTPS URL with a host and without quotes or newlines.")
    return f"{base_url.rstrip('/')}/{models_archive_name(version)}"


def download_models_archive(output: Path, version: str) -> Path:
    name = models_archive_name(version)
    release_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/tags/v{version}"
    headers = {"User-Agent": "StarTrailsAI-release-builder", "Accept": "application/vnd.github+json"}
    missing_archive_message = f"Publish {name} to the v{version} GitHub Release before building installers."
    try:
        with urlopen(Request(release_url, headers=headers), timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            metadata = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            raise ValueError(missing_archive_message) from error
        raise
    asset = next((asset for asset in metadata["assets"] if asset["name"] == name), None)
    if asset is None:
        raise ValueError(missing_archive_message)
    digest = asset.get("digest")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError(f"The published {name} asset must have a GitHub SHA-256 digest.")
    expected_hash = digest.removeprefix("sha256:")
    archive = output / name
    if archive.is_file() and sha256(archive) == expected_hash:
        return archive

    output.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=output, prefix=f".{name}.", suffix=".download", delete=False) as stream:
            temporary = Path(stream.name)
            request = Request(models_archive_url(version, None), headers={"User-Agent": headers["User-Agent"]})
            with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
                shutil.copyfileobj(response, stream)
        if sha256(temporary) != expected_hash:
            raise ValueError(f"Downloaded {name} failed GitHub SHA-256 verification.")
        temporary.replace(archive)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return archive


def create_models_archive(path: Path) -> None:
    models = sorted(
        source
        for source in (ROOT / "models").rglob("*")
        if source.is_file()
        and "__pycache__" not in source.parts
        and not source.name.startswith(".")
        and source.suffix not in {".pyc", ".pyo"}
    )
    if not models or not any(model.suffix == ".safetensors" for model in models):
        raise ValueError("The checked-in models, including sky detection, are required to build a release.")
    with ZipFile(path, "w") as archive:
        for model in models:
            entry = ZipInfo(model.relative_to(ROOT).as_posix(), ZIP_TIMESTAMP)
            # ZIP creator metadata must be identical on Windows and Unix hosts.
            entry.create_system = ZIP_CREATOR_SYSTEM_UNIX
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            content = model.read_bytes()
            # Git may check text files out with CRLF on Windows; release hashes
            # must be identical across platforms for the same model content.
            if model.suffix in MODEL_METADATA_SUFFIXES:
                content = content.replace(b"\r\n", b"\n")
            archive.writestr(entry, content)


def stage_models_archive(source: Path, output: Path, version: str) -> tuple[Path, str, int]:
    name = models_archive_name(version)
    if source.name != name:
        raise ValueError(f"Expected model archive named {name}, got {source.name}.")
    with ZipFile(source) as archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        if not entries or not any(entry.filename.endswith(".safetensors") for entry in entries):
            raise ValueError("The model archive must include sky detection weights.")
        if any(not entry.filename.startswith("models/") or ".." in Path(entry.filename).parts for entry in entries):
            raise ValueError("The model archive contains a path outside models/.")
        if bad_entry := archive.testzip():
            raise ValueError(f"The model archive contains a corrupt entry: {bad_entry}")
        models_size = sum(entry.file_size for entry in entries)
    destination = output / name
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    return destination, sha256(destination), models_size
