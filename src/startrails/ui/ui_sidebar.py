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
    QPushButton, QScrollArea, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_Sidebar(object):
    def setupUi(self, sidebar):
        if not sidebar.objectName():
            sidebar.setObjectName(u"sidebar")
        sidebar.setMinimumSize(QSize(360, 0))
        self.layout = QVBoxLayout(sidebar)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(sidebar)
        self.scroll.setObjectName(u"scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName(u"content")
        self.contentLayout = QVBoxLayout(self.content)
        self.contentLayout.setSpacing(10)
        self.contentLayout.setObjectName(u"contentLayout")
        self.projectTitle = QLabel(self.content)
        self.projectTitle.setObjectName(u"projectTitle")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.projectTitle.setFont(font)

        self.contentLayout.addWidget(self.projectTitle)

        self.projectActions = QHBoxLayout()
        self.projectActions.setObjectName(u"projectActions")
        self.newProject = QPushButton(self.content)
        self.newProject.setObjectName(u"newProject")

        self.projectActions.addWidget(self.newProject)

        self.openProject = QPushButton(self.content)
        self.openProject.setObjectName(u"openProject")

        self.projectActions.addWidget(self.openProject)


        self.contentLayout.addLayout(self.projectActions)

        self.inputLayout = QVBoxLayout()
        self.inputLayout.setObjectName(u"inputLayout")

        self.contentLayout.addLayout(self.inputLayout)

        self.outputLayout = QVBoxLayout()
        self.outputLayout.setObjectName(u"outputLayout")

        self.contentLayout.addLayout(self.outputLayout)

        self.operationsTitle = QLabel(self.content)
        self.operationsTitle.setObjectName(u"operationsTitle")
        self.operationsTitle.setFont(font)

        self.contentLayout.addWidget(self.operationsTitle)

        self.detectLayout = QVBoxLayout()
        self.detectLayout.setObjectName(u"detectLayout")

        self.contentLayout.addLayout(self.detectLayout)

        self.stackLayout = QVBoxLayout()
        self.stackLayout.setObjectName(u"stackLayout")

        self.contentLayout.addLayout(self.stackLayout)

        self.fillLayout = QVBoxLayout()
        self.fillLayout.setObjectName(u"fillLayout")

        self.contentLayout.addLayout(self.fillLayout)

        self.exportLayout = QVBoxLayout()
        self.exportLayout.setObjectName(u"exportLayout")

        self.contentLayout.addLayout(self.exportLayout)

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
        pass
    # retranslateUi
