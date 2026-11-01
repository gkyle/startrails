"""StarNet setup-time platform selection and installation discovery/validation.

Runtime adapters consume the installation selected by setup. Filesystem layout
validation here does not establish package integrity, platform trust or inference
readiness; acquisition verification and setup probes must establish those.
"""

from concurrent.futures import CancelledError
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import stat
from tempfile import TemporaryDirectory
import os
from pathlib import Path
import platform
import sys
from typing import Any, Callable, Dict, Optional

from startrails.lib.finish.starnet import StarNetProbeInfo, parse_starnet_machine_info, run_starnet_process
from startrails.lib.model_manifest import (
    PlatformNotSupportedError,
    StarNetPlatformPackage,
    get_starnet_package_for_platform,
)
from startrails.lib.signatures import verify_file_integrity


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


def probe_starnet_installation(
    installation: StarNetInstallation, cancel_check: Optional[Callable[[], bool]] = None
) -> StarNetProbeInfo:
    """Probe a trusted candidate during setup; enforce the pinned CLI contract.

    Package integrity/platform trust must be established before calling this.
    Runtime inference uses the selected executable without repeating the probe.
    """
    _, stdout, _ = run_starnet_process([str(installation.executable), "--machine-info"], should_interrupt=cancel_check)
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


STARNET_TERMS_REVISION = "2026-09-07"
STARNET_TERMS_TEXT = (Path(__file__).parent / "finish" / "STARNET_LICENSE.txt").read_text(encoding="utf-8")
STARNET_TERMS_SHA256 = hashlib.sha256(STARNET_TERMS_TEXT.encode("utf-8")).hexdigest()
_DOWNLOAD_CHUNK_BYTES = 64 * 1024
STARNET_SMOKE_SIZE_PIXELS = 512
_SMOKE_MIN_SAMPLE_UINT16 = 4096
_SMOKE_MAX_SAMPLE_UINT16 = 32768


def starnet_terms_accepted(state: Dict[str, Any]) -> bool:
    record = state.get("starnet", {})
    return bool(
        isinstance(record, dict)
        and record.get("terms_accepted") is True
        and record.get("terms_revision") == STARNET_TERMS_REVISION
        and record.get("terms_sha256") == STARNET_TERMS_SHA256
    )


def create_starnet_smoke_image():
    """Create RGB texture that exercises inference rather than the flat-image shortcut."""
    import numpy as np

    size = STARNET_SMOKE_SIZE_PIXELS
    return np.random.default_rng(0).integers(
        _SMOKE_MIN_SAMPLE_UINT16, _SMOKE_MAX_SAMPLE_UINT16, (size, size, 3), dtype=np.uint16
    )


def smoke_test_starnet_installation(
    installation: StarNetInstallation, cancel_check: Optional[Callable[[], bool]] = None
) -> None:
    """Exercise model/library loading, beyond the lightweight machine-info probe."""
    from startrails.lib.finish.starnet import build_starnet_cli_args
    from startrails.lib.image_io import imread, imwrite

    pixels = create_starnet_smoke_image()
    with TemporaryDirectory(prefix="startrails-starnet-smoke-") as temporary:
        source, result = (Path(temporary) / name for name in ("input.tif", "starless.tif"))
        imwrite(source, pixels, bit_depth=16)
        cmd = build_starnet_cli_args(str(installation.executable), str(source), str(result))
        run_starnet_process(cmd, should_interrupt=cancel_check)
        output = imread(result)
        if output.shape != pixels.shape or output.dtype != pixels.dtype:
            raise StarNetSetupError("StarNet inference returned invalid dimensions or bit depth.")


@contextmanager
def starnet_installation_lock(storage_dir: Path):
    """Exclude managed installation changes while setup or inference uses it."""
    storage_dir.mkdir(parents=True, exist_ok=True)
    lock = storage_dir / ".installation-lock"
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise StarNetSetupError(
            f"StarNet setup or processing is already running. If it stopped unexpectedly, remove {lock}."
        ) from error
    try:
        yield
    finally:
        lock.rmdir()


