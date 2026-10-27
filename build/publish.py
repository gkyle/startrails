"""Interactively sync verified build artifacts to a staged GitHub Release."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build.release import GITHUB_REPOSITORY  # noqa: E402

CHECKSUM_NAME = "SHA256SUMS"
SHA256_DIGEST = re.compile(r"sha256:([0-9a-fA-F]{64})\Z")
CHECKSUM_LINE = re.compile(r"([0-9a-fA-F]{64})  ([^/\\\r\n]+)\Z")


def run_gh(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["gh", *arguments], capture_output=True, text=True, check=False)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or f"gh {' '.join(arguments[:2])} failed.")
    return result


def confirm(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def release_state(path: str) -> dict | None:
    result = run_gh("api", f"repos/{GITHUB_REPOSITORY}/releases/{path}", check=False)
    if result.returncode:
        if re.search(r"\bHTTP 404\b", result.stderr):
            return None
        raise RuntimeError(result.stderr.strip() or f"Could not inspect GitHub Release {path}.")
    return json.loads(result.stdout)


def read_checksums(path: Path) -> dict[str, str]:
    checksums = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = CHECKSUM_LINE.fullmatch(line)
        if match is None or match[2] == CHECKSUM_NAME or match[2] in checksums:
            raise ValueError(f"Invalid checksum entry in {path}: {line!r}")
        checksums[match[2]] = match[1].lower()
    return checksums


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sync_release(version: str, artifacts: list[Path], *, create_release: bool) -> None:
    if shutil.which("gh") is None:
        print("GitHub CLI (gh) is unavailable; release assets remain local.", file=sys.stderr)
        return

    tag = f"v{version}"
    paths = {path.name: path.resolve() for path in artifacts}
    if len(paths) != len(artifacts) or CHECKSUM_NAME in paths:
        raise ValueError("Release artifact names must be unique and cannot include SHA256SUMS.")
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    if not confirm(f"Sync {', '.join(paths)} to GitHub Release {tag}?"):
        print("GitHub Release unchanged.")
        return

    release = release_state(f"tags/{tag}")
    if release is None and not create_release:
        raise RuntimeError(f"GitHub Release {tag} does not exist. Publish the model archive first.")
    if release is None and not confirm(
        f"Create published release {tag} without a Latest or prerelease label from its existing Git tag?"
    ):
        print("GitHub Release unchanged.")
        return
    if release is not None and release.get("draft"):
        raise RuntimeError(f"GitHub Release {tag} is a draft; publish it before syncing assets.")
    if release is not None and release.get("immutable"):
        raise RuntimeError(f"GitHub Release {tag} is immutable and cannot accept replacement assets.")
    convert_latest = False
    if release is not None:
        latest = release_state("latest")
        if latest is not None and latest["tag_name"] == tag:
            if not confirm(f"{tag} is marked Latest. Convert it to a prerelease before syncing assets?"):
                print("GitHub Release unchanged.")
                return
            convert_latest = True

    remote_assets = {asset["name"]: asset for asset in release["assets"]} if release is not None else {}
    selected = {}
    for name, path in paths.items():
        remote = remote_assets.get(name)
        if remote is not None:
            remote_digest = remote.get("digest") or "unavailable"
            if not confirm(
                f"Replace existing {name} (remote {remote_digest}; local sha256:{sha256(path)})? "
                "The old asset is deleted before upload."
            ):
                continue
        selected[name] = path
    if not selected:
        print("No assets selected; GitHub Release unchanged.")
        return

    with TemporaryDirectory(prefix="startrails-release-sync-") as temporary:
        checksum_path = Path(temporary) / CHECKSUM_NAME
        existing_text = None
        if CHECKSUM_NAME in remote_assets:
            run_gh(
                "release", "download", tag, "--pattern", CHECKSUM_NAME,
                "--dir", temporary, "--repo", GITHUB_REPOSITORY,
            )
            existing_text = checksum_path.read_text(encoding="utf-8")
            checksums = read_checksums(checksum_path)
        else:
            checksums = {}

        current_names = set(remote_assets) - {CHECKSUM_NAME}
        current_names.update(selected)
        checksums = {name: digest for name, digest in checksums.items() if name in current_names}
        for name, asset in remote_assets.items():
            match = SHA256_DIGEST.fullmatch(asset.get("digest") or "")
            if name != CHECKSUM_NAME and match:
                checksums[name] = match[1].lower()
        for name, path in selected.items():
            checksums[name] = sha256(path)
        uncovered = current_names - checksums.keys()
        if uncovered:
            raise RuntimeError(
                "Cannot write a complete SHA256SUMS; existing assets lack a GitHub digest or checksum: "
                + ", ".join(sorted(uncovered))
            )
        checksum_text = "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items()))
        replace_checksum = existing_text is not None and existing_text != checksum_text
        if replace_checksum and not confirm(
            f"Replace existing {CHECKSUM_NAME} with a merged checksum list? "
            "The old asset is deleted before upload."
        ):
            print("GitHub Release unchanged; checksum replacement was declined.")
            return

        if release is None:
            run_gh(
                "release", "create", tag, "--repo", GITHUB_REPOSITORY,
                "--verify-tag", "--latest=false", "--notes", "",
            )
        elif convert_latest:
            run_gh("release", "edit", tag, "--repo", GITHUB_REPOSITORY, "--prerelease", "--latest=false")
        for name, path in selected.items():
            arguments = ["release", "upload", tag, str(path), "--repo", GITHUB_REPOSITORY]
            if name in remote_assets:
                arguments.append("--clobber")
            run_gh(*arguments)
            print(f"Uploaded {name} to {tag}.")

        if existing_text != checksum_text:
            checksum_path.write_text(checksum_text, encoding="utf-8")
            arguments = ["release", "upload", tag, str(checksum_path), "--repo", GITHUB_REPOSITORY]
            if existing_text is not None:
                arguments.append("--clobber")
            run_gh(*arguments)
            print(f"Uploaded {CHECKSUM_NAME} to {tag}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--create-release", action="store_true")
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        parser.error("--version must have three numeric components")
    sync_release(args.version, args.artifacts, create_release=args.create_release)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"Release sync failed: {error}") from error
