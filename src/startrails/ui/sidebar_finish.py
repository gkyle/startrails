"""Composition of the Finish mode sidebar shell and step cards."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
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
    DEFAULT_ORIGINAL_STARS_AMOUNT_PERCENT,
    DEFAULT_STAR_AMOUNT_PERCENT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_FINISHED_STARS,
    ROLE_SKY_MASK,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
)
from startrails.lib.project_finish import FinishProject
from startrails.ui.file_manager import FileSection
from startrails.ui.sky_mask_settings import SkyMaskSettings
from startrails.ui.steps import StepCard
from startrails.ui.steps_separate import SeparateStarsSettings
from startrails.ui.steps_starless import FinishStarlessSettings
from startrails.ui.steps_stars import FinishStarsSettings
from startrails.ui.theme import system_theme

if TYPE_CHECKING:
    from startrails.app import App


class FinishRecombineSettings(QWidget):
    """Step 5 card body widget handling layer blending amounts, modes, and export."""

    star_amount_changed = Signal(float)
    blend_mode_changed = Signal(str)
    original_stars_amount_changed = Signal(float)
    original_stars_blend_mode_changed = Signal(str)
    settings_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()
        self._init_events()
        self.refresh_prerequisites(False)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Finished Stars section
        fin_header = QHBoxLayout()
        self.lbl_star_amount_title = QLabel("Finished Stars", self)
        self.lbl_star_amount_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        self.lbl_star_amount_value = QLabel(f"{int(DEFAULT_STAR_AMOUNT_PERCENT)}%", self)
        self.lbl_star_amount_value.setStyleSheet("font-size: 11px; font-weight: 600; color: #0369a1;")
        self.lbl_star_amount_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        fin_header.addWidget(self.lbl_star_amount_title)
        fin_header.addWidget(self.lbl_star_amount_value)
        layout.addLayout(fin_header)

        self.slider_star_amount = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_star_amount.setRange(0, 100)
        self.slider_star_amount.setSingleStep(1)
        self.slider_star_amount.setPageStep(10)
        self.slider_star_amount.setValue(int(DEFAULT_STAR_AMOUNT_PERCENT))
        layout.addWidget(self.slider_star_amount)

        fin_mode_layout = QHBoxLayout()
        lbl_fin_mode = QLabel("Blend Mode", self)
        lbl_fin_mode.setStyleSheet("font-size: 11px; font-weight: 500; color: #64748b;")
        self.combo_star_blend_mode = QComboBox(self)
        self.combo_star_blend_mode.addItem("Add", "add")
        self.combo_star_blend_mode.addItem("Screen", "screen")
        self.combo_star_blend_mode.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 6px; font-size: 11px; color: #1e293b;"
        )
        fin_mode_layout.addWidget(lbl_fin_mode)
        fin_mode_layout.addWidget(self.combo_star_blend_mode)
        layout.addLayout(fin_mode_layout)

        # Separator line
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(sep)

        # Original Stars section
        orig_header = QHBoxLayout()
        self.lbl_original_stars_amount_title = QLabel("Original Stars", self)
        self.lbl_original_stars_amount_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #475569;")
        self.lbl_original_stars_amount_value = QLabel(f"{int(DEFAULT_ORIGINAL_STARS_AMOUNT_PERCENT)}%", self)
        self.lbl_original_stars_amount_value.setStyleSheet("font-size: 11px; font-weight: 600; color: #0369a1;")
        self.lbl_original_stars_amount_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        orig_header.addWidget(self.lbl_original_stars_amount_title)
        orig_header.addWidget(self.lbl_original_stars_amount_value)
        layout.addLayout(orig_header)

        self.slider_original_stars_amount = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_original_stars_amount.setRange(0, 100)
        self.slider_original_stars_amount.setSingleStep(1)
        self.slider_original_stars_amount.setPageStep(10)
        self.slider_original_stars_amount.setValue(int(DEFAULT_ORIGINAL_STARS_AMOUNT_PERCENT))
        layout.addWidget(self.slider_original_stars_amount)

        orig_mode_layout = QHBoxLayout()
        lbl_orig_mode = QLabel("Blend Mode", self)
        lbl_orig_mode.setStyleSheet("font-size: 11px; font-weight: 500; color: #64748b;")
        self.combo_original_stars_blend_mode = QComboBox(self)
        self.combo_original_stars_blend_mode.addItem("Add", "add")
        self.combo_original_stars_blend_mode.addItem("Screen", "screen")
        self.combo_original_stars_blend_mode.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 6px; font-size: 11px; color: #1e293b;"
        )
        orig_mode_layout.addWidget(lbl_orig_mode)
        orig_mode_layout.addWidget(self.combo_original_stars_blend_mode)
        layout.addLayout(orig_mode_layout)

        # Action: Save Image
        self.btn_save_output = QPushButton("Save Image", self)
        self.btn_save_output.setCursor(Qt.PointingHandCursor)
        self.btn_save_output.setStyleSheet(
            "QPushButton { font-weight: 600; padding: 6px; background-color: #ffffff; color: #0284c7; border: 1px solid #0284c7; border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { background-color: #f0f9ff; }"
            "QPushButton:disabled { background-color: #f8fafc; color: #cbd5e1; border-color: #e2e8f0; }"
        )
        layout.addWidget(self.btn_save_output)

    def _init_events(self) -> None:
        self.slider_star_amount.valueChanged.connect(self._on_star_amount_changed)
        self.combo_star_blend_mode.currentIndexChanged.connect(self._on_star_blend_mode_changed)
        self.slider_original_stars_amount.valueChanged.connect(self._on_orig_amount_changed)
        self.combo_original_stars_blend_mode.currentIndexChanged.connect(self._on_orig_blend_mode_changed)

    def _on_star_amount_changed(self, value: int) -> None:
        self.lbl_star_amount_value.setText(f"{value}%")
        self.star_amount_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_star_blend_mode_changed(self, index: int) -> None:
        data = self.combo_star_blend_mode.currentData()
        if data is not None:
            self.blend_mode_changed.emit(str(data))
            self.settings_changed.emit()

    def _on_orig_amount_changed(self, value: int) -> None:
        self.lbl_original_stars_amount_value.setText(f"{value}%")
        self.original_stars_amount_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_orig_blend_mode_changed(self, index: int) -> None:
        data = self.combo_original_stars_blend_mode.currentData()
        if data is not None:
            self.original_stars_blend_mode_changed.emit(str(data))
            self.settings_changed.emit()

    def get_star_amount(self) -> float:
        return float(self.slider_star_amount.value())

    def set_star_amount(self, amount: float) -> None:
        val = int(round(amount))
        val = max(0, min(100, val))
        self.lbl_star_amount_value.setText(f"{val}%")
        with QSignalBlocker(self.slider_star_amount):
            self.slider_star_amount.setValue(val)

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

    def get_original_stars_amount(self) -> float:
        return float(self.slider_original_stars_amount.value())

    def set_original_stars_amount(self, amount: float) -> None:
        val = int(round(amount))
        val = max(0, min(100, val))
        self.lbl_original_stars_amount_value.setText(f"{val}%")
        with QSignalBlocker(self.slider_original_stars_amount):
            self.slider_original_stars_amount.setValue(val)

    def get_original_stars_blend_mode(self) -> str:
        data = self.combo_original_stars_blend_mode.currentData()
        if data is None:
            raise ValueError("Original stars blend mode combo has no valid selection.")
        return str(data)

    def set_original_stars_blend_mode(self, mode: str) -> None:
        idx = self.combo_original_stars_blend_mode.findData(mode)
        if idx < 0:
            raise ValueError(f"Unsupported original stars blend mode '{mode}'.")
        with QSignalBlocker(self.combo_original_stars_blend_mode):
            self.combo_original_stars_blend_mode.setCurrentIndex(idx)

    def set_from_project(self, project: FinishProject) -> None:
        settings = project.get_settings()
        self.set_star_amount(settings.star_amount)
        self.set_blend_mode(settings.blend_mode)
        self.set_original_stars_amount(settings.original_stars_amount)
        self.set_original_stars_blend_mode(settings.original_stars_blend_mode)

    def refresh_prerequisites(self, has_prerequisites: bool = True) -> None:
        self.slider_star_amount.setEnabled(has_prerequisites)
        self.combo_star_blend_mode.setEnabled(has_prerequisites)
        self.slider_original_stars_amount.setEnabled(has_prerequisites)
        self.combo_original_stars_blend_mode.setEnabled(has_prerequisites)


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
        # Step Cards (1 to 5)
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

        self.starsCard = StepCard(title="Finish Stars", number=4, expanded=False, parent=self.content)
        self.starsCard.setSubtitle("Star selection, rounding, and glow")
        self.starsSettings = FinishStarsSettings(parent=self.content)
        self.starsCard.add_body(self.starsSettings)
        self.contentLayout.addWidget(self.starsCard)

        self.recombineCard = StepCard(title="Recombine & Save", number=5, expanded=False, parent=self.content)
        self.recombineCard.setSubtitle("Blend layers and export image")

        self.recombineSettings = FinishRecombineSettings(parent=self.content)
        self.recombineCard.add_body(self.recombineSettings)
        self.btn_save_output = self.recombineSettings.btn_save_output
        self.slider_star_amount = self.recombineSettings.slider_star_amount
        self.contentLayout.addWidget(self.recombineCard)

        self._step_cards = (self.skyCard, self.separateCard, self.starlessCard, self.starsCard, self.recombineCard)
        for card in self._step_cards:
            card.expanded.connect(lambda c=card: self._collapse_other_steps(c))

        self.contentLayout.addStretch(1)
        self.scroll.setWidget(self.content)
        self.root_layout.addWidget(self.scroll)

    def _collapse_other_steps(self, expanded_card: StepCard) -> None:
        for card in self._step_cards:
            if card is not expanded_card and card.ui.toggle.isChecked():
                card.setExpanded(False)

    def update_from_project(self, project: FinishProject, dimensions: Optional[tuple[int, int]]) -> None:
        """Update file sections and step prerequisites from active project."""
        self.separateSettings.set_stride(project.starnet_stride)
        if hasattr(self, "starlessSettings"):
            self.starlessSettings.set_from_project(project)
        if hasattr(self, "starsSettings"):
            self.starsSettings.set_from_project(project)
        if hasattr(self, "recombineSettings"):
            self.recombineSettings.set_from_project(project)
        self.update_prerequisites(project)

    def update_prerequisites(self, project: FinishProject) -> None:
        """Update enabled states and subtitles according to stage prerequisite availability."""
        has_source = project.source_is_current()
        has_mask = project.current_artifact_path(ROLE_SKY_MASK) is not None
        has_starless = project.current_artifact_path(ROLE_SEPARATED_STARLESS) is not None
        has_stars = project.current_artifact_path(ROLE_SEPARATED_STARS) is not None
        has_denoise_endpoint = project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None
        has_finished_starless = project.current_artifact_path(ROLE_FINISHED_STARLESS) is not None
        has_finished_stars = project.current_artifact_path(ROLE_FINISHED_STARS) is not None
        has_composite = project.current_artifact_path(ROLE_FINISHED_COMPOSITE) is not None

        if hasattr(self, "skySettings"):
            self.skySettings.refresh_inputs(has_source=has_source)

        starnet_status = {}
        if (
            hasattr(self, "app")
            and self.app
            and hasattr(self.app, "workflow")
            and hasattr(self.app.workflow, "get_starnet_status")
        ):
            starnet_status = self.app.workflow.get_starnet_status()

        if hasattr(self, "separateSettings"):
            self.separateSettings.refresh_status(starnet_status, has_prerequisites=has_source and has_mask)

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
            self.starsCard.setStatus("locked", "Prerequisite: Source image required")
            self.recombineCard.setStatus("locked", "Prerequisite: Source image required")
            if hasattr(self, "starsSettings"):
                self.starsSettings.refresh_prerequisites(has_prerequisites=False)
            if hasattr(self, "recombineSettings"):
                self.recombineSettings.refresh_prerequisites(has_prerequisites=False)
            self.btn_save_output.setEnabled(False)
            return

        if has_mask:
            self.skyCard.setStatus("done", "Sky mask defined")
        else:
            self.skyCard.setStatus("ready", "Ready to define sky region")

        if not has_mask:
            self.separateCard.setStatus("locked", "Prerequisite: Sky region required")
            self.starlessCard.setStatus("locked", "Prerequisite: Separated starless required")
            self.starsCard.setStatus("locked", "Prerequisite: Separated stars required")
            self.recombineCard.setStatus("locked", "Prerequisite: Sky region required")
            if hasattr(self, "starsSettings"):
                self.starsSettings.refresh_prerequisites(has_prerequisites=False)
            if hasattr(self, "recombineSettings"):
                self.recombineSettings.refresh_prerequisites(has_prerequisites=False)
            self.btn_save_output.setEnabled(False)
            return

        if not (has_starless and has_stars):
            if not starnet_status.get("configured", False):
                self.separateCard.setStatus("ready", "StarNet2 setup required")
            else:
                self.separateCard.setStatus("ready", "Ready to separate stars")
            self.starlessCard.setStatus("locked", "Prerequisite: Separated starless required")
            self.starsCard.setStatus("locked", "Prerequisite: Separated stars required")
            self.recombineCard.setStatus("locked", "Prerequisite: Separated layers required")
            if hasattr(self, "starsSettings"):
                self.starsSettings.refresh_prerequisites(has_prerequisites=False)
            if hasattr(self, "recombineSettings"):
                self.recombineSettings.refresh_prerequisites(has_prerequisites=False)
            self.btn_save_output.setEnabled(False)
            return

        policy = graxpert_status.get("policy")
        model_ready = graxpert_status.get("model_ready", False)
        graxpert_ready = bool(model_ready and policy and policy.get("verified", False))

        self.separateCard.setStatus("done", "Stars separated")
        if has_finished_starless:
            self.starlessCard.setStatus("done", "Starless finished")
        elif has_denoise_endpoint:
            self.starlessCard.setStatus("ready", "Ready to update starless")
        elif not graxpert_ready:
            self.starlessCard.setStatus("ready", "GraXpert setup required")
        else:
            self.starlessCard.setStatus("ready", "Ready to finish starless")

        if hasattr(self, "starsSettings"):
            self.starsSettings.refresh_prerequisites(has_prerequisites=True)
        if hasattr(self, "recombineSettings"):
            self.recombineSettings.refresh_prerequisites(has_prerequisites=True)

        settings = project.get_settings()
        workflow = getattr(self.app, "workflow", None) if self.app else None
        effects_enabled = bool(workflow and workflow._star_effects_enabled(settings))
        if has_finished_stars:
            self.starsCard.setStatus("done", "Stars finished")
        elif effects_enabled:
            self.starsCard.setStatus("ready", "Ready to update stars")
        else:
            self.starsCard.setStatus("ready", "Ready to finish stars")

        self.recombineCard.setStatus("ready", "Ready to recombine")
        self.btn_save_output.setEnabled(has_source and has_mask and has_starless and has_stars)


__all__ = ["FinishRecombineSettings", "SidebarFinish"]
