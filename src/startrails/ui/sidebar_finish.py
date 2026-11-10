"""Composition of the Finish mode sidebar shell and step cards."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from startrails.lib.finish.defaults import (
    DEFAULT_BLEND_MODE,
    DEFAULT_STAR_AMOUNT_PERCENT,
    DEFAULT_STAR_THRESHOLD_PERCENT,
    ROLE_DENOISE_ENDPOINT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_SKY_MASK,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
)
from startrails.lib.project_finish import FinishProject
from startrails.ui.checkbox_label import CheckboxLabel
from startrails.ui.file_manager import FileSection
from startrails.ui.sky_mask_settings import SkyMaskSettings
from startrails.ui.steps import StepCard
from startrails.ui.steps_separate import SeparateStarsSettings
from startrails.ui.steps_starless import FinishStarlessSettings
from startrails.ui.theme import system_theme

if TYPE_CHECKING:
    from startrails.app import App


class FinishRecombineSettings(QWidget):
    """Step 4 card body widget handling layer blending amounts, modes, and export."""

    star_amount_changed = Signal(float)
    star_threshold_changed = Signal(float)
    blend_mode_changed = Signal(str)
    slider_dragging = Signal()
    settings_changed = Signal()
    compare_original_toggled = Signal(bool)
    export_layers_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()
        self._init_events()
        self.refresh_prerequisites(False)

    def _add_percent_slider(
        self, layout: QVBoxLayout, title: str, initial_percent: float
    ) -> tuple[QLabel, QLabel, QSlider]:
        header = QHBoxLayout()
        lbl_title = QLabel(title, self)
        lbl_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        lbl_value = QLabel(f"{int(round(initial_percent))}%", self)
        lbl_value.setStyleSheet("font-size: 11px; font-weight: 600; color: #0369a1;")
        lbl_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(lbl_title)
        header.addWidget(lbl_value)
        layout.addLayout(header)

        slider = QSlider(Qt.Orientation.Horizontal, self)
        slider.setRange(0, 100)
        slider.setSingleStep(1)
        slider.setPageStep(10)
        slider.setValue(int(round(initial_percent)))
        slider.setStyleSheet(
            "QSlider { border: none; padding: 0px; margin: 0px; min-height: 20px; max-height: 20px; }"
            "QSlider:focus { border: none; outline: none; }"
        )
        layout.addWidget(slider)
        return lbl_title, lbl_value, slider

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Stars amount & brightness threshold sections
        self.lbl_star_amount_title, self.lbl_star_amount_value, self.slider_star_amount = self._add_percent_slider(
            layout, "Stars", DEFAULT_STAR_AMOUNT_PERCENT
        )
        (
            self.lbl_star_threshold_title,
            self.lbl_star_threshold_value,
            self.slider_star_threshold,
        ) = self._add_percent_slider(layout, "Threshold", DEFAULT_STAR_THRESHOLD_PERCENT)

        fin_mode_layout = QHBoxLayout()
        lbl_fin_mode = QLabel("Blend Mode", self)
        lbl_fin_mode.setStyleSheet("font-size: 11px; font-weight: 500; color: #64748b;")
        self.combo_star_blend_mode = QComboBox(self)
        self.combo_star_blend_mode.addItem("Add", "add")
        self.combo_star_blend_mode.addItem("Screen", "screen")
        self.combo_star_blend_mode.setStyleSheet(
            "QComboBox { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 6px; font-size: 11px; color: #1e293b; min-height: 20px; max-height: 24px; }"
            "QComboBox:focus { border: 1px solid #0369a1; outline: none; }"
        )
        fin_mode_layout.addWidget(lbl_fin_mode)
        fin_mode_layout.addWidget(self.combo_star_blend_mode)
        layout.addLayout(fin_mode_layout)

        # Compare with original
        compare_layout = QHBoxLayout()
        self.lbl_compare_original = CheckboxLabel("Compare with original", self)
        self.lbl_compare_original.setCursor(Qt.PointingHandCursor)
        self.lbl_compare_original.setStyleSheet("font-size: 11px; font-weight: 500; color: #334155;")
        self.check_compare_original = QCheckBox(self)
        self.check_compare_original.setCursor(Qt.PointingHandCursor)
        self.check_compare_original.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.check_compare_original.setChecked(False)
        self.check_compare_original.setStyleSheet(
            "QCheckBox { spacing: 0px; border: none; padding: 0px; background: transparent; }\n"
            "QCheckBox::indicator { width: 36px; height: 20px; border-radius: 10px; }\n"
            "QCheckBox::indicator:unchecked { image: url(:/startrails/ui/switch_off.svg); }\n"
            "QCheckBox::indicator:checked { image: url(:/startrails/ui/switch_on.svg); }\n"
            "QCheckBox:focus, QCheckBox:focus:enabled { border: none; outline: none; padding: 0px; }"
        )
        self.lbl_compare_original.setBuddy(self.check_compare_original)
        compare_layout.addWidget(self.lbl_compare_original)
        compare_layout.addStretch(1)
        compare_layout.addWidget(self.check_compare_original)
        layout.addLayout(compare_layout)

        # Status / error feedback label
        self.lbl_status = QLabel(self)
        self.lbl_status.setStyleSheet("color: #b91c1c; font-size: 11px;")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.hide()
        layout.addWidget(self.lbl_status)

        # Actions: Save Image & Export Layers
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        btn_style = (
            "QPushButton { font-weight: 600; padding: 6px; background-color: #ffffff; color: #0284c7; border: 1px solid #0284c7; border-radius: 4px; font-size: 11px; }\n"
            "QPushButton:hover { background-color: #f0f9ff; }\n"
            "QPushButton:disabled { background-color: #f8fafc; color: #cbd5e1; border-color: #e2e8f0; }"
        )

        self.btn_save_output = QPushButton("Save Image", self)
        self.btn_save_output.setCursor(Qt.PointingHandCursor)
        self.btn_save_output.setStyleSheet(btn_style)
        actions_layout.addWidget(self.btn_save_output)

        self.btn_export_layers = QPushButton("Export Layers", self)
        self.btn_export_layers.setCursor(Qt.PointingHandCursor)
        self.btn_export_layers.setStyleSheet(btn_style)
        self.btn_export_layers.setToolTip(
            "Export separated and finished layers to disk. Stars is positive-only "
            "(the internal Add negative correction is not exported), so external "
            "layer recombination or JPEG export may not reconstruct the source exactly."
        )
        actions_layout.addWidget(self.btn_export_layers)

        layout.addLayout(actions_layout)

    def _init_events(self) -> None:
        for slider, label, sig in (
            (self.slider_star_amount, self.lbl_star_amount_value, self.star_amount_changed),
            (self.slider_star_threshold, self.lbl_star_threshold_value, self.star_threshold_changed),
        ):
            slider.valueChanged.connect(lambda v, s=slider, l=label, sg=sig: self._on_percent_slider_changed(s, l, sg, v))
            slider.sliderPressed.connect(self.slider_dragging.emit)
            slider.sliderReleased.connect(lambda s=slider, l=label, sg=sig: self._on_percent_slider_released(s, l, sg))
        self.combo_star_blend_mode.currentIndexChanged.connect(self._on_star_blend_mode_changed)
        self.check_compare_original.toggled.connect(self.compare_original_toggled.emit)
        self.btn_export_layers.clicked.connect(self.export_layers_requested.emit)

    def _on_percent_slider_changed(self, slider: QSlider, label: QLabel, signal: Signal, value: int) -> None:
        label.setText(f"{value}%")
        if slider.isSliderDown():
            self.slider_dragging.emit()
        else:
            signal.emit(float(value))
            self.settings_changed.emit()

    def _on_percent_slider_released(self, slider: QSlider, label: QLabel, signal: Signal) -> None:
        val = slider.value()
        label.setText(f"{val}%")
        signal.emit(float(val))
        self.settings_changed.emit()

    def is_slider_down(self) -> bool:
        """Return True if any composition slider is actively held down."""
        return bool(self.slider_star_amount.isSliderDown() or self.slider_star_threshold.isSliderDown())

    def _on_star_blend_mode_changed(self, index: int) -> None:
        data = self.combo_star_blend_mode.currentData()
        if data is not None:
            self.blend_mode_changed.emit(str(data))
            self.settings_changed.emit()

    def get_star_amount(self) -> float:
        return float(self.slider_star_amount.value())

    @staticmethod
    def _set_percent_slider(slider: QSlider, label: QLabel, value: float) -> None:
        val = int(round(value))
        val = max(0, min(100, val))
        label.setText(f"{val}%")
        with QSignalBlocker(slider):
            slider.setValue(val)

    def set_star_amount(self, amount: float) -> None:
        self._set_percent_slider(self.slider_star_amount, self.lbl_star_amount_value, amount)

    def get_star_threshold(self) -> float:
        return float(self.slider_star_threshold.value())

    def set_star_threshold(self, threshold: float) -> None:
        self._set_percent_slider(self.slider_star_threshold, self.lbl_star_threshold_value, threshold)

    def get_blend_mode(self) -> str:
        data = self.combo_star_blend_mode.currentData()
        if data is None:
            raise ValueError("Blend mode combo has no valid selection.")
        return str(data)

    def set_blend_mode(self, mode: str) -> None:
        idx = self.combo_star_blend_mode.findData(mode)
        if idx < 0:
            raise ValueError(f"Unsupported blend mode '{mode}'.")
        with QSignalBlocker(self.combo_star_blend_mode):
            self.combo_star_blend_mode.setCurrentIndex(idx)

    def set_from_project(self, project: FinishProject) -> None:
        settings = project.get_settings()
        self.set_star_amount(settings.star_amount)
        self.set_star_threshold(settings.star_threshold)
        self.set_blend_mode(settings.blend_mode)

    def get_compare_original(self) -> bool:
        return bool(self.check_compare_original.isChecked())

    def set_compare_original(self, checked: bool) -> None:
        with QSignalBlocker(self.check_compare_original):
            self.check_compare_original.setChecked(checked)

    def refresh_prerequisites(self, has_prerequisites: bool = True) -> None:
        self.slider_star_amount.setEnabled(has_prerequisites)
        self.slider_star_threshold.setEnabled(has_prerequisites)
        self.combo_star_blend_mode.setEnabled(has_prerequisites)
        self.check_compare_original.setEnabled(has_prerequisites)
        self.lbl_compare_original.setEnabled(has_prerequisites)
        self.btn_save_output.setEnabled(has_prerequisites)
        self.btn_export_layers.setEnabled(has_prerequisites)
        if not has_prerequisites and self.check_compare_original.isChecked():
            self.set_compare_original(False)


class SidebarFinish(QWidget):
    """Sidebar widget hosting Finish mode project actions, file sections, step cards, and outputs."""

    def __init__(self, parent: Optional[QWidget] = None, app: Optional[App] = None):
        super().__init__(parent)
        self.app = app
        self.setObjectName("SidebarFinish")

        self._init_ui()
        system_theme().register(self)

    def _init_ui(self) -> None:
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setSpacing(0)
        self.root_layout.setObjectName("layout")
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("scroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)

        self.content = QWidget()
        self.content.setObjectName("content")
        self.contentLayout = QVBoxLayout(self.content)
        self.contentLayout.setSpacing(8)
        self.contentLayout.setObjectName("contentLayout")
        self.contentLayout.setContentsMargins(8, 8, 8, 8)

        # -------------------------------------------------------------
        # Project Actions (New / Open)
        # -------------------------------------------------------------
        self.projectActions = QHBoxLayout()
        self.projectActions.setSpacing(6)
        self.projectActions.setObjectName("projectActions")

        self.newProject = QPushButton("New Project", self.content)
        self.newProject.setObjectName("newProject")
        self.newProject.setCursor(Qt.PointingHandCursor)
        self.projectActions.addWidget(self.newProject)

        self.openProject = QPushButton("Open Project", self.content)
        self.openProject.setObjectName("openProject")
        self.openProject.setCursor(Qt.PointingHandCursor)
        self.projectActions.addWidget(self.openProject)

        self.pushButton_newProject = self.newProject
        self.pushButton_openProject = self.openProject
        self.contentLayout.addLayout(self.projectActions)

        # -------------------------------------------------------------
        # Input Files Section (single source image)
        # -------------------------------------------------------------
        self.inputFiles = FileSection(title="Input Files", inputs=True, parent=self.content)
        self.inputFiles.setObjectName("inputFiles")
        self.inputFiles.setProperty("show_legend", False)
        self.inputFiles.setProperty("is_expanded", True)
        self.contentLayout.addWidget(self.inputFiles)

        # -------------------------------------------------------------
        # Output Files Section
        # -------------------------------------------------------------
        self.outputFiles = FileSection(title="Output Files", inputs=False, parent=self.content)
        self.outputFiles.setObjectName("outputFiles")
        self.outputFiles.setProperty("show_legend", False)
        self.outputFiles.setProperty("is_expanded", True)
        self.outputs = self.outputFiles
        self.contentLayout.addWidget(self.outputFiles)

        # -------------------------------------------------------------
        # Step Cards (1 to 4)
        # -------------------------------------------------------------
        self.skyCard = StepCard(title="Define Sky Region", number=1, expanded=False, parent=self.content)
        self.skyCard.setSubtitle("Detect Sky and refine sky protection mask")
        self.skySettings = SkyMaskSettings(parent=self.content, app=self.app)
        self.skyCard.add_body(self.skySettings)
        self.btn_detect_sky = self.skySettings.ui.detect
        self.contentLayout.addWidget(self.skyCard)

        self.separateCard = StepCard(title="Separate Stars", number=2, expanded=False, parent=self.content)
        self.separateCard.setSubtitle("Separate into starless and stars layers")
        self.separateSettings = SeparateStarsSettings(parent=self.content)
        self.separateCard.add_body(self.separateSettings)
        self.contentLayout.addWidget(self.separateCard)

        self.starlessCard = StepCard(title="Finish Starless", number=3, expanded=False, parent=self.content)
        self.starlessCard.setSubtitle("AI denoise with Structure and Detail controls")
        self.starlessSettings = FinishStarlessSettings(parent=self.content)
        self.starlessCard.add_body(self.starlessSettings)
        self.contentLayout.addWidget(self.starlessCard)

        self.recombineCard = StepCard(title="Recombine & Save", number=4, expanded=False, parent=self.content)
        self.recombineCard.setSubtitle("Blend layers and export image")

        self.recombineSettings = FinishRecombineSettings(parent=self.content)
        self.recombineCard.add_body(self.recombineSettings)
        self.btn_save_output = self.recombineSettings.btn_save_output
        self.btn_export_layers = self.recombineSettings.btn_export_layers
        self.check_compare_original = self.recombineSettings.check_compare_original
        self.slider_star_amount = self.recombineSettings.slider_star_amount
        self.slider_star_threshold = self.recombineSettings.slider_star_threshold
        self.contentLayout.addWidget(self.recombineCard)

        self._step_cards = (self.skyCard, self.separateCard, self.starlessCard, self.recombineCard)
        for card in self._step_cards:
            card.expanded.connect(lambda c=card: self._collapse_other_steps(c))

        self.contentLayout.addStretch(1)
        self.scroll.setWidget(self.content)
        self.root_layout.addWidget(self.scroll)

    def _collapse_other_steps(self, expanded_card: StepCard) -> None:
        for card in self._step_cards:
            if card is not expanded_card and card.ui.toggle.isChecked():
                card.setExpanded(False)

    def lock_output_files_height(self) -> None:
        """Lock output files table to a constant 4-row height to prevent vertical position shifts."""
        if hasattr(self, "outputFiles") and self.outputFiles.model.rowCount() > 0:
            hh = self.outputFiles.ui.files.header().height() or 26
            self.outputFiles.ui.files.setFixedHeight(hh + 4 * 24 + 4)

    def update_from_project(self, project: FinishProject, dimensions: Optional[tuple[int, int]]) -> None:
        """Update file sections and step prerequisites from active project."""
        self.separateSettings.set_from_project(project)
        if hasattr(self, "starlessSettings"):
            self.starlessSettings.set_from_project(project)
        if hasattr(self, "recombineSettings"):
            self.recombineSettings.set_from_project(project)
        self.update_prerequisites(project)

    def update_prerequisites(self, project: FinishProject) -> None:
        """Update enabled states and subtitles according to stage prerequisite availability."""
        has_source = project.source_is_current()
        has_mask = project.current_artifact_path(ROLE_SKY_MASK) is not None
        has_starless = project.current_artifact_path(ROLE_SEPARATED_STARLESS) is not None
        has_stars = project.current_artifact_path(ROLE_SEPARATED_STARS) is not None
        settings = project.get_settings()
        has_denoise_endpoint = (
            project.current_artifact_path(ROLE_DENOISE_ENDPOINT) is not None
            or project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None
        )
        has_finished_starless = (
            project.current_artifact_path(ROLE_FINISHED_STARLESS) is not None
            if settings.enable_starless_sharpen
            else project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None
        )
        has_composite = project.current_artifact_path(ROLE_FINISHED_COMPOSITE) is not None

        if hasattr(self, "skySettings"):
            self.skySettings.refresh_inputs(has_source=has_source)

        star_removal_status = {}
        if (
            hasattr(self, "app")
            and self.app
            and hasattr(self.app, "workflow")
            and hasattr(self.app.workflow, "get_star_removal_status")
        ):
            star_removal_status = self.app.workflow.get_star_removal_status()

        if hasattr(self, "separateSettings"):
            self.separateSettings.refresh_status(star_removal_status, has_prerequisites=has_source and has_mask)

        graxpert_status = {}
        if (
            hasattr(self, "app")
            and self.app
            and hasattr(self.app, "workflow")
            and hasattr(self.app.workflow, "get_graxpert_status")
        ):
            graxpert_status = self.app.workflow.get_graxpert_status()

        if hasattr(self, "starlessSettings"):
            self.starlessSettings.refresh_status(
                graxpert_status,
                has_prerequisites=has_starless,
                has_endpoint=has_denoise_endpoint,
            )

        if not has_source:
            self.skyCard.setStatus("locked", "Prerequisite: Source image required")
            self.separateCard.setStatus("locked", "Prerequisite: Source image required")
            self.starlessCard.setStatus("locked", "Prerequisite: Source image required")
            self.recombineCard.setStatus("locked", "Prerequisite: Source image required")
            if hasattr(self, "recombineSettings"):
                self.recombineSettings.refresh_prerequisites(has_prerequisites=False)
            self.btn_save_output.setEnabled(False)
            self.btn_export_layers.setEnabled(False)
            return

        if has_mask:
            self.skyCard.setStatus("done", "Sky mask defined")
        else:
            self.skyCard.setStatus("ready", "Ready to define sky region")

        if not has_mask:
            self.separateCard.setStatus("locked", "Prerequisite: Sky region required")
            self.starlessCard.setStatus("locked", "Prerequisite: Separated starless required")
            self.recombineCard.setStatus("locked", "Prerequisite: Sky region required")
            if hasattr(self, "recombineSettings"):
                self.recombineSettings.refresh_prerequisites(has_prerequisites=False)
            self.btn_save_output.setEnabled(False)
            self.btn_export_layers.setEnabled(False)
            return

        if not (has_starless and has_stars):
            if not star_removal_status.get("configured", False):
                self.separateCard.setStatus("ready", "Star removal model missing")
            else:
                self.separateCard.setStatus("ready", "Ready to separate stars")
            self.starlessCard.setStatus("locked", "Prerequisite: Separated starless required")
            self.recombineCard.setStatus("locked", "Prerequisite: Separated layers required")
            if hasattr(self, "recombineSettings"):
                self.recombineSettings.refresh_prerequisites(has_prerequisites=False)
            self.btn_save_output.setEnabled(False)
            self.btn_export_layers.setEnabled(False)
            return

        graxpert_ready = bool(graxpert_status.get("configured", graxpert_status.get("model_ready", False)))

        self.separateCard.setStatus("done", "Stars separated")
        if has_finished_starless:
            self.starlessCard.setStatus("done", "Starless finished")
        elif has_denoise_endpoint:
            self.starlessCard.setStatus("ready", "Ready to update starless")
        elif not graxpert_ready:
            self.starlessCard.setStatus("ready", "GraXpert setup required")
        else:
            self.starlessCard.setStatus("ready", "Ready to finish starless")

        if hasattr(self, "recombineSettings"):
            self.recombineSettings.refresh_prerequisites(has_prerequisites=True)

        if project.current_export_path() is not None:
            self.recombineCard.setStatus("done", "Finished image saved")
        else:
            self.recombineCard.setStatus("ready", "Ready to recombine")

        ready = has_source and has_mask and has_starless and has_stars
        self.btn_save_output.setEnabled(ready)
        self.btn_export_layers.setEnabled(ready)


__all__ = ["FinishRecombineSettings", "SidebarFinish"]
