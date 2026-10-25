"""Build or download the versioned model archive shared by platform releases."""

import argparse
from pathlib import Path
import re
import sys
import tomllib

from release import create_models_archive, download_models_archive, models_archive_name, sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "out/models"
DEFAULT_DOWNLOAD_DIR = DEFAULT_OUTPUT_DIR / "downloads"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Archive and checksum directory (default: out/models/; out/models/downloads/ with --download)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--print-path", action="store_true", help="Print the versioned archive path without building it")
    mode.add_argument(
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
    archive = output / models_archive_name(version)
    if args.print_path:
        print(archive)
        return
    if args.download:
        print(f"Fetching published models for v{version}...", file=sys.stderr)
        archive = download_models_archive(output, version)
    else:
        output.mkdir(parents=True, exist_ok=True)
        create_models_archive(archive)
    (output / "SHA256SUMS").write_text(f"{sha256(archive)}  {archive.name}\n", encoding="utf-8")
    print(archive)


if __name__ == "__main__":
    main()
