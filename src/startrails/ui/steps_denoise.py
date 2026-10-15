"""Behavior and controls for Denoise mode Designer-authored step settings."""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional
from PySide6.QtCore import Qt, QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget

from startrails.lib.denoise.config import DenoiseSettings
from .steps import toggle_advanced_settings
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

    MODEL_MAP = {
        0: "nightstack",
        1: "segformer",
        2: "heuristic",
        3: "auto",
    }
    REV_MODEL_MAP = {v: k for k, v in MODEL_MAP.items()}

    def __init__(self, app: Optional[App] = None, parent: Optional[QWidget] = None, ui: Any = None):
        if isinstance(app, QWidget) and parent is None:
            app, parent = None, app
        if not isinstance(parent, QWidget) and parent is not None:
            app, parent = parent, app
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.app = app
        self.defaults = DenoiseSettings()

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
            self.ui.modelType.setCurrentIndex(0)
        with QSignalBlocker(self.ui.searchRadius):
            self.ui.searchRadius.setValue(0)
        with QSignalBlocker(self.ui.erosionPixels):
            self.ui.erosionPixels.setValue(self.defaults.mask_erosion_pixels)
        with QSignalBlocker(self.ui.showMaskOverlay):
            self.ui.showMaskOverlay.setChecked(False)
        with QSignalBlocker(self.ui.brushSlider):
            self.ui.brushSlider.setValue(25)
        with QSignalBlocker(self.ui.brushRadius):
            self.ui.brushRadius.setValue(25)
        self.ui.error.clear()
        self.ui.error.hide()
        self.set_from_project()

    def values(self) -> Dict[str, Any]:
        return {
            "auto_mask_model": self.MODEL_MAP.get(self.ui.modelType.currentIndex(), "nightstack"),
            "mask_search_radius": self.ui.searchRadius.value() or None,
            "mask_erosion_pixels": self.ui.erosionPixels.value(),
        }

    def set_from_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj: DenoiseProject = self.app.project
        if not hasattr(proj, "auto_mask_model"):
            return
        with QSignalBlocker(self.ui.erosionPixels):
            self.ui.erosionPixels.setValue(int(getattr(proj, "mask_erosion_pixels", self.defaults.mask_erosion_pixels)))
        radius = getattr(proj, "mask_search_radius", None)
        with QSignalBlocker(self.ui.searchRadius):
            self.ui.searchRadius.setValue(int(radius) if radius else 0)
        model = getattr(proj, "auto_mask_model", None)
        if model in self.REV_MODEL_MAP:
            with QSignalBlocker(self.ui.modelType):
                self.ui.modelType.setCurrentIndex(self.REV_MODEL_MAP[model])

    def sync_to_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        if not hasattr(proj, "auto_mask_model"):
            return
        vals = self.values()
        for k, v in vals.items():
            setattr(proj, k, v)

    def refresh_inputs(self) -> None:
        has_stars = False
        if self.app and hasattr(self.app, "workflow") and hasattr(self.app.workflow, "get_star_files"):
            has_stars = bool(self.app.workflow.get_star_files())
        self.ui.detect.setEnabled(has_stars)
        self.ui.refineMask.setEnabled(has_stars)


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
        self.defaults = DenoiseSettings()

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
                self.ui.useGPU.setChecked(True)
        self.ui.referenceFile.setText("None")
        self.ui.alignStatus.setText("Homographies: 0 computed")
        self.ui.error.clear()
        self.ui.error.hide()
        self.set_from_project()

    def set_reference_file(self, file: Optional[DenoiseInputFile]) -> None:
        text = file.basename if file is not None and file.basename else ("Reference Frame" if file else "None")
        self.ui.referenceFile.setText(text)

    def values(self) -> Dict[str, Any]:
        return {
            "use_gpu": self.ui.useGPU.isChecked() if hasattr(self.ui, "useGPU") else True,
        }

    def set_from_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        if not hasattr(proj, "use_gpu"):
            return
        with QSignalBlocker(self.ui.useGPU):
            self.ui.useGPU.setChecked(bool(getattr(proj, "use_gpu", True)))
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
        if hasattr(proj, "use_gpu"):
            proj.use_gpu = self.ui.useGPU.isChecked()

    def refresh_inputs(self, ready: bool = False) -> None:
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
        self.defaults = DenoiseSettings()

        self.ui = Ui_DenoiseStackSettings()
        self.ui.setupUi(self)

        if getattr(self.ui, "advancedToggle", None) is not None:
            self.ui.advancedToggle.toggled.connect(self._toggle_advanced)
            self.ui.advancedToggle.setChecked(False)
            self._toggle_advanced(False)

        self.ui.method.currentIndexChanged.connect(self._on_change)
        self.ui.sigmaThreshold.valueChanged.connect(self._on_change)
        self.ui.sigmaIterations.valueChanged.connect(self._on_change)
        self.ui.useGPU.toggled.connect(self._on_change)

        self.reset()

    def _toggle_advanced(self, checked: bool) -> None:
        toggle_advanced_settings(self, checked)

    def _on_change(self, *_) -> None:
        self.sync_to_project()
        self.settings_changed.emit()

    def reset(self) -> None:
        with QSignalBlocker(self.ui.method):
            self.ui.method.setCurrentIndex(0)
        with QSignalBlocker(self.ui.sigmaThreshold):
            self.ui.sigmaThreshold.setValue(self.defaults.sigma_clip_threshold)
        with QSignalBlocker(self.ui.sigmaIterations):
            self.ui.sigmaIterations.setValue(self.defaults.sigma_clip_iterations)
        with QSignalBlocker(self.ui.useGPU):
            self.ui.useGPU.setChecked(True)
        self.ui.outputFileName.setText("Output: project.tif")
        self.ui.stackStatus.setText("Base stacks: Not generated")
        self.ui.error.clear()
        self.ui.error.hide()
        self.set_from_project()

    def values(self) -> Dict[str, Any]:
        return {
            "stack_method": self.METHOD_MAP.get(self.ui.method.currentIndex(), "sigma_clipped"),
            "sigma_clip_threshold": self.ui.sigmaThreshold.value(),
            "sigma_clip_iterations": self.ui.sigmaIterations.value(),
            "use_gpu": self.ui.useGPU.isChecked(),
        }

    def set_from_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        if not hasattr(proj, "stack_method"):
            return
        method_name = getattr(proj, "stack_method", "sigma_clipped")
        if method_name == "median":
            method_name = proj.stack_method = "mean"
        if method_name not in self.REV_METHOD_MAP:
            method_name = proj.stack_method = "sigma_clipped"
        with QSignalBlocker(self.ui.method):
            self.ui.method.setCurrentIndex(self.REV_METHOD_MAP.get(method_name, 0))
        with QSignalBlocker(self.ui.sigmaThreshold):
            self.ui.sigmaThreshold.setValue(float(getattr(proj, "sigma_clip_threshold", self.defaults.sigma_clip_threshold)))
        with QSignalBlocker(self.ui.sigmaIterations):
            self.ui.sigmaIterations.setValue(int(getattr(proj, "sigma_clip_iterations", self.defaults.sigma_clip_iterations)))
        with QSignalBlocker(self.ui.useGPU):
            self.ui.useGPU.setChecked(bool(getattr(proj, "use_gpu", True)))
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
        if not hasattr(proj, "stack_method"):
            return
        vals = self.values()
        proj.stack_method = vals["stack_method"]
        proj.sigma_clip_threshold = vals["sigma_clip_threshold"]
        proj.sigma_clip_iterations = vals["sigma_clip_iterations"]
        proj.use_gpu = vals["use_gpu"]

    def refresh_inputs(self, ready: bool = False) -> None:
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
        self.defaults = DenoiseSettings()

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
            self.ui.enableCorrections.setChecked(True)
        with QSignalBlocker(self.ui.showGradientMask):
            self.ui.showGradientMask.setChecked(False)
        with QSignalBlocker(self.ui.colorDenoiseSlider):
            self.ui.colorDenoiseSlider.setValue(100)
        with QSignalBlocker(self.ui.colorStrength):
            self.ui.colorStrength.setValue(1.0)
        with QSignalBlocker(self.ui.valueDenoiseSlider):
            self.ui.valueDenoiseSlider.setValue(20)
        with QSignalBlocker(self.ui.valueStrength):
            self.ui.valueStrength.setValue(0.2)
        with QSignalBlocker(self.ui.blendSlider):
            self.ui.blendSlider.setValue(60)
        with QSignalBlocker(self.ui.blendPercent):
            self.ui.blendPercent.setValue(60.0)
        with QSignalBlocker(self.ui.blurSlider):
            self.ui.blurSlider.setValue(2)
        with QSignalBlocker(self.ui.blurRadius):
            self.ui.blurRadius.setValue(2.0)
        self.ui.tuneStatus.setText("Requires base stacks")
        self.ui.error.clear()
        self.ui.error.hide()
        self.set_from_project()

    def values(self) -> Dict[str, Any]:
        return {
            "enable_horizon_corrections": self.ui.enableCorrections.isChecked(),
            "denoise_horizon_band": getattr(self.app.project, "denoise_horizon_band", self.defaults.denoise_horizon_band) if self.app else self.defaults.denoise_horizon_band,
            "horizon_blend_percent": self.ui.blendPercent.value(),
            "horizon_blur_radius": self.ui.blurRadius.value(),
            "horizon_denoise_radius": getattr(self.app.project, "horizon_denoise_radius", self.defaults.horizon_denoise_radius) if self.app else self.defaults.horizon_denoise_radius,
            "horizon_denoise_strength": getattr(self.app.project, "horizon_denoise_strength", self.defaults.horizon_denoise_strength) if self.app else self.defaults.horizon_denoise_strength,
            "horizon_color_denoise_strength": self.ui.colorStrength.value(),
            "horizon_value_denoise_strength": self.ui.valueStrength.value(),
        }

    def set_from_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        if not hasattr(proj, "enable_horizon_corrections"):
            return
        with QSignalBlocker(self.ui.enableCorrections):
            self.ui.enableCorrections.setChecked(bool(getattr(proj, "enable_horizon_corrections", True)))

        blend = float(getattr(proj, "horizon_blend_percent", 60.0))
        with QSignalBlocker(self.ui.blendPercent):
            self.ui.blendPercent.setValue(blend)
        with QSignalBlocker(self.ui.blendSlider):
            self.ui.blendSlider.setValue(int(round(blend)))

        blur = float(getattr(proj, "horizon_blur_radius", 2.0))
        with QSignalBlocker(self.ui.blurRadius):
            self.ui.blurRadius.setValue(blur)
        with QSignalBlocker(self.ui.blurSlider):
            self.ui.blurSlider.setValue(int(round(blur)))

        color_str = float(getattr(proj, "horizon_color_denoise_strength", 1.0))
        with QSignalBlocker(self.ui.colorStrength):
            self.ui.colorStrength.setValue(color_str)
        with QSignalBlocker(self.ui.colorDenoiseSlider):
            self.ui.colorDenoiseSlider.setValue(int(round(color_str * 100)))

        val_str = float(getattr(proj, "horizon_value_denoise_strength", 0.2))
        with QSignalBlocker(self.ui.valueStrength):
            self.ui.valueStrength.setValue(val_str)
        with QSignalBlocker(self.ui.valueDenoiseSlider):
            self.ui.valueDenoiseSlider.setValue(int(round(val_str * 100)))

    def sync_to_project(self) -> None:
        if not self.app or not hasattr(self.app, "project"):
            return
        proj = self.app.project
        if not hasattr(proj, "enable_horizon_corrections"):
            return
        vals = self.values()
        for k, v in vals.items():
            setattr(proj, k, v)

    def refresh_inputs(self, ready: bool = False) -> None:
        self.ui.run.setEnabled(ready)
        if ready:
            self.ui.tuneStatus.setText("Stacks ready for composite tuning")
        else:
            self.ui.tuneStatus.setText("Requires stacked sky and ground frames")

DenoiseSkySettings.settingsChanged = property(lambda self: self.settings_changed)

DenoiseAlignSettings.settingsChanged = property(lambda self: self.settings_changed)

DenoiseStackSettings.settingsChanged = property(lambda self: self.settings_changed)

DenoiseTuneSettings.settingsChanged = property(lambda self: self.settings_changed)

DenoiseSkySettings.brushRadiusChanged = property(lambda self: self.brush_radius_changed)

DenoiseSkySettings.clearMaskRequested = property(lambda self: self.clear_mask_requested)

DenoiseSkySettings.fullFrameRequested = property(lambda self: self.full_frame_requested)

DenoiseSkySettings.refineMaskRequested = property(lambda self: self.refine_mask_requested)

DenoiseSkySettings.maskEditToggled = property(lambda self: self.mask_edit_toggled)

DenoiseTuneSettings.gradientMaskToggled = property(lambda self: self.gradient_mask_toggled)
