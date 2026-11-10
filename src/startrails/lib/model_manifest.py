"""Pinned model metadata shared by application setup and Finish mode.

Inference contracts live with their adapters; discovery and validation live in
setup helpers. These manifests do not inspect or modify the host environment.
"""

from dataclasses import dataclass


NOX_MODEL_VERSION = "1.0.0"
NOX_MODEL_FILENAME = "nox_color_finetuned_best.pt"
NOX_MODEL_SHA256 = "e2e460a1ba182e3380d64175b063084ef3f208d1d76a87527fc420e9f21965ce"
NOX_MODEL_SIZE_BYTES = 217703507

GRAXPERT_MODEL_VERSION = "3.0.2"
GRAXPERT_MODEL_FILENAME = "graxpert-denoise-3.0.2-mixed-int4-int8.pt"
GRAXPERT_MODEL_SHA256 = "e02957100e6088a644de64e154e777588eba2e323b8f5b914efc4aa91a0ad4b0"
GRAXPERT_MODEL_SIZE_BYTES = 87819947
GRAXPERT_LICENSE_NAME = "CC BY-NC-SA 4.0"


@dataclass(frozen=True)
class NoxModelManifest:
    """Pinned metadata for the bundled Nox star removal PyTorch model."""

    relative_path: str = f"removeStars/{NOX_MODEL_FILENAME}"
    version: str = NOX_MODEL_VERSION
    filename: str = NOX_MODEL_FILENAME
    sha256: str = NOX_MODEL_SHA256
    size_bytes: int = NOX_MODEL_SIZE_BYTES


NOX_MANIFEST = NoxModelManifest()


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


__all__ = [
    "GRAXPERT_LICENSE_NAME",
    "GRAXPERT_MANIFEST",
    "GRAXPERT_MODEL_FILENAME",
    "GRAXPERT_MODEL_SHA256",
    "GRAXPERT_MODEL_SIZE_BYTES",
    "GRAXPERT_MODEL_VERSION",
    "GraXpertModelManifest",
    "NOX_MANIFEST",
    "NOX_MODEL_FILENAME",
    "NOX_MODEL_SHA256",
    "NOX_MODEL_SIZE_BYTES",
    "NOX_MODEL_VERSION",
    "NoxModelManifest",
]
