"""Build or download the versioned model archive shared by platform releases."""

import argparse
from pathlib import Path
import re
import shutil
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
# Reuse the app's pinned asset identity and integrity check without importing
# inference libraries into the build tool.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from build.release import create_models_archive, download_models_archive, models_archive_name, sha256
from build.publish import sync_release
from startrails.lib.finish.graxpert import GRAXPERT_MODEL_RELATIVE_PATH

DEFAULT_OUTPUT_DIR = ROOT / "out/models"
DEFAULT_DOWNLOAD_DIR = DEFAULT_OUTPUT_DIR / "downloads"


def prepare_graxpert_bundle(models_dir: Path) -> None:
    model = models_dir / GRAXPERT_MODEL_RELATIVE_PATH
    if not model.is_file():
        raise ValueError(f"Missing GraXpert model: {model}. See {model.parent / 'README.md'}.")
    notice_names = ("README.md", "LICENSE.html", "LICENSE.txt")
    for notice in notice_names:
        if not (model.parent / notice).is_file():
            raise ValueError(f"Missing GraXpert attribution/license notice: {model.parent / notice}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Archive and checksum directory (default: out/models/; out/models/downloads/ with --download)",
    )
    parser.add_argument(
        "--download", action="store_true", help="Fetch the shared archive and verify GitHub's asset digest"
    )
    args = parser.parse_args()
    with (ROOT / "pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Release versions must have three numeric components.")
    output = (
        args.output.resolve()
        if args.output is not None
        else (DEFAULT_DOWNLOAD_DIR if args.download else DEFAULT_OUTPUT_DIR)
    )
    if args.download:
        print(f"Fetching published models for v{version}...", file=sys.stderr)
        archive = download_models_archive(output, version)
    else:
        prepare_graxpert_bundle(ROOT / "models")
        output.mkdir(parents=True, exist_ok=True)
        archive = output / models_archive_name(version)
        create_models_archive(archive)
    (output / "SHA256SUMS").write_text(f"{sha256(archive)}  {archive.name}\n", encoding="utf-8")
    print(archive)
    if not args.download:
        try:
            sync_release(version, [archive], create_release=True)
        except (OSError, ValueError, RuntimeError) as error:
            raise SystemExit(f"Release sync failed: {error}") from error


if __name__ == "__main__":
    main()
