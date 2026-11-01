"""Project model and state persistence for Finish mode (.proj_finish)."""

from __future__ import annotations

import copy
from dataclasses import asdict, fields
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import jsonpickle
import numpy as np

from startrails.lib.file import InputFile, Unpickle
from startrails.lib.image_io import imread
from startrails.lib.finish.defaults import (
    FINISH_DEFAULTS,
    FINISH_EXT,
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
    ROLE_FINISHED_STARLESS: "finished_starless_path",
    ROLE_FINISHED_STARS: "finished_stars_path",
    ROLE_FINISHED_COMPOSITE: "composite_path",
}


_INPUT_ARTIFACT_ROLES = (ROLE_SOURCE_SNAPSHOT, ROLE_SKY_MASK)
_EXPORT_ROLE = "export"
_SOURCE_FORMATS_BY_SUFFIX = {".jpg": "jpeg", ".jpeg": "jpeg", ".tif": "tiff", ".tiff": "tiff"}


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
        finished_starless_path: Optional[Union[str, Path]] = None,
        finished_stars_path: Optional[Union[str, Path]] = None,
        composite_path: Optional[Union[str, Path]] = None,
        output_path: Optional[Union[str, Path]] = None,
        final_output_path: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ):
        super().__init__()
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
        self.finished_starless_path: Optional[Union[str, Path]] = finished_starless_path
        self.finished_stars_path: Optional[Union[str, Path]] = finished_stars_path
        self.composite_path: Optional[Union[str, Path]] = composite_path
        self.output_path: Optional[Union[str, Path]] = output_path
        self.final_output_path: Optional[Union[str, Path]] = final_output_path

        # Authoritative defaults from FinishSettings
        defaults = asdict(FINISH_DEFAULTS)
        for name, default_val in defaults.items():
            setattr(self, name, kwargs.pop(name, default_val))

        for k, v in kwargs.items():
            setattr(self, k, v)

        self.processing_revision: int = 0
        self.separation_signature: Optional[str] = None
        self.denoise_signature: Optional[str] = None
        self.composite_signature: Optional[str] = None
        self.artifact_manifest: Dict[str, Any] = {}

    @property
    def projectFile(self) -> str:  # noqa: N802 - compatibility property for host shell
        """Compatibility property for host shell and persistence."""
        return self.project_file

    @projectFile.setter
    def projectFile(self, value: str) -> None:  # noqa: N802
        self.project_file = value

    def __getstate__(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    def __setstate__(self, state: Dict[str, Any]) -> None:
        state = dict(state)
        if "projectFile" in state:
            state["project_file"] = state.pop("projectFile")
        state.pop("source_dimensions", None)
        state.pop("source_format", None)
        super().__setstate__(state)

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

    def artifact_path(self, role: str) -> Path:
        """Resolve a named Finish artifact using project output directory."""
        if role not in _ARTIFACT_FILENAMES:
            raise ValueError(f"Unknown finish artifact role: {role}")
        field = _ARTIFACT_PATH_FIELDS[role]
        value = getattr(self, field, None)
        if value:
            return Path(value).resolve()
        return (self.get_output_dir() / _ARTIFACT_FILENAMES[role]).resolve()

    def get_default_export_path(self) -> Path:
        """Derive the source-matching export path from the input path and project directory."""
        stem = self.get_project_stem()
        out_dir = self.get_output_dir()
        if self.source_file and self.source_file.path:
            suffix = Path(self.source_file.path).suffix.lower()
            return (out_dir / f"{stem}{suffix}").resolve()
        return (out_dir / f"{stem}.tif").resolve()

    def validate_export_path(self, path: Path) -> None:
        """Enforce the imported source's codec, accepting equivalent suffixes."""
        if self.source_file is None:
            raise ValueError("No source image imported to export.")
        if _source_format(path) != _source_format(Path(self.source_file.path)):
            raise ValueError("Export format must match the source image format.")

    def source_is_current(self) -> bool:
        return bool(
            self.source_file
            and self.source_stamp is not None
            and _file_stamp(Path(self.source_file.path)) == tuple(self.source_stamp)
        )

    def _source_key(self) -> list:
        return [self.source_file.sourceId, list(self.source_stamp)]

    def set_source_image(self, path: Union[str, Path]) -> None:
        """Validate before replacing the source; never reuse its predecessor's artifacts."""
        resolved_path = Path(path).resolve()
        bit_depth = probe_source_image(resolved_path)
        stamp = _file_stamp(resolved_path)
        if stamp is None:
            raise FileNotFoundError(f"Source image became unavailable: {resolved_path}")
        self.source_file = InputFile(basename=resolved_path.name, path=str(resolved_path))
        self.source_bit_depth = bit_depth
        self.source_stamp = stamp
        self.source_snapshot_path = None
        self.sky_mask_path = None
        self.artifact_manifest.clear()
        self.invalidate_results()
        self.output_path = str(self.get_default_export_path())

    def _record_artifact(self, role: str, path: Path) -> None:
        if not self.source_is_current():
            raise ValueError("Source image changed or is unavailable; import it again.")
        stamp = _file_stamp(path)
        if stamp is None:
            raise FileNotFoundError(f"Cannot record missing artifact: {path}")
        self.artifact_manifest[role] = {
            "source": self._source_key(),
            "file": list(stamp),
            "revision": self.processing_revision,
        }

    def record_artifact(self, role: str, path: Union[str, Path]) -> None:
        """Register an ordinary image only after successful publication of its job."""
        self.artifact_path(role)  # Reject unknown roles before changing state.
        resolved = Path(path).resolve()
        self._record_artifact(role, resolved)
        setattr(self, _ARTIFACT_PATH_FIELDS[role], str(resolved))

    def _artifact_is_current(self, role: str, path: Path) -> bool:
        record = self.artifact_manifest.get(role)
        if not record or not self.source_is_current():
            return False
        return bool(
            record["source"] == self._source_key()
            and _file_stamp(path) == tuple(record["file"])
            and (role in _INPUT_ARTIFACT_ROLES or record["revision"] == self.processing_revision)
        )

    def current_artifact_path(self, role: str) -> Optional[Path]:
        """Return a published image only if its source, revision and file are current."""
        path = self.artifact_path(role)
        return path if self._artifact_is_current(role, path) else None

    def record_export(self, path: Path) -> None:
        self._record_artifact(_EXPORT_ROLE, path)
        self.final_output_path = str(path)

    def current_export_path(self) -> Optional[Path]:
        if self.final_output_path is None:
            return None
        path = Path(self.final_output_path)
        return path if self._artifact_is_current(_EXPORT_ROLE, path) else None

    def invalidate_results(self) -> None:
        """Discard derived references, preserving canonical input images and disk files."""
        self.processing_revision += 1
        self.separation_signature = None
        self.denoise_signature = None
        self.composite_signature = None
        self.final_output_path = None
        for role, field in _ARTIFACT_PATH_FIELDS.items():
            if role not in _INPUT_ARTIFACT_ROLES:
                setattr(self, field, None)
        self.artifact_manifest = {
            role: record for role, record in self.artifact_manifest.items() if role in _INPUT_ARTIFACT_ROLES
        }

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
        if settings != self.get_settings():
            self.invalidate_results()
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


__all__ = ["FinishProject", "probe_source_image"]
