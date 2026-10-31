"""StarNet setup-time platform selection and installation discovery/validation.

Runtime adapters consume the installation selected by setup. Filesystem layout
validation here does not establish package integrity, platform trust or inference
readiness; acquisition verification and setup probes must establish those.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import platform
from typing import Optional

from startrails.lib.model_manifest import (
    PlatformNotSupportedError,
    StarNetPlatformPackage,
    get_starnet_package_for_platform,
)
from startrails.lib.finish.starnet import StarNetProbeInfo, parse_starnet_machine_info, run_starnet_process


def detect_platform_target(system_override: Optional[str] = None, machine_override: Optional[str] = None) -> str:
    """Detect the current platform key ('linux-x64', 'macos-arm64', 'windows-x64')."""
    os_name = (system_override or platform.system()).lower()
    machine = (machine_override or platform.machine()).lower()

    if os_name == "linux":
        if machine in ("x86_64", "amd64"):
            return "linux-x64"
        raise PlatformNotSupportedError(f"Unsupported Linux CPU architecture: {machine}")
    elif os_name == "darwin":
        if machine in ("arm64", "aarch64"):
            return "macos-arm64"
        elif machine in ("x86_64", "amd64"):
            raise PlatformNotSupportedError("macOS Intel (x64) is not a supported release target for StarTrails.")
        raise PlatformNotSupportedError(f"Unsupported macOS CPU architecture: {machine}")
    elif os_name == "windows":
        if machine in ("x86_64", "amd64"):
            return "windows-x64"
        raise PlatformNotSupportedError(f"Unsupported Windows CPU architecture: {machine}")
    else:
        raise PlatformNotSupportedError(f"Unsupported operating system: {os_name}")


class StarNetSetupError(ValueError):
    """An installation cannot be discovered, validated or matched to the pinned CLI."""


@dataclass(frozen=True)
class StarNetInstallation:
    executable: Path
    weights: Path
    package: StarNetPlatformPackage


def _discover_executable(location: Path, executable_name: str) -> Path:
    if location.is_file():
        if location.name != executable_name:
            raise StarNetSetupError(f"Expected StarNet executable named {executable_name}: {location}")
        return location
    if not location.is_dir():
        raise StarNetSetupError(f"Installation path does not exist: {location}")
    direct = location / executable_name
    if direct.is_file():
        return direct
    # Covers an install prefix's bin/ and a single extracted archive root.
    candidates = sorted(
        child / executable_name
        for child in location.iterdir()
        if child.is_dir() and (child / executable_name).is_file()
    )
    if not candidates:
        raise StarNetSetupError(f"Missing StarNet executable: {executable_name}")
    if len(candidates) != 1:
        raise StarNetSetupError("Multiple StarNet installations found; select the executable or its directory.")
    return candidates[0]


def validate_starnet_installation(
    location: Path,
    platform_id: Optional[str] = None,
) -> StarNetInstallation:
    """Resolve an explicit executable, portable directory or native install prefix.

    Returns absolute paths; never searches PATH. Only checks executable/model
    locations. The setup probe and inference smoke test establish whether the
    CLI can load its libraries and model; this does not authorize an untrusted binary.
    """
    resolved_id = platform_id if platform_id is not None else detect_platform_target()
    package = get_starnet_package_for_platform(resolved_id)
    try:
        executable = _discover_executable(Path(location).expanduser().resolve(), package.executable_relative_path)
        if resolved_id != "windows-x64" and not os.access(executable, os.X_OK):
            raise StarNetSetupError(f"StarNet executable is not executable: {executable}")

        directory = executable.parent
        portable_weights = directory / package.weights_relative_path
        if portable_weights.exists():
            weights = portable_weights
        elif directory.name == "bin":
            # Native installers put model assets under prefix/lib/starnet2.
            # The CLI owns library discovery and model-package contents.
            native_lib = directory.parent / "lib" / "starnet2"
            weights = native_lib / package.weights_relative_path
        else:
            raise StarNetSetupError(f"Missing model weights: {package.weights_relative_path}")

        model_exists = weights.is_dir() if weights.suffix == ".mlpackage" else weights.is_file()
        if not model_exists:
            raise StarNetSetupError(f"Missing model weights: {weights}")
        return StarNetInstallation(executable, weights, package)
    except OSError as exc:
        raise StarNetSetupError(f"Cannot inspect StarNet installation {location}: {exc}") from exc


def probe_starnet_installation(installation: StarNetInstallation) -> StarNetProbeInfo:
    """Probe a trusted candidate during setup; enforce the pinned CLI contract.

    Package integrity/platform trust must be established before calling this.
    Runtime inference uses the selected executable without repeating the probe.
    """
    _, stdout, _ = run_starnet_process([str(installation.executable), "--machine-info"])
    info = parse_starnet_machine_info(stdout)
    package = installation.package
    if (info.version, info.build, info.backend_id) != (package.version, package.build, package.backend_id):
        raise StarNetSetupError(
            f"Unexpected StarNet identity {info.version}-{info.build}/{info.backend_id}; "
            f"expected {package.version}-{package.build}/{package.backend_id}."
        )
    required_options = {"input", "output", "stride", "machine_progress", "upsample", "disable_highlights_protection"}
    if (
        info.raw_info.get("schema") != "starnetastro.cli.machine-info.v1"
        or info.raw_info.get("product") != "starnet2"
        or not required_options.issubset(info.options)
    ):
        raise StarNetSetupError("StarNet probe does not describe the required StarNet2 CLI options.")
    if not info.highlight_protection_supported:
        raise StarNetSetupError("StarNet probe does not support highlight protection.")
    return info
