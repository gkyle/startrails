# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'sidebar_denoise.ui'
##
## Created by: Qt User Interface Compiler version 6.12.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget)

from startrails.ui.file_manager import FileSection
from startrails.ui.steps import StepCard
from startrails.ui.steps_denoise import (DenoiseAlignSettings, DenoiseExportSettings, DenoiseSkySettings, DenoiseStackSettings,
    DenoiseTuneSettings)
from . import resources_rc

class Ui_SidebarDenoise(object):
    def setupUi(self, SidebarDenoise):
        if not SidebarDenoise.objectName():
            SidebarDenoise.setObjectName(u"SidebarDenoise")
        SidebarDenoise.resize(213, 305)
        SidebarDenoise.setMinimumSize(QSize(0, 0))
        SidebarDenoise.setMaximumSize(QSize(16777215, 16777215))
        SidebarDenoise.setStyleSheet(u"QWidget#SidebarDenoise {\n"
"    background-color: #f8fafc;\n"
"}\n"
"QScrollArea#scroll {\n"
"    border: none;\n"
"    background: transparent;\n"
"}\n"
"QWidget#content {\n"
"    background-color: #f8fafc;\n"
"}\n"
"QScrollBar:vertical {\n"
"    border: none;\n"
"    background: #f1f5f9;\n"
"    width: 6px;\n"
"    border-radius: 3px;\n"
"    margin: 2px 0px 2px 0px;\n"
"}\n"
"QScrollBar::handle:vertical {\n"
"    background: #cbd5e1;\n"
"    min-height: 24px;\n"
"    border-radius: 3px;\n"
"}\n"
"QScrollBar::handle:vertical:hover {\n"
"    background: #94a3b8;\n"
"}\n"
"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {\n"
"    height: 0px;\n"
"}\n"
"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {\n"
"    background: none;\n"
"}\n"
"QScrollBar:horizontal {\n"
"    height: 0px;\n"
"}")
        self.layout = QVBoxLayout(SidebarDenoise)
        self.layout.setSpacing(0)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(SidebarDenoise)
        self.scroll.setObjectName(u"scroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content.setObjectName(u"content")
        self.content.setGeometry(QRect(0, 0, 213, 320))
        self.contentLayout = QVBoxLayout(self.content)
        self.contentLayout.setSpacing(8)
        self.contentLayout.setObjectName(u"contentLayout")
        self.contentLayout.setContentsMargins(8, 8, 8, 8)
        self.projectActions = QHBoxLayout()
        self.projectActions.setSpacing(6)
        self.projectActions.setObjectName(u"projectActions")
        self.newProject = QPushButton(self.content)
        self.newProject.setObjectName(u"newProject")
        self.newProject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.newProject.setStyleSheet(u"QPushButton#newProject {\n"
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
"}")

        self.projectActions.addWidget(self.newProject)

        self.openProject = QPushButton(self.content)
        self.openProject.setObjectName(u"openProject")
        self.openProject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.openProject.setStyleSheet(u"QPushButton#openProject {\n"
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
"}")

        self.projectActions.addWidget(self.openProject)


        self.contentLayout.addLayout(self.projectActions)

        self.projectTitle = QLabel(self.content)
        self.projectTitle.setObjectName(u"projectTitle")
        self.projectTitle.setStyleSheet(u"QLabel#projectTitle {\n"
"    font-size: 15px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}")

        self.contentLayout.addWidget(self.projectTitle)

        self.starFilesLayout = QVBoxLayout()
        self.starFilesLayout.setObjectName(u"starFilesLayout")
        self.starFiles = FileSection(self.content)
        self.starFiles.setObjectName(u"starFiles")
        self.starFiles.setProperty(u"inputs", True)
        self.starFiles.setProperty(u"show_legend", False)
        self.starFiles.setProperty(u"is_expanded", True)

        self.starFilesLayout.addWidget(self.starFiles)


        self.contentLayout.addLayout(self.starFilesLayout)

        self.noiseFilesLayout = QVBoxLayout()
        self.noiseFilesLayout.setObjectName(u"noiseFilesLayout")
        self.noiseFiles = FileSection(self.content)
        self.noiseFiles.setObjectName(u"noiseFiles")
        self.noiseFiles.setProperty(u"inputs", True)
        self.noiseFiles.setProperty(u"show_legend", False)
        self.noiseFiles.setProperty(u"is_expanded", False)

        self.noiseFilesLayout.addWidget(self.noiseFiles)


        self.contentLayout.addLayout(self.noiseFilesLayout)

        self.outputFilesLayout = QVBoxLayout()
        self.outputFilesLayout.setObjectName(u"outputFilesLayout")
        self.outputFiles = FileSection(self.content)
        self.outputFiles.setObjectName(u"outputFiles")
        self.outputFiles.setProperty(u"inputs", False)
        self.outputFiles.setProperty(u"show_legend", False)
        self.outputFiles.setProperty(u"is_expanded", True)

        self.outputFilesLayout.addWidget(self.outputFiles)


        self.contentLayout.addLayout(self.outputFilesLayout)

        self.operationsHeaderWidget = QWidget(self.content)
        self.operationsHeaderWidget.setObjectName(u"operationsHeaderWidget")
        self.operationsHeaderLayout = QVBoxLayout(self.operationsHeaderWidget)
        self.operationsHeaderLayout.setSpacing(3)
        self.operationsHeaderLayout.setObjectName(u"operationsHeaderLayout")
        self.operationsHeaderLayout.setContentsMargins(0, 4, 0, 0)
        self.operationsTitle = QLabel(self.operationsHeaderWidget)
        self.operationsTitle.setObjectName(u"operationsTitle")
        self.operationsTitle.setStyleSheet(u"QLabel#operationsTitle {\n"
"    font-size: 15px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}")

        self.operationsHeaderLayout.addWidget(self.operationsTitle)

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(10, 6, 10, 6)
        self.operationsProgressLabel = QLabel(self.operationsHeaderWidget)
        self.operationsProgressLabel.setObjectName(u"operationsProgressLabel")
        self.operationsProgressLabel.setStyleSheet(u"QLabel#operationsProgressLabel {\n"
"    font-size: 11px;\n"
"    color: #64748b;\n"
"    font-weight: 500;\n"
"}")

        self.verticalLayout.addWidget(self.operationsProgressLabel)

        self.operationsProgress = QProgressBar(self.operationsHeaderWidget)
        self.operationsProgress.setObjectName(u"operationsProgress")
        self.operationsProgress.setStyleSheet(u"QProgressBar#operationsProgress {\n"
"    background-color: #e2e8f0;\n"
"    border-radius: 3px;\n"
"    max-height: 6px;\n"
"    min-height: 6px;\n"
"    border: none;\n"
"}\n"
"QProgressBar#operationsProgress::chunk {\n"
"    background-color: #16a34a;\n"
"    border-radius: 3px;\n"
"}")
        self.operationsProgress.setMaximum(4)
        self.operationsProgress.setValue(0)
        self.operationsProgress.setTextVisible(False)

        self.verticalLayout.addWidget(self.operationsProgress)


        self.operationsHeaderLayout.addLayout(self.verticalLayout)


        self.contentLayout.addWidget(self.operationsHeaderWidget)

        self.skyLayout = QVBoxLayout()
        self.skyLayout.setObjectName(u"skyLayout")
        self.skyCard = StepCard(self.content)
        self.skyCard.setObjectName(u"skyCard")
        self.skyCard.setProperty(u"step_number", 1)
        self.skyCard.setProperty(u"is_expanded", True)
        self.skySettings = DenoiseSkySettings(self.skyCard)
        self.skySettings.setObjectName(u"skySettings")
        self.skySettings.setGeometry(QRect(0, 0, 100, 30))
        self.skyCard.add_body(self.skySettings)

        self.skyLayout.addWidget(self.skyCard)


        self.contentLayout.addLayout(self.skyLayout)

        self.alignLayout = QVBoxLayout()
        self.alignLayout.setObjectName(u"alignLayout")
        self.alignCard = StepCard(self.content)
        self.alignCard.setObjectName(u"alignCard")
        self.alignCard.setProperty(u"step_number", 2)
        self.alignCard.setProperty(u"is_expanded", False)
        self.alignSettings = DenoiseAlignSettings(self.alignCard)
        self.alignSettings.setObjectName(u"alignSettings")
        self.alignSettings.setGeometry(QRect(0, 0, 100, 30))
        self.alignCard.add_body(self.alignSettings)

        self.alignLayout.addWidget(self.alignCard)


        self.contentLayout.addLayout(self.alignLayout)

        self.stackLayout = QVBoxLayout()
        self.stackLayout.setObjectName(u"stackLayout")
        self.stackCard = StepCard(self.content)
        self.stackCard.setObjectName(u"stackCard")
        self.stackCard.setProperty(u"step_number", 3)
        self.stackCard.setProperty(u"is_expanded", False)
        self.stackSettings = DenoiseStackSettings(self.stackCard)
        self.stackSettings.setObjectName(u"stackSettings")
        self.stackSettings.setGeometry(QRect(0, 0, 100, 30))
        self.stackCard.add_body(self.stackSettings)

        self.stackLayout.addWidget(self.stackCard)


        self.contentLayout.addLayout(self.stackLayout)

        self.tuneLayout = QVBoxLayout()
        self.tuneLayout.setObjectName(u"tuneLayout")
        self.tuneCard = StepCard(self.content)
        self.tuneCard.setObjectName(u"tuneCard")
        self.tuneCard.setProperty(u"step_number", 4)
        self.tuneCard.setProperty(u"is_expanded", False)
        self.tuneSettings = DenoiseTuneSettings(self.tuneCard)
        self.tuneSettings.setObjectName(u"tuneSettings")
        self.tuneSettings.setGeometry(QRect(0, 0, 100, 30))
        self.tuneCard.add_body(self.tuneSettings)

        self.tuneLayout.addWidget(self.tuneCard)


        self.contentLayout.addLayout(self.tuneLayout)

        self.exportLayout = QVBoxLayout()
        self.exportLayout.setObjectName(u"exportLayout")
        self.exportCard = StepCard(self.content)
        self.exportCard.setObjectName(u"exportCard")
        self.exportCard.setProperty(u"is_expanded", False)
        self.exportSettings = DenoiseExportSettings(self.exportCard)
        self.exportSettings.setObjectName(u"exportSettings")
        self.exportSettings.setGeometry(QRect(0, 0, 100, 30))
        self.exportCard.add_body(self.exportSettings)

        self.exportLayout.addWidget(self.exportCard)


        self.contentLayout.addLayout(self.exportLayout)

        self.saveOutput = QPushButton(self.content)
        self.saveOutput.setObjectName(u"saveOutput")
        self.saveOutput.setEnabled(False)
        self.saveOutput.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.saveOutput.setStyleSheet(u"QPushButton#saveOutput {\n"
"    background-color: #f1f5f9;\n"
"    color: #1e293b;\n"
"    font-weight: bold;\n"
"    font-size: 13px;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 4px;\n"
"    min-height: 36px;\n"
"    max-height: 36px;\n"
"}\n"
"QPushButton#saveOutput:hover {\n"
"    background-color: #e2e8f0;\n"
"}\n"
"QPushButton#saveOutput:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"}")

        self.contentLayout.addWidget(self.saveOutput)

        self.runPipeline = QPushButton(self.content)
        self.runPipeline.setObjectName(u"runPipeline")
        self.runPipeline.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.runPipeline.setStyleSheet(u"QPushButton#runPipeline {\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    font-weight: bold;\n"
"    font-size: 13px;\n"
"    border-radius: 6px;\n"
"    border: none;\n"
"    min-height: 36px;\n"
"    max-height: 36px;\n"
"}\n"
"QPushButton#runPipeline:hover {\n"
"    background-color: #075985;\n"
"}\n"
"QPushButton#runPipeline:disabled {\n"
"    background-color: #cbd5e1;\n"
"    color: #94a3b8;\n"
"}")

        self.contentLayout.addWidget(self.runPipeline)

        self.bottomSpace = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.contentLayout.addItem(self.bottomSpace)

        self.scroll.setWidget(self.content)

        self.layout.addWidget(self.scroll)


        self.retranslateUi(SidebarDenoise)

        QMetaObject.connectSlotsByName(SidebarDenoise)
    # setupUi

    def retranslateUi(self, SidebarDenoise):
#if QT_CONFIG(tooltip)
        self.newProject.setToolTip(QCoreApplication.translate("SidebarDenoise", u"Create a new project", None))
#endif // QT_CONFIG(tooltip)
        self.newProject.setText(QCoreApplication.translate("SidebarDenoise", u"New Project", None))
#if QT_CONFIG(tooltip)
        self.openProject.setToolTip(QCoreApplication.translate("SidebarDenoise", u"Open an existing project", None))
#endif // QT_CONFIG(tooltip)
        self.openProject.setText(QCoreApplication.translate("SidebarDenoise", u"Open Project", None))
        self.projectTitle.setText(QCoreApplication.translate("SidebarDenoise", u"Project Images", None))
        self.starFiles.setProperty(u"title", QCoreApplication.translate("SidebarDenoise", u"Star Images", None))
        self.noiseFiles.setProperty(u"title", QCoreApplication.translate("SidebarDenoise", u"Dark Frames", None))
        self.outputFiles.setProperty(u"title", QCoreApplication.translate("SidebarDenoise", u"Output Files", None))
        self.operationsTitle.setText(QCoreApplication.translate("SidebarDenoise", u"Operations", None))
        self.operationsProgressLabel.setText(QCoreApplication.translate("SidebarDenoise", u"0 of 4 steps complete", None))
        self.skyCard.setProperty(u"title", QCoreApplication.translate("SidebarDenoise", u"Define Sky Region", None))
        self.skyCard.setProperty(u"subtitle", QCoreApplication.translate("SidebarDenoise", u"Ready to detect or paint mask", None))
        self.alignCard.setProperty(u"title", QCoreApplication.translate("SidebarDenoise", u"Align Stars", None))
        self.alignCard.setProperty(u"subtitle", QCoreApplication.translate("SidebarDenoise", u"Requires sky mask", None))
        self.stackCard.setProperty(u"title", QCoreApplication.translate("SidebarDenoise", u"Stack Sky and Ground", None))
        self.stackCard.setProperty(u"subtitle", QCoreApplication.translate("SidebarDenoise", u"Requires aligned stars", None))
        self.tuneCard.setProperty(u"title", QCoreApplication.translate("SidebarDenoise", u"Tune Horizon", None))
        self.tuneCard.setProperty(u"subtitle", QCoreApplication.translate("SidebarDenoise", u"Requires base stacks", None))
        self.exportCard.setProperty(u"title", QCoreApplication.translate("SidebarDenoise", u"Contribute and Export", None))
        self.exportCard.setProperty(u"subtitle", QCoreApplication.translate("SidebarDenoise", u"Optional utilities", None))
        self.saveOutput.setText(QCoreApplication.translate("SidebarDenoise", u"Save Image", None))
        self.runPipeline.setText(QCoreApplication.translate("SidebarDenoise", u"\u25b6 Run Full Denoise Pipeline", None))
        pass
    # retranslateUi

Ui_sidebarDenoise = Ui_SidebarDenoise
