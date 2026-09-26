# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'file_manager.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QSizePolicy,
    QToolButton, QTreeView, QVBoxLayout, QWidget)

class Ui_FileSection(object):
    def setupUi(self, fileSection):
        if not fileSection.objectName():
            fileSection.setObjectName(u"fileSection")
        fileSection.setStyleSheet(u"QFrame#fileSection { border: 1px solid palette(mid); border-radius: 8px; }\n"
"QToolButton#toggle { border: none; font-weight: bold; padding: 6px; }\n"
"QToolButton#toggle:hover { background: palette(alternate-base); }\n"
"QToolButton#toggle:focus { border: 1px solid palette(highlight); }")
        self.layout = QVBoxLayout(fileSection)
        self.layout.setSpacing(6)
        self.layout.setObjectName(u"layout")
        self.header = QHBoxLayout()
        self.header.setObjectName(u"header")
        self.toggle = QToolButton(fileSection)
        self.toggle.setObjectName(u"toggle")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.toggle.sizePolicy().hasHeightForWidth())
        self.toggle.setSizePolicy(sizePolicy)
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.RightArrow)

        self.header.addWidget(self.toggle)

        self.count = QLabel(fileSection)
        self.count.setObjectName(u"count")

        self.header.addWidget(self.count)

        self.add = QPushButton(fileSection)
        self.add.setObjectName(u"add")

        self.header.addWidget(self.add)


        self.layout.addLayout(self.header)

        self.body = QWidget(fileSection)
        self.body.setObjectName(u"body")
        self.bodyLayout = QVBoxLayout(self.body)
        self.bodyLayout.setObjectName(u"bodyLayout")
        self.bodyLayout.setContentsMargins(0, 0, 0, 0)
        self.files = QTreeView(self.body)
        self.files.setObjectName(u"files")
        self.files.setMinimumSize(QSize(0, 160))
        self.files.setMaximumSize(QSize(16777215, 240))
        self.files.setAlternatingRowColors(True)
        self.files.setSelectionMode(QAbstractItemView.SingleSelection)
        self.files.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.files.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.files.setRootIsDecorated(False)
        self.files.setUniformRowHeights(True)
        self.files.setTextElideMode(Qt.ElideMiddle)
        self.files.setContextMenuPolicy(Qt.CustomContextMenu)

        self.bodyLayout.addWidget(self.files)

        self.empty = QLabel(self.body)
        self.empty.setObjectName(u"empty")
        self.empty.setWordWrap(True)

        self.bodyLayout.addWidget(self.empty)

        self.actions = QHBoxLayout()
        self.actions.setObjectName(u"actions")
        self.remove = QPushButton(self.body)
        self.remove.setObjectName(u"remove")
        self.remove.setEnabled(False)

        self.actions.addWidget(self.remove)

        self.exclude = QPushButton(self.body)
        self.exclude.setObjectName(u"exclude")
        self.exclude.setCheckable(True)
        self.exclude.setEnabled(False)

        self.actions.addWidget(self.exclude)


        self.bodyLayout.addLayout(self.actions)


        self.layout.addWidget(self.body)


        self.retranslateUi(fileSection)

        QMetaObject.connectSlotsByName(fileSection)
    # setupUi

    def retranslateUi(self, fileSection):
        self.toggle.setText(QCoreApplication.translate("FileSection", u"Input Files", None))
        self.count.setText(QCoreApplication.translate("FileSection", u"0", None))
#if QT_CONFIG(accessibility)
        self.count.setAccessibleName(QCoreApplication.translate("FileSection", u"File count", None))
#endif // QT_CONFIG(accessibility)
        self.add.setText(QCoreApplication.translate("FileSection", u"Add Files\u2026", None))
        self.empty.setText(QCoreApplication.translate("FileSection", u"No files yet.", None))
        self.remove.setText(QCoreApplication.translate("FileSection", u"Remove from Project", None))
        self.exclude.setText(QCoreApplication.translate("FileSection", u"Exclude from Stack", None))
        pass
    # retranslateUi
