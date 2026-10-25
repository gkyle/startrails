"""Build the versioned model archive shared by macOS and Windows releases."""

import argparse
from pathlib import Path
import re
import tomllib

from release import create_models_archive, models_archive_name, sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "out/models"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the model archive and checksum (default: repository out/models/)",
    )
    parser.add_argument("--print-path", action="store_true", help="Print the versioned archive path without building it")
    args = parser.parse_args()
    with (ROOT / "pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Release versions must have three numeric components.")
    output = args.output.resolve()
    archive = output / models_archive_name(version)
    if args.print_path:
        print(archive)
        return
    output.mkdir(parents=True, exist_ok=True)
    create_models_archive(archive)
    (output / "SHA256SUMS").write_text(f"{sha256(archive)}  {archive.name}\n", encoding="utf-8")
    print(archive)


if __name__ == "__main__":
    main()
