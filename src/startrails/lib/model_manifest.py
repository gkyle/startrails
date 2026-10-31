"""Pinned upstream model and binary acquisition metadata shared by application setup.

Inference contracts live with their adapters; discovery and validation live in
setup helpers. These manifests do not inspect or modify the host environment.
"""

from dataclasses import dataclass
from typing import Dict, Optional


STARNET_VERSION = "2.6.2"
STARNET_BUILD = "0242"

GRAXPERT_MODEL_VERSION = "3.0.2"
GRAXPERT_MODEL_FILENAME = "model.onnx"
GRAXPERT_MODEL_SHA256 = "e61c880e7fb955917e91141660e66801c9de5c4f3d9946dc449e5a7dd7346563"
GRAXPERT_MODEL_SIZE_BYTES = 477703971
GRAXPERT_LICENSE_NAME = "CC BY-NC-SA 4.0"


class PlatformNotSupportedError(Exception):
    """Raised when no supported package is available for an OS/architecture."""


@dataclass(frozen=True)
class StarNetPlatformPackage:
    """Pinned metadata for an official StarNet2 platform distribution."""

    platform_id: str
    version: str
    build: str
    archive_name: str
    archive_url: str
    archive_sha256: str
    archive_size_bytes: int
    executable_relative_path: str
    weights_relative_path: str
    backend_id: str
    installer_name: Optional[str] = None
    installer_url: Optional[str] = None
    installer_sha256: Optional[str] = None
    installer_size_bytes: Optional[int] = None


STARNET_PACKAGES: Dict[str, StarNetPlatformPackage] = {
    "linux-x64": StarNetPlatformPackage(
        platform_id="linux-x64",
        version=STARNET_VERSION,
        build=STARNET_BUILD,
        archive_name="starnet2_linux_2.6.2-0242_ORT_x64_cli.zip",
        archive_url="https://download.starnetastro.com/starnet2_linux_2.6.2-0242_ORT_x64_cli.zip",
        archive_sha256="066a7683f0321ae8400d3bc1023a48747ac228e1d14e76b5d39c4e48cbce4920",
        archive_size_bytes=151481786,
        installer_name="StarNet2_linux_2.6.2-0242_ORT_x64.sh",
        installer_url="https://download.starnetastro.com/StarNet2_linux_2.6.2-0242_ORT_x64.sh",
        installer_sha256="ffbb6292936a97841e464cf0e5f77960858257b3c8a2ee891fae44d092336e00",
        installer_size_bytes=138493623,
        executable_relative_path="starnet2",
        weights_relative_path="StarNet2_weights.onnx",
        backend_id="ort",
    ),
    "macos-arm64": StarNetPlatformPackage(
        platform_id="macos-arm64",
        version=STARNET_VERSION,
        build=STARNET_BUILD,
        archive_name="starnet2_macos-arm64_2.6.2-0242_COREML_arm64_cli.zip",
        archive_url="https://download.starnetastro.com/starnet2_macos-arm64_2.6.2-0242_COREML_arm64_cli.zip",
        archive_sha256="dfeb471e983a9de1233b439a8c56d3e373ed26e37c85aababe737187d164d20f",
        archive_size_bytes=127977753,
        installer_name="StarNet2_macos-arm64_2.6.2-0242_COREML_arm64.pkg",
        installer_url="https://download.starnetastro.com/StarNet2_macos-arm64_2.6.2-0242_COREML_arm64.pkg",
        installer_sha256="53a2167269a0560a5255444f7248d6524c4de1f3c28b3aa6a3721184081ce12a",
        installer_size_bytes=128062691,
        executable_relative_path="starnet2",
        weights_relative_path="StarNet2_weights.mlpackage",
        backend_id="coreml",
    ),
    "windows-x64": StarNetPlatformPackage(
        platform_id="windows-x64",
        version=STARNET_VERSION,
        build=STARNET_BUILD,
        archive_name="starnet2_win_2.6.2-0242_ORT_x64_cli.zip",
        archive_url="https://download.starnetastro.com/starnet2_win_2.6.2-0242_ORT_x64_cli.zip",
        archive_sha256="fbd5c7bdbbbee0cdbabf101b2c7ac2af3d33e3c477f9585f38f98b882f1551a0",
        archive_size_bytes=192822891,
        installer_name="StarNet2_win_2.6.2-0242_ORT_x64_setup.exe",
        installer_url="https://download.starnetastro.com/StarNet2_win_2.6.2-0242_ORT_x64_setup.exe",
        installer_sha256="5f85474f3889ba115e4e2290be6c0292da403f90ae15f4d692d41dce7a84d028",
        installer_size_bytes=168216446,
        executable_relative_path="starnet2.exe",
        weights_relative_path="StarNet2_weights.onnx",
        backend_id="ort",
    ),
}


@dataclass(frozen=True)
class GraXpertModelManifest:
    """Pinned acquisition metadata for the GraXpert Denoise model."""

    relative_path: str = f"graxpert/denoise/{GRAXPERT_MODEL_VERSION}/{GRAXPERT_MODEL_FILENAME}"
    version: str = GRAXPERT_MODEL_VERSION
    filename: str = GRAXPERT_MODEL_FILENAME
    sha256: str = GRAXPERT_MODEL_SHA256
    size_bytes: int = GRAXPERT_MODEL_SIZE_BYTES
    license_name: str = GRAXPERT_LICENSE_NAME


GRAXPERT_MANIFEST = GraXpertModelManifest()


def get_starnet_package_for_platform(platform_id: str) -> StarNetPlatformPackage:
    """Return the pinned StarNet2 package manifest for the given platform."""
    if platform_id not in STARNET_PACKAGES:
        raise PlatformNotSupportedError(f"No StarNet package registered for platform: {platform_id}")
    return STARNET_PACKAGES[platform_id]
