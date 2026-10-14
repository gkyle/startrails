"""Project model and state persistence for Denoise mode (.proj_denoise)."""

from __future__ import annotations
import os
import hashlib
import json
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional
import jsonpickle

from startrails.lib.file import DenoiseInputFile, Unpickle
from startrails.lib.denoise.config import DenoiseConfig
from startrails.lib.project_type import get_project_output_dir, DENOISE_EXT


class DenoiseProject(Unpickle):
    """Project state model for the astrophotography Denoise workflow."""

    def __init__(
        self,
        projectFile: str = f"projects/default{DENOISE_EXT}",
        star_files: Optional[List[DenoiseInputFile]] = None,
        noise_files: Optional[List[DenoiseInputFile]] = None,
        vignetting_files: Optional[List[DenoiseInputFile]] = None,
        reference_file: Optional[DenoiseInputFile] = None,
    ):
        super().__init__()
        self.projectFile = projectFile
        self.star_files: List[DenoiseInputFile] = list(star_files) if star_files is not None else []
        self.noise_files: List[DenoiseInputFile] = list(noise_files) if noise_files is not None else []
        self.vignetting_files: List[DenoiseInputFile] = (
            list(vignetting_files) if vignetting_files is not None else []
        )
        self.reference_file: Optional[DenoiseInputFile] = reference_file

        # Sidecars and intermediate outputs
        self.mask_path: Optional[str] = None
        self.refined_mask_path: Optional[str] = None
        self.gradient_mask_path: Optional[str] = None
        self.sky_stack_path: Optional[str] = None
        self.ground_stack_path: Optional[str] = None
        self.output_path: Optional[str] = None
        self.final_output_path: Optional[str] = None

        # Alignment homographies: mapped by path string or identifier
        self.homographies: Dict[str, Any] = {}

        # Masking parameters
        self.mask_search_radius: Optional[int] = None
        self.mask_erosion_pixels: int = 5
        self.mask_foliage_protection: bool = True
        self.refine_sky_mask: bool = False
        self.auto_mask: bool = False
        self.auto_mask_model: Optional[str] = None
        self.auto_mask_path: Optional[str] = None
        self.export_refined_mask: bool = True
        self.export_gradient_mask: bool = True
        self.taper_mask_edges: bool = True
        self.mask_taper_pixels: int = 5

        # Stacking parameters
        self.stack_method: str = "sigma_clipped"
        self.sigma_clip_threshold: float = 1.2
        self.sigma_clip_iterations: int = 3

        # Horizon transition parameters
        self.enable_horizon_corrections: bool = True
        self.denoise_horizon_band: bool = True
        self.horizon_denoise_radius: int = 5
        self.horizon_denoise_eps: float = 1e-3
        self.horizon_denoise_strength: float = 0.2
        self.horizon_color_denoise_strength: float = 1.0
        self.horizon_value_denoise_strength: float = 0.2
        self.horizon_blend_percent: float = 60.0
        self.horizon_blur_radius: float = 2.0

        # Hardware acceleration
        self.use_gpu: bool = True
        self.processing_revision = 0
        self.alignment_signature = None
        self.stack_signature = None
        self.stack_artifacts = {}
        self.mask_invalidated = False

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
        if self.homographies and self.alignment_signature != self.source_signature():
            self.invalidate_results()
        elif self.stack_signature and self.stack_signature != self.source_signature(stacking=True):
            self.invalidate_results(alignment=False)

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
        return get_project_output_dir(self.projectFile)

    def relocate(self, project_file: str) -> None:
        """Rebase owned artifacts; imported masks and external exports remain references."""
        previous_dir = self.get_output_dir()
        previous_file = Path(self.projectFile).resolve()
        self.projectFile = project_file
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
        """Return the authoritative reference frame, defaulting to the first star frame."""
        if self.reference_file is not None:
            return self.reference_file
        if self.star_files:
            return self.star_files[0]
        return None

    def set_reference_file(self, file: DenoiseInputFile) -> None:
        """Mark a single input frame as the active reference frame."""
        for f in self.star_files:
            f.is_reference = f is file or f.path == file.path
        self.reference_file = file

    def get_project_stem(self) -> str:
        """Return the base stem of the project file without extension."""
        if not self.projectFile:
            return "project"
        name = Path(self.projectFile).name
        if name.endswith(DENOISE_EXT):
            return name[:-len(DENOISE_EXT)]
        if name.endswith(".json"):
            return name[:-5]
        return Path(self.projectFile).stem

    def to_denoise_config(self) -> DenoiseConfig:
        """Construct a DenoiseConfig instance matching this project's current state."""
        ref = self.get_reference_file()
        base_path = Path(ref.path) if ref and ref.path else None

        homographies_dict: dict[Path, Any] = {}
        for k, v in self.homographies.items():
            homographies_dict[Path(k)] = copy.deepcopy(v)

        out_dir = self.get_output_dir()
        stem = self.get_project_stem()
        mask_p = Path(self.mask_path) if self.mask_path and not self.mask_invalidated else None
        if mask_p is None and not self.mask_invalidated and (out_dir / "mask.png").exists():
            mask_p = out_dir / "mask.png"

        # Writable engine destinations never come from serialized artifact refs.
        sky_stack_p = out_dir / "sky_stack.tif"
        ground_stack_p = out_dir / "ground_stack.tif"
        refined_mask_p = out_dir / "refined_mask.png"
        gradient_mask_p = out_dir / "gradient_mask.png"
        output_p = out_dir / f"{stem}.tif"

        return DenoiseConfig(
            star_images=[Path(f.path) for f in self.star_files if f.path],
            base_image=base_path,
            noise_images=[Path(f.path) for f in self.noise_files if f.path],
            output_path=output_p,
            sky_stack_path=sky_stack_p,
            ground_stack_path=ground_stack_p,
            mask_path=mask_p,
            mask_search_radius=self.mask_search_radius,
            mask_erosion_pixels=self.mask_erosion_pixels,
            mask_foliage_protection=self.mask_foliage_protection,
            refine_sky_mask=self.refine_sky_mask,
            auto_mask=self.auto_mask,
            auto_mask_model=self.auto_mask_model,
            auto_mask_path=self.auto_mask_path,
            export_refined_mask=self.export_refined_mask,
            refined_mask_path=refined_mask_p,
            export_gradient_mask=self.export_gradient_mask,
            gradient_mask_path=gradient_mask_p,
            taper_mask_edges=self.taper_mask_edges,
            mask_taper_pixels=self.mask_taper_pixels,
            enable_horizon_corrections=self.enable_horizon_corrections,
            denoise_horizon_band=self.denoise_horizon_band,
            horizon_denoise_radius=self.horizon_denoise_radius,
            horizon_denoise_eps=self.horizon_denoise_eps,
            horizon_denoise_strength=self.horizon_denoise_strength,
            horizon_color_denoise_strength=self.horizon_color_denoise_strength,
            horizon_value_denoise_strength=self.horizon_value_denoise_strength,
            horizon_blend_percent=self.horizon_blend_percent,
            horizon_blur_radius=self.horizon_blur_radius,
            stack_method=self.stack_method,
            sigma_clip_threshold=self.sigma_clip_threshold,
            sigma_clip_iterations=self.sigma_clip_iterations,
            homographies=homographies_dict,
            use_gpu=self.use_gpu,
        )

    @classmethod
    def ensure_default_project(cls, path: str = "projects/default.proj_denoise") -> DenoiseProject:
        """Create and persist the default starter denoise project file if absent."""
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    proj = jsonpickle.decode(f.read())
                    if isinstance(proj, DenoiseProject):
                        return proj
            except Exception:
                pass
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        default_proj = cls(projectFile=path)
        with open(path, "w+") as f:
            f.write(jsonpickle.encode(default_proj, indent=4))
        return default_proj
