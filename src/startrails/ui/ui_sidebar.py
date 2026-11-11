# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'sidebar.ui'
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

class Ui_Sidebar(object):
    def setupUi(self, Sidebar):
        if not Sidebar.objectName():
            Sidebar.setObjectName(u"Sidebar")
        Sidebar.resize(200, 215)
        Sidebar.setMinimumSize(QSize(200, 0))
        Sidebar.setMaximumSize(QSize(200, 16777215))
        self.layout = QVBoxLayout(Sidebar)
        self.layout.setSpacing(0)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(Sidebar)
        self.scroll.setObjectName(u"scroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content.setObjectName(u"content")
        self.content.setGeometry(QRect(0, 0, 213, 230))
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

        self.projectActions.addWidget(self.newProject)

        self.openProject = QPushButton(self.content)
        self.openProject.setObjectName(u"openProject")
        self.openProject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.projectActions.addWidget(self.openProject)


        self.contentLayout.addLayout(self.projectActions)

        self.projectTitle = QLabel(self.content)
        self.projectTitle.setObjectName(u"projectTitle")

        self.contentLayout.addWidget(self.projectTitle)

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

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(10, 6, 10, 6)
        self.operationsProgressLabel = QLabel(self.operationsHeaderWidget)
        self.operationsProgressLabel.setObjectName(u"operationsProgressLabel")

        self.verticalLayout.addWidget(self.operationsProgressLabel)

        self.operationsProgress = QProgressBar(self.operationsHeaderWidget)
        self.operationsProgress.setObjectName(u"operationsProgress")
        self.operationsProgress.setMaximum(4)
        self.operationsProgress.setValue(0)
        self.operationsProgress.setTextVisible(False)

        self.verticalLayout.addWidget(self.operationsProgress)


        self.operationsHeaderLayout.addLayout(self.verticalLayout)


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


        self.retranslateUi(Sidebar)

        QMetaObject.connectSlotsByName(Sidebar)
    # setupUi

    def retranslateUi(self, Sidebar):
        self.newProject.setText(QCoreApplication.translate("Sidebar", u"New Project", None))
        self.openProject.setText(QCoreApplication.translate("Sidebar", u"Open Project", None))
        self.projectTitle.setText(QCoreApplication.translate("Sidebar", u"Project Images", None))
        self.operationsTitle.setText(QCoreApplication.translate("Sidebar", u"Operations", None))
        self.operationsProgressLabel.setText(QCoreApplication.translate("Sidebar", u"0 of 4 steps complete", None))
        pass
    # retranslateUi

Ui_sidebar = Ui_Sidebar
