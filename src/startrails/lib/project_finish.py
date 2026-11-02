"""Project model and state persistence for Finish mode (.proj_finish)."""

from __future__ import annotations

import copy
from dataclasses import asdict, fields
import json
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
    CATALOG_SETTING_NAMES,
    COMPOSITION_ONLY_SETTING_NAMES,
    FINISHED_STARS_COMPOSITION_SETTING_NAMES,
    FINISH_DEFAULTS,
    FINISH_EXT,
    GLOW_SETTING_NAMES,
    PERCENT_SCALE,
    RETIRED_FINISH_SETTING_NAMES,
    STAR_EFFECT_SETTING_NAMES,
    FinishSettings,
    ROLE_SOURCE_SNAPSHOT,
    ROLE_SKY_MASK,
    ROLE_UNMASKED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_STARLESS,
    ROLE_FINISHED_STARS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_STAR_CATALOG,
    ROLE_ROUND_DELTA,
    SUPPORTED_CHANNELS,
    SUPPORTED_SOURCE_FORMATS,
)
from startrails.lib.project_type import get_project_output_dir
from startrails.lib.signatures import read_file_identity

_ARTIFACT_FILENAMES: Dict[str, str] = {
    ROLE_SOURCE_SNAPSHOT: "source_snapshot.tif",
    ROLE_SKY_MASK: "sky_mask.png",
    ROLE_UNMASKED_STARLESS: "unmasked_starless.tif",
    ROLE_SEPARATED_STARLESS: "starless.tif",
    ROLE_SEPARATED_STARS: "stars.tif",
    ROLE_DENOISED_STARLESS: "denoised_starless.tif",
    ROLE_STAR_CATALOG: "catalog.npz",
    ROLE_ROUND_DELTA: "round_delta.npz",
    ROLE_FINISHED_STARLESS: "finished_starless.tif",
    ROLE_FINISHED_STARS: "finished_stars.tif",
    ROLE_FINISHED_COMPOSITE: "composite.tif",
}

_ARTIFACT_PATH_FIELDS: Dict[str, str] = {
    ROLE_SOURCE_SNAPSHOT: "source_snapshot_path",
    ROLE_SKY_MASK: "sky_mask_path",
    ROLE_UNMASKED_STARLESS: "unmasked_starless_path",
    ROLE_SEPARATED_STARLESS: "separated_starless_path",
    ROLE_SEPARATED_STARS: "separated_stars_path",
    ROLE_DENOISED_STARLESS: "denoised_starless_path",
    ROLE_STAR_CATALOG: "star_catalog_path",
    ROLE_ROUND_DELTA: "round_delta_path",
    ROLE_FINISHED_STARLESS: "finished_starless_path",
    ROLE_FINISHED_STARS: "finished_stars_path",
    ROLE_FINISHED_COMPOSITE: "composite_path",
}


_INPUT_ARTIFACT_ROLES = (ROLE_SOURCE_SNAPSHOT, ROLE_SKY_MASK)
_EXPORT_ROLE = "export"
_SOURCE_FORMATS_BY_SUFFIX = {".jpg": "jpeg", ".jpeg": "jpeg", ".tif": "tiff", ".tiff": "tiff"}
_UNSET = object()


