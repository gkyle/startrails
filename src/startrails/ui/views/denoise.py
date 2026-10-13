"""Denoise mode sidebar view and workflow controller."""

from __future__ import annotations
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
import numpy as np
from PySide6.QtCore import Slot, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from startrails.lib.file import File, DenoiseInputFile
from startrails.ui.file_manager import FileSection
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.steps import StepCard
from startrails.ui.steps_denoise import (
    DenoiseSkySettings,
    DenoiseAlignSettings,
    DenoiseStackSettings,
    DenoiseTuneSettings,
)
from startrails.ui.views.base import ModeView

if TYPE_CHECKING:
    from startrails.app import App


# Conditional style overrides for changing sidebar style from startrails to denoise (if any).
SIDEBAR_STYLESHEET = """
QWidget#sidebar {
    background-color: #f8fafc;
}
QScrollArea#scroll {
    border: none;
    background: transparent;
}
QWidget#content {
    background-color: #f8fafc;
}
QScrollBar:vertical {
    border: none;
    background: #f1f5f9;
    width: 6px;
    border-radius: 3px;
    margin: 2px 0px 2px 0px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 24px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    height: 0px;
}
"""


class DenoiseView(ModeView):
    """View controller managing the Denoise sidebar, input lists, and denoising pipeline."""

    mode_name: str = "denoise"

    def __init__(self, app: App, shell: Any):
        super().__init__(app, shell)
        self.sidebar: Optional[QWidget] = None
        self.starFiles: Optional[FileSection] = None
        self.noiseFiles: Optional[FileSection] = None
        self.vignettingFiles: Optional[FileSection] = None

        self.skySettings: Optional[DenoiseSkySettings] = None
        self.alignSettings: Optional[DenoiseAlignSettings] = None
        self.stackSettings: Optional[DenoiseStackSettings] = None
        self.tuneSettings: Optional[DenoiseTuneSettings] = None

        self.skyCard: Optional[StepCard] = None
        self.alignCard: Optional[StepCard] = None
        self.stackCard: Optional[StepCard] = None
        self.tuneCard: Optional[StepCard] = None

        self.pushButton_newProject: Optional[QPushButton] = None
        self.pushButton_openProject: Optional[QPushButton] = None
        self.btn_detect_sky: Optional[QPushButton] = None
        self.btn_align_stars: Optional[QPushButton] = None
        self.btn_stack: Optional[QPushButton] = None
        self.btn_compose: Optional[QPushButton] = None
        self.btn_save_output: Optional[QPushButton] = None
        self.btn_pipeline: Optional[QPushButton] = None

        self.lbl_ops_progress: Optional[QLabel] = None
        self.ops_progress_bar: Optional[QProgressBar] = None
        self.progress_bar: Optional[QProgressBar] = None
        self.lbl_status: Optional[QLabel] = None

        self._step_cards: tuple[StepCard, ...] = ()
        self._output_saved: bool = False

        self.last_compositor: Any = None
        self.last_align_result: Any = None

    def build_sidebar(self, parent: QWidget) -> QWidget:
        if self.sidebar is not None and self.sidebar.parent() is parent:
            return self.sidebar

        sidebar = QWidget(parent)
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(350)
        sidebar.setMaximumWidth(450)
        sidebar.setStyleSheet(SIDEBAR_STYLESHEET)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scrollable body matching startrails mode
        scroll = QScrollArea(sidebar)
        scroll.setObjectName("scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget(scroll)
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        # Project header and actions matching startrails mode
        project_title = QLabel("Project Images", content)
        project_title.setObjectName("projectTitle")
        project_title.setStyleSheet("QLabel#projectTitle { font-size: 15px; font-weight: bold; color: #0f172a; }")
        content_layout.addWidget(project_title)

        project_actions = QHBoxLayout()
        project_actions.setObjectName("projectActions")
        project_actions.setSpacing(6)

        btn_style_new = (
            "QPushButton#newProject {\n"
            "    background-color: #ffffff;\n"
            "    color: #1e293b;\n"
            "    border: 2px solid #cbd5e1;\n"
            "    border-radius: 6px;\n"
            "    padding: 6px 12px;\n"
            "    font-weight: 500;\n"
            "    font-size: 12px;\n"
            "}\n"
            "QPushButton#newProject:hover {\n"
            "    background-color: #f1f5f9;\n"
            "    border-color: #94a3b8;\n"
            "}\n"
            "QPushButton#newProject:pressed {\n"
            "    background-color: #e2e8f0;\n"
            "}\n"
            "QPushButton#newProject:focus:enabled {\n"
            "    border-color: #0f172a;\n"
            "}"
        )
        btn_style_open = (
            "QPushButton#openProject {\n"
            "    background-color: #ffffff;\n"
            "    color: #1e293b;\n"
            "    border: 2px solid #cbd5e1;\n"
            "    border-radius: 6px;\n"
            "    padding: 6px 12px;\n"
            "    font-weight: 500;\n"
            "    font-size: 12px;\n"
            "}\n"
            "QPushButton#openProject:hover {\n"
            "    background-color: #f1f5f9;\n"
            "    border-color: #94a3b8;\n"
            "}\n"
            "QPushButton#openProject:pressed {\n"
            "    background-color: #e2e8f0;\n"
            "}\n"
            "QPushButton#openProject:focus:enabled {\n"
            "    border-color: #0f172a;\n"
            "}"
        )
        self.pushButton_newProject = QPushButton("New Project", content)
        self.pushButton_newProject.setObjectName("newProject")
        self.pushButton_newProject.setCursor(Qt.PointingHandCursor)
        self.pushButton_newProject.setToolTip("Create a new project")
        self.pushButton_newProject.setStyleSheet(btn_style_new)

        self.pushButton_openProject = QPushButton("Open Project", content)
        self.pushButton_openProject.setObjectName("openProject")
        self.pushButton_openProject.setCursor(Qt.PointingHandCursor)
        self.pushButton_openProject.setToolTip("Open an existing project")
        self.pushButton_openProject.setStyleSheet(btn_style_open)

        project_actions.addWidget(self.pushButton_newProject)
        project_actions.addWidget(self.pushButton_openProject)
        content_layout.addLayout(project_actions)

        # File Sections: star images expanded; noise & flat frames collapsed; no streak legends
        self.starFiles = FileSection("Star Images", inputs=True, show_legend=False, expanded=True)
        self.noiseFiles = FileSection("Dark / Noise Frames", inputs=True, show_legend=False, expanded=False)
        self.vignettingFiles = FileSection("Flat / Vignetting Frames", inputs=True, show_legend=False, expanded=False)

        content_layout.addWidget(self.starFiles)
        content_layout.addWidget(self.noiseFiles)
        content_layout.addWidget(self.vignettingFiles)

        # Operations header matching startrails mode
        ops_header = QWidget(content)
        ops_header.setObjectName("operationsHeaderWidget")
        ops_header_layout = QVBoxLayout(ops_header)
        ops_header_layout.setObjectName("operationsHeaderLayout")
        ops_header_layout.setContentsMargins(0, 4, 0, 0)
        ops_header_layout.setSpacing(3)

        ops_title = QLabel("Operations", ops_header)
        ops_title.setObjectName("operationsTitle")
        ops_title.setStyleSheet("QLabel#operationsTitle { font-size: 15px; font-weight: bold; color: #0f172a; }")
        ops_header_layout.addWidget(ops_title)

        self.lbl_ops_progress = QLabel("0 of 4 steps complete", ops_header)
        self.lbl_ops_progress.setObjectName("operationsProgressLabel")
        self.lbl_ops_progress.setStyleSheet("QLabel#operationsProgressLabel { font-size: 11px; color: #64748b; font-weight: 500; }")
        ops_header_layout.addWidget(self.lbl_ops_progress)

        self.ops_progress_bar = QProgressBar(ops_header)
        self.ops_progress_bar.setObjectName("operationsProgress")
        self.ops_progress_bar.setStyleSheet(
            "QProgressBar#operationsProgress {\n"
            "    background-color: #e2e8f0;\n"
            "    border-radius: 3px;\n"
            "    max-height: 6px;\n"
            "    min-height: 6px;\n"
            "    border: none;\n"
            "}\n"
            "QProgressBar#operationsProgress::chunk {\n"
            "    background-color: #16a34a;\n"
            "    border-radius: 3px;\n"
            "}"
        )
        self.ops_progress_bar.setRange(0, 4)
        self.ops_progress_bar.setValue(0)
        self.ops_progress_bar.setTextVisible(False)
        ops_header_layout.addWidget(self.ops_progress_bar)

        content_layout.addWidget(ops_header)

        # Step Settings Widgets
        self.skySettings = DenoiseSkySettings(self.app)
        self.skyCard = StepCard("Define Sky Region", self.skySettings, 1, expanded=True)
        self.skyCard.setSubtitle("Ready to detect or paint mask")

        self.alignSettings = DenoiseAlignSettings(self.app)
        self.alignCard = StepCard("Align Stars", self.alignSettings, 2, expanded=False)
        self.alignCard.setSubtitle("Requires sky mask")

        self.stackSettings = DenoiseStackSettings(self.app)
        self.stackCard = StepCard("Stack Foreground and Background", self.stackSettings, 3, expanded=False)
        self.stackCard.setSubtitle("Requires aligned stars")

        self.tuneSettings = DenoiseTuneSettings(self.app)
        self.tuneCard = StepCard("Interactive Horizon Tuning", self.tuneSettings, 4, expanded=False)
        self.tuneCard.setSubtitle("Requires base stacks")

        # Convenient aliases for external access and tests
        self.btn_detect_sky = self.skySettings.ui.detect
        self.btn_align_stars = self.alignSettings.ui.run
        self.btn_stack = self.stackSettings.ui.run
        self.btn_compose = self.tuneSettings.ui.run

        # Step card accordion behavior
        self._step_cards = (self.skyCard, self.alignCard, self.stackCard, self.tuneCard)
        for card in self._step_cards:
            card.expanded.connect(lambda c=card: self._collapse_other_steps(c))

        content_layout.addWidget(self.skyCard)
        content_layout.addWidget(self.alignCard)
        content_layout.addWidget(self.stackCard)
        content_layout.addWidget(self.tuneCard)

        # Save Image action matching pyquator reference
        self.btn_save_output = QPushButton("Save Image", content)
        self.btn_save_output.setObjectName("saveOutput")
        self.btn_save_output.setFixedHeight(36)
        self.btn_save_output.setStyleSheet(
            "QPushButton#saveOutput { background-color: #f1f5f9; color: #1e293b; font-weight: bold; font-size: 13px; border: 1px solid #cbd5e1; border-radius: 4px; }"
            "QPushButton#saveOutput:hover { background-color: #e2e8f0; }"
            "QPushButton#saveOutput:disabled { background-color: #f8fafc; color: #94a3b8; border-color: #e2e8f0; }"
        )
        self.btn_save_output.setCursor(Qt.PointingHandCursor)
        self.btn_save_output.setEnabled(False)
        content_layout.addWidget(self.btn_save_output)

        # Run Full Pipeline action matching pyquator reference
        self.btn_pipeline = QPushButton("▶ Run Full Denoise Pipeline", content)
        self.btn_pipeline.setObjectName("runPipeline")
        self.btn_pipeline.setFixedHeight(36)
        self.btn_pipeline.setStyleSheet(
            "QPushButton#runPipeline { background-color: #0369a1; color: #ffffff; font-weight: bold; font-size: 13px; border-radius: 6px; border: none; }"
            "QPushButton#runPipeline:hover { background-color: #075985; }"
            "QPushButton#runPipeline:disabled { background-color: #cbd5e1; color: #94a3b8; }"
        )
        self.btn_pipeline.setCursor(Qt.PointingHandCursor)
        content_layout.addWidget(self.btn_pipeline)

        # Task Progress bar and Status label matching pyquator
        self.progress_bar = QProgressBar(content)
        self.progress_bar.setObjectName("pipelineProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar#pipelineProgressBar { background-color: #e2e8f0; border-radius: 2px; max-height: 4px; min-height: 4px; border: none; }"
            "QProgressBar#pipelineProgressBar::chunk { background-color: #0284c7; border-radius: 2px; }"
        )
        content_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Ready", content)
        self.lbl_status.setObjectName("pipelineStatusLabel")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 11px;")
        content_layout.addWidget(self.lbl_status)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.sidebar = sidebar
        self.sidebar_widget = sidebar
        return sidebar

    def _collapse_other_steps(self, expanded_card: StepCard) -> None:
        if self.starFiles is not None:
            self.starFiles.setExpanded(False)
        if self.noiseFiles is not None:
            self.noiseFiles.setExpanded(False)
        if self.vignettingFiles is not None:
            self.vignettingFiles.setExpanded(False)
        for card in self._step_cards:
            if card is not expanded_card and card.ui.toggle.isChecked():
                card.setExpanded(False)

    def bind(self) -> None:
        if self.sidebar is None:
            return

        if self.pushButton_newProject is not None and hasattr(self.shell, "doNewProject"):
            self.connect_signal(self.pushButton_newProject.clicked, self.shell.doNewProject)
        if self.pushButton_openProject is not None and hasattr(self.shell, "doOpenProject"):
            self.connect_signal(self.pushButton_openProject.clicked, self.shell.doOpenProject)

        # Connect FileSection actions
        if self.starFiles is not None:
            self.connect_signal(self.starFiles.addRequested, self.select_star_files)
            self.connect_signal(self.starFiles.showFile, self.showFile)
            self.connect_signal(self.starFiles.removeFile, self.remove_star_file)
            self.connect_signal(self.starFiles.setReferenceRequested, self.set_reference_file)

        if self.noiseFiles is not None:
            self.connect_signal(self.noiseFiles.addRequested, self.select_noise_files)
            self.connect_signal(self.noiseFiles.showFile, self.showFile)
            self.connect_signal(self.noiseFiles.removeFile, self.remove_noise_file)

        if self.vignettingFiles is not None:
            self.connect_signal(self.vignettingFiles.addRequested, self.select_vignetting_files)
            self.connect_signal(self.vignettingFiles.showFile, self.showFile)
            self.connect_signal(self.vignettingFiles.removeFile, self.remove_vignetting_file)

        # Connect operation actions
        if self.btn_detect_sky is not None:
            self.connect_signal(self.btn_detect_sky.clicked, self.do_detect_sky_action)
        if self.skySettings is not None:
            self.connect_signal(self.skySettings.ui.refineMask.clicked, self.do_refine_mask_action)
            self.connect_signal(self.skySettings.clearMaskRequested, self.do_clear_mask_action)
            self.connect_signal(self.skySettings.fullFrameRequested, self.do_full_frame_mask_action)
        if self.btn_align_stars is not None:
            self.connect_signal(self.btn_align_stars.clicked, self.do_align_stars_action)
        if self.btn_stack is not None:
            self.connect_signal(self.btn_stack.clicked, self.do_stack_action)
        if self.btn_compose is not None:
            self.connect_signal(self.btn_compose.clicked, self.do_compose_action)
        if self.btn_save_output is not None:
            self.connect_signal(self.btn_save_output.clicked, self.do_save_output_action)
        if self.btn_pipeline is not None:
            self.connect_signal(self.btn_pipeline.clicked, self.do_pipeline_action)

    def teardown(self) -> None:
        super().teardown()
        if self.sidebar is not None:
            self.sidebar.setParent(None)

    # -------------------------------------------------------------------------
    # File Management
    # -------------------------------------------------------------------------

    def select_star_files(self) -> None:
        fileNames, _ = QFileDialog.getOpenFileNames(
            None,
            "Select Star Images",
            filter="Image Files (*.jpg *.jpeg *.tif *.tiff)",
        )
        if fileNames and hasattr(self.app.workflow, "add_star_files"):
            self.app.workflow.add_star_files(fileNames)
            self.resetProjectView()

    def remove_star_file(self, file: File) -> None:
        if hasattr(self.app.workflow, "remove_star_file"):
            self.app.workflow.remove_star_file(file)
            self.resetProjectView()

    def set_reference_file(self, file: DenoiseInputFile) -> None:
        if hasattr(self.app.workflow, "set_reference_file"):
            self.app.workflow.set_reference_file(file)
            if self.alignSettings is not None:
                self.alignSettings.set_reference_file(file)
            self.resetProjectView()

    def select_noise_files(self) -> None:
        fileNames, _ = QFileDialog.getOpenFileNames(
            None,
            "Select Dark/Noise Frames",
            filter="Image Files (*.jpg *.jpeg *.tif *.tiff)",
        )
        if fileNames and hasattr(self.app.workflow, "add_noise_files"):
            self.app.workflow.add_noise_files(fileNames)
            self.resetProjectView()

    def remove_noise_file(self, file: File) -> None:
        if hasattr(self.app.workflow, "remove_noise_file"):
            self.app.workflow.remove_noise_file(file)
            self.resetProjectView()

    def select_vignetting_files(self) -> None:
        fileNames, _ = QFileDialog.getOpenFileNames(
            None,
            "Select Flat/Vignetting Frames",
            filter="Image Files (*.jpg *.jpeg *.tif *.tiff)",
        )
        if fileNames and hasattr(self.app.workflow, "add_vignetting_files"):
            self.app.workflow.add_vignetting_files(fileNames)
            self.resetProjectView()

    def remove_vignetting_file(self, file: File) -> None:
        if hasattr(self.app.workflow, "remove_vignetting_file"):
            self.app.workflow.remove_vignetting_file(file)
            self.resetProjectView()

    def resetProjectView(self) -> None:
        if not hasattr(self.app.workflow, "get_star_files"):
            return
        stars = self.app.workflow.get_star_files()
        darks = self.app.workflow.get_noise_files()
        flats = self.app.workflow.get_vignetting_files()

        if self.starFiles is not None:
            self.starFiles.set_files(stars)
        if self.noiseFiles is not None:
            self.noiseFiles.set_files(darks)
        if self.vignettingFiles is not None:
            self.vignettingFiles.set_files(flats)

        if self.skySettings is not None:
            self.skySettings.set_from_project()
        if self.alignSettings is not None:
            self.alignSettings.set_from_project()
        if self.stackSettings is not None:
            self.stackSettings.set_from_project()
        if self.tuneSettings is not None:
            self.tuneSettings.set_from_project()

        self.updateReadyStates()

        ref = self.app.workflow.get_reference_file()
        if ref is not None:
            self.showFile(ref)
        elif stars:
            self.showFile(stars[0])
        else:
            self.showFile(None)

    def showFile(self, file: Optional[File]) -> None:
        if hasattr(self.shell, "currentFile"):
            self.shell.currentFile = file
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setFile(file)
        if hasattr(self.shell, "label_imageName") and self.shell.label_imageName is not None:
            self.shell.label_imageName.setText(file.basename if file is not None else "")

    def updateReadyStates(self, _=None) -> None:
        has_stars = bool(hasattr(self.app.workflow, "get_star_files") and self.app.workflow.get_star_files())
        if self.skySettings is not None:
            self.skySettings.refresh_inputs()
        if self.alignSettings is not None:
            self.alignSettings.refresh_inputs()

        has_homographies = bool(
            self.last_align_result is not None
            or (hasattr(self.app.workflow, "project") and getattr(self.app.workflow.project, "homographies", {}))
        )
        if self.stackSettings is not None:
            self.stackSettings.refresh_inputs(ready=has_homographies)

        has_compositor = bool(self.last_compositor is not None)
        if self.tuneSettings is not None:
            self.tuneSettings.refresh_inputs(ready=has_compositor)

        if self.btn_pipeline is not None:
            self.btn_pipeline.setEnabled(has_stars)
        if self.btn_save_output is not None:
            self.btn_save_output.setEnabled(has_compositor)

        # Update StepCard status badges and subtitles matching pyquator
        has_mask = bool(
            hasattr(self.app.workflow, "project") and getattr(self.app.workflow.project, "mask_path", None)
        )
        if self.skyCard is not None:
            self.skyCard.setStatus("done" if has_mask else "ready")
            if has_mask:
                self.skyCard.setSubtitle("Sky mask defined")
            else:
                self.skyCard.setSubtitle("Ready to detect or paint mask")

        if self.alignCard is not None:
            self.alignCard.setStatus("done" if has_homographies else "ready")
            if has_homographies:
                n_homo = len(getattr(self.app.workflow.project, "homographies", {}))
                self.alignCard.setSubtitle(f"{n_homo} frames aligned")
            else:
                self.alignCard.setSubtitle("Requires sky mask" if not has_mask else "Ready to align")

        if self.stackCard is not None:
            self.stackCard.setStatus("done" if has_compositor else "ready")
            if has_compositor:
                self.stackCard.setSubtitle("Base stacks ready")
            else:
                self.stackCard.setSubtitle("Requires aligned stars")

        if self.tuneCard is not None:
            self.tuneCard.setStatus("done" if self._output_saved else "ready")
            if has_compositor:
                self.tuneCard.setSubtitle("Live canvas tuning active")
            else:
                self.tuneCard.setSubtitle("Requires base stacks")

        # Update Operations Progress
        completed = sum([
            1 if has_mask else 0,
            1 if has_homographies else 0,
            1 if has_compositor else 0,
            1 if self._output_saved else 0,
        ])
        if self.lbl_ops_progress is not None:
            self.lbl_ops_progress.setText(f"{completed} of 4 steps complete")
        if self.ops_progress_bar is not None:
            self.ops_progress_bar.setValue(completed)

    # -------------------------------------------------------------------------
    # Denoise Step Operations
    # -------------------------------------------------------------------------

    def do_detect_sky_action(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return

        vals = self.skySettings.values() if self.skySettings else {}

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=2,
                desc="Detecting sky mask...",
            )
            mask = self.app.workflow.do_detect_sky(
                ref.path,
                progressBar=progressUpdater.tick,
                model_type=vals.get("auto_mask_model", "nightstack"),
            )
            if mask is not None:
                mask = self.app.workflow.do_refine_mask(
                    ref.path,
                    mask,
                    progressBar=progressUpdater.tick,
                    search_radius=vals.get("mask_search_radius"),
                    erosion_pixels=vals.get("mask_erosion_pixels", 5),
                )
            if mask is not None and hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                self.shell.canvas_main.setFromNumpyArray((mask * 255).astype(np.uint8), resetZoomAndPosition=False)
            if self.skyCard is not None:
                self.skyCard.setStatus("done")
            self.updateReadyStates()

        self.shell.enqueue_task("detectSky", "Detect Sky", 1, "Running sky detection...", work)

    def do_refine_mask_action(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return
        vals = self.skySettings.values() if self.skySettings else {}
        mask_path = getattr(self.app.workflow.project, "mask_path", None)
        if not mask_path:
            return

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=1,
                desc="Refining sky mask...",
            )
            from startrails.lib.denoise.reader import ImageReader
            existing_mask = ImageReader.read(mask_path).data
            refined = self.app.workflow.do_refine_mask(
                ref.path,
                existing_mask,
                progressBar=progressUpdater.tick,
                search_radius=vals.get("mask_search_radius"),
                erosion_pixels=vals.get("mask_erosion_pixels", 5),
            )
            if refined is not None and hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                self.shell.canvas_main.setFromNumpyArray((refined * 255).astype(np.uint8), resetZoomAndPosition=False)
            if self.skyCard is not None:
                self.skyCard.setStatus("done")
            self.updateReadyStates()

        self.shell.enqueue_task("refineMask", "Refine Mask", 1, "Refining sky mask...", work)

    def do_clear_mask_action(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return
        from startrails.lib.denoise.reader import ImageReader
        img = ImageReader.read(ref.path).data
        h, w = img.shape[:2]
        mask = np.zeros((h, w), dtype=np.float32)
        if hasattr(self.app.workflow, "project"):
            from startrails.lib.denoise.writer import ImageWriter
            out_mask = Path(self.app.workflow.project.projectFile).parent / "mask_sky.tif"
            ImageWriter.write(mask, out_mask)
            self.app.workflow.project.mask_path = str(out_mask)
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setFromNumpyArray((mask * 255).astype(np.uint8), resetZoomAndPosition=False)
        self.updateReadyStates()

    def do_full_frame_mask_action(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return
        from startrails.lib.denoise.reader import ImageReader
        img = ImageReader.read(ref.path).data
        h, w = img.shape[:2]
        mask = np.ones((h, w), dtype=np.float32)
        if hasattr(self.app.workflow, "project"):
            from startrails.lib.denoise.writer import ImageWriter
            out_mask = Path(self.app.workflow.project.projectFile).parent / "mask_sky.tif"
            ImageWriter.write(mask, out_mask)
            self.app.workflow.project.mask_path = str(out_mask)
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setFromNumpyArray((mask * 255).astype(np.uint8), resetZoomAndPosition=False)
        self.updateReadyStates()

    def do_align_stars_action(self) -> None:
        stars = self.app.workflow.get_star_files()
        if not stars:
            return

        vals = self.alignSettings.values() if self.alignSettings else {}

        def work():
            n = len(stars)
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=n,
                desc="Aligning star frames...",
            )
            cfg = self.app.workflow.get_config()
            cfg.warp_frames_for_stacking = vals.get("warp_frames", True)
            cfg.use_gpu = vals.get("use_gpu", True)
            cfg.detector_type = vals.get("detector_type", "auto")
            cfg.max_stars = vals.get("max_stars", 500)

            result = self.app.workflow.do_align_stars(
                config=cfg,
                progressBar=progressUpdater.tick,
            )
            self.last_align_result = result
            if self.alignCard is not None:
                self.alignCard.setStatus("done")
            self.updateReadyStates()

        self.shell.enqueue_task("alignStars", "Align Stars", len(stars), "Aligning frames...", work)

    def do_stack_action(self) -> None:
        if self.last_align_result is None:
            return

        vals = self.stackSettings.values() if self.stackSettings else {}

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=2,
                desc="Stacking sky and ground...",
            )
            cfg = self.app.workflow.get_config()
            cfg.stack_method = vals.get("stack_method", "sigma_clipped")
            cfg.sigma_clip_threshold = vals.get("sigma_clip_threshold", 1.2)
            cfg.sigma_clip_iterations = vals.get("sigma_clip_iterations", 3)
            cfg.use_gpu = vals.get("use_gpu", True)

            compositor = self.app.workflow.do_stack_denoise(
                aligned_sky_frames=self.last_align_result.aligned_sky_frames,
                sky_coverages=self.last_align_result.sky_coverages,
                raw_ground_frames=self.last_align_result.raw_ground_frames,
                sky_mask=self.last_align_result.sky_mask,
                config=cfg,
                progressBar=progressUpdater.tick,
            )
            self.last_compositor = compositor
            if self.stackCard is not None:
                self.stackCard.setStatus("done")
            self.updateReadyStates()

        self.shell.enqueue_task("stackDenoise", "Stack Denoise", 2, "Stacking base frames...", work)

    def do_compose_action(self) -> None:
        if self.last_compositor is None:
            return

        vals = self.tuneSettings.values() if self.tuneSettings else {}

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=1,
                desc="Compositing horizon...",
            )
            cfg = self.app.workflow.get_config()
            cfg.enable_horizon_corrections = vals.get("enable_horizon_corrections", True)
            cfg.denoise_horizon_band = vals.get("denoise_horizon_band", True)
            cfg.horizon_blend_percent = vals.get("horizon_blend_percent", 60.0)
            cfg.horizon_blur_radius = vals.get("horizon_blur_radius", 2.0)
            cfg.horizon_denoise_radius = vals.get("horizon_denoise_radius", 5)
            cfg.horizon_denoise_strength = vals.get("horizon_denoise_strength", 0.2)
            cfg.horizon_color_denoise_strength = vals.get("horizon_color_denoise_strength", 1.0)
            cfg.horizon_value_denoise_strength = vals.get("horizon_value_denoise_strength", 0.2)

            res = self.app.workflow.do_compose_horizon(
                self.last_compositor,
                config=cfg,
                progressBar=progressUpdater.tick,
                sky_coverages=self.last_align_result.sky_coverages if self.last_align_result else None,
            )
            if res and res[0] is not None and hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                img = res[0]
                if img.dtype in (np.float32, np.float64):
                    img = (np.clip(img, 0.0, 1.0) * 255.0).astype(np.uint8)
                self.shell.canvas_main.setFromNumpyArray(img, resetZoomAndPosition=False)
            if self.tuneCard is not None:
                self.tuneCard.setStatus("done")
            self.updateReadyStates()

        self.shell.enqueue_task("composeHorizon", "Compose Horizon", 1, "Compositing final image...", work)

    def do_save_output_action(self) -> None:
        if self.last_compositor is None:
            return
        out_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save Final Image",
            "final_denoise.tif",
            filter="TIFF Image (*.tif *.tiff);;JPEG Image (*.jpg *.jpeg)",
        )
        if not out_path:
            return

        vals = self.tuneSettings.values() if self.tuneSettings else {}
        cfg = self.app.workflow.get_config()
        cfg.output_path = Path(out_path)
        cfg.enable_horizon_corrections = vals.get("enable_horizon_corrections", True)
        cfg.denoise_horizon_band = vals.get("denoise_horizon_band", True)
        cfg.horizon_blend_percent = vals.get("horizon_blend_percent", 60.0)
        cfg.horizon_blur_radius = vals.get("horizon_blur_radius", 2.0)
        cfg.horizon_denoise_radius = vals.get("horizon_denoise_radius", 5)
        cfg.horizon_denoise_strength = vals.get("horizon_denoise_strength", 0.2)
        cfg.horizon_color_denoise_strength = vals.get("horizon_color_denoise_strength", 1.0)
        cfg.horizon_value_denoise_strength = vals.get("horizon_value_denoise_strength", 0.2)

        res = self.app.workflow.do_compose_horizon(
            self.last_compositor,
            config=cfg,
            sky_coverages=self.last_align_result.sky_coverages if self.last_align_result else None,
        )
        if res and res[0] is not None:
            from startrails.lib.denoise.writer import ImageWriter
            ImageWriter.write(res[0], Path(out_path))
            self._output_saved = True
            self.updateReadyStates()

    def do_pipeline_action(self) -> None:
        stars = self.app.workflow.get_star_files()
        if not stars:
            return

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=100,
                desc="Running denoise pipeline...",
            )
            out_path = self.app.workflow.do_pipeline(progressBar=progressUpdater.tick)
            if out_path and Path(out_path).exists() and hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                self.showFile(DenoiseInputFile(basename=Path(out_path).name, path=str(out_path)))
            if self.skyCard is not None:
                self.skyCard.setStatus("done")
            if self.alignCard is not None:
                self.alignCard.setStatus("done")
            if self.stackCard is not None:
                self.stackCard.setStatus("done")
            if self.tuneCard is not None:
                self.tuneCard.setStatus("done")
            self._output_saved = True
            self.updateReadyStates()

        self.shell.enqueue_task("pipeline", "Full Pipeline", len(stars), "Processing denoise pipeline...", work)
