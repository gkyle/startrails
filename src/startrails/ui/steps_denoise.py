"""Behavior and controls for Denoise mode Designer-authored step settings."""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional
from PySide6.QtCore import Qt, QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget

from startrails.lib.denoise.defaults import DENOISE_DEFAULTS, DEFAULT_MASK_BRUSH_RADIUS
from .steps import toggle_advanced_settings, update_gpu_checkbox
from .ui_step_denoise_sky import Ui_DenoiseSkySettings
from .ui_step_denoise_align import Ui_DenoiseAlignSettings
from .ui_step_denoise_stack import Ui_DenoiseStackSettings
from .ui_step_denoise_tune import Ui_DenoiseTuneSettings

if TYPE_CHECKING:
    from startrails.app import App
    from startrails.lib.file import DenoiseInputFile
    from startrails.lib.project_denoise import DenoiseProject


class DenoiseSkySettings(QWidget):
    """Step 1: Define Sky Region settings widget."""

    settings_changed = Signal()
    brush_radius_changed = Signal(int)
    clear_mask_requested = Signal()
    full_frame_requested = Signal()
    refine_mask_requested = Signal()
    mask_edit_toggled = Signal(bool)
    export_training_requested = Signal()
    contribute_requested = Signal()

    MODEL_MAP = {
        0: "nightstack",
        1: "segformer",
    }
    REV_MODEL_MAP = {v: k for k, v in MODEL_MAP.items()}

    def __init__(self, app: Optional[App] = None, parent: Optional[QWidget] = None, ui: Any = None):
        if isinstance(app, QWidget) and parent is None:
            app, parent = None, app
        if not isinstance(parent, QWidget) and parent is not None:
            app, parent = parent, app
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.app = app
        self.defaults = DENOISE_DEFAULTS

        self.ui = Ui_DenoiseSkySettings()
        self.ui.setupUi(self)

        # Synchronize brush slider and spinbox
        self.ui.brushSlider.valueChanged.connect(self._on_brush_slider_changed)
        self.ui.brushRadius.valueChanged.connect(self._on_brush_spin_changed)

        # Action and utility buttons
        self.ui.clearMask.clicked.connect(self.clear_mask_requested.emit)
        self.ui.fullFrameMask.clicked.connect(self.full_frame_requested.emit)
        self.ui.refineMask.clicked.connect(self.refine_mask_requested.emit)
        self.ui.showMaskOverlay.toggled.connect(self.mask_edit_toggled.emit)
        self.ui.training.clicked.connect(self.export_training_requested.emit)
        self.ui.contribute.clicked.connect(self.contribute_requested.emit)

        # Connect change signals
        self.ui.modelType.currentIndexChanged.connect(self._on_change)
        self.ui.searchRadius.valueChanged.connect(self._on_change)
        self.ui.erosionPixels.valueChanged.connect(self._on_change)

        self.reset()

    def _on_brush_slider_changed(self, val: int) -> None:
        with QSignalBlocker(self.ui.brushRadius):
            self.ui.brushRadius.setValue(val)
        self.brush_radius_changed.emit(val)

    def _on_brush_spin_changed(self, val: int) -> None:
        with QSignalBlocker(self.ui.brushSlider):
            self.ui.brushSlider.setValue(val)
        self.brush_radius_changed.emit(val)

    def _on_change(self, *_) -> None:
        self.sync_to_project()
        self.settings_changed.emit()

    def reset(self) -> None:
        with QSignalBlocker(self.ui.modelType):
            self.ui.modelType.setCurrentIndex(self.REV_MODEL_MAP[self.defaults.auto_mask_model])
        with QSignalBlocker(self.ui.searchRadius):
            self.ui.searchRadius.setValue(self.defaults.mask_search_radius or 0)
        with QSignalBlocker(self.ui.erosionPixels):
            self.ui.erosionPixels.setValue(self.defaults.mask_erosion_pixels)
        with QSignalBlocker(self.ui.showMaskOverlay):
            self.ui.showMaskOverlay.setChecked(False)
        with QSignalBlocker(self.ui.brushSlider):
            self.ui.brushSlider.setValue(DEFAULT_MASK_BRUSH_RADIUS)
        with QSignalBlocker(self.ui.brushRadius):
            self.ui.brushRadius.setValue(DEFAULT_MASK_BRUSH_RADIUS)
        self.ui.error.clear()
        self.ui.error.hide()
        self.set_corrections_enabled(False)
        self.set_from_project()

    def set_corrections_enabled(self, enabled: bool) -> None:
        """Enable or disable sky training contribution/export buttons."""
        self.ui.contribute.setEnabled(enabled)
        self.ui.training.setEnabled(enabled)
        export_tip = (
            "Export manual sky mask corrections to disk"
            if enabled
            else "Requires manual sky mask brush corrections."
        )
        contrib_tip = (
            "Contribute manual sky mask corrections to help improve sky models"
            if enabled
            else "Requires manual sky mask brush corrections."
        )
        self.ui.training.setToolTip(export_tip)
        self.ui.contribute.setToolTip(contrib_tip)

    def values(self) -> Dict[str, Any]:
        return {
            "auto_mask_model": self.MODEL_MAP.get(self.ui.modelType.currentIndex(), self.defaults.auto_mask_model),
            "mask_search_radius": self.ui.searchRadius.value() or None,
            "mask_erosion_pixels": self.ui.erosionPixels.value(),
        }

    def set_from_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj: DenoiseProject = self.app.project
        with QSignalBlocker(self.ui.erosionPixels):
            self.ui.erosionPixels.setValue(int(proj.mask_erosion_pixels))
        radius = proj.mask_search_radius
        with QSignalBlocker(self.ui.searchRadius):
            self.ui.searchRadius.setValue(int(radius) if radius else 0)
        model = proj.auto_mask_model
        if model in self.REV_MODEL_MAP:
            with QSignalBlocker(self.ui.modelType):
                self.ui.modelType.setCurrentIndex(self.REV_MODEL_MAP[model])
        self.set_corrections_enabled(getattr(proj, "has_manual_sky_corrections", False))

    def sync_to_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        vals = self.values()
        for k, v in vals.items():
            setattr(proj, k, v)

    def refresh_inputs(self, has_manual_corrections: bool = False) -> None:
        has_stars = False
        if self.app and hasattr(self.app, "workflow") and hasattr(self.app.workflow, "get_star_files"):
            has_stars = bool(self.app.workflow.get_star_files())
        self.ui.detect.setEnabled(has_stars)
        self.ui.refineMask.setEnabled(has_stars)
        self.set_corrections_enabled(has_manual_corrections)


