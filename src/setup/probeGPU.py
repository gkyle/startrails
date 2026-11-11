"""Select a locked dependency extra from uv's automatic PyTorch backend choice."""

import argparse
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib
from urllib.parse import urlparse


PROBE_TIMEOUT_SECONDS = 120
BACKEND_VERSION = re.compile(r"^(?:\d+\.)+\d+\+(cpu|cu\d+|rocm\d+(?:\.\d+)+|xpu)$")
CUDA_BACKEND = re.compile(r"^cu(\d+)$")
ROCM_BACKEND = re.compile(r"^rocm(\d+(?:\.\d+)+)$")


def backend_key(backend: str) -> tuple[str, tuple[int, ...]]:
    if backend in {"cpu", "xpu"}:
        return backend, ()
    if match := CUDA_BACKEND.fullmatch(backend):
        digits = match.group(1)
        if len(digits) < 2:
            raise ValueError(f"Unknown PyTorch backend: {backend}")
        return "cu", (int(digits[:-1]), int(digits[-1]))
    if match := ROCM_BACKEND.fullmatch(backend):
        return "rocm", tuple(int(part) for part in match.group(1).split("."))
    raise ValueError(f"Unknown PyTorch backend: {backend}")


def supported_backends(project: dict) -> dict[str, tuple[str, tuple[int, ...]]]:
    extras = project["project"]["optional-dependencies"]
    indexes = {
        index["name"]: urlparse(index["url"]).path.rstrip("/").split("/")[-1]
        for index in project["tool"]["uv"]["index"]
    }
    supported = {}
    for source in project["tool"]["uv"]["sources"]["torch"]:
        extra = source["extra"]
        if extra not in extras:
            raise ValueError(f"Torch source refers to unknown extra: {extra}")
        supported[extra] = backend_key(indexes[source["index"]])
    return supported


def select_extra(torch_version: str, supported: dict[str, tuple[str, tuple[int, ...]]]) -> str:
    match = BACKEND_VERSION.fullmatch(torch_version)
    if match is None:
        raise ValueError(f"uv returned an unrecognized PyTorch version: {torch_version!r}")
    family, version = backend_key(match.group(1))
    if family in {"cpu", "xpu"}:
        if family in supported:
            return family
        raise ValueError(f"No locked extra supports {family}")
    family_candidates = [
        (supported_version, extra)
        for extra, (supported_family, supported_version) in supported.items()
        if supported_family == family
    ]
    candidates = [
        (supported_version, extra)
        for supported_version, extra in family_candidates
        if supported_version[0] == version[0] and supported_version <= version
    ]
    if candidates:
        return max(candidates)[1]
    if family == "cu" and family_candidates and version[0] > max(ver[0] for ver, _ in family_candidates):
        _, fallback_extra = max(family_candidates)
        print(f"No tested cu build matches {match.group(1)}; using {fallback_extra}.", file=sys.stderr)
        return fallback_extra
    if "cpu" not in supported:
        raise ValueError("No locked CPU extra is available")
    print(f"No tested {family} build is compatible with {match.group(1)}; using CPU.", file=sys.stderr)
    return "cpu"


def torch_version_from_report(output: str) -> str:
    try:
        report = json.loads(output)
        if report["schema"]["version"] != "preview" or report["dry_run"] is not True:
            raise ValueError("Unexpected uv JSON schema or dry-run flag")
        torch_changes = [
            change for change in report["changes"] if change["name"] == "torch" and change["action"] == "installed"
        ]
        if len(torch_changes) != 1 or not isinstance(torch_changes[0]["version"], str):
            raise ValueError("Expected one planned Torch installation")
        return torch_changes[0]["version"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError("Could not read uv's JSON installation plan") from error


def run_uv(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    executable = arguments[0]
    try:
        return subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except OSError as error:
        raise RuntimeError(f"Could not run {executable}: {error}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip()
        raise RuntimeError(f"uv GPU probe failed ({executable}): {detail}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"uv GPU probe exceeded {PROBE_TIMEOUT_SECONDS} seconds ({executable})") from error


def probe_torch_version(uv: Path) -> str:
    with TemporaryDirectory(prefix="startrails-uv-probe-") as directory:
        environment = Path(directory) / "venv"
        run_uv([str(uv), "venv", "--no-config", "--python", sys.executable, str(environment)])
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        result = run_uv([
            str(uv), "pip", "install", "torch", "--torch-backend=auto", "--dry-run", "--no-deps", "--no-config",
            "--output-format=json", "--python", str(python),
        ])
        return torch_version_from_report(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", type=Path, required=True, help="Verified uv executable")
    args = parser.parse_args()
    application_dir = Path(__file__).resolve().parents[2]
    try:
        with (application_dir / "pyproject.toml").open("rb") as stream:
            supported = supported_backends(tomllib.load(stream))
        if sys.platform == "darwin" and platform.machine() == "arm64":
            if "mps" not in supported:
                raise ValueError("No locked MPS extra is available")
            selected = "mps"
        else:
            selected = select_extra(probe_torch_version(args.uv), supported)
    except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(selected, end="")


if __name__ == "__main__":
    main()
