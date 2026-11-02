# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_separate.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)
from . import resources_rc

class Ui_SeparateStarsSettings(object):
    def setupUi(self, SeparateStarsSettings):
        if not SeparateStarsSettings.objectName():
            SeparateStarsSettings.setObjectName(u"SeparateStarsSettings")
        SeparateStarsSettings.resize(300, 200)
        SeparateStarsSettings.setStyleSheet(u"QFrame#unconfigured_box {\n"
"    background-color: #fffbeb;\n"
"    border: 1px solid #fef3c7;\n"
"    border-radius: 6px;\n"
"    padding: 8px;\n"
"}\n"
"QLabel#lbl_unconf_msg {\n"
"    color: #92400e;\n"
"    font-size: 11px;\n"
"    line-height: 1.3;\n"
"}\n"
"QPushButton#btn_setup_starnet {\n"
"    background-color: #d97706;\n"
"    color: #ffffff;\n"
"    border-radius: 4px;\n"
"    padding: 5px 10px;\n"
"    font-weight: 600;\n"
"    font-size: 11px;\n"
"}\n"
"QPushButton#btn_setup_starnet:hover {\n"
"    background-color: #b45309;\n"
"}\n"
"QPushButton#btn_setup_starnet:disabled {\n"
"    background-color: #cbd5e1;\n"
"    color: #94a3b8;\n"
"}\n"
"QPushButton#btn_browse_starnet {\n"
"    background-color: #ffffff;\n"
"    color: #475569;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 4px;\n"
"    padding: 5px 10px;\n"
"    font-size: 11px;\n"
"}\n"
"QPushButton#btn_browse_starnet:hover {\n"
"    background-color: #f1f5f9;\n"
"}\n"
"QLabel#lbl_starnet_info {\n"
"    font-size: 11px;\n"
"    "
                        "font-weight: 600;\n"
"    color: #1e293b;\n"
"}\n"
"QPushButton#btn_repair {\n"
"    border: none;\n"
"    color: #0284c7;\n"
"    font-size: 11px;\n"
"    text-decoration: underline;\n"
"    background: transparent;\n"
"}\n"
"QPushButton#btn_repair:hover {\n"
"    color: #0369a1;\n"
"}\n"
"QPushButton#btn_change {\n"
"    border: none;\n"
"    color: #64748b;\n"
"    font-size: 11px;\n"
"    text-decoration: underline;\n"
"    background: transparent;\n"
"}\n"
"QPushButton#btn_change:hover {\n"
"    color: #334155;\n"
"}\n"
"QLabel#lbl_stride {\n"
"    font-size: 11px;\n"
"    color: #475569;\n"
"}\n"
"QComboBox#combo_stride {\n"
"    font-size: 11px;\n"
"    padding: 2px 4px;\n"
"}\n"
"QPushButton#btn_separate {\n"
"    background-color: #0284c7;\n"
"    color: #ffffff;\n"
"    border-radius: 4px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 600;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#btn_separate:disabled {\n"
"    background-color: #94a3b8;\n"
"}\n"
"QPushButton#btn_separate:hover:!disabled {\n"
""
                        "    background-color: #0369a1;\n"
"}\n"
"QLabel#lbl_status {\n"
"    font-size: 11px;\n"
"    color: #dc2626;\n"
"}")
        self.layout = QVBoxLayout(SeparateStarsSettings)
        self.layout.setSpacing(8)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.unconfigured_box = QFrame(SeparateStarsSettings)
        self.unconfigured_box.setObjectName(u"unconfigured_box")
        self.unconf_layout = QVBoxLayout(self.unconfigured_box)
        self.unconf_layout.setSpacing(6)
        self.unconf_layout.setObjectName(u"unconf_layout")
        self.unconf_layout.setContentsMargins(6, 6, 6, 6)
        self.lbl_unconf_msg = QLabel(self.unconfigured_box)
        self.lbl_unconf_msg.setObjectName(u"lbl_unconf_msg")
        self.lbl_unconf_msg.setWordWrap(True)

        self.unconf_layout.addWidget(self.lbl_unconf_msg)

        self.btn_row = QHBoxLayout()
        self.btn_row.setSpacing(6)
        self.btn_row.setObjectName(u"btn_row")
        self.btn_setup_starnet = QPushButton(self.unconfigured_box)
        self.btn_setup_starnet.setObjectName(u"btn_setup_starnet")
        self.btn_setup_starnet.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.btn_row.addWidget(self.btn_setup_starnet)

        self.btn_browse_starnet = QPushButton(self.unconfigured_box)
        self.btn_browse_starnet.setObjectName(u"btn_browse_starnet")
        self.btn_browse_starnet.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.btn_row.addWidget(self.btn_browse_starnet)


        self.unconf_layout.addLayout(self.btn_row)


        self.layout.addWidget(self.unconfigured_box)

        self.configured_box = QWidget(SeparateStarsSettings)
        self.configured_box.setObjectName(u"configured_box")
        self.conf_layout = QVBoxLayout(self.configured_box)
        self.conf_layout.setSpacing(6)
        self.conf_layout.setObjectName(u"conf_layout")
        self.conf_layout.setContentsMargins(0, 0, 0, 0)
        self.header_row = QHBoxLayout()
        self.header_row.setSpacing(4)
        self.header_row.setObjectName(u"header_row")
        self.lbl_starnet_info = QLabel(self.configured_box)
        self.lbl_starnet_info.setObjectName(u"lbl_starnet_info")

        self.header_row.addWidget(self.lbl_starnet_info)

        self.header_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.header_row.addItem(self.header_spacer)

        self.btn_repair = QPushButton(self.configured_box)
        self.btn_repair.setObjectName(u"btn_repair")
        self.btn_repair.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.header_row.addWidget(self.btn_repair)

        self.btn_change = QPushButton(self.configured_box)
        self.btn_change.setObjectName(u"btn_change")
        self.btn_change.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.header_row.addWidget(self.btn_change)


        self.conf_layout.addLayout(self.header_row)

        self.stride_row = QHBoxLayout()
        self.stride_row.setSpacing(6)
        self.stride_row.setObjectName(u"stride_row")
        self.lbl_stride = QLabel(self.configured_box)
        self.lbl_stride.setObjectName(u"lbl_stride")

        self.stride_row.addWidget(self.lbl_stride)

        self.combo_stride = QComboBox(self.configured_box)
        self.combo_stride.setObjectName(u"combo_stride")

        self.stride_row.addWidget(self.combo_stride)

        self.stride_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.stride_row.addItem(self.stride_spacer)


        self.conf_layout.addLayout(self.stride_row)

        self.btn_separate = QPushButton(self.configured_box)
        self.btn_separate.setObjectName(u"btn_separate")
        self.btn_separate.setEnabled(False)
        self.btn_separate.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.conf_layout.addWidget(self.btn_separate)


        self.layout.addWidget(self.configured_box)

        self.lbl_status = QLabel(SeparateStarsSettings)
        self.lbl_status.setObjectName(u"lbl_status")
        self.lbl_status.setWordWrap(True)

        self.layout.addWidget(self.lbl_status)


        self.retranslateUi(SeparateStarsSettings)

        QMetaObject.connectSlotsByName(SeparateStarsSettings)
    # setupUi

    def retranslateUi(self, SeparateStarsSettings):
        self.lbl_unconf_msg.setText(QCoreApplication.translate("SeparateStarsSettings", u"StarNet2 is required to separate stars from the sky background.", None))
        self.btn_setup_starnet.setText(QCoreApplication.translate("SeparateStarsSettings", u"Set Up StarNet2\u2026", None))
        self.btn_browse_starnet.setText(QCoreApplication.translate("SeparateStarsSettings", u"Use Existing\u2026", None))
        self.lbl_starnet_info.setText(QCoreApplication.translate("SeparateStarsSettings", u"StarNet2 Ready", None))
        self.btn_repair.setText(QCoreApplication.translate("SeparateStarsSettings", u"Repair", None))
        self.btn_change.setText(QCoreApplication.translate("SeparateStarsSettings", u"Change\u2026", None))
        self.lbl_stride.setText(QCoreApplication.translate("SeparateStarsSettings", u"Stride:", None))
        self.btn_separate.setText(QCoreApplication.translate("SeparateStarsSettings", u"Separate Stars", None))
        self.lbl_status.setText("")
        pass
    # retranslateUi

Ui_separateStarsSettings = Ui_SeparateStarsSettings