def _star_effect_options(settings: FinishSettings) -> Dict[str, Any]:
    """Return provenance settings baked into a finished-stars result."""
    names = STAR_EFFECT_SETTING_NAMES + FINISHED_STARS_COMPOSITION_SETTING_NAMES
    return {name: getattr(settings, name) for name in names}


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
        denoised_starless_path: Optional[Union[str, Path]] = None,
        star_catalog_path: Optional[Union[str, Path]] = None,
        round_delta_path: Optional[Union[str, Path]] = None,
        finished_starless_path: Optional[Union[str, Path]] = None,
        finished_stars_path: Optional[Union[str, Path]] = None,
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
        self.denoised_starless_path: Optional[Union[str, Path]] = denoised_starless_path
        self.star_catalog_path: Optional[Union[str, Path]] = star_catalog_path
        self.round_delta_path: Optional[Union[str, Path]] = round_delta_path
        self.finished_starless_path: Optional[Union[str, Path]] = finished_starless_path
        self.finished_stars_path: Optional[Union[str, Path]] = finished_stars_path
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
        for retired in RETIRED_FINISH_SETTING_NAMES:
            state.pop(retired, None)
        super().__setstate__(state)
        # Projects saved before a new setting existed inherit its authoritative
        # default instead of missing the attribute at runtime.
        for name, default_val in asdict(FINISH_DEFAULTS).items():
            if not hasattr(self, name):
                setattr(self, name, default_val)

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
            ROLE_DENOISED_STARLESS,
            ROLE_STAR_CATALOG,
            ROLE_ROUND_DELTA,
            ROLE_FINISHED_STARLESS,
            ROLE_FINISHED_STARS,
            ROLE_FINISHED_COMPOSITE,
            _EXPORT_ROLE,
        ):
            artifact_signature = record.get("options", {}).get("separation_signature")
            if artifact_signature is not None and artifact_signature != self.separation_signature:
                return False
        if role == ROLE_DENOISED_STARLESS:
            artifact_signature = record.get("options", {}).get("denoise_signature")
            if artifact_signature is not None and artifact_signature != self.denoise_signature:
                return False
            sep_signature = record.get("options", {}).get("separation_signature")
            if sep_signature is not None and sep_signature != self.separation_signature:
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
                ROLE_DENOISED_STARLESS,
                ROLE_STAR_CATALOG,
                ROLE_ROUND_DELTA,
                ROLE_FINISHED_STARLESS,
                ROLE_FINISHED_STARS,
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
        """Discard the cached denoise endpoint and the plates built from it."""
        self.invalidate_artifact_roles(
            {ROLE_DENOISED_STARLESS, ROLE_FINISHED_STARLESS, ROLE_FINISHED_COMPOSITE, _EXPORT_ROLE}
        )

    def invalidate_starless_filter_descendants(self) -> None:
        """Discard finished plates built by another sharpening algorithm version.

        The full-strength denoise endpoint is independent of Structure/Detail and
        remains a valid base for rebuilding the finished plate.
        """
        self.invalidate_artifact_roles({ROLE_FINISHED_STARLESS, ROLE_FINISHED_COMPOSITE, _EXPORT_ROLE})

    def invalidate_star_effects_descendants(self) -> None:
        """Discard the catalog, its derived layers and results built from them.

        Only outputs derived from star analysis/effects are discarded. The
        separated layers, denoise endpoint and finished starless plate do not
        depend on them, so they remain valid bases for rebuilding the catalog.
        """
        self.invalidate_artifact_roles(
            {
                ROLE_STAR_CATALOG,
                ROLE_ROUND_DELTA,
                ROLE_FINISHED_STARS,
                ROLE_FINISHED_COMPOSITE,
                _EXPORT_ROLE,
            }
        )

    def invalidate_star_effect_layers(self) -> None:
        """Discard effect layers produced by an older effect algorithm.

        The catalog is analysis-versioned and independent of effect versioning, so
        it remains valid while Round/Glow-derived outputs are rebuilt.
        """
        self.invalidate_artifact_roles({ROLE_ROUND_DELTA, ROLE_FINISHED_STARS, ROLE_FINISHED_COMPOSITE, _EXPORT_ROLE})

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
            if ROLE_DENOISED_STARLESS in roles:
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
                    "options": artifact_options,
                }
                setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_FINISHED_COMPOSITE], str(composite))
            return True

    def publish_denoise_results(
        self,
        finished_path: Union[str, Path],
        *,
        separation_signature: str,
        expected_revision: int,
        strength: float,
        scope: str,
        structure_amount: float,
        detail_amount: float,
        starless_filter_version: int,
        endpoint_path: Optional[Union[str, Path]] = None,
        endpoint_signature: Optional[str] = None,
        model_identity: Optional[str] = None,
        transaction: Optional[ArtifactTransaction] = None,
    ) -> bool:
        """Atomically publish a finished-starless blend and, when computed, its endpoint.

        The full-strength endpoint is keyed by its inference signature. Strength,
        scope, Structure and Detail only describe the finished blend, so changing
        them never requires a new endpoint. The finished artifact records the
        Structure/Detail amounts and sharpening algorithm version that produced it.
        A new finished starless plate invalidates the previous composite and export
        because both were built from the replaced plate.
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

            finished = Path(finished_path).resolve()
            finished_stamp = _file_stamp(finished)
            if finished_stamp is None:
                raise FileNotFoundError(f"Cannot register a missing finished starless image: {finished}")

            endpoint: Optional[Path] = None
            endpoint_stamp = None
            if endpoint_path is not None:
                if endpoint_signature is None or model_identity is None:
                    raise ValueError("A published denoise endpoint requires its signature and model identity.")
                endpoint = Path(endpoint_path).resolve()
                if endpoint == finished:
                    raise ValueError("Denoise endpoint and finished starless paths must differ.")
                endpoint_stamp = _file_stamp(endpoint)
                if endpoint_stamp is None:
                    raise FileNotFoundError(f"Cannot register a missing denoise endpoint: {endpoint}")

            source = self._source_key()
            common_options = {
                "separation_signature": separation_signature,
                "denoise_signature": endpoint_signature,
            }
            if endpoint is not None:
                self.artifact_manifest[ROLE_DENOISED_STARLESS] = {
                    "source": source,
                    "file": list(endpoint_stamp),
                    "revision": self.processing_revision,
                    "options": dict(common_options),
                }
                setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_DENOISED_STARLESS], str(endpoint))
                self.denoise_signature = endpoint_signature
                self.denoise_model_identity = model_identity

            self.artifact_manifest[ROLE_FINISHED_STARLESS] = {
                "source": source,
                "file": list(finished_stamp),
                "revision": self.processing_revision,
                "options": dict(
                    common_options,
                    strength=float(strength),
                    scope=scope,
                    structure_amount=float(structure_amount),
                    detail_amount=float(detail_amount),
                    starless_filter_version=starless_filter_version,
                ),
            }
            setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_FINISHED_STARLESS], str(finished))

            # Composite and export were derived from the previous finished plate.
            setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_FINISHED_COMPOSITE], None)
            self.final_output_path = None
            self.artifact_manifest.pop(ROLE_FINISHED_COMPOSITE, None)
            self.artifact_manifest.pop(_EXPORT_ROLE, None)
            self.composite_signature = None
            return True

    def publish_star_effects(
        self,
        *,
        catalog_path: Union[str, Path],
        round_delta_path: Optional[Union[str, Path]] = None,
        finished_stars_path: Optional[Union[str, Path]] = None,
        separation_signature: str,
        expected_revision: int,
        catalog_identity: str,
        star_effect_version: int,
        settings: FinishSettings,
        round_identity: Optional[str] = None,
        catalog_options: Optional[Dict[str, Any]] = None,
        round_options: Optional[Dict[str, Any]] = None,
        transaction: Optional[ArtifactTransaction] = None,
    ) -> bool:
        """Atomically publish the analysis catalog and its derived effect layers.

        The project stores paths, file stamps and identity/version metadata only;
        array payloads live in the `.npz` artifacts. The optional finished-stars
        TIFF is a derived display output for OutputFiles interoperability and is
        never authoritative effect state. Publishing new effect layers invalidates
        the composite and export built from the previous layers while preserving
        the finished starless and denoise outputs.
        """
        with self._state_lock:
            if type(star_effect_version) is not int or star_effect_version < 1:
                raise ValueError(f"Star effect version must be a positive integer, got {star_effect_version}")
            if not catalog_identity:
                raise ValueError("A star catalog publication requires its identity.")
            if round_delta_path is not None and not round_identity:
                raise ValueError("A round-delta publication requires its identity.")
            if not self._commit_if_current(
                transaction,
                expected_revision=expected_revision,
                expected_separation_signature=separation_signature,
            ):
                return False

            source = self._source_key()
            catalog = Path(catalog_path).resolve()
            catalog_stamp = _file_stamp(catalog)
            if catalog_stamp is None:
                raise FileNotFoundError(f"Cannot register a missing star catalog: {catalog}")

            finished = Path(finished_stars_path).resolve() if finished_stars_path is not None else None
            resolved_round: Optional[Path] = None
            round_stamp = None
            if round_delta_path is not None:
                resolved_round = Path(round_delta_path).resolve()
                if resolved_round in (catalog, finished):
                    raise ValueError("Star artifact paths must differ.")
                round_stamp = _file_stamp(resolved_round)
                if round_stamp is None:
                    raise FileNotFoundError(f"Cannot register a missing round-stars delta: {resolved_round}")

            finished_stamp = None
            if finished is not None:
                if finished in (catalog, resolved_round):
                    raise ValueError("Star artifact paths must differ.")
                finished_stamp = _file_stamp(finished)
                if finished_stamp is None:
                    raise FileNotFoundError(f"Cannot register a missing finished stars image: {finished}")

            self.artifact_manifest[ROLE_STAR_CATALOG] = {
                "source": source,
                "file": list(catalog_stamp),
                "revision": self.processing_revision,
                "options": dict(
                    catalog_options or {},
                    separation_signature=separation_signature,
                    catalog_identity=catalog_identity,
                ),
            }
            setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_STAR_CATALOG], str(catalog))

            if resolved_round is not None:
                self.artifact_manifest[ROLE_ROUND_DELTA] = {
                    "source": source,
                    "file": list(round_stamp),
                    "revision": self.processing_revision,
                    "options": dict(
                        round_options or {},
                        separation_signature=separation_signature,
                        catalog_identity=catalog_identity,
                        round_identity=round_identity,
                        star_effect_version=star_effect_version,
                    ),
                }
                setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_ROUND_DELTA], str(resolved_round))
            else:
                setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_ROUND_DELTA], None)
                self.artifact_manifest.pop(ROLE_ROUND_DELTA, None)

            if finished is not None:
                options = {
                    "separation_signature": separation_signature,
                    "catalog_identity": catalog_identity,
                    "round_identity": round_identity,
                    "star_effect_version": star_effect_version,
                    **_star_effect_options(settings),
                }
                self.artifact_manifest[ROLE_FINISHED_STARS] = {
                    "source": source,
                    "file": list(finished_stamp),
                    "revision": self.processing_revision,
                    "options": options,
                }
                setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_FINISHED_STARS], str(finished))
            else:
                setattr(self, _ARTIFACT_PATH_FIELDS[ROLE_FINISHED_STARS], None)
                self.artifact_manifest.pop(ROLE_FINISHED_STARS, None)

            # Composite and export were derived from the previous star layers.
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
                if changed & {"denoise_strength", "denoise_scope", "structure_amount", "detail_amount"}:
                    invalidated_roles.update({ROLE_FINISHED_STARLESS, ROLE_FINISHED_COMPOSITE, _EXPORT_ROLE})
                if changed & set(CATALOG_SETTING_NAMES):
                    # The catalog keeps its measurements; a new cutoff selects a
                    # different included set, so Round/Glow and compositions rebuild.
                    invalidated_roles.update(
                        {ROLE_ROUND_DELTA, ROLE_FINISHED_STARS, ROLE_FINISHED_COMPOSITE, _EXPORT_ROLE}
                    )
                if changed & (set(GLOW_SETTING_NAMES) | set(FINISHED_STARS_COMPOSITION_SETTING_NAMES)):
                    # Glow geometry and Round/Glow composition are baked into the
                    # derived finished-stars TIFF; catalog/Round/Glow caches remain.
                    invalidated_roles.update({ROLE_FINISHED_STARS, ROLE_FINISHED_COMPOSITE, _EXPORT_ROLE})
                if changed & set(COMPOSITION_ONLY_SETTING_NAMES):
                    # Layer amounts/modes change recombination only; the derived
                    # S_fin TIFF remains valid when no baked control changed.
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
    "CATALOG_SETTING_NAMES",
    "COMPOSITION_ONLY_SETTING_NAMES",
    "FinishProject",
    "GLOW_SETTING_NAMES",
    "RETIRED_FINISH_SETTING_NAMES",
    "STAR_EFFECT_SETTING_NAMES",
    "probe_source_image",
]
