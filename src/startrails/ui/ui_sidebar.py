# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'sidebar.ui'
##
## Created by: Qt User Interface Compiler version 6.8.2
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

class Ui_Sidebar(object):
    def setupUi(self, sidebar):
        if not sidebar.objectName():
            sidebar.setObjectName(u"sidebar")
        sidebar.setMinimumSize(QSize(320, 0))
        sidebar.setMaximumSize(QSize(320, 16777215))
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
"}\n"
"QLabel#projectTitle, QLabel#operationsTitle {\n"
"    font-size: 15px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}\n"
"QLabel#operationsProgressLabel {\n"
"    font-size: 11px;\n"
"    color"
                        ": #64748b;\n"
"    font-weight: 500;\n"
"}\n"
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
"}\n"
"QPushButton#newProject, QPushButton#openProject {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 2px solid #cbd5e1;\n"
"    border-radius: 6px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 500;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#newProject:hover, QPushButton#openProject:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#newProject:pressed, QPushButton#openProject:pressed {\n"
"    background-color: #e2e8f0;\n"
"}\n"
"QPushButton#newProject:focus:enabled, QPushButton#openProject:focus:enabled { border-color: #0f172a; }")
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

        self.contentLayout.addWidget(self.projectTitle)

        self.projectActions = QHBoxLayout()
        self.projectActions.setSpacing(6)
        self.projectActions.setObjectName(u"projectActions")
        self.newProject = QPushButton(self.content)
        self.newProject.setObjectName(u"newProject")
        self.newProject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.projectActions.addWidget(self.newProject)

        self.openProject = QPushButton(self.content)
        self.openProject.setObjectName(u"openProject")
        self.openProject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.projectActions.addWidget(self.openProject)


        self.contentLayout.addLayout(self.projectActions)

        self.inputLayout = QVBoxLayout()
        self.inputLayout.setObjectName(u"inputLayout")

        self.contentLayout.addLayout(self.inputLayout)

        self.outputLayout = QVBoxLayout()
        self.outputLayout.setObjectName(u"outputLayout")

        self.contentLayout.addLayout(self.outputLayout)

        self.operationsHeaderWidget = QWidget(self.content)
        self.operationsHeaderWidget.setObjectName(u"operationsHeaderWidget")
        self.operationsHeaderLayout = QVBoxLayout(self.operationsHeaderWidget)
        self.operationsHeaderLayout.setSpacing(3)
        self.operationsHeaderLayout.setObjectName(u"operationsHeaderLayout")
        self.operationsHeaderLayout.setContentsMargins(0, 4, 0, 0)
        self.operationsTitle = QLabel(self.operationsHeaderWidget)
        self.operationsTitle.setObjectName(u"operationsTitle")

        self.operationsHeaderLayout.addWidget(self.operationsTitle)

        self.operationsProgressLabel = QLabel(self.operationsHeaderWidget)
        self.operationsProgressLabel.setObjectName(u"operationsProgressLabel")

        self.operationsHeaderLayout.addWidget(self.operationsProgressLabel)

        self.operationsProgress = QProgressBar(self.operationsHeaderWidget)
        self.operationsProgress.setObjectName(u"operationsProgress")
        self.operationsProgress.setMaximum(4)
        self.operationsProgress.setValue(0)
        self.operationsProgress.setTextVisible(False)

        self.operationsHeaderLayout.addWidget(self.operationsProgress)


        self.contentLayout.addWidget(self.operationsHeaderWidget)

        self.detectLayout = QVBoxLayout()
        self.detectLayout.setObjectName(u"detectLayout")

        self.contentLayout.addLayout(self.detectLayout)

        self.stackLayout = QVBoxLayout()
        self.stackLayout.setObjectName(u"stackLayout")

        self.contentLayout.addLayout(self.stackLayout)

        self.reviewLayout = QVBoxLayout()
        self.reviewLayout.setObjectName(u"reviewLayout")

        self.contentLayout.addLayout(self.reviewLayout)

        self.fillLayout = QVBoxLayout()
        self.fillLayout.setObjectName(u"fillLayout")

        self.contentLayout.addLayout(self.fillLayout)

        self.toolsLayout = QVBoxLayout()
        self.toolsLayout.setObjectName(u"toolsLayout")

        self.contentLayout.addLayout(self.toolsLayout)

        self.bottomSpace = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.contentLayout.addItem(self.bottomSpace)

        self.scroll.setWidget(self.content)

        self.layout.addWidget(self.scroll)


        self.retranslateUi(sidebar)

        QMetaObject.connectSlotsByName(sidebar)
    # setupUi

    def retranslateUi(self, sidebar):
        self.projectTitle.setText(QCoreApplication.translate("Sidebar", u"Project Images", None))
        self.newProject.setText(QCoreApplication.translate("Sidebar", u"New Project", None))
        self.openProject.setText(QCoreApplication.translate("Sidebar", u"Open Project", None))
        self.operationsTitle.setText(QCoreApplication.translate("Sidebar", u"Operations", None))
        self.operationsProgressLabel.setText(QCoreApplication.translate("Sidebar", u"0 of 4 steps complete", None))
        pass
    # retranslateUi
