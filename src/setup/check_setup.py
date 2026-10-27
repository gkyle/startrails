"""Validate the probe's result against the project's dependency policy."""

import argparse
from pathlib import Path
import tomllib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", required=True)
    args = parser.parse_args()
    application_dir = Path(__file__).resolve().parents[2]
    with (application_dir / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    if args.variant not in project["optional-dependencies"]:
        parser.error(f"GPU probe returned an unknown dependency variant: {args.variant!r}")


if __name__ == "__main__":
    main()
