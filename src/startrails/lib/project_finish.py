"""Project model and state persistence for Finish mode (.proj_finish)."""

from __future__ import annotations

import copy
from dataclasses import asdict, fields
import json
import logging
import os
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Final, Optional, Tuple, Union

import jsonpickle
import numpy as np
from PIL import Image

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.file import InputFile, Unpickle
from startrails.lib.image_io import imread
from startrails.lib.finish.defaults import (
    COMPOSITION_ONLY_SETTING_NAMES,
    FINISH_DEFAULTS,
    FINISH_EXT,
    PERCENT_SCALE,
    RETIRED_FINISH_SETTING_NAMES,
    FinishSettings,
    ROLE_SOURCE_SNAPSHOT,
    ROLE_SKY_MASK,
    ROLE_UNMASKED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_DENOISE_ENDPOINT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    SUPPORTED_CHANNELS,
    SUPPORTED_SOURCE_FORMATS,
)
from startrails.lib.project_type import get_project_output_dir
from startrails.lib.signatures import read_file_identity

logger = logging.getLogger(__name__)

_ARTIFACT_FILENAMES: Dict[str, str] = {
    ROLE_SOURCE_SNAPSHOT: "source_snapshot.tif",
    ROLE_SKY_MASK: "sky_mask.png",
    ROLE_UNMASKED_STARLESS: "unmasked_starless.tif",
    ROLE_SEPARATED_STARLESS: "starless.tif",
    ROLE_SEPARATED_STARS: "stars.tif",
    ROLE_DENOISE_ENDPOINT: "denoise_endpoint.tif",
    ROLE_DENOISED_STARLESS: "denoised_starless.tif",
    ROLE_FINISHED_STARLESS: "finished_starless.tif",
    ROLE_FINISHED_COMPOSITE: "composite.tif",
}

_ARTIFACT_PATH_FIELDS: Dict[str, str] = {
    ROLE_SOURCE_SNAPSHOT: "source_snapshot_path",
    ROLE_SKY_MASK: "sky_mask_path",
    ROLE_UNMASKED_STARLESS: "unmasked_starless_path",
    ROLE_SEPARATED_STARLESS: "separated_starless_path",
    ROLE_SEPARATED_STARS: "separated_stars_path",
    ROLE_DENOISE_ENDPOINT: "denoise_endpoint_path",
    ROLE_DENOISED_STARLESS: "denoised_starless_path",
    ROLE_FINISHED_STARLESS: "finished_starless_path",
    ROLE_FINISHED_COMPOSITE: "composite_path",
}

_INPUT_ARTIFACT_ROLES = (ROLE_SOURCE_SNAPSHOT, ROLE_SKY_MASK)
_EXPORT_ROLE = "export"
_SOURCE_FORMATS_BY_SUFFIX = {".jpg": "jpeg", ".jpeg": "jpeg", ".tif": "tiff", ".tiff": "tiff"}
_UNSET = object()

# User-facing layer exports keep the project stem and append a role-specific
# tail so every separated or finished layer is identifiable after export.
LAYER_EXPORT_SUFFIXES: Final[Dict[str, str]] = {
    ROLE_SEPARATED_STARLESS: "_starless",
    ROLE_SEPARATED_STARS: "_stars",
    ROLE_DENOISED_STARLESS: "_denoised_starless",
    ROLE_FINISHED_STARLESS: "_finished_starless",
}

# Finish Stars was removed in Step 10R before shipping. Development projects
# may still carry its manifest roles, path fields and disposable caches. Decoding
# discards the records; opening the project removes only cache files it owns.
_RETIRED_STAR_EFFECT_ROLES: Final[Tuple[str, ...]] = ("star_catalog", "round_delta", "finished_stars")
_RETIRED_STAR_EFFECT_PATH_FIELDS: Final[Tuple[str, ...]] = (
    "star_catalog_path",
    "round_delta_path",
    "finished_stars_path",
)
_RETIRED_STAR_EFFECT_CACHE_FILENAMES: Final[Tuple[str, ...]] = (
    "catalog.npz",
    "round_delta.npz",
    "finished_stars.tif",
)


