"""Project model and state persistence for Denoise mode (.proj_denoise)."""

from __future__ import annotations
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import jsonpickle
import numpy as np

from startrails.lib.denoise.defaults import DENOISE_DEFAULTS, DenoiseSettings
from startrails.lib.file import DenoiseInputFile, Unpickle
from startrails.lib.project_type import get_project_output_dir, DENOISE_EXT

_ARTIFACT_FILENAMES = {
    "mask": "mask.png",
    "refined_mask": "refined_mask.png",
    "gradient_mask": "gradient_mask.png",
    "sky_stack": "sky_stack.tif",
    "ground_stack": "ground_stack.tif",
}
_ARTIFACT_PATH_FIELDS = {
    "mask": "mask_path",
    "refined_mask": "refined_mask_path",
    "gradient_mask": "gradient_mask_path",
    "sky_stack": "sky_stack_path",
    "ground_stack": "ground_stack_path",
}


class DenoiseProject(Unpickle):
    """Project state model and runtime configuration for the astrophotography Denoise workflow."""

    def __init__(
        self,
        project_file: str = f"projects/default{DENOISE_EXT}",
        star_files: Optional[List[DenoiseInputFile]] = None,
        noise_files: Optional[List[DenoiseInputFile]] = None,
        vignetting_files: Optional[List[DenoiseInputFile]] = None,
        reference_file: Optional[DenoiseInputFile] = None,
        *,
        star_images: Optional[List[Path | str]] = None,
        base_image: Optional[Path | str] = None,
        noise_images: Optional[List[Path | str]] = None,
        mask_array: Optional[np.ndarray] = None,
        output_path: Optional[Path | str] = None,
        sky_stack_path: Optional[Path | str] = None,
        ground_stack_path: Optional[Path | str] = None,
        mask_path: Optional[Path | str] = None,
        refined_mask_path: Optional[Path | str] = None,
        gradient_mask_path: Optional[Path | str] = None,
        homographies: Optional[Dict[Any, Any]] = None,
        **kwargs,
    ):
        super().__init__()
        self.project_file = kwargs.pop("projectFile", project_file)

        # Star files / images
        if star_files is not None:
            self.star_files = list(star_files)
        elif star_images is not None:
            self.star_files = [DenoiseInputFile(basename=Path(p).name, path=str(p)) for p in star_images]
        else:
            self.star_files = []

        # Noise / dark files
        if noise_files is not None:
            self.noise_files = list(noise_files)
        elif noise_images is not None:
            self.noise_files = [DenoiseInputFile(basename=Path(p).name, path=str(p)) for p in noise_images]
        else:
            self.noise_files = []

        # Vignetting / flat files
        self.vignetting_files: List[DenoiseInputFile] = (
            list(vignetting_files) if vignetting_files is not None else []
        )

        # Reference / base frame
        if reference_file is not None:
            self.reference_file = reference_file
        elif base_image is not None:
            base_str = str(base_image)
            base_res = Path(base_image).resolve()
            match = next((f for f in self.star_files if f.path == base_str or Path(f.path).resolve() == base_res), None)
            self.reference_file = match if match is not None else DenoiseInputFile(basename=Path(base_image).name, path=base_str)
        else:
            self.reference_file = None

        # Sidecars and intermediate outputs
        self.mask_path: Optional[str | Path] = mask_path
        self.refined_mask_path: Optional[str | Path] = refined_mask_path
        self.gradient_mask_path: Optional[str | Path] = gradient_mask_path
        self.sky_stack_path: Optional[str | Path] = sky_stack_path
        self.ground_stack_path: Optional[str | Path] = ground_stack_path
        self.output_path: Optional[str | Path] = output_path
        self.final_output_path: Optional[str | Path] = None
        self.mask_array: Optional[np.ndarray] = mask_array

        # Alignment homographies
        self.homographies: Dict[Any, Any] = dict(homographies) if homographies is not None else {}

        # Settings
        default_settings = asdict(DENOISE_DEFAULTS)
        for name, default_val in default_settings.items():
            setattr(self, name, kwargs.pop(name, default_val))

        # Any extra kwargs
        for k, v in kwargs.items():
            setattr(self, k, v)

        self.processing_revision = 0
        self.alignment_signature = None
        self.stack_signature = None
        self.stack_artifacts = {}
        self.mask_invalidated = False
        self.has_manual_sky_corrections = bool(getattr(self, "has_manual_sky_corrections", False))
        self.bind_files()

    @property
    def star_images(self) -> List[Path]:
        return [Path(f.path) for f in self.star_files if f.path]

    @star_images.setter
    def star_images(self, paths: List[Path | str]) -> None:
        self.star_files = [DenoiseInputFile(basename=Path(p).name, path=str(p)) for p in paths]
        self.bind_files()

    @property
    def noise_images(self) -> List[Path]:
        return [Path(f.path) for f in self.noise_files if f.path]

    @noise_images.setter
    def noise_images(self, paths: List[Path | str]) -> None:
        self.noise_files = [DenoiseInputFile(basename=Path(p).name, path=str(p)) for p in paths]
        self.bind_files()

    @property
    def base_image(self) -> Optional[Path]:
        ref = self.get_reference_file()
        return Path(ref.path) if ref and ref.path else None

    @base_image.setter
    def base_image(self, path: Optional[Path | str]) -> None:
        if path is None:
            self.reference_file = None
        else:
            p_str = str(path)
            p_res = Path(path).resolve()
            match = next((f for f in self.star_files if f.path == p_str or Path(f.path).resolve() == p_res), None)
            ref_file = match if match is not None else DenoiseInputFile(basename=Path(path).name, path=p_str)
            self.reference_file = ref_file
            if match is not None:
                self.bind_files()

    def bind_files(self):
        for file in self.star_files + self.noise_files + self.vignetting_files:
            file.bind_project(self)

    def __getstate__(self):
        state = dict(self.__dict__)
        # Transient in-memory mask array should not be persisted into project json
        state.pop("mask_array", None)
        return state

    def __setstate__(self, state):
        state = dict(state)
        if "projectFile" in state:
            state["project_file"] = state.pop("projectFile")
        if state.get("stack_method") == "median":
            # The old port's Median choice actually executed a mean stack.
            state["stack_method"] = "mean"
        super().__setstate__(state)
        self.bind_files()

    @staticmethod
    def file_signature(path) -> tuple:
        resolved = Path(path).resolve()
        try:
            stat = resolved.stat()
            return str(resolved), stat.st_size, stat.st_mtime_ns
        except OSError:
            return str(resolved), None, None

    def source_signature(self, stacking: bool = False) -> str:
        reference = self.get_reference_file()
        data = {
            "stars": [self.file_signature(f.path) for f in self.star_files],
            "darks": [self.file_signature(f.path) for f in self.noise_files],
            "reference": reference.path if reference else None,
            "mask": self.file_signature(self.mask_path) if self.mask_path and not self.mask_invalidated else None,
            "taper": (self.taper_mask_edges, self.mask_taper_pixels),
            "mask_settings": (self.auto_mask, self.auto_mask_model, self.auto_mask_path, self.refine_sky_mask,
                              self.mask_search_radius, self.mask_erosion_pixels, self.mask_foliage_protection),
        }
        if stacking:
            data["stack"] = (self.stack_method, self.sigma_clip_threshold, self.sigma_clip_iterations,
                             self.horizon_denoise_radius, self.horizon_denoise_eps)
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def invalidate_results(self, alignment: bool = True) -> None:
        self.processing_revision += 1
        if alignment:
            self.homographies = {}
            self.alignment_signature = None
            for file in self.star_files:
                file.aligned = False
        self.stack_signature = None
        self.stack_artifacts = {}
        self.final_output_path = None

    def validate_cached_results(self) -> None:
        if self.homographies and not self.alignment_is_current():
            self.invalidate_results()
        elif self.stack_signature and self.stack_signature != self.source_signature(stacking=True):
            self.invalidate_results(alignment=False)

    def alignment_is_current(self) -> bool:
        return self.alignment_signature == self.source_signature()

    def record_stacks(self) -> None:
        self.stack_signature = self.source_signature(stacking=True)
        self.stack_artifacts = {
            str(path): self.file_signature(path)
            for path in (self.sky_stack_path, self.ground_stack_path, self.gradient_mask_path)
            if path and Path(path).is_file()
        }

    def stacks_are_current(self) -> bool:
        return bool(
            self.stack_signature == self.source_signature(stacking=True)
            and self.sky_stack_path and self.ground_stack_path
            and len(self.stack_artifacts) >= 2
            and all(Path(path).is_file() and tuple(signature) == self.file_signature(path)
                    for path, signature in self.stack_artifacts.items())
        )

    def get_output_dir(self) -> Path:
        """Resolve the authoritative output directory for this project."""
        return get_project_output_dir(self.project_file)

    def artifact_path(self, artifact: str) -> Path:
        """Resolve a named denoise artifact using the project output directory."""
        if artifact not in _ARTIFACT_FILENAMES:
            raise ValueError(f"Unknown denoise artifact: {artifact}")
        field = _ARTIFACT_PATH_FIELDS[artifact]
        value = getattr(self, field, None)
        if artifact == "mask" and getattr(self, "mask_invalidated", False):
            value = None
        return (
            Path(value).resolve()
            if value
            else (self.get_output_dir() / _ARTIFACT_FILENAMES[artifact]).resolve()
        )

    def relocate(self, project_file: str) -> None:
        """Rebase owned artifacts; imported masks and external exports remain references."""
        previous_dir = self.get_output_dir()
        previous_file = Path(self.project_file).resolve()
        self.project_file = project_file
        if previous_file == Path(project_file).resolve():
            return
        output_dir = self.get_output_dir()
        for name in ("sky_stack_path", "ground_stack_path", "gradient_mask_path",
                     "refined_mask_path", "output_path", "final_output_path", "mask_path"):
            value = getattr(self, name)
            if not value:
                continue
            try:
                relative = Path(value).resolve().relative_to(previous_dir)
            except ValueError:
                continue  # Imported mask or explicitly exported image.
            rebased = output_dir / relative
            if name == "mask_path" and not rebased.exists() and Path(value).is_file():
                continue  # Safe read-only source; edited masks always go to output_dir.
            setattr(self, name, str(rebased))
        self.invalidate_results()

    def get_reference_file(self) -> Optional[DenoiseInputFile]:
        """Return the chosen reference frame, defaulting to the middle star frame."""
        if self.reference_file is not None:
            for file in self.star_files:
                if file is self.reference_file or file.file_id == self.reference_file.file_id:
                    return file
            ref_path = getattr(self.reference_file, "path", None)
            if ref_path:
                ref_res = Path(ref_path).resolve()
                for file in self.star_files:
                    if file.path == ref_path or Path(file.path).resolve() == ref_res:
                        return file
            return self.reference_file
        if self.star_files:
            return self.star_files[len(self.star_files) // 2]
        return None

    def set_reference_file(self, file: DenoiseInputFile) -> None:
        """Mark a single input frame as the active reference frame."""
        if file not in self.star_files and not any(f.path == file.path for f in self.star_files):
            raise ValueError("Reference frame must be a star input in this project")
        self.reference_file = file
        self.bind_files()

    def get_project_stem(self) -> str:
        """Return the base stem of the project file without extension."""
        if not self.project_file:
            return "project"
        name = Path(self.project_file).name
        if name.endswith(DENOISE_EXT):
            return name[:-len(DENOISE_EXT)]
        if name.endswith(".json"):
            return name[:-5]
        return Path(self.project_file).stem

    @property
    def projectFile(self) -> str:  # noqa: N802 - compatibility property for host shell
        """Compatibility property for host shell and persistence."""
        return self.project_file

    @projectFile.setter
    def projectFile(self, value: str) -> None:  # noqa: N802
        self.project_file = value

    def to_denoise_config(self) -> DenoiseProject:
        """Construct an isolated DenoiseProject snapshot matching operation configuration."""
        ref = self.get_reference_file()
        base_path = Path(ref.path) if ref and ref.path else None

        homographies_dict: dict[Path, Any] = {}
        for k, v in self.homographies.items():
            homographies_dict[Path(k).resolve()] = copy.deepcopy(v)

        out_dir = self.get_output_dir()
        stem = self.get_project_stem()
        mask_p = Path(self.mask_path) if self.mask_path and not self.mask_invalidated else None
        if mask_p is None and not self.mask_invalidated and self.artifact_path("mask").exists():
            mask_p = self.artifact_path("mask")

        sky_stack_p = self.artifact_path("sky_stack")
        ground_stack_p = self.artifact_path("ground_stack")
        refined_mask_p = self.artifact_path("refined_mask")
        gradient_mask_p = self.artifact_path("gradient_mask")
        output_p = out_dir / f"{stem}.tif"

        snapshot = copy.copy(self)
        snapshot.star_files = [copy.copy(f) for f in self.star_files]
        snapshot.noise_files = [copy.copy(f) for f in self.noise_files]
        snapshot.vignetting_files = [copy.copy(f) for f in self.vignetting_files]
        snapshot.reference_file = copy.copy(self.reference_file) if self.reference_file else None
        snapshot.homographies = homographies_dict
        snapshot.output_path = output_p
        snapshot.sky_stack_path = sky_stack_p
        snapshot.ground_stack_path = ground_stack_p
        snapshot.refined_mask_path = refined_mask_p
        snapshot.gradient_mask_path = gradient_mask_p
        snapshot.mask_path = mask_p
        snapshot.mask_array = copy.deepcopy(self.mask_array) if self.mask_array is not None else None
        snapshot.bind_files()
        return snapshot

    @classmethod
    def ensure_default_project(cls, path: str = f"projects/default{DENOISE_EXT}") -> DenoiseProject:
        """Create and persist the default starter denoise project file if absent."""
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    raw_project = f.read()
                json.loads(raw_project)
                proj = jsonpickle.decode(raw_project)
            except (OSError, ValueError, TypeError) as error:
                raise ValueError(f"Could not load denoise project {path}: {error}") from error
            if isinstance(proj, DenoiseProject):
                return proj
            raise ValueError(f"File {path} is not a denoise project.")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        default_proj = cls(project_file=path)
        with open(path, "w+") as f:
            f.write(jsonpickle.encode(default_proj, indent=4))
        return default_proj


__all__ = ["DenoiseProject", "DenoiseSettings"]
