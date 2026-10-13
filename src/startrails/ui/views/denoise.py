"""Denoise mode sidebar view and workflow controller."""

from __future__ import annotations
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
import numpy as np
from PySide6.QtCore import Slot, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from startrails.lib.file import File, DenoiseInputFile
from startrails.ui.file_manager import FileSection
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.views.base import ModeView

if TYPE_CHECKING:
    from startrails.app import App
    from startrails.ui.ui_wrap import Ui_AppWindow


class DenoiseView(ModeView):
    """View controller managing the Denoise sidebar, input lists, and denoising pipeline."""

    mode_name: str = "denoise"

    def __init__(self, app: App, shell: Any):
        super().__init__(app, shell)
        self.sidebar: Optional[QWidget] = None
        self.starFiles: Optional[FileSection] = None
        self.noiseFiles: Optional[FileSection] = None
        self.vignettingFiles: Optional[FileSection] = None

        self.pushButton_newProject: Optional[QPushButton] = None
        self.pushButton_openProject: Optional[QPushButton] = None
        self.btn_detect_sky: Optional[QPushButton] = None
        self.btn_align_stars: Optional[QPushButton] = None
        self.btn_stack: Optional[QPushButton] = None
        self.btn_compose: Optional[QPushButton] = None
        self.btn_pipeline: Optional[QPushButton] = None

        self.last_compositor: Any = None
        self.last_align_result: Any = None

    def build_sidebar(self, parent: QWidget) -> QWidget:
        if self.sidebar is not None and self.sidebar.parent() is parent:
            return self.sidebar

        sidebar = QWidget(parent)
        sidebar.setObjectName("denoiseSidebar")
        sidebar.setMinimumWidth(320)
        sidebar.setMaximumWidth(320)
        sidebar.setStyleSheet("QWidget#denoiseSidebar { background-color: #f8fafc; border-right: 1px solid #e2e8f0; }")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header with Project actions
        header_frame = QFrame(sidebar)
        header_frame.setStyleSheet("background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(6)

        self.pushButton_newProject = QPushButton("New", header_frame)
        self.pushButton_newProject.setToolTip("Create a new project")
        self.pushButton_openProject = QPushButton("Open", header_frame)
        self.pushButton_openProject.setToolTip("Open an existing project")

        mode_badge = QLabel("DENOISE", header_frame)
        mode_badge.setStyleSheet("font-size: 10px; font-weight: bold; color: #3b82f6; background-color: #eff6ff; padding: 2px 6px; border-radius: 4px;")
        mode_badge.setAlignment(Qt.AlignCenter)

        header_layout.addWidget(self.pushButton_newProject)
        header_layout.addWidget(self.pushButton_openProject)
        header_layout.addStretch()
        header_layout.addWidget(mode_badge)
        layout.addWidget(header_frame)

        # Scrollable body
        scroll = QScrollArea(sidebar)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        # File Sections
        self.starFiles = FileSection("Star Images", inputs=True)
        self.noiseFiles = FileSection("Dark / Noise Frames", inputs=True)
        self.vignettingFiles = FileSection("Flat / Vignetting Frames", inputs=True)

        content_layout.addWidget(self.starFiles)
        content_layout.addWidget(self.noiseFiles)
        content_layout.addWidget(self.vignettingFiles)

        # Pipeline Operations Card
        ops_card = QFrame(content)
        ops_card.setStyleSheet("background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px;")
        ops_layout = QVBoxLayout(ops_card)
        ops_layout.setContentsMargins(6, 6, 6, 6)
        ops_layout.setSpacing(6)

        title = QLabel("Denoise Pipeline Steps", ops_card)
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #0f172a;")
        ops_layout.addWidget(title)

        self.btn_detect_sky = QPushButton("1. Detect Celestial Sky", ops_card)
        self.btn_align_stars = QPushButton("2. Align Stars (Homography)", ops_card)
        self.btn_stack = QPushButton("3. Stack Sky & Ground", ops_card)
        self.btn_compose = QPushButton("4. Horizon Composite", ops_card)
        self.btn_pipeline = QPushButton("▶ Run Full Denoise Pipeline", ops_card)
        self.btn_pipeline.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: bold; padding: 6px; border-radius: 4px;")

        ops_layout.addWidget(self.btn_detect_sky)
        ops_layout.addWidget(self.btn_align_stars)
        ops_layout.addWidget(self.btn_stack)
        ops_layout.addWidget(self.btn_compose)
        ops_layout.addWidget(self.btn_pipeline)

        content_layout.addWidget(ops_card)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.sidebar = sidebar
        self.sidebar_widget = sidebar
        return sidebar

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
        if self.btn_align_stars is not None:
            self.connect_signal(self.btn_align_stars.clicked, self.do_align_stars_action)
        if self.btn_stack is not None:
            self.connect_signal(self.btn_stack.clicked, self.do_stack_action)
        if self.btn_compose is not None:
            self.connect_signal(self.btn_compose.clicked, self.do_compose_action)
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
        if self.btn_detect_sky is not None:
            self.btn_detect_sky.setEnabled(has_stars)
        if self.btn_align_stars is not None:
            self.btn_align_stars.setEnabled(has_stars)
        if self.btn_stack is not None:
            self.btn_stack.setEnabled(has_stars)
        if self.btn_compose is not None:
            self.btn_compose.setEnabled(self.last_compositor is not None)
        if self.btn_pipeline is not None:
            self.btn_pipeline.setEnabled(has_stars)

    # -------------------------------------------------------------------------
    # Denoise Step Operations
    # -------------------------------------------------------------------------

    def do_detect_sky_action(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=1,
                desc="Detecting sky mask...",
            )
            mask = self.app.workflow.do_detect_sky(ref.path, progressBar=progressUpdater.tick)
            if mask is not None and hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                self.shell.canvas_main.setFromNumpyArray((mask * 255).astype(np.uint8), resetZoomAndPosition=False)

        self.shell.enqueue_task("detectSky", "Detect Sky", 1, "Running sky detection...", work)

    def do_align_stars_action(self) -> None:
        def work():
            n = len(self.app.workflow.get_star_files())
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=n,
                desc="Aligning star frames...",
            )
            self.last_align_result = self.app.workflow.do_align_stars(progressBar=progressUpdater.tick)
            self.updateReadyStates()

        self.shell.enqueue_task("alignStars", "Align Stars", len(self.app.workflow.get_star_files()), "Aligning frames...", work)

    def do_stack_action(self) -> None:
        if self.last_align_result is None:
            return

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=2,
                desc="Stacking sky and ground...",
            )
            compositor = self.app.workflow.do_stack_denoise(
                aligned_sky_frames=self.last_align_result.aligned_sky_frames,
                sky_coverages=self.last_align_result.sky_coverages,
                raw_ground_frames=self.last_align_result.raw_ground_frames,
                sky_mask=self.last_align_result.sky_mask,
                progressBar=progressUpdater.tick,
            )
            self.last_compositor = compositor
            self.updateReadyStates()

        self.shell.enqueue_task("stackDenoise", "Stack Denoise", 2, "Stacking base frames...", work)

    def do_compose_action(self) -> None:
        if self.last_compositor is None:
            return

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=1,
                desc="Compositing horizon...",
            )
            res = self.app.workflow.do_compose_horizon(
                self.last_compositor,
                progressBar=progressUpdater.tick,
                sky_coverages=self.last_align_result.sky_coverages if self.last_align_result else None,
            )
            if res and res[0] is not None and hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                self.shell.canvas_main.setFromNumpyArray(res[0], resetZoomAndPosition=False)

        self.shell.enqueue_task("composeHorizon", "Compose Horizon", 1, "Compositing final image...", work)

    def do_pipeline_action(self) -> None:
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

        n = len(self.app.workflow.get_star_files())
        self.shell.enqueue_task("pipeline", "Full Pipeline", n, "Processing denoise pipeline...", work)
