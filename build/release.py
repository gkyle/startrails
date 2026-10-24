"""Files shared by platform release builders."""

import hashlib
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".py", ".ps1", ".sh", ".ui", ".qrc", ".qss", ".svg", ".png"}
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
RELEASE_HASH_PREFIX_LENGTH = 12
MODEL_METADATA_SUFFIXES = {".json", ".xml", ".yaml", ".yml"}


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


def create_models_archive(path: Path) -> None:
    models = sorted(
        source for source in (ROOT / "models").rglob("*")
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