def _remove_retired_star_effect_caches(project_file: str) -> None:
    """Delete only exact project-owned Finish Stars caches from the output directory.

    Never follows symlinks or touches user inputs, exports or arbitrary manifest
    paths: ownership is the resolved output directory plus one of the canonical
    cache basenames. Unremovable caches are reported with context rather than
    failing the project load.
    """
    output_dir = get_project_output_dir(project_file)
    if output_dir.is_symlink():
        # A symlinked output directory points outside the project's own storage;
        # canonical filenames there are not project-owned caches.
        logger.warning(
            "Skipped retired Finish Stars cache cleanup because the output directory is a symlink: %s",
            output_dir,
        )
        return
    output_dir = output_dir.resolve()
    for name in _RETIRED_STAR_EFFECT_CACHE_FILENAMES:
        candidate = output_dir / name
        if candidate.name != name or candidate.is_symlink():
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError:
            continue
        except OSError as error:
            logger.warning("Could not inspect retired Finish Stars cache %s: %s", candidate, error)
            continue
        parent = resolved.parent
        if parent != output_dir:
            logger.warning("Skipped retired Finish Stars cache outside output directory: %s", candidate)
            continue
        if not resolved.is_file():
            continue
        try:
            resolved.unlink()
        except OSError as error:
            logger.warning("Could not remove retired Finish Stars cache %s: %s", resolved, error)


def _source_format(path: Path) -> str:
    fmt = _SOURCE_FORMATS_BY_SUFFIX.get(path.suffix.lower())
    if fmt not in SUPPORTED_SOURCE_FORMATS:
        raise ValueError("Finish mode supports developed JPEG and TIFF images.")
    return fmt


def _file_stamp(path: Path) -> Optional[Tuple[int, int]]:
    # Paths are excluded so owned inputs can move with their project. Missing or
    # inaccessible files cannot establish freshness, just as in Denoise caches.
    try:
        identity = read_file_identity(path)
        return identity.size, identity.mtime_ns
    except OSError:
        return None


def probe_source_image(path: Union[str, Path]) -> int:
    """Validate a developed RGB source and determine depth before normalization."""
    p = Path(path).resolve()
    _source_format(p)
    raw = imread(p)
    if raw.dtype == np.uint8:
        bit_depth = 8
    elif raw.dtype == np.uint16:
        bit_depth = 16
    else:
        raise ValueError(f"Unsupported image dtype '{raw.dtype}'; use uint8 or uint16.")
    if raw.ndim != 3 or raw.shape[2] != SUPPORTED_CHANNELS:
        raise ValueError(f"Finish mode requires a {SUPPORTED_CHANNELS}-channel RGB image, got {raw.shape}.")
    return bit_depth