class DenoiseAlignSettings(QWidget):
    """Step 2: Align Stars settings widget."""

    settings_changed = Signal()


    def __init__(self, app: Optional[App] = None, parent: Optional[QWidget] = None, ui: Any = None):
        if isinstance(app, QWidget) and parent is None:
            app, parent = None, app
        if not isinstance(parent, QWidget) and parent is not None:
            app, parent = parent, app
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.app = app
        self.defaults = DENOISE_DEFAULTS

        self.ui = Ui_DenoiseAlignSettings()
        self.ui.setupUi(self)

        if getattr(self.ui, "advancedToggle", None) is not None:
            self.ui.advancedToggle.toggled.connect(self._toggle_advanced)
            self.ui.advancedToggle.setChecked(False)
            self._toggle_advanced(False)

        if hasattr(self.ui, "useGPU"):
            self.ui.useGPU.toggled.connect(self._on_change)

        self.reset()

    def _toggle_advanced(self, checked: bool) -> None:
        toggle_advanced_settings(self, checked)

    def _on_change(self, *_) -> None:
        self.sync_to_project()
        self.settings_changed.emit()

    def reset(self) -> None:
        if hasattr(self.ui, "useGPU"):
            with QSignalBlocker(self.ui.useGPU):
                self.ui.useGPU.setChecked(self.defaults.use_gpu)
        self.ui.referenceFile.setText("None")
        self.ui.alignStatus.setText("Homographies: 0 computed")
        self.ui.error.clear()
        self.ui.error.hide()
        self.set_from_project()
        update_gpu_checkbox(self.ui.useGPU, self.app)

    def set_reference_file(self, file: Optional[DenoiseInputFile]) -> None:
        text = file.basename if file is not None and file.basename else ("Reference Frame" if file else "None")
        self.ui.referenceFile.setText(text)

    def values(self) -> Dict[str, Any]:
        return {
            "use_gpu": self.ui.useGPU.isChecked() if hasattr(self.ui, "useGPU") else self.defaults.use_gpu,
        }

    def set_from_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        with QSignalBlocker(self.ui.useGPU):
            self.ui.useGPU.setChecked(bool(proj.use_gpu))
        update_gpu_checkbox(self.ui.useGPU, self.app)
        ref = proj.get_reference_file() if hasattr(proj, "get_reference_file") else None
        self.set_reference_file(ref)
        aligned_count = len(getattr(proj, "homographies", {}))
        total_count = len(getattr(proj, "star_files", []))
        if aligned_count > 0:
            self.ui.alignStatus.setText(f"Homographies: {aligned_count} computed")
        elif total_count > 0:
            self.ui.alignStatus.setText(f"Ready to align {total_count} frames")
        else:
            self.ui.alignStatus.setText("Homographies: 0 computed")

    def sync_to_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        proj.use_gpu = self.ui.useGPU.isChecked()

    def refresh_inputs(self, ready: bool = False) -> None:
        update_gpu_checkbox(self.ui.useGPU, self.app)
        has_stars = False
        if self.app and hasattr(self.app, "workflow") and hasattr(self.app.workflow, "get_star_files"):
            has_stars = bool(self.app.workflow.get_star_files())
        self.ui.run.setEnabled(has_stars and ready)
        if self.app and hasattr(self.app, "workflow") and hasattr(self.app.workflow, "get_reference_file"):
            self.set_reference_file(self.app.workflow.get_reference_file())


