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


def create_models_archive(path: Path) -> list[Path]:
    models = sorted(source for source in (ROOT / "models").rglob("*") if source.is_file())
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
    return models