class FinishProject(Unpickle):
    """Project model and state persistence for the Finish mode (.proj_finish)."""

    def __init__(
        self,
        project_file: str = f"projects/default{FINISH_EXT}",
        source_file: Optional[InputFile] = None,
        *,
        source_bit_depth: Optional[int] = None,
        source_snapshot_path: Optional[Union[str, Path]] = None,
        sky_mask_path: Optional[Union[str, Path]] = None,
        unmasked_starless_path: Optional[Union[str, Path]] = None,
        separated_starless_path: Optional[Union[str, Path]] = None,
        separated_stars_path: Optional[Union[str, Path]] = None,
        denoise_endpoint_path: Optional[Union[str, Path]] = None,
        denoised_starless_path: Optional[Union[str, Path]] = None,
        finished_starless_path: Optional[Union[str, Path]] = None,
        composite_path: Optional[Union[str, Path]] = None,
        output_path: Optional[Union[str, Path]] = None,
        final_output_path: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ):
        super().__init__()
        self._state_lock = RLock()
        self.project_file = kwargs.pop("projectFile", project_file)
        self.source_file: Optional[InputFile] = source_file
        self.source_bit_depth: Optional[int] = source_bit_depth
        self.source_stamp: Optional[Tuple[int, int]] = None

        # Artifact paths
        self.source_snapshot_path: Optional[Union[str, Path]] = source_snapshot_path
        self.sky_mask_path: Optional[Union[str, Path]] = sky_mask_path
        self.unmasked_starless_path: Optional[Union[str, Path]] = unmasked_starless_path
        self.separated_starless_path: Optional[Union[str, Path]] = separated_starless_path
        self.separated_stars_path: Optional[Union[str, Path]] = separated_stars_path
        self.denoise_endpoint_path: Optional[Union[str, Path]] = denoise_endpoint_path
        self.denoised_starless_path: Optional[Union[str, Path]] = denoised_starless_path
        self.finished_starless_path: Optional[Union[str, Path]] = finished_starless_path
        self.composite_path: Optional[Union[str, Path]] = composite_path
        self.output_path: Optional[Union[str, Path]] = output_path
        self.final_output_path: Optional[Union[str, Path]] = final_output_path

        # Authoritative defaults from FinishSettings. Retired fields from older
        # projects are consumed but never assigned.
        for retired in RETIRED_FINISH_SETTING_NAMES:
            kwargs.pop(retired, None)
        defaults = asdict(FINISH_DEFAULTS)
        for name, default_val in defaults.items():
            setattr(self, name, kwargs.pop(name, default_val))

        self.has_manual_sky_corrections: bool = kwargs.pop("has_manual_sky_corrections", False)
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.processing_revision: int = 0
        self.separation_signature: Optional[str] = None
        self.denoise_signature: Optional[str] = None
        self.denoise_model_identity: Optional[str] = None
        self.composite_signature: Optional[str] = None
        self.artifact_manifest: Dict[str, Any] = {}
        self.separation_model_identity: Optional[str] = None
        self.separation_options: Optional[Dict[str, Any]] = None

    @property
    def projectFile(self) -> str:  # noqa: N802 - compatibility property for host shell
        """Compatibility property for host shell and persistence."""
        return self.project_file

    @projectFile.setter
    def projectFile(self, value: str) -> None:  # noqa: N802
        self.project_file = value

    def __getstate__(self) -> Dict[str, Any]:
        with self._state_lock:
            state = dict(self.__dict__)
            state.pop("_state_lock", None)
            state["artifact_manifest"] = copy.deepcopy(self.artifact_manifest)
            state["separation_options"] = copy.deepcopy(self.separation_options)
            return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        state = dict(state)
        if "projectFile" in state:
            state["project_file"] = state.pop("projectFile")
        state.pop("source_dimensions", None)
        state.pop("source_format", None)
        state.pop("_state_lock", None)
        manifest = state.get("artifact_manifest")
        retired_star_state = bool(
            isinstance(manifest, dict) and any(role in manifest for role in _RETIRED_STAR_EFFECT_ROLES)
        ) or any(field in state for field in _RETIRED_STAR_EFFECT_PATH_FIELDS)
        retired_star_state = retired_star_state or any(name in state for name in RETIRED_FINISH_SETTING_NAMES)
        for retired in RETIRED_FINISH_SETTING_NAMES:
            state.pop(retired, None)
        for field in _RETIRED_STAR_EFFECT_PATH_FIELDS:
            state.pop(field, None)
        if isinstance(manifest, dict):
            state["artifact_manifest"] = {
                role: record for role, record in manifest.items() if role not in _RETIRED_STAR_EFFECT_ROLES
            }
        super().__setstate__(state)
        # Projects saved before a new setting existed inherit its authoritative
        # default instead of missing the attribute at runtime.
        for name, default_val in asdict(FINISH_DEFAULTS).items():
            if not hasattr(self, name):
                setattr(self, name, default_val)
        if retired_star_state:
            # A legacy composite may include removed effect layers. Drop only its
            # references so a single-layer composite can be rebuilt from cached
            # separation/starless artifacts without rerunning models. Cache files
            # are deleted only on open: see remove_retired_star_effect_caches().
            self.invalidate_artifact_roles({ROLE_FINISHED_COMPOSITE, _EXPORT_ROLE})

    def remove_retired_star_effect_caches(self) -> None:
        """Delete Finish Stars caches left in the output directory by pre-Step 10R builds.

        Call only after the project is opened at its authoritative path. Decoding
        alone (type detection, recent-project listing) must never delete files, and
        a decoded ``project_file`` may still name the original folder of a copy.
        """
        _remove_retired_star_effect_caches(self.project_file)

    def get_output_dir(self) -> Path:
        """Resolve authoritative output directory for this project."""
        return get_project_output_dir(self.project_file)

    def get_project_stem(self) -> str:
        """Return base stem of the project file without extension."""
        if not self.project_file:
            return "project"
        name = Path(self.project_file).name
        if name.endswith(FINISH_EXT):
            return name[: -len(FINISH_EXT)]
        if name.endswith(".json"):
            return name[:-5]
        return Path(self.project_file).stem

    def artifact_path(self, role: str, *, for_write: bool = False) -> Path:
        """Resolve an artifact reference, or its owned destination when writing."""
        if role not in _ARTIFACT_FILENAMES:
            raise ValueError(f"Unknown finish artifact role: {role}")
        field = _ARTIFACT_PATH_FIELDS[role]
        value = getattr(self, field, None)
        if value and not for_write:
            return Path(value).resolve()
        return (self.get_output_dir() / _ARTIFACT_FILENAMES[role]).resolve()

    def get_default_export_path(self) -> Path:
        """Derive the source-matching export path from the input path and project directory."""
        stem = self.get_project_stem()
        out_dir = self.get_output_dir()
        suffix = Path(self.source_file.path).suffix.lower() if self.source_file and self.source_file.path else ".tif"
        destination = (out_dir / f"{stem}{suffix}").resolve()
        protected = self._protected_image_paths()
        counter = 0
        while destination in protected:
            counter += 1
            tail = "_finished" if counter == 1 else f"_finished_{counter}"
            destination = (out_dir / f"{stem}{tail}{suffix}").resolve()
        return destination

    def get_default_layer_export_path(
        self,
        role: str,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Derive a source-matching export path for one stored layer."""
        if role not in LAYER_EXPORT_SUFFIXES:
            raise ValueError(f"Unsupported layer export role: {role}")
        stem = self.get_project_stem()
        base_dir = Path(output_dir).resolve() if output_dir is not None else self.get_output_dir()
        suffix = Path(self.source_file.path).suffix.lower() if self.source_file and self.source_file.path else ".tif"
        role_tail = LAYER_EXPORT_SUFFIXES[role]
        destination = (base_dir / f"{stem}{role_tail}{suffix}").resolve()
        protected = self._protected_image_paths()
        counter = 0
        while destination in protected:
            counter += 1
            destination = (base_dir / f"{stem}{role_tail}_{counter}{suffix}").resolve()
        return destination

    def _protected_image_paths(self) -> set[Path]:
        """Reserve both owned destinations and referenced inputs/caches for processing."""
        paths = {self.artifact_path(role, for_write=True) for role in _ARTIFACT_FILENAMES}
        paths.update(self.artifact_path(role) for role in _ARTIFACT_FILENAMES)
        if self.source_file and self.source_file.path:
            paths.add(Path(self.source_file.path).resolve())
        return paths

    def validate_export_path(self, path: Path) -> None:
        """Enforce the imported source's codec, accepting equivalent suffixes."""
        if self.source_file is None:
            raise ValueError("No source image imported to export.")
        if _source_format(path) != _source_format(Path(self.source_file.path)):
            raise ValueError("Export format must match the source image format.")
        if path.resolve() in self._protected_image_paths():
            raise ValueError("Export must not overwrite the original source image or an internal artifact.")

    def source_is_current(self) -> bool:
        return bool(
            self.source_file
            and self.source_stamp is not None
            and _file_stamp(Path(self.source_file.path)) == tuple(self.source_stamp)
        )

    def _source_key(self) -> list:
        return [self.source_file.sourceId, list(self.source_stamp)]

    def get_source_dimensions(self) -> Optional[Tuple[int, int]]:
        """Return (height, width) of the current source image without loading full RGB buffer."""
        if not self.source_file or not self.source_file.path:
            return None
        p = Path(self.source_file.path)
        if not p.is_file():
            return None
        with Image.open(p) as img:
            w, h = img.size
            return (h, w)

    def set_source_image(self, path: Union[str, Path]) -> None:
        """Validate before replacing the source; never reuse its predecessor's artifacts."""
        resolved_path = Path(path).resolve()
        bit_depth = probe_source_image(resolved_path)
        stamp = _file_stamp(resolved_path)
        if stamp is None:
            raise FileNotFoundError(f"Source image became unavailable: {resolved_path}")
        with self._state_lock:
            self.source_file = InputFile(basename=resolved_path.name, path=str(resolved_path))
            self.source_bit_depth = bit_depth
            self.source_stamp = stamp
            self.source_snapshot_path = None
            self.sky_mask_path = None
            self.has_manual_sky_corrections = False
            self.artifact_manifest.clear()
            self.invalidate_results()
            self.output_path = str(self.get_default_export_path())

    def clear_source_image(self) -> None:
        """Remove the source and dependent references without deleting any image files."""
        with self._state_lock:
            self.source_file = None
            self.source_bit_depth = None
            self.source_stamp = None
            self.source_snapshot_path = None
            self.sky_mask_path = None
            self.has_manual_sky_corrections = False
            self.artifact_manifest.clear()
            self.invalidate_results()
            self.output_path = str(self.get_default_export_path())

    def _record_artifact(self, role: str, path: Path, options: Optional[Dict[str, Any]] = None) -> None:
        if not self.source_is_current():
            raise ValueError("Source image changed or is unavailable; import it again.")
        stamp = _file_stamp(path)
        if stamp is None:
            raise FileNotFoundError(f"Cannot record missing artifact: {path}")
        entry: Dict[str, Any] = {
            "source": self._source_key(),
            "file": list(stamp),
            "revision": self.processing_revision,
        }
        if options is not None:
            entry["options"] = options
        self.artifact_manifest[role] = entry

    def _commit_if_current(
        self,
        transaction: Optional[ArtifactTransaction],
        *,
        expected_revision: Optional[int],
        expected_separation_signature: Any = _UNSET,
    ) -> bool:
        """Commit staged files while the caller holds the state lock and the job is current."""
        if expected_revision is not None and (
            expected_revision != self.processing_revision or not self.source_is_current()
        ):
            return False
        if expected_separation_signature is not _UNSET and expected_separation_signature != self.separation_signature:
            return False
        if transaction is not None:
            transaction.commit()
        return True

    def commit_layer_export(
        self,
        transaction: ArtifactTransaction,
        *,
        expected_revision: int,
        expected_separation_signature: Any,
    ) -> bool:
        """Commit external layer exports while project state is still current.

        Layer exports are user-facing files, not project artifacts, so publishing
        them records nothing in the manifest. Holding the state lock keeps the
        revision/signature check and commit atomic with respect to project edits.
        """
        with self._state_lock:
            return self._commit_if_current(
                transaction,
                expected_revision=expected_revision,
                expected_separation_signature=expected_separation_signature,
            )

    def record_artifact(
        self,
        role: str,
        path: Union[str, Path],
        options: Optional[Dict[str, Any]] = None,
        *,
        expected_revision: Optional[int] = None,
        expected_separation_signature: Any = _UNSET,
        transaction: Optional[ArtifactTransaction] = None,
    ) -> bool:
        """Register an ordinary image only after successful publication of its job."""
        with self._state_lock:
            self.artifact_path(role)  # Reject unknown roles before changing state.
            if not self._commit_if_current(
                transaction,
                expected_revision=expected_revision,
                expected_separation_signature=expected_separation_signature,
            ):
                return False
            resolved = Path(path).resolve()
            self._record_artifact(role, resolved, options=options)
            setattr(self, _ARTIFACT_PATH_FIELDS[role], str(resolved))
            return True

    def _artifact_is_current(self, role: str, path: Path, options: Optional[Dict[str, Any]] = None) -> bool:
        record = self.artifact_manifest.get(role)
        if not record or not self.source_is_current():
            return False
        if options is not None and record.get("options") != options:
            return False
        if role in (
            ROLE_SEPARATED_STARLESS,
            ROLE_SEPARATED_STARS,
            ROLE_DENOISE_ENDPOINT,
            ROLE_DENOISED_STARLESS,
            ROLE_FINISHED_STARLESS,
            ROLE_FINISHED_COMPOSITE,
            _EXPORT_ROLE,
        ):
            artifact_signature = record.get("options", {}).get("separation_signature")
            if artifact_signature is not None and artifact_signature != self.separation_signature:
                return False
        if role in (ROLE_DENOISE_ENDPOINT, ROLE_DENOISED_STARLESS, ROLE_FINISHED_STARLESS):
            artifact_signature = record.get("options", {}).get("denoise_signature")
            if artifact_signature is not None and artifact_signature != self.denoise_signature:
                return False
        return bool(
            record["source"] == self._source_key()
            and _file_stamp(path) == tuple(record["file"])
            and (
                role in _INPUT_ARTIFACT_ROLES
                or role == ROLE_UNMASKED_STARLESS
                or record["revision"] == self.processing_revision
            )
        )

    def current_artifact_path(self, role: str, options: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        """Return a published image only if its source, revision and file are current."""
        with self._state_lock:
            path = self.artifact_path(role)
            return path if self._artifact_is_current(role, path, options=options) else None

    def record_export(self, path: Path) -> None:
        self.record_export_if_current(path)

    def publish_mask(
        self,
        path: Union[str, Path],
        *,
        expected_revision: int,
        transaction: Optional[ArtifactTransaction] = None,
    ) -> bool:
        """Publish a mask and invalidate its descendants as one state transition."""
        with self._state_lock:
            if not self._commit_if_current(transaction, expected_revision=expected_revision):
                return False
            if not self.record_artifact(ROLE_SKY_MASK, path, expected_revision=expected_revision):
                return False
            self.invalidate_results(preserve_unmasked=True)
            return True

    def record_export_if_current(
        self,
        path: Path,
        *,
        expected_revision: Optional[int] = None,
        expected_separation_signature: Any = _UNSET,
        transaction: Optional[ArtifactTransaction] = None,
    ) -> bool:
        """Record an export only if its source/composite snapshot is still current."""
        with self._state_lock:
            if not self._commit_if_current(
                transaction,
                expected_revision=expected_revision,
                expected_separation_signature=expected_separation_signature,
            ):
                return False
            options = None
            if self.current_artifact_path(ROLE_FINISHED_COMPOSITE) is not None:
                options = {"separation_signature": self.separation_signature}
            self._record_artifact(_EXPORT_ROLE, path, options=options)
            self.final_output_path = str(path)
            return True

    def current_export_path(self) -> Optional[Path]:
        with self._state_lock:
            if self.final_output_path is None:
                return None
            path = Path(self.final_output_path)
            return path if self._artifact_is_current(_EXPORT_ROLE, path) else None

    def invalidate_results(self, preserve_unmasked: bool = False) -> None:
        """Discard derived references, preserving canonical input images and disk files."""
        with self._state_lock:
            self.processing_revision += 1
            self.separation_signature = None
            self.separation_model_identity = None
            self.separation_options = None
            self.denoise_signature = None
            self.denoise_model_identity = None
            self.composite_signature = None
            self.final_output_path = None
            for role, field in _ARTIFACT_PATH_FIELDS.items():
                if role not in _INPUT_ARTIFACT_ROLES:
                    if preserve_unmasked and role == ROLE_UNMASKED_STARLESS:
                        continue
                    setattr(self, field, None)
            self.artifact_manifest = {
                role: record
                for role, record in self.artifact_manifest.items()
                if role in _INPUT_ARTIFACT_ROLES or (preserve_unmasked and role == ROLE_UNMASKED_STARLESS)
            }

    def invalidate_separation_descendants(self) -> None:
        """Discard outputs derived from the separated layers without invalidating them."""
        with self._state_lock:
            descendant_roles = (
                ROLE_DENOISE_ENDPOINT,
                ROLE_DENOISED_STARLESS,
                ROLE_FINISHED_STARLESS,
                ROLE_FINISHED_COMPOSITE,
            )
            for role in descendant_roles:
                setattr(self, _ARTIFACT_PATH_FIELDS[role], None)
                self.artifact_manifest.pop(role, None)
            self.denoise_signature = None
            self.denoise_model_identity = None
            self.composite_signature = None
            self.invalidate_export()

    def invalidate_denoise_descendants(self) -> None:
        """Discard the internal endpoint and the plates built from it."""
        self.invalidate_artifact_roles(
            {
                ROLE_DENOISE_ENDPOINT,
                ROLE_DENOISED_STARLESS,
                ROLE_FINISHED_STARLESS,
                ROLE_FINISHED_COMPOSITE,
                _EXPORT_ROLE,
            }
        )

    def invalidate_starless_filter_descendants(self) -> None:
        """Discard finished plates built by another sharpening algorithm version.

        Both the internal endpoint and the user-blended denoised plate are
        independent of Structure/Detail and remain valid bases for rebuilding
        the finished plate.
        """
        self.invalidate_artifact_roles({ROLE_FINISHED_STARLESS, ROLE_FINISHED_COMPOSITE, _EXPORT_ROLE})

    def invalidate_export(self) -> None:
        """Discard only the user-encoded export while keeping its source composite."""
        with self._state_lock:
            self.final_output_path = None
            self.artifact_manifest.pop(_EXPORT_ROLE, None)

    def invalidate_artifact_roles(self, roles: set[str]) -> None:
        """Invalidate selected outputs and advance unaffected cached records to a new revision."""
        with self._state_lock:
            self.processing_revision += 1
            for role in roles:
                if role == _EXPORT_ROLE:
                    self.final_output_path = None
                elif role in _ARTIFACT_PATH_FIELDS:
                    setattr(self, _ARTIFACT_PATH_FIELDS[role], None)
                self.artifact_manifest.pop(role, None)
            if ROLE_DENOISE_ENDPOINT in roles:
                self.denoise_signature = None
                self.denoise_model_identity = None
            if ROLE_FINISHED_COMPOSITE in roles:
                self.composite_signature = None
            for role, record in self.artifact_manifest.items():
                if role not in _INPUT_ARTIFACT_ROLES and role != ROLE_UNMASKED_STARLESS:
                    record["revision"] = self.processing_revision

    def publish_separation(
        self,
        starless_path: Union[str, Path],
        stars_path: Union[str, Path],
        *,
        signature: str,
        model_identity: str,
        expected_revision: int,
        composite_path: Optional[Union[str, Path]] = None,
        options: Optional[Dict[str, Any]] = None,
        composite_options: Optional[Dict[str, Any]] = None,
        transaction: Optional[ArtifactTransaction] = None,
    ) -> bool:
        """Atomically publish separated layers and their initial composite for one revision."""
        with self._state_lock:
            starless = Path(starless_path).resolve()
            stars = Path(stars_path).resolve()
            if starless == stars:
                raise ValueError("Starless and stars artifact paths must differ.")
            composite = Path(composite_path).resolve() if composite_path is not None else None
            destinations = {starless, stars}
            if composite is not None and composite in destinations:
                raise ValueError("Composite artifact path must differ from the separated layers.")
            if not self._commit_if_current(transaction, expected_revision=expected_revision):
                return False
            stamps = {ROLE_SEPARATED_STARLESS: _file_stamp(starless), ROLE_SEPARATED_STARS: _file_stamp(stars)}
            if any(stamp is None for stamp in stamps.values()):
                raise FileNotFoundError("Cannot register separation outputs that are missing.")
            if composite is not None:
                composite_stamp = _file_stamp(composite)
                if composite_stamp is None:
                    raise FileNotFoundError("Cannot register a missing composite output.")

            self.invalidate_separation_descendants()
            self.separation_signature = signature
            self.separation_model_identity = model_identity
            self.separation_options = dict(options) if options is not None else None
            if options is not None and "stride" in options:
                # Persist the actual producing stride so reopening the project
                # shows the setting that created these layers.
                self.starnet_stride = int(options["stride"])
            source = self._source_key()
            artifact_options = {"separation_signature": signature}
            composite_artifact_options = (
                artifact_options if composite_options is None else {**artifact_options, **composite_options}
            )
            for role, path in (
                (ROLE_SEPARATED_STARLESS, starless),
                (ROLE_SEPARATED_STARS, stars),
            ):
                self.artifact_manifest[role] = {
                    "source": source,
                    "file": list(stamps[role]),
                    "revision": self.processing_revision,
                    "options": artifact_options,
                }
                setattr(self, _ARTIFACT_PATH_FIELDS[role], str(path))
            if composite is not None:
                self.artifact_manifest[ROLE_FINISHED_COMPOSITE] = {
                    "source": source,
                    "file": list(composite_stamp),
                    "revision": self.processing_revision,
                    "options": composite_artifact_options,
                }
                setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_FINISHED_COMPOSITE], str(composite))
            return True

    def publish_denoise_results(
        self,
        denoised_starless_path: Optional[Union[str, Path]] = None,
        *,
        separation_signature: str,
        expected_revision: int,
        strength: float,
        scope: str,
        structure_amount: float,
        detail_amount: float,
        starless_filter_version: int,
        finished_starless_path: Optional[Union[str, Path]] = None,
        endpoint_path: Optional[Union[str, Path]] = None,
        endpoint_signature: Optional[str] = None,
        model_identity: Optional[str] = None,
        transaction: Optional[ArtifactTransaction] = None,
    ) -> bool:
        """Publish any updated starless denoise outputs in one transaction.

        Denoise and sharpening are independent stages: the internal full-strength
        endpoint, the user-blended denoised plate, and the sharpened finished plate
        each have their own artifact. Callers pass only the plates that changed;
        omitted roles keep their existing records, so a sharpening-only update
        preserves a current denoised plate and a denoise-only update preserves any
        current finished plate. Every published plate invalidates the composite and
        export derived from it.
        """
        with self._state_lock:
            if not np.isfinite(structure_amount) or not 0 <= structure_amount <= PERCENT_SCALE:
                raise ValueError(f"Structure amount must be in range [0.0, 100.0], got {structure_amount}")
            if not np.isfinite(detail_amount) or not 0 <= detail_amount <= PERCENT_SCALE:
                raise ValueError(f"Detail amount must be in range [0.0, 100.0], got {detail_amount}")
            if type(starless_filter_version) is not int or starless_filter_version < 1:
                raise ValueError(f"Starless filter version must be a positive integer, got {starless_filter_version}")
            if not self._commit_if_current(
                transaction,
                expected_revision=expected_revision,
                expected_separation_signature=separation_signature,
            ):
                return False

            published: Dict[str, Path] = {}
            for role, value in (
                (ROLE_DENOISE_ENDPOINT, endpoint_path),
                (ROLE_DENOISED_STARLESS, denoised_starless_path),
                (ROLE_FINISHED_STARLESS, finished_starless_path),
            ):
                if value is None:
                    continue
                path = Path(value).resolve()
                if path in published.values():
                    raise ValueError("Denoise endpoint, denoised starless and finished starless paths must differ.")
                published[role] = path

            if ROLE_DENOISE_ENDPOINT in published and (endpoint_signature is None or model_identity is None):
                raise ValueError("A published denoise endpoint requires its signature and model identity.")

            stamps = {role: _file_stamp(path) for role, path in published.items()}
            missing = [str(path) for role, path in published.items() if stamps[role] is None]
            if missing:
                raise FileNotFoundError(f"Cannot register missing denoise outputs: {', '.join(missing)}")

            source = self._source_key()
            common_options = {
                "separation_signature": separation_signature,
                "denoise_signature": endpoint_signature,
            }
            if endpoint_signature is not None and model_identity is not None:
                self.denoise_signature = endpoint_signature
                self.denoise_model_identity = model_identity

            for role, path in published.items():
                options = dict(common_options)
                if role == ROLE_DENOISED_STARLESS:
                    options.update(
                        denoise_strength=float(strength),
                        denoise_scope=scope,
                    )
                elif role == ROLE_FINISHED_STARLESS:
                    options.update(
                        denoise_strength=float(strength),
                        denoise_scope=scope,
                        structure_amount=float(structure_amount),
                        detail_amount=float(detail_amount),
                        starless_filter_version=starless_filter_version,
                    )
                self.artifact_manifest[role] = {
                    "source": source,
                    "file": list(stamps[role]),
                    "revision": self.processing_revision,
                    "options": options,
                }
                setattr(self, _ARTIFACT_PATH_FIELDS[role], str(path))

            # Composite and export were derived from the previous starless plates.
            setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_FINISHED_COMPOSITE], None)
            self.final_output_path = None
            self.artifact_manifest.pop(ROLE_FINISHED_COMPOSITE, None)
            self.artifact_manifest.pop(_EXPORT_ROLE, None)
            self.composite_signature = None
            return True

    def relocate(self, new_project_file: str) -> None:
        """Rebase owned inputs after a move; retain existing read-only inputs on Save As.

        External references stay external. Derived caches are invalidated, following
        Denoise relocation; a project move never deletes existing artifact files.
        """
        previous_dir = self.get_output_dir()
        previous_file = Path(self.project_file).resolve()
        self.project_file = new_project_file
        if previous_file == Path(new_project_file).resolve():
            return
        output_dir = self.get_output_dir()

        def rebase(value: Union[str, Path], preserve_input: bool) -> str:
            path = Path(value).resolve()
            try:
                candidate = output_dir / path.relative_to(previous_dir)
            except ValueError:
                return str(path)
            if preserve_input and not candidate.is_file() and path.is_file():
                return str(path)
            return str(candidate)

        if self.source_file is not None:
            self.source_file.path = rebase(self.source_file.path, True)
        for field in ("source_snapshot_path", "sky_mask_path"):
            value = getattr(self, field)
            if value is not None:
                setattr(self, field, rebase(value, True))
        if self.output_path is not None:
            self.output_path = rebase(self.output_path, False)
        self.invalidate_results()

    def get_settings(self) -> FinishSettings:
        """Extract authoritative FinishSettings dataclass snapshot."""
        return FinishSettings(**{f.name: getattr(self, f.name) for f in fields(FinishSettings)})

    def update_settings(self, settings: FinishSettings) -> None:
        """Update persisted settings fields from a FinishSettings snapshot."""
        with self._state_lock:
            previous = self.get_settings()
            changed = {name for name, value in asdict(settings).items() if value != getattr(previous, name)}
            if not changed:
                return
            # The effective StarNet options are recorded with each separation, so
            # changing the project default no longer discards valid outputs.
            if changed & {"mask_feather_radius_px"}:
                self.invalidate_results(preserve_unmasked=True)
            else:
                invalidated_roles: set[str] = set()
                if changed & {"denoise_strength", "denoise_scope"}:
                    # Rebuild the user-blended plate from the retained endpoint,
                    # then any finished plate that was derived from it.
                    invalidated_roles.update(
                        {
                            ROLE_DENOISED_STARLESS,
                            ROLE_FINISHED_STARLESS,
                            ROLE_FINISHED_COMPOSITE,
                            _EXPORT_ROLE,
                        }
                    )
                if changed & {"structure_amount", "detail_amount"}:
                    # Sharpen only: both the endpoint and the denoised plate stay
                    # current, so the finished plate is rebuilt from them.
                    invalidated_roles.update({ROLE_FINISHED_STARLESS, ROLE_FINISHED_COMPOSITE, _EXPORT_ROLE})
                if changed & set(COMPOSITION_ONLY_SETTING_NAMES):
                    # Starless toggles and recombination controls change the
                    # composite only; all three stored starless plates remain valid.
                    invalidated_roles.update({ROLE_FINISHED_COMPOSITE, _EXPORT_ROLE})
                if changed & {"jpeg_quality", "jpeg_optimize", "tiff_deflate_compression"}:
                    invalidated_roles.add(_EXPORT_ROLE)
                self.invalidate_artifact_roles(invalidated_roles)
            for k, v in asdict(settings).items():
                setattr(self, k, v)

    def to_finish_config(self) -> FinishProject:
        """Construct an isolated FinishProject snapshot matching operation configuration."""
        snapshot = copy.copy(self)
        snapshot.artifact_manifest = copy.deepcopy(self.artifact_manifest)
        if self.source_file is not None:
            snapshot.source_file = copy.copy(self.source_file)
        return snapshot

    @classmethod
    def ensure_default_project(cls, path: str = f"projects/default{FINISH_EXT}") -> FinishProject:
        """Create and persist default starter Finish project file if absent."""
        p = Path(path)
        if p.exists():
            try:
                raw_text = p.read_text(encoding="utf-8")
                json.loads(raw_text)
                proj = jsonpickle.decode(raw_text)
            except (OSError, ValueError, TypeError) as error:
                raise ValueError(f"Could not load finish project {path}: {error}") from error
            if isinstance(proj, FinishProject):
                return proj
            raise ValueError(f"File {path} is not a finish project.")

        os.makedirs(p.parent.resolve(), exist_ok=True)
        default_proj = cls(project_file=path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(jsonpickle.encode(default_proj, indent=4))
        return default_proj


__all__ = [
    "COMPOSITION_ONLY_SETTING_NAMES",
    "FinishProject",
    "LAYER_EXPORT_SUFFIXES",
    "RETIRED_FINISH_SETTING_NAMES",
    "probe_source_image",
]
