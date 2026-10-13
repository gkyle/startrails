"""Project model and state persistence for Denoise mode (.proj_denoise)."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import jsonpickle

from startrails.lib.file import DenoiseInputFile, Unpickle
from startrails.lib.denoise.config import DenoiseConfig


class DenoiseProject(Unpickle):
    """Project state model for the astrophotography Denoise workflow."""

    def __init__(
        self,
        projectFile: str = "projects/default.proj_denoise",
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

    def to_denoise_config(self) -> DenoiseConfig:
        """Construct a DenoiseConfig instance matching this project's current state."""
        ref = self.get_reference_file()
        base_path = Path(ref.path) if ref and ref.path else None

        homographies_dict: dict[Path, Any] = {}
        for k, v in self.homographies.items():
            homographies_dict[Path(k)] = v

        return DenoiseConfig(
            star_images=[Path(f.path) for f in self.star_files if f.path],
            base_image=base_path,
            noise_images=[Path(f.path) for f in self.noise_files if f.path],
            vignetting_images=[Path(f.path) for f in self.vignetting_files if f.path],
            output_path=Path(self.output_path) if self.output_path else None,
            sky_stack_path=Path(self.sky_stack_path) if self.sky_stack_path else None,
            ground_stack_path=Path(self.ground_stack_path) if self.ground_stack_path else None,
            mask_path=Path(self.mask_path) if self.mask_path else None,
            mask_search_radius=self.mask_search_radius,
            mask_erosion_pixels=self.mask_erosion_pixels,
            mask_foliage_protection=self.mask_foliage_protection,
            refine_sky_mask=self.refine_sky_mask,
            auto_mask=self.auto_mask,
            auto_mask_model=self.auto_mask_model,
            auto_mask_path=self.auto_mask_path,
            export_refined_mask=self.export_refined_mask,
            refined_mask_path=Path(self.refined_mask_path) if self.refined_mask_path else None,
            export_gradient_mask=self.export_gradient_mask,
            gradient_mask_path=Path(self.gradient_mask_path) if self.gradient_mask_path else None,
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