class DenoiseStackSettings(QWidget):
    """Step 3: Stack Foreground and Background settings widget."""

    settings_changed = Signal()

    METHOD_MAP = {0: "sigma_clipped", 1: "mean"}
    REV_METHOD_MAP = {v: k for k, v in METHOD_MAP.items()}

    def __init__(self, app: Optional[App] = None, parent: Optional[QWidget] = None, ui: Any = None):
        if isinstance(app, QWidget) and parent is None:
            app, parent = None, app
        if not isinstance(parent, QWidget) and parent is not None:
            app, parent = parent, app
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.app = app
        self.defaults = DENOISE_DEFAULTS

        self.ui = Ui_DenoiseStackSettings()
        self.ui.setupUi(self)

        if getattr(self.ui, "advancedToggle", None) is not None:
            self.ui.advancedToggle.toggled.connect(self._toggle_advanced)
            self.ui.advancedToggle.setChecked(False)
            self._toggle_advanced(False)

        self.ui.method.currentIndexChanged.connect(self._on_change)
        self.ui.sigmaThreshold.valueChanged.connect(self._on_change)
        self.ui.sigmaIterations.valueChanged.connect(self._on_change)
        self.ui.compressIntermediateTiffs.toggled.connect(self._on_change)
        self.ui.useGPU.toggled.connect(self._on_change)

        self.reset()

    def _toggle_advanced(self, checked: bool) -> None:
        toggle_advanced_settings(self, checked)

    def _on_change(self, *_) -> None:
        self.sync_to_project()
        self.settings_changed.emit()

    def reset(self) -> None:
        with QSignalBlocker(self.ui.method):
            self.ui.method.setCurrentIndex(self.REV_METHOD_MAP[self.defaults.stack_method])
        with QSignalBlocker(self.ui.sigmaThreshold):
            self.ui.sigmaThreshold.setValue(self.defaults.sigma_clip_threshold)
        with QSignalBlocker(self.ui.sigmaIterations):
            self.ui.sigmaIterations.setValue(self.defaults.sigma_clip_iterations)
        with QSignalBlocker(self.ui.compressIntermediateTiffs):
            self.ui.compressIntermediateTiffs.setChecked(self.defaults.compress_intermediate_tiffs)
        with QSignalBlocker(self.ui.useGPU):
            self.ui.useGPU.setChecked(self.defaults.use_gpu)
        self.ui.outputFileName.setText("Output: project.tif")
        self.ui.stackStatus.setText("Base stacks: Not generated")
        self.ui.error.clear()
        self.ui.error.hide()
        self.set_from_project()
        update_gpu_checkbox(self.ui.useGPU, self.app)

    def values(self) -> Dict[str, Any]:
        return {
            "stack_method": self.METHOD_MAP.get(self.ui.method.currentIndex(), self.defaults.stack_method),
            "sigma_clip_threshold": self.ui.sigmaThreshold.value(),
            "sigma_clip_iterations": self.ui.sigmaIterations.value(),
            "compress_intermediate_tiffs": self.ui.compressIntermediateTiffs.isChecked(),
            "use_gpu": self.ui.useGPU.isChecked(),
        }

    def set_from_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        method_name = proj.stack_method
        if method_name == "median":
            method_name = proj.stack_method = "mean"
        if method_name not in self.REV_METHOD_MAP:
            method_name = proj.stack_method = self.defaults.stack_method
        with QSignalBlocker(self.ui.method):
            self.ui.method.setCurrentIndex(self.REV_METHOD_MAP[method_name])
        with QSignalBlocker(self.ui.sigmaThreshold):
            self.ui.sigmaThreshold.setValue(float(proj.sigma_clip_threshold))
        with QSignalBlocker(self.ui.sigmaIterations):
            self.ui.sigmaIterations.setValue(int(proj.sigma_clip_iterations))
        with QSignalBlocker(self.ui.compressIntermediateTiffs):
            self.ui.compressIntermediateTiffs.setChecked(proj.compress_intermediate_tiffs)
        with QSignalBlocker(self.ui.useGPU):
            self.ui.useGPU.setChecked(bool(proj.use_gpu))
        update_gpu_checkbox(self.ui.useGPU, self.app)
        stem = "project"
        if hasattr(proj, "get_project_stem"):
            stem = proj.get_project_stem()
        elif hasattr(proj, "projectFile") and proj.projectFile:
            pf = Path(proj.projectFile)
            name = pf.name
            if name.endswith(".proj_denoise"):
                stem = name[:-len(".proj_denoise")]
            elif name.endswith(".json"):
                stem = name[:-5]
            else:
                stem = pf.stem
        out_name = getattr(proj, "output_path", None)
        if not out_name:
            out_name = f"{stem}.tif"
        elif hasattr(out_name, "name"):
            out_name = out_name.name
        elif isinstance(out_name, str):
            out_name = out_name.split("/")[-1].split("\\")[-1]
        self.ui.outputFileName.setText(f"Output: {out_name}")

    def sync_to_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        vals = self.values()
        proj.stack_method = vals["stack_method"]
        proj.sigma_clip_threshold = vals["sigma_clip_threshold"]
        proj.sigma_clip_iterations = vals["sigma_clip_iterations"]
        proj.compress_intermediate_tiffs = vals["compress_intermediate_tiffs"]
        proj.use_gpu = vals["use_gpu"]

    def refresh_inputs(self, ready: bool = False) -> None:
        update_gpu_checkbox(self.ui.useGPU, self.app)
        self.ui.run.setEnabled(ready)
        if ready:
            self.ui.stackStatus.setText("Ready to stack (alignment runs automatically if needed)")
        else:
            self.ui.stackStatus.setText("Requires star images and a sky mask")


