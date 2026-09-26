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
    QSpacerItem, QToolButton, QTreeView, QVBoxLayout,
    QWidget)

class Ui_FileSection(object):
    def setupUi(self, fileSection):
        if not fileSection.objectName():
            fileSection.setObjectName(u"fileSection")
        fileSection.setStyleSheet(u"QFrame#fileSection {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 8px;\n"
"}\n"
"QFrame#fileSection:hover {\n"
"    border-color: #cbd5e1;\n"
"}\n"
"QLabel#chevron {\n"
"    font-size: 10px;\n"
"    color: #64748b;\n"
"    font-weight: bold;\n"
"}\n"
"QToolButton#toggle {\n"
"    border: none;\n"
"    background: transparent;\n"
"    font-weight: bold;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"    padding: 0px;\n"
"}\n"
"QLabel#count {\n"
"    background-color: #f1f5f9;\n"
"    color: #475569;\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    padding: 1px 7px;\n"
"    border-radius: 9px;\n"
"    min-width: 14px;\n"
"}\n"
"QPushButton#add {\n"
"    border: none;\n"
"    border-radius: 3px;\n"
"    font-weight: bold;\n"
"    font-size: 13px;\n"
"    color: #475569;\n"
"    background: transparent;\n"
"    min-width: 20px;\n"
"    max-width: 20px;\n"
"    min-height: 20px;\n"
"    max-height: 20px;\n"
"}\n"
"QPushButton#add:hover {\n"
"    backgr"
                        "ound-color: #e2e8f0;\n"
"    color: #0f172a;\n"
"}\n"
"QTreeView#files {\n"
"    border: none;\n"
"    background: transparent;\n"
"}\n"
"QTreeView#files::item {\n"
"    padding: 2px 0px;\n"
"    border-radius: 4px;\n"
"}\n"
"QTreeView#files::item:hover {\n"
"    background-color: #f8fafc;\n"
"}\n"
"QTreeView#files::item:selected {\n"
"    background-color: #eff6ff;\n"
"    color: #1d4ed8;\n"
"}\n"
"QHeaderView::section {\n"
"    background-color: #f8fafc;\n"
"    color: #64748b;\n"
"    font-weight: 600;\n"
"    font-size: 11px;\n"
"    border: none;\n"
"    border-bottom: 1px solid #e2e8f0;\n"
"    padding: 3px 6px;\n"
"}\n"
"QLabel#empty {\n"
"    color: #94a3b8;\n"
"    font-size: 12px;\n"
"    font-style: italic;\n"
"    padding: 12px;\n"
"}\n"
"QPushButton#remove, QPushButton#exclude {\n"
"    background-color: #ffffff;\n"
"    color: #475569;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 4px;\n"
"    padding: 4px 8px;\n"
"    font-size: 11px;\n"
"    font-weight: 500;\n"
"}\n"
"QPushButton#r"
                        "emove:hover, QPushButton#exclude:hover {\n"
"    background-color: #f1f5f9;\n"
"    color: #0f172a;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#remove:disabled, QPushButton#exclude:disabled {\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"    background-color: #f8fafc;\n"
"}")
        self.layout = QVBoxLayout(fileSection)
        self.layout.setSpacing(2)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.headerWidget = QWidget(fileSection)
        self.headerWidget.setObjectName(u"headerWidget")
        self.headerWidget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.header = QHBoxLayout(self.headerWidget)
        self.header.setSpacing(6)
        self.header.setObjectName(u"header")
        self.header.setContentsMargins(6, 4, 6, 4)
        self.chevron = QLabel(self.headerWidget)
        self.chevron.setObjectName(u"chevron")

        self.header.addWidget(self.chevron)

        self.icon = QLabel(self.headerWidget)
        self.icon.setObjectName(u"icon")
        self.icon.setMinimumSize(QSize(16, 16))
        self.icon.setMaximumSize(QSize(16, 16))
        self.icon.setAlignment(Qt.AlignCenter)

        self.header.addWidget(self.icon)

        self.toggle = QToolButton(self.headerWidget)
        self.toggle.setObjectName(u"toggle")
        self.toggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle.setCheckable(True)

        self.header.addWidget(self.toggle)

        self.count = QLabel(self.headerWidget)
        self.count.setObjectName(u"count")
        self.count.setAlignment(Qt.AlignCenter)

        self.header.addWidget(self.count)

        self.headerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.header.addItem(self.headerSpacer)

        self.add = QPushButton(self.headerWidget)
        self.add.setObjectName(u"add")
        self.add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.header.addWidget(self.add)


        self.layout.addWidget(self.headerWidget)

        self.body = QWidget(fileSection)
        self.body.setObjectName(u"body")
        self.bodyLayout = QVBoxLayout(self.body)
        self.bodyLayout.setSpacing(6)
        self.bodyLayout.setObjectName(u"bodyLayout")
        self.bodyLayout.setContentsMargins(4, 2, 4, 4)
        self.files = QTreeView(self.body)
        self.files.setObjectName(u"files")
        self.files.setMinimumSize(QSize(0, 160))
        self.files.setMaximumSize(QSize(16777215, 240))
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
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)

        self.bodyLayout.addWidget(self.empty)

        self.actions = QHBoxLayout()
        self.actions.setSpacing(6)
        self.actions.setObjectName(u"actions")
        self.remove = QPushButton(self.body)
        self.remove.setObjectName(u"remove")
        self.remove.setEnabled(False)

        self.actions.addWidget(self.remove)

        self.exclude = QPushButton(self.body)
        self.exclude.setObjectName(u"exclude")
        self.exclude.setEnabled(False)
        self.exclude.setCheckable(True)

        self.actions.addWidget(self.exclude)


        self.bodyLayout.addLayout(self.actions)


        self.layout.addWidget(self.body)


        self.retranslateUi(fileSection)

        QMetaObject.connectSlotsByName(fileSection)
    # setupUi

    def retranslateUi(self, fileSection):
        self.chevron.setText(QCoreApplication.translate("FileSection", u"\u25b6", None))
        self.icon.setText("")
        self.toggle.setText(QCoreApplication.translate("FileSection", u"Input Files", None))
        self.count.setText(QCoreApplication.translate("FileSection", u"0", None))
#if QT_CONFIG(accessibility)
        self.count.setAccessibleName(QCoreApplication.translate("FileSection", u"File count", None))
#endif // QT_CONFIG(accessibility)
        self.add.setText(QCoreApplication.translate("FileSection", u"+", None))
#if QT_CONFIG(tooltip)
        self.add.setToolTip(QCoreApplication.translate("FileSection", u"Add files\u2026", None))
#endif // QT_CONFIG(tooltip)
        self.empty.setText(QCoreApplication.translate("FileSection", u"No files yet.", None))
        self.remove.setText(QCoreApplication.translate("FileSection", u"Remove from Project", None))
        self.exclude.setText(QCoreApplication.translate("FileSection", u"Exclude from Stack", None))
        pass
    # retranslateUi
