"""Stage a per-user macOS installer and a verified model archive."""

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build"))
from release import (  # noqa: E402
    RELEASE_HASH_PREFIX_LENGTH,
    copy_source_tree,
    models_archive_name,
    models_archive_url,
    sha256,
    stage_models_archive,
)

BUNDLE_ID = "org.startrails.ai"


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def write_executable(source: Path, target: Path) -> None:
    copy_file(source, target)
    target.chmod(0o755)


def build_app(stage: Path, version: str, min_macos_version: str) -> None:
    contents = stage / "StarTrails AI.app/Contents"
    contents.mkdir(parents=True)
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(
            {
                "CFBundleDevelopmentRegion": "en",
                "CFBundleExecutable": "StarTrails",
                "CFBundleIconFile": "startrails.icns",
                "CFBundleIdentifier": BUNDLE_ID,
                "CFBundleInfoDictionaryVersion": "6.0",
                "CFBundleName": "StarTrails AI",
                "CFBundlePackageType": "APPL",
                "CFBundleShortVersionString": version,
                "CFBundleVersion": version,
                "LSArchitecturePriority": ["arm64"],
                "LSMinimumSystemVersion": min_macos_version,
                "NSHighResolutionCapable": True,
            },
            stream,
        )
    write_executable(ROOT / "build/macos/launcher.sh", contents / "MacOS/StarTrails")
    copy_file(ROOT / "build/macos/common.sh", contents / "Resources/common.sh")
    copy_file(ROOT / "src/startrails/ui/icons/startrails_macos.icns", contents / "Resources/startrails.icns")


def build_installer_app(dmg: Path, version: str, min_macos_version: str) -> None:
    contents = dmg / "Install StarTrails AI.app/Contents"
    executable = contents / "MacOS/Install StarTrails AI"
    executable.parent.mkdir(parents=True)
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(
            {
                "CFBundleDevelopmentRegion": "en",
                "CFBundleExecutable": executable.name,
                "CFBundleIconFile": "startrails.icns",
                "CFBundleIdentifier": "org.startrails.ai.installer",
                "CFBundleInfoDictionaryVersion": "6.0",
                "CFBundleName": "Install StarTrails AI",
                "CFBundlePackageType": "APPL",
                "CFBundleShortVersionString": version,
                "CFBundleVersion": version,
                "LSMinimumSystemVersion": min_macos_version,
                "NSHighResolutionCapable": True,
            },
            stream,
        )
    resource = contents / "Resources/install.sh"
    copy_file(ROOT / "build/macos/install.sh", resource)
    resource.chmod(0o644)
    copy_file(ROOT / "src/startrails/ui/icons/startrails_macos.icns", contents / "Resources/startrails.icns")
    with TemporaryDirectory(prefix="startrails-swift-cache-") as module_cache:
        subprocess.run(
            [
                "xcrun",
                "swiftc",
                "-O",
                "-module-cache-path",
                module_cache,
                "-target",
                f"arm64-apple-macosx{min_macos_version}",
                "-o",
                str(executable),
                str(ROOT / "build/macos/installer.swift"),
            ],
            check=True,
            env={**os.environ, "CLANG_MODULE_CACHE_PATH": module_cache},
        )


def finalize(output: Path) -> dict:
    release_file = output / "release.json"
    release = json.loads(release_file.read_text(encoding="utf-8"))
    model_archive = output / models_archive_name(release["version"])
    if sha256(model_archive) != release["models_sha256"]:
        raise ValueError("The staged model archive changed after preparation.")

    payload = output / "dmg/.payload"
    payload_hash = hashlib.sha256()
    for path in sorted(path for path in payload.rglob("*") if path.is_file() and path != payload / "release.conf"):
        payload_hash.update(path.relative_to(payload).as_posix().encode("utf-8"))
        payload_hash.update(bytes.fromhex(sha256(path)))
    payload_hash.update(bytes.fromhex(release["models_sha256"]))
    payload_hash.update(release["python_version"].encode("ascii"))
    payload_hash.update(release["uv_version"].encode("ascii"))
    release["release_id"] = f"{release['version']}-{payload_hash.hexdigest()[:RELEASE_HASH_PREFIX_LENGTH]}"
    release_file.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    (payload / "release.conf").write_text(
        "".join(f"{key}={shlex.quote(value)}\n" for key, value in release.items()), encoding="utf-8"
    )
    (output / "SHA256SUMS").write_text(f"{release['models_sha256']}  {model_archive.name}\n", encoding="utf-8")
    return release


def prepare(output: Path, uv_executable: Path, models_archive: Path, model_base_url: str | None) -> dict:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    toolchain = json.loads((ROOT / "build/toolchain.json").read_text(encoding="utf-8"))
    version = project["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("macOS installer versions must have three numeric components.")
    if not re.fullmatch(r"\d+\.\d+", toolchain["macos_min_version"]):
        raise ValueError("macos_min_version must contain a major and minor version.")
    python_requirement = project["requires-python"]
    if not python_requirement.startswith("==") or not fnmatch.fnmatchcase(
        toolchain["python_version"], python_requirement.removeprefix("==")
    ):
        raise ValueError("The pinned Python version must satisfy project.requires-python.")
    models_url = models_archive_url(version, model_base_url)

    output.mkdir(parents=True, exist_ok=True)
    dmg = output / "dmg"
    dmg.mkdir()
    payload = dmg / ".payload"
    payload.mkdir()
    for name in ("README.md", "LICENSE", "pyproject.toml", "uv.lock"):
        copy_file(ROOT / name, payload / name)
    copy_source_tree(payload)
    copy_file(uv_executable, payload / "tools/uv")
    (payload / "tools/uv").chmod(0o755)
    for name in ("LICENSE-MIT", "LICENSE-APACHE"):
        copy_file(uv_executable.parent / name, payload / "tools" / name)
    build_app(payload, version, toolchain["macos_min_version"])
    copy_file(ROOT / "build/macos/common.sh", payload / "common.sh")

    model_archive, model_hash, _ = stage_models_archive(models_archive, output, version)
    release = {
        "version": version,
        "python_version": toolchain["python_version"],
        "uv_version": toolchain["uv_version"],
        "macos_min_version": toolchain["macos_min_version"],
        "models_url": models_url,
        "models_sha256": model_hash,
    }
    (output / "release.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    build_installer_app(dmg, version, toolchain["macos_min_version"])
    (dmg / "Install Instructions.txt").write_text(
        "Double-click Install StarTrails AI.app. Installation needs an internet connection "
        "for Python, dependencies, and the model archive.\n"
        "The installer opens StarTrails AI after installation or repair. Run it again to repair the app.\n"
        "To remove the app, move StarTrails AI.app from your Applications folder to the Trash.\n"
        "Its runtime and cache remain in your Library until removed separately; projects are kept.\n",
        encoding="utf-8",
    )
    return finalize(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--uv-executable", type=Path)
    parser.add_argument("--models-archive", type=Path)
    parser.add_argument("--model-base-url")
    parser.add_argument("--toolchain", action="store_true")
    parser.add_argument("--finalize-output", type=Path)
    args = parser.parse_args()
    if args.toolchain:
        toolchain = json.loads((ROOT / "build/toolchain.json").read_text(encoding="utf-8"))
        print(toolchain["uv_version"], toolchain["macos_arm64_uv_archive_sha256"])
        return
    if args.finalize_output is not None:
        print(json.dumps(finalize(args.finalize_output.resolve())))
        return
    if args.output is None or args.uv_executable is None or args.models_archive is None:
        parser.error("--output, --uv-executable, and --models-archive are required to prepare a release")
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