def get_starnet_storage_dir() -> Path:
    """Return user-local data directory for managed StarNet installations."""
    system = platform.system().lower()
    if system == "linux":
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    elif system == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif system == "windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".startrails"
    path = base / "startrails" / "starnet2"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_starnet_package(
    package: StarNetPlatformPackage,
    destination_file: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    chunk_size: int = _DOWNLOAD_CHUNK_BYTES,
) -> Path:
    """Download package archive to destination with SHA-256 validation and cancellation."""
    import hashlib
    import urllib.request

    if cancel_check and cancel_check():
        raise CancelledError("Download cancelled before start")

    destination_file.parent.mkdir(parents=True, exist_ok=True)
    part_file = destination_file.with_suffix(destination_file.suffix + ".part")
    hasher = hashlib.sha256()
    downloaded_bytes = 0

    try:
        req = urllib.request.Request(
            package.archive_url,
            headers={"User-Agent": "StarTrails-Setup/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as response, open(part_file, "wb") as f:
            total_bytes = int(response.headers.get("Content-Length", package.archive_size_bytes))
            while True:
                if cancel_check and cancel_check():
                    raise CancelledError("Download cancelled by user")
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                hasher.update(chunk)
                downloaded_bytes += len(chunk)
                if progress_callback:
                    progress_callback(downloaded_bytes, total_bytes)

        if downloaded_bytes != package.archive_size_bytes:
            raise StarNetSetupError(
                f"Downloaded size ({downloaded_bytes} bytes) does not match expected ({package.archive_size_bytes} bytes)."
            )

        calculated_sha = hasher.hexdigest().lower()
        if calculated_sha != package.archive_sha256.lower():
            raise StarNetSetupError(
                f"Integrity check failed: expected SHA-256 {package.archive_sha256}, got {calculated_sha}."
            )

        if cancel_check and cancel_check():
            raise CancelledError("Download cancelled by user")
        part_file.replace(destination_file)
        return destination_file
    except Exception:
        if part_file.exists():
            part_file.unlink(missing_ok=True)
        raise


def extract_starnet_package(archive_path: Path, target_dir: Path) -> Path:
    """Safely extract StarNet archive into target_dir preventing directory traversal."""
    import zipfile

    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_target = target_dir.resolve()

    with zipfile.ZipFile(archive_path, "r") as zf:
        for member in zf.infolist():
            member_path = (target_dir / member.filename).resolve()
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise StarNetSetupError(f"Archive contains a symbolic link: {member.filename}")
            if "\\" in member.filename or not member_path.is_relative_to(resolved_target):
                raise StarNetSetupError(f"Archive entry escapes target directory: {member.filename}")
        zf.extractall(target_dir)

    # Set executable permissions on POSIX
    if not sys.platform.startswith("win"):
        for path in target_dir.rglob("starnet2*"):
            if path.is_file() and not path.suffix:
                current_mode = path.stat().st_mode
                path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return target_dir


def managed_starnet_setup_notice(platform_id: str) -> Optional[str]:
    if platform_id == "macos-arm64":
        return (
            "Automated macOS installation awaits signing/notarization validation. "
            "Install the official StarNet package through macOS, then select its executable."
        )
    return None


def install_starnet_managed(
    package: Optional[StarNetPlatformPackage] = None,
    storage_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> StarNetInstallation:
    """Download, validate and publish StarNet, retaining the prior version for rollback.

    The caller obtains affirmative acceptance before invoking setup. This helper
    owns acquisition/verification, never consent or application settings.
    """
    import shutil

    resolved_pkg = package or get_starnet_package_for_platform(detect_platform_target())
    base_dir = storage_dir or get_starnet_storage_dir()
    version_tag = f"starnet2-{resolved_pkg.version}-{resolved_pkg.build}"
    target_install_dir = base_dir / version_tag
    archive_dest = base_dir / resolved_pkg.archive_name
    backup_dir = base_dir / f".prev_{version_tag}"
    notice = managed_starnet_setup_notice(resolved_pkg.platform_id)
    if notice is not None:
        raise StarNetSetupError(notice)
    with (
        starnet_installation_lock(base_dir),
        TemporaryDirectory(prefix=f".staging_{version_tag}_", dir=base_dir) as temporary,
    ):
        staging_dir = Path(temporary) / "candidate"
        backup_created = False
        published = False
        try:
            if not (
                archive_dest.is_file()
                and verify_file_integrity(archive_dest, resolved_pkg.archive_sha256, resolved_pkg.archive_size_bytes)
            ):
                download_starnet_package(
                    resolved_pkg, archive_dest, progress_callback=progress_callback, cancel_check=cancel_check
                )
            if cancel_check and cancel_check():
                raise CancelledError("Installation cancelled by user")
            extract_starnet_package(archive_dest, staging_dir)
            installation = validate_starnet_installation(staging_dir, platform_id=resolved_pkg.platform_id)
            probe_starnet_installation(installation, cancel_check=cancel_check)
            smoke_test_starnet_installation(installation, cancel_check=cancel_check)
            if cancel_check and cancel_check():
                raise CancelledError("Installation cancelled by user")
            if target_install_dir.exists():
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                target_install_dir.rename(backup_dir)
                backup_created = True
            staging_dir.rename(target_install_dir)
            published = True
            result = validate_starnet_installation(target_install_dir, platform_id=resolved_pkg.platform_id)
            probe_starnet_installation(result, cancel_check=cancel_check)
            if cancel_check and cancel_check():
                raise CancelledError("Installation cancelled by user")
            return result
        except BaseException:
            if published:
                shutil.rmtree(target_install_dir)
            if backup_created:
                backup_dir.rename(target_install_dir)
            raise


def record_starnet_installation(
    state: Dict[str, Any],
    installation: StarNetInstallation,
    *,
    managed: bool,
    terms_accepted: bool,
) -> None:
    """Persist verified installation location, metadata, and terms status in app state."""
    state["starnet"] = {
        "executable": str(installation.executable),
        "weights": str(installation.weights),
        "version": installation.package.version,
        "build": installation.package.build,
        "backend_id": installation.package.backend_id,
        "managed": managed,
        "terms_accepted": terms_accepted,
        "terms_revision": STARNET_TERMS_REVISION,
        "terms_sha256": STARNET_TERMS_SHA256,
        "files": _installation_stamps(installation),
    }


def _installation_stamps(installation: StarNetInstallation) -> list:
    # Cheap change detection; archive verification and inference belong to setup.
    return [[path.stat().st_size, path.stat().st_mtime_ns] for path in (installation.executable, installation.weights)]


def get_active_starnet_installation(state: Dict[str, Any]) -> Optional[StarNetInstallation]:
    """Retrieve and validate the currently recorded StarNet installation from app state."""
    record = state.get("starnet")
    if not record or not isinstance(record, dict):
        return None
    executable_path = record.get("executable")
    if not executable_path:
        return None
    p = Path(executable_path)
    if not p.is_file():
        return None
    try:
        installation = validate_starnet_installation(p)
        package = installation.package
        if (record.get("version"), record.get("build"), record.get("backend_id")) != (
            package.version,
            package.build,
            package.backend_id,
        ) or record.get("files") != _installation_stamps(installation):
            return None
        return installation
    except (StarNetSetupError, PlatformNotSupportedError, OSError):
        return None


def repair_starnet_installation(
    state: Dict[str, Any],
    *,
    storage_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> StarNetInstallation:
    """Repair or re-verify the active StarNet installation in app state."""
    if not starnet_terms_accepted(state):
        raise StarNetSetupError("Accept the current StarNet terms before installing or repairing.")
    record = state["starnet"]
    is_managed = record.get("managed", False)
    if is_managed:
        installation = install_starnet_managed(
            storage_dir=storage_dir,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        record_starnet_installation(state, installation, managed=True, terms_accepted=True)
        return installation

    executable_path = record.get("executable")
    if not executable_path:
        raise StarNetSetupError("No executable path in StarNet record.")

    installation = validate_starnet_installation(Path(executable_path))
    probe_starnet_installation(installation, cancel_check=cancel_check)
    smoke_test_starnet_installation(installation, cancel_check=cancel_check)
    record_starnet_installation(state, installation, managed=False, terms_accepted=True)
    return installation
