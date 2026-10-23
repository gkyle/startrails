"""Build the versioned model archive shared by macOS and Windows releases."""

import argparse
from pathlib import Path
import re
import tomllib

from release import create_models_archive, models_archive_name, sha256

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Directory for the model archive and checksum")
    args = parser.parse_args()
    with (ROOT / "pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Release versions must have three numeric components.")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / models_archive_name(version)
    create_models_archive(archive)
    (output / "SHA256SUMS").write_text(f"{sha256(archive)}  {archive.name}\n", encoding="utf-8")
    print(archive)


if __name__ == "__main__":
    main()
