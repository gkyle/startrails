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

class Ui_fileSection(object):
    def setupUi(self, fileSection):
        if not fileSection.objectName():
            fileSection.setObjectName(u"fileSection")
        fileSection.resize(274, 318)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(fileSection.sizePolicy().hasHeightForWidth())
        fileSection.setSizePolicy(sizePolicy)
        fileSection.setStyleSheet(u"QFrame#fileSection {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 8px;\n"
"}\n"
"QFrame#fileSection:hover {\n"
"    border-color: #cbd5e1;\n"
"}\n"
"QLabel#chevron {\n"
"    min-width: 14px;\n"
"    max-width: 14px;\n"
"    image: url(:/startrails/ui/chevron_right.svg);\n"
"}\n"
"QLabel#chevron[expanded=\"true\"] {\n"
"    image: url(:/startrails/ui/chevron_down.svg);\n"
"}\n"
"QToolButton#toggle {\n"
"    border: 2px solid transparent;\n"
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
"    border: 2px solid transparent;\n"
"    border-radius: 3px;\n"
"    font-weight: bold;\n"
"    font-size: 13px;\n"
"    color: #475569;\n"
"    background: "
                        "transparent;\n"
"    min-width: 20px;\n"
"    max-width: 20px;\n"
"    min-height: 20px;\n"
"    max-height: 20px;\n"
"}\n"
"QPushButton#add:hover {\n"
"    background-color: #e2e8f0;\n"
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
"    color: #64748b;\n"
"    font-size: 12px;\n"
"    font-style: italic;\n"
"    padding: 12px;\n"
"}\n"
"QMenu {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: "
                        "6px;\n"
"    padding: 4px;\n"
"}\n"
"QMenu::item {\n"
"    padding: 6px 20px 6px 12px;\n"
"    border-radius: 4px;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"}\n"
"QMenu::item:selected {\n"
"    background-color: #f1f5f9;\n"
"    color: #0f172a;\n"
"}\n"
"QMenu::separator {\n"
"    height: 1px;\n"
"    background-color: #e2e8f0;\n"
"    margin: 4px 6px;\n"
"}\n"
"QToolButton#toggle:focus:enabled { border-color: #0f172a; }\n"
"QPushButton#add:focus:enabled { border-color: #0f172a; }")
        self.layout = QVBoxLayout(fileSection)
        self.layout.setSpacing(2)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.headerWidget = QWidget(fileSection)
        self.headerWidget.setObjectName(u"headerWidget")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.headerWidget.sizePolicy().hasHeightForWidth())
        self.headerWidget.setSizePolicy(sizePolicy1)
        self.headerWidget.setMaximumSize(QSize(16777215, 32))
        self.headerWidget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.header = QHBoxLayout(self.headerWidget)
        self.header.setSpacing(6)
        self.header.setObjectName(u"header")
        self.header.setContentsMargins(6, 4, 6, 4)
        self.chevron = QLabel(self.headerWidget)
        self.chevron.setObjectName(u"chevron")
        self.chevron.setMinimumSize(QSize(14, 0))
        self.chevron.setMaximumSize(QSize(14, 16777215))
        self.chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.header.addWidget(self.chevron)

        self.icon = QLabel(self.headerWidget)
        self.icon.setObjectName(u"icon")
        self.icon.setMinimumSize(QSize(16, 16))
        self.icon.setMaximumSize(QSize(16, 16))
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.header.addWidget(self.icon)

        self.toggle = QToolButton(self.headerWidget)
        self.toggle.setObjectName(u"toggle")
        self.toggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle.setCheckable(True)

        self.header.addWidget(self.toggle)

        self.count = QLabel(self.headerWidget)
        self.count.setObjectName(u"count")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.count.sizePolicy().hasHeightForWidth())
        self.count.setSizePolicy(sizePolicy2)
        self.count.setMaximumSize(QSize(16777215, 18))
        self.count.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        sizePolicy.setHeightForWidth(self.body.sizePolicy().hasHeightForWidth())
        self.body.setSizePolicy(sizePolicy)
        self.bodyLayout = QVBoxLayout(self.body)
        self.bodyLayout.setSpacing(6)
        self.bodyLayout.setObjectName(u"bodyLayout")
        self.bodyLayout.setContentsMargins(4, 2, 4, 4)
        self.files = QTreeView(self.body)
        self.files.setObjectName(u"files")
        sizePolicy1.setHeightForWidth(self.files.sizePolicy().hasHeightForWidth())
        self.files.setSizePolicy(sizePolicy1)
        self.files.setMinimumSize(QSize(0, 0))
        self.files.setMaximumSize(QSize(16777215, 220))
        self.files.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.files.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.files.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.files.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.files.setRootIsDecorated(False)
        self.files.setUniformRowHeights(True)

        self.bodyLayout.addWidget(self.files)

        self.empty = QLabel(self.body)
        self.empty.setObjectName(u"empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)

        self.bodyLayout.addWidget(self.empty)

        self.legend = QWidget(self.body)
        self.legend.setObjectName(u"legend")
        sizePolicy1.setHeightForWidth(self.legend.sizePolicy().hasHeightForWidth())
        self.legend.setSizePolicy(sizePolicy1)
        self.legend.setMinimumSize(QSize(0, 20))
        self.legend.setMaximumSize(QSize(16777215, 24))
        self.legendLayout = QHBoxLayout(self.legend)
        self.legendLayout.setSpacing(6)
        self.legendLayout.setObjectName(u"legendLayout")
        self.legendLayout.setContentsMargins(4, 2, 4, 2)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.legendLayout.addItem(self.horizontalSpacer)

        self.legendAuto = QLabel(self.legend)
        self.legendAuto.setObjectName(u"legendAuto")
        self.legendAuto.setStyleSheet(u"QLabel#legendAuto {\n"
"    background-color: #dcfce7;\n"
"    color: #15803d;\n"
"    border: 1px solid #bbf7d0;\n"
"    border-radius: 4px;\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    padding: 0px 6px;\n"
"    min-height: 16px;\n"
"    max-height: 16px;\n"
"}")
        self.legendAuto.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.legendLayout.addWidget(self.legendAuto)

        self.legendManual = QLabel(self.legend)
        self.legendManual.setObjectName(u"legendManual")
        self.legendManual.setStyleSheet(u"QLabel#legendManual {\n"
"    background-color: #e0f2fe;\n"
"    color: #0369a1;\n"
"    border: 1px solid #bae6fd;\n"
"    border-radius: 4px;\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    padding: 0px 6px;\n"
"    min-height: 16px;\n"
"    max-height: 16px;\n"
"}")
        self.legendManual.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.legendLayout.addWidget(self.legendManual)

        self.legendDeleted = QLabel(self.legend)
        self.legendDeleted.setObjectName(u"legendDeleted")
        self.legendDeleted.setStyleSheet(u"QLabel#legendDeleted {\n"
"    background-color: #fef3c7;\n"
"    color: #b45309;\n"
"    border: 1px solid #fde68a;\n"
"    border-radius: 4px;\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    padding: 0px 6px;\n"
"    min-height: 16px;\n"
"    max-height: 16px;\n"
"}")
        self.legendDeleted.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.legendLayout.addWidget(self.legendDeleted)

        self.legendSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.legendLayout.addItem(self.legendSpacer)


        self.bodyLayout.addWidget(self.legend)


        self.layout.addWidget(self.body)


        self.retranslateUi(fileSection)

        QMetaObject.connectSlotsByName(fileSection)
    # setupUi

    def retranslateUi(self, fileSection):
        self.chevron.setText("")
        self.icon.setText("")
        self.toggle.setText(QCoreApplication.translate("fileSection", u"Input Files", None))
#if QT_CONFIG(accessibility)
        self.count.setAccessibleName(QCoreApplication.translate("fileSection", u"File count", None))
#endif // QT_CONFIG(accessibility)
        self.count.setText(QCoreApplication.translate("fileSection", u"0", None))
#if QT_CONFIG(tooltip)
        self.add.setToolTip(QCoreApplication.translate("fileSection", u"Add files\u2026", None))
#endif // QT_CONFIG(tooltip)
        self.add.setText(QCoreApplication.translate("fileSection", u"+", None))
        self.empty.setText(QCoreApplication.translate("fileSection", u"No files yet.", None))
        self.legendAuto.setText(QCoreApplication.translate("fileSection", u"Auto", None))
        self.legendManual.setText(QCoreApplication.translate("fileSection", u"Manual", None))
        self.legendDeleted.setText(QCoreApplication.translate("fileSection", u"Deleted", None))
        pass
    # retranslateUi

Ui_FileSection = Ui_fileSection