class DenoiseTuneSettings(QWidget):
    """Step 4: Interactive Horizon Tuning settings widget."""

    settings_changed = Signal()
    gradient_mask_toggled = Signal(bool)

    def __init__(self, app: Optional[App] = None, parent: Optional[QWidget] = None, ui: Any = None):
        if isinstance(app, QWidget) and parent is None:
            app, parent = None, app
        if not isinstance(parent, QWidget) and parent is not None:
            app, parent = parent, app
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.app = app
        self.defaults = DENOISE_DEFAULTS

        self.ui = Ui_DenoiseTuneSettings()
        self.ui.setupUi(self)

        # Synchronize Sliders and DoubleSpinBoxes
        self.ui.colorDenoiseSlider.valueChanged.connect(self._on_color_slider_changed)
        self.ui.colorStrength.valueChanged.connect(self._on_color_spin_changed)

        self.ui.valueDenoiseSlider.valueChanged.connect(self._on_value_slider_changed)
        self.ui.valueStrength.valueChanged.connect(self._on_value_spin_changed)

        self.ui.blendSlider.valueChanged.connect(self._on_blend_slider_changed)
        self.ui.blendPercent.valueChanged.connect(self._on_blend_spin_changed)

        self.ui.blurSlider.valueChanged.connect(self._on_blur_slider_changed)
        self.ui.blurRadius.valueChanged.connect(self._on_blur_spin_changed)

        # Horizon corrections toggle updates sub-controls
        self.ui.enableCorrections.toggled.connect(self._on_enable_corrections_toggled)
        self.ui.showGradientMask.toggled.connect(self.gradient_mask_toggled.emit)

        self.reset()

    def _on_color_slider_changed(self, val: int) -> None:
        with QSignalBlocker(self.ui.colorStrength):
            self.ui.colorStrength.setValue(val / 100.0)
        self._on_change()

    def _on_color_spin_changed(self, val: float) -> None:
        with QSignalBlocker(self.ui.colorDenoiseSlider):
            self.ui.colorDenoiseSlider.setValue(int(round(val * 100)))
        self._on_change()

    def _on_value_slider_changed(self, val: int) -> None:
        with QSignalBlocker(self.ui.valueStrength):
            self.ui.valueStrength.setValue(val / 100.0)
        self._on_change()

    def _on_value_spin_changed(self, val: float) -> None:
        with QSignalBlocker(self.ui.valueDenoiseSlider):
            self.ui.valueDenoiseSlider.setValue(int(round(val * 100)))
        self._on_change()

    def _on_blend_slider_changed(self, val: int) -> None:
        with QSignalBlocker(self.ui.blendPercent):
            self.ui.blendPercent.setValue(float(val))
        self._on_change()

    def _on_blend_spin_changed(self, val: float) -> None:
        with QSignalBlocker(self.ui.blendSlider):
            self.ui.blendSlider.setValue(int(round(val)))
        self._on_change()

    def _on_blur_slider_changed(self, val: int) -> None:
        with QSignalBlocker(self.ui.blurRadius):
            self.ui.blurRadius.setValue(float(val))
        self._on_change()

    def _on_blur_spin_changed(self, val: float) -> None:
        with QSignalBlocker(self.ui.blurSlider):
            self.ui.blurSlider.setValue(int(round(val)))
        self._on_change()

    def _on_enable_corrections_toggled(self, checked: bool) -> None:
        controls = (
            self.ui.colorDenoiseSlider, self.ui.colorStrength,
            self.ui.valueDenoiseSlider, self.ui.valueStrength,
            self.ui.blendSlider, self.ui.blendPercent,
            self.ui.blurSlider, self.ui.blurRadius,
        )
        for w in controls:
            w.setEnabled(checked)
        self._on_change()

    def _on_change(self, *_) -> None:
        self.sync_to_project()
        self.settings_changed.emit()

    def reset(self) -> None:
        with QSignalBlocker(self.ui.enableCorrections):
            self.ui.enableCorrections.setChecked(self.defaults.enable_horizon_corrections)
        with QSignalBlocker(self.ui.showGradientMask):
            self.ui.showGradientMask.setChecked(False)
        with QSignalBlocker(self.ui.colorDenoiseSlider):
            self.ui.colorDenoiseSlider.setValue(int(round(self.defaults.horizon_color_denoise_strength * 100)))
        with QSignalBlocker(self.ui.colorStrength):
            self.ui.colorStrength.setValue(self.defaults.horizon_color_denoise_strength)
        with QSignalBlocker(self.ui.valueDenoiseSlider):
            self.ui.valueDenoiseSlider.setValue(int(round(self.defaults.horizon_value_denoise_strength * 100)))
        with QSignalBlocker(self.ui.valueStrength):
            self.ui.valueStrength.setValue(self.defaults.horizon_value_denoise_strength)
        with QSignalBlocker(self.ui.blendSlider):
            self.ui.blendSlider.setValue(int(round(self.defaults.horizon_blend_percent)))
        with QSignalBlocker(self.ui.blendPercent):
            self.ui.blendPercent.setValue(self.defaults.horizon_blend_percent)
        with QSignalBlocker(self.ui.blurSlider):
            self.ui.blurSlider.setValue(int(round(self.defaults.horizon_blur_radius)))
        with QSignalBlocker(self.ui.blurRadius):
            self.ui.blurRadius.setValue(self.defaults.horizon_blur_radius)
        self.ui.tuneStatus.setText("Requires base stacks")
        self.ui.error.clear()
        self.ui.error.hide()
        self.set_from_project()

    def values(self) -> Dict[str, Any]:
        return {
            "enable_horizon_corrections": self.ui.enableCorrections.isChecked(),
            "denoise_horizon_band": self.app.project.denoise_horizon_band if self.app else self.defaults.denoise_horizon_band,
            "horizon_blend_percent": self.ui.blendPercent.value(),
            "horizon_blur_radius": self.ui.blurRadius.value(),
            "horizon_denoise_radius": self.app.project.horizon_denoise_radius if self.app else self.defaults.horizon_denoise_radius,
            "horizon_denoise_strength": self.app.project.horizon_denoise_strength if self.app else self.defaults.horizon_denoise_strength,
            "horizon_color_denoise_strength": self.ui.colorStrength.value(),
            "horizon_value_denoise_strength": self.ui.valueStrength.value(),
        }

    def set_from_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        with QSignalBlocker(self.ui.enableCorrections):
            self.ui.enableCorrections.setChecked(bool(proj.enable_horizon_corrections))

        blend = float(proj.horizon_blend_percent)
        with QSignalBlocker(self.ui.blendPercent):
            self.ui.blendPercent.setValue(blend)
        with QSignalBlocker(self.ui.blendSlider):
            self.ui.blendSlider.setValue(int(round(blend)))

        blur = float(proj.horizon_blur_radius)
        with QSignalBlocker(self.ui.blurRadius):
            self.ui.blurRadius.setValue(blur)
        with QSignalBlocker(self.ui.blurSlider):
            self.ui.blurSlider.setValue(int(round(blur)))

        color_str = float(proj.horizon_color_denoise_strength)
        with QSignalBlocker(self.ui.colorStrength):
            self.ui.colorStrength.setValue(color_str)
        with QSignalBlocker(self.ui.colorDenoiseSlider):
            self.ui.colorDenoiseSlider.setValue(int(round(color_str * 100)))

        val_str = float(proj.horizon_value_denoise_strength)
        with QSignalBlocker(self.ui.valueStrength):
            self.ui.valueStrength.setValue(val_str)
        with QSignalBlocker(self.ui.valueDenoiseSlider):
            self.ui.valueDenoiseSlider.setValue(int(round(val_str * 100)))

    def sync_to_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        vals = self.values()
        for k, v in vals.items():
            setattr(proj, k, v)

    def refresh_inputs(self, ready: bool = False) -> None:
        if hasattr(self.ui, "run"):
            self.ui.run.setEnabled(ready)
        if ready:
            self.ui.tuneStatus.setText("Stacks ready for composite tuning")
        else:
            self.ui.tuneStatus.setText("Requires stacked sky and ground frames")

