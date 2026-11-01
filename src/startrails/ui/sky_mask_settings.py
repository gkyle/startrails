"""Reusable Step 1: Define Sky Region settings widget shared between Denoise and Finish modes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional
from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget

from startrails.lib.denoise.defaults import DENOISE_DEFAULTS, DEFAULT_MASK_BRUSH_RADIUS
from .ui_step_denoise_sky import Ui_DenoiseSkySettings

if TYPE_CHECKING:
    from startrails.app import App


class SkyMaskSettings(QWidget):
    """Step 1: Define Sky Region settings widget for neural detection, refinement, and brush overlay."""

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
            self.ui.modelType.setCurrentIndex(self.REV_MODEL_MAP[DENOISE_DEFAULTS.auto_mask_model])
        with QSignalBlocker(self.ui.searchRadius):
            self.ui.searchRadius.setValue(DENOISE_DEFAULTS.mask_search_radius or 0)
        with QSignalBlocker(self.ui.erosionPixels):
            self.ui.erosionPixels.setValue(DENOISE_DEFAULTS.mask_erosion_pixels)
        with QSignalBlocker(self.ui.showMaskOverlay):
            self.ui.showMaskOverlay.setChecked(False)
        with QSignalBlocker(self.ui.brushSlider):
            self.ui.brushSlider.setValue(DEFAULT_MASK_BRUSH_RADIUS)
        with QSignalBlocker(self.ui.brushRadius):
            self.ui.brushRadius.setValue(DEFAULT_MASK_BRUSH_RADIUS)
        self.ui.error.clear()
        self.ui.error.hide()
        self.set_from_project()

    def set_corrections_enabled(self, enabled: bool) -> None:
        """Backward compatibility no-op; corrections buttons moved to DenoiseExportSettings."""
        if hasattr(self.ui, "contribute"):
            self.ui.contribute.setEnabled(enabled)
        if hasattr(self.ui, "training"):
            self.ui.training.setEnabled(enabled)

    def values(self) -> Dict[str, Any]:
        project = self.app.project if self.app else DENOISE_DEFAULTS
        return {
            "auto_mask_model": self.MODEL_MAP[self.ui.modelType.currentIndex()],
            "auto_mask_path": project.auto_mask_path,
            "mask_foliage_protection": project.mask_foliage_protection,
            "mask_search_radius": self.ui.searchRadius.value() or None,
            "mask_erosion_pixels": self.ui.erosionPixels.value(),
        }

    def set_from_project(self, project: Optional[Any] = None) -> None:
        proj = project or (getattr(self.app, "project", None) if self.app else None)
        if proj is None:
            return
        if hasattr(proj, "mask_erosion_pixels"):
            with QSignalBlocker(self.ui.erosionPixels):
                self.ui.erosionPixels.setValue(int(proj.mask_erosion_pixels))
        if hasattr(proj, "mask_search_radius"):
            radius = proj.mask_search_radius
            with QSignalBlocker(self.ui.searchRadius):
                self.ui.searchRadius.setValue(int(radius) if radius else 0)
        if hasattr(proj, "auto_mask_model"):
            model = proj.auto_mask_model
            if model in self.REV_MODEL_MAP:
                with QSignalBlocker(self.ui.modelType):
                    self.ui.modelType.setCurrentIndex(self.REV_MODEL_MAP[model])

    def sync_to_project(self, project: Optional[Any] = None) -> None:
        proj = project or (getattr(self.app, "project", None) if self.app else None)
        if proj is None:
            return
        vals = self.values()
        for k, v in vals.items():
            if hasattr(proj, k):
                setattr(proj, k, v)

    def refresh_inputs(self, *, has_source: bool) -> None:
        self.ui.detect.setEnabled(has_source)
        self.ui.refineMask.setEnabled(has_source)


__all__ = ["SkyMaskSettings"]
