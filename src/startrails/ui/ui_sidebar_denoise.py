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

class Ui_SidebarDenoise(object):
    def setupUi(self, sidebar):
        if not sidebar.objectName():
            sidebar.setObjectName(u"sidebar")
        sidebar.setMinimumSize(QSize(0, 0))
        sidebar.setMaximumSize(QSize(16777215, 16777215))
        sidebar.setStyleSheet(u"QWidget#sidebar {\n"
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
        self.layout = QVBoxLayout(sidebar)
        self.layout.setSpacing(0)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(sidebar)
        self.scroll.setObjectName(u"scroll")
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content.setObjectName(u"content")
        self.contentLayout = QVBoxLayout(self.content)
        self.contentLayout.setSpacing(8)
        self.contentLayout.setObjectName(u"contentLayout")
        self.contentLayout.setContentsMargins(8, 8, 8, 8)
        self.projectTitle = QLabel(self.content)
        self.projectTitle.setObjectName(u"projectTitle")
        self.projectTitle.setStyleSheet(u"QLabel#projectTitle {\n"
"    font-size: 15px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}")

        self.contentLayout.addWidget(self.projectTitle)

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

        self.starFilesLayout = QVBoxLayout()
        self.starFilesLayout.setObjectName(u"starFilesLayout")

        self.contentLayout.addLayout(self.starFilesLayout)

        self.noiseFilesLayout = QVBoxLayout()
        self.noiseFilesLayout.setObjectName(u"noiseFilesLayout")

        self.contentLayout.addLayout(self.noiseFilesLayout)

        self.outputFilesLayout = QVBoxLayout()
        self.outputFilesLayout.setObjectName(u"outputFilesLayout")

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

        self.operationsProgressLabel = QLabel(self.operationsHeaderWidget)
        self.operationsProgressLabel.setObjectName(u"operationsProgressLabel")
        self.operationsProgressLabel.setStyleSheet(u"QLabel#operationsProgressLabel {\n"
"    font-size: 11px;\n"
"    color: #64748b;\n"
"    font-weight: 500;\n"
"}")

        self.operationsHeaderLayout.addWidget(self.operationsProgressLabel)

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

        self.operationsHeaderLayout.addWidget(self.operationsProgress)


        self.contentLayout.addWidget(self.operationsHeaderWidget)

        self.skyLayout = QVBoxLayout()
        self.skyLayout.setObjectName(u"skyLayout")

        self.contentLayout.addLayout(self.skyLayout)

        self.alignLayout = QVBoxLayout()
        self.alignLayout.setObjectName(u"alignLayout")

        self.contentLayout.addLayout(self.alignLayout)

        self.stackLayout = QVBoxLayout()
        self.stackLayout.setObjectName(u"stackLayout")

        self.contentLayout.addLayout(self.stackLayout)

        self.tuneLayout = QVBoxLayout()
        self.tuneLayout.setObjectName(u"tuneLayout")

        self.contentLayout.addLayout(self.tuneLayout)

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

        self.pipelineProgressBar = QProgressBar(self.content)
        self.pipelineProgressBar.setObjectName(u"pipelineProgressBar")
        self.pipelineProgressBar.setStyleSheet(u"QProgressBar#pipelineProgressBar {\n"
"    background-color: #e2e8f0;\n"
"    border-radius: 2px;\n"
"    max-height: 4px;\n"
"    min-height: 4px;\n"
"    border: none;\n"
"}\n"
"QProgressBar#pipelineProgressBar::chunk {\n"
"    background-color: #0284c7;\n"
"    border-radius: 2px;\n"
"}")
        self.pipelineProgressBar.setMaximum(100)
        self.pipelineProgressBar.setValue(0)
        self.pipelineProgressBar.setTextVisible(False)

        self.contentLayout.addWidget(self.pipelineProgressBar)

        self.pipelineStatusLabel = QLabel(self.content)
        self.pipelineStatusLabel.setObjectName(u"pipelineStatusLabel")
        self.pipelineStatusLabel.setStyleSheet(u"QLabel#pipelineStatusLabel {\n"
"    color: #64748b;\n"
"    font-size: 11px;\n"
"}")
        self.pipelineStatusLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.contentLayout.addWidget(self.pipelineStatusLabel)

        self.bottomSpace = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.contentLayout.addItem(self.bottomSpace)

        self.scroll.setWidget(self.content)

        self.layout.addWidget(self.scroll)


        self.retranslateUi(sidebar)

        QMetaObject.connectSlotsByName(sidebar)
    # setupUi

    def retranslateUi(self, sidebar):
        self.projectTitle.setText(QCoreApplication.translate("SidebarDenoise", u"Project Images", None))
#if QT_CONFIG(tooltip)
        self.newProject.setToolTip(QCoreApplication.translate("SidebarDenoise", u"Create a new project", None))
#endif // QT_CONFIG(tooltip)
        self.newProject.setText(QCoreApplication.translate("SidebarDenoise", u"New Project", None))
#if QT_CONFIG(tooltip)
        self.openProject.setToolTip(QCoreApplication.translate("SidebarDenoise", u"Open an existing project", None))
#endif // QT_CONFIG(tooltip)
        self.openProject.setText(QCoreApplication.translate("SidebarDenoise", u"Open Project", None))
        self.operationsTitle.setText(QCoreApplication.translate("SidebarDenoise", u"Operations", None))
        self.operationsProgressLabel.setText(QCoreApplication.translate("SidebarDenoise", u"0 of 4 steps complete", None))
        self.saveOutput.setText(QCoreApplication.translate("SidebarDenoise", u"Save Image", None))
        self.runPipeline.setText(QCoreApplication.translate("SidebarDenoise", u"\u25b6 Run Full Denoise Pipeline", None))
        self.pipelineStatusLabel.setText(QCoreApplication.translate("SidebarDenoise", u"Ready", None))
        pass
    # retranslateUi

Ui_sidebarDenoise = Ui_SidebarDenoise
