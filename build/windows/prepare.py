"""Stage an allowlisted Windows release and its downloadable model archive."""

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import runpy
import shutil
import sys
import tomllib
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build"))
from release import (  # noqa: E402
    RELEASE_HASH_PREFIX_LENGTH,
    copy_source_tree,
    models_archive_url,
    sha256,
    stage_models_archive,
)


def prepare(output: Path, uv_executable: Path, models_archive: Path, model_base_url: str | None) -> dict:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    toolchain = json.loads((ROOT / "build/toolchain.json").read_text(encoding="utf-8"))
    version = project["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Windows installer versions must have three numeric components.")
    python_requirement = project["requires-python"]
    if not python_requirement.startswith("==") or not fnmatch.fnmatchcase(
        toolchain["python_version"],
        python_requirement.removeprefix("=="),
    ):
        raise ValueError("The pinned Windows Python version must satisfy project.requires-python.")
    models_url = models_archive_url(version, model_base_url)

    output.mkdir(parents=True, exist_ok=True)
    stage = output / "app"
    # A fresh directory prevents deleted source files from leaking into a later build.
    stage.mkdir()
    for name in ("README.md", "LICENSE", "pyproject.toml", "uv.lock"):
        shutil.copy2(ROOT / name, stage / name)
    copy_source_tree(stage)
    (stage / "tools").mkdir()
    shutil.copy2(uv_executable, stage / "tools/uv.exe")
    # uv is redistributed under both licenses, alongside its upstream copyright notices.
    for name in ("LICENSE-MIT", "LICENSE-APACHE"):
        license_path = uv_executable.parent / name
        shutil.copy2(license_path, stage / "tools" / license_path.name)

    (stage / "resources").mkdir()
    shutil.copy2(ROOT / "src/startrails/ui/icons/startrails_windows.ico", stage / "resources/startrails.ico")

    model_archive, model_hash, models_size = stage_models_archive(models_archive, output, version)
    payload_hash = hashlib.sha256()
    for path in sorted(path for path in stage.rglob("*") if path.is_file()):
        payload_hash.update(path.relative_to(stage).as_posix().encode("utf-8"))
        payload_hash.update(bytes.fromhex(sha256(path)))
    payload_hash.update(bytes.fromhex(model_hash))
    payload_hash.update(toolchain["python_version"].encode("ascii"))
    payload_hash.update(toolchain["uv_version"].encode("ascii"))
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
        "ModelsUrl": models_url,
        "ModelsHash": model_hash,
    }
    config = "".join(f'#define {key} "{value}"\n' for key, value in definitions.items())
    config += f"#define ModelsSize {models_size}\n"
    config += f"#define ApplicationSize {sum(path.stat().st_size for path in application_files)}\n"
    (output / "build_config.iss").write_text(config, encoding="utf-8")
    (output / "SHA256SUMS").write_text(f"{model_hash}  {model_archive.name}\n", encoding="utf-8")
    return {"output": str(output), **release}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--uv-executable", type=Path, required=True)
    parser.add_argument("--models-archive", type=Path, required=True)
    parser.add_argument("--model-base-url")
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                args.output.resolve(),
                args.uv_executable.resolve(),
                args.models_archive.resolve(),
                args.model_base_url,
            )
        )
    )


if __name__ == "__main__":
    main()
