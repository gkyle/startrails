"""Stage an allowlisted Windows release and its downloadable model archive."""

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import runpy
import shutil
import tomllib
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SUFFIXES = {".py", ".ps1", ".ui", ".qrc", ".qss", ".svg", ".png"}
RELEASE_HASH_PREFIX_LENGTH = 12


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(output: Path, uv_executable: Path, model_base_url: str | None) -> dict:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    toolchain = json.loads((ROOT / "build/windows/toolchain.json").read_text(encoding="utf-8"))
    version = project["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Windows installer versions must have three numeric components.")
    python_requirement = project["requires-python"]
    if not python_requirement.startswith("==") or not fnmatch.fnmatchcase(
        toolchain["python_version"],
        python_requirement.removeprefix("=="),
    ):
        raise ValueError("The pinned Windows Python version must satisfy project.requires-python.")
    base_url = model_base_url or f"https://github.com/gkyle/startrails/releases/download/v{version}"
    parsed_url = urlparse(base_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc or any(char in base_url for char in "\r\n\"';"):
        raise ValueError("ModelBaseUrl must be an HTTPS URL with a host and without quotes or newlines.")

    output.mkdir(parents=True, exist_ok=True)
    stage = output / "app"
    # A fresh directory prevents deleted source files from leaking into a later build.
    stage.mkdir()
    for name in ("README.md", "LICENSE", "pyproject.toml", "uv.lock"):
        shutil.copy2(ROOT / name, stage / name)
    for source in sorted((ROOT / "src").rglob("*")):
        if source.is_file() and source.suffix in SOURCE_SUFFIXES and "__pycache__" not in source.parts:
            destination = stage / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    shutil.copy2(ROOT / "build/windows/run.bat", stage / "run.bat")
    (stage / "tools").mkdir()
    shutil.copy2(uv_executable, stage / "tools/uv.exe")
    # uv is redistributed under both licenses, alongside its upstream copyright notices.
    for name in ("LICENSE-MIT", "LICENSE-APACHE"):
        license_path = uv_executable.parent / name
        shutil.copy2(license_path, stage / "tools" / license_path.name)

    (stage / "resources").mkdir()
    shutil.copy2(ROOT / "src/startrails/ui/icons/startrails_windows.ico", stage / "resources/startrails.ico")

    model_archive = output / f"StarTrailsAI-{version}-models.zip"
    models = sorted(path for path in (ROOT / "models").rglob("*") if path.is_file())
    if not models or not any(path.suffix == ".safetensors" for path in models):
        raise ValueError("The checked-in models, including sky detection, are required to build a release.")
    with ZipFile(model_archive, "w", compression=ZIP_DEFLATED) as archive:
        for model in models:
            archive.write(model, model.relative_to(ROOT).as_posix())
    model_hash = sha256(model_archive)
    payload_hash = hashlib.sha256()
    for path in sorted(path for path in stage.rglob("*") if path.is_file()):
        payload_hash.update(path.relative_to(stage).as_posix().encode("utf-8"))
        payload_hash.update(bytes.fromhex(sha256(path)))
    payload_hash.update(bytes.fromhex(model_hash))
    payload_hash.update(json.dumps(toolchain, sort_keys=True).encode("utf-8"))
    release = {
        "version": version,
        "release_id": f"{version}-{payload_hash.hexdigest()[:RELEASE_HASH_PREFIX_LENGTH]}",
        "python_version": toolchain["python_version"],
        "uv_version": toolchain["uv_version"],
    }
    (stage / "release.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    application_files = sorted(path for path in stage.rglob("*") if path.is_file())
    application_archive = output / "application.zip"
    with ZipFile(application_archive, "w", compression=ZIP_DEFLATED) as archive:
        for path in application_files:
            archive.write(path, path.relative_to(stage).as_posix())
    # Load the runtime's shell identity without requiring Qt at build time.
    app_user_model_id = runpy.run_path(str(ROOT / "src/startrails/windows.py"))["APP_USER_MODEL_ID"]
    definitions = {
        "AppVersion": version,
        "AppUserModelId": app_user_model_id,
        "ReleaseId": release["release_id"],
        "ApplicationName": application_archive.name,
        "ModelsName": model_archive.name,
        "ModelsUrl": f"{base_url.rstrip('/')}/{model_archive.name}",
        "ModelsHash": model_hash,
    }
    config = "".join(f'#define {key} "{value}"\n' for key, value in definitions.items())
    config += f"#define ModelsSize {sum(path.stat().st_size for path in models)}\n"
    config += f"#define ApplicationSize {sum(path.stat().st_size for path in application_files)}\n"
    (output / "build_config.iss").write_text(config, encoding="utf-8")
    (output / "SHA256SUMS").write_text(f"{model_hash}  {model_archive.name}\n", encoding="utf-8")
    return {"output": str(output), **release}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--uv-executable", type=Path, required=True)
    parser.add_argument("--model-base-url")
    args = parser.parse_args()
    print(json.dumps(prepare(args.output.resolve(), args.uv_executable.resolve(), args.model_base_url)))


if __name__ == "__main__":
    main()
