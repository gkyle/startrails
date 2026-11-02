# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_finish_starless.ui'
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
    QPushButton, QRadioButton, QSizePolicy, QSlider,
    QSpacerItem, QVBoxLayout, QWidget)

class Ui_FinishStarlessSettings(object):
    def setupUi(self, FinishStarlessSettings):
        if not FinishStarlessSettings.objectName():
            FinishStarlessSettings.setObjectName(u"FinishStarlessSettings")
        FinishStarlessSettings.resize(300, 340)
        FinishStarlessSettings.setStyleSheet(u"QFrame#unconfigured_box {\n"
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
"QFrame#configured_box {\n"
"    background-color: #f8fafc;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 6px;\n"
"    padding: 6px 8px;\n"
"}\n"
"QLabel#lbl_provider_dot {\n"
"    color: #10b981;\n"
"    font-size: 11px;\n"
"    font-weight: bold;\n"
"}\n"
"QLabel#lbl_provider_info {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #1e293b;\n"
"}\n"
"QLabel#lbl_strength_title, QLabel#lbl_scope_title, QLabel#lbl_structure_title, QLabel#lbl_detail_title {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #475569;\n"
"}\n"
"QLabel#lbl_strength_value, QLabel#lbl_structure_value, QLabel#lbl_detail_value {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #0369a1;\n"
"}\n"
"QRadioButton {\n"
"   "
                        " font-size: 11px;\n"
"    color: #334155;\n"
"    font-weight: 500;\n"
"    spacing: 5px;\n"
"}\n"
"QPushButton#btn_run_denoise {\n"
"    background-color: #0284c7;\n"
"    color: #ffffff;\n"
"    border-radius: 4px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 600;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#btn_run_denoise:hover {\n"
"    background-color: #0369a1;\n"
"}\n"
"QPushButton#btn_run_denoise:disabled {\n"
"    background-color: #cbd5e1;\n"
"    color: #94a3b8;\n"
"}\n"
"QPushButton#btn_reset {\n"
"    background-color: #ffffff;\n"
"    color: #475569;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 4px;\n"
"    padding: 6px 12px;\n"
"    font-size: 11px;\n"
"}\n"
"QPushButton#btn_reset:hover {\n"
"    background-color: #f1f5f9;\n"
"}\n"
"QPushButton#btn_reset:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #cbd5e1;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QLabel#lbl_status {\n"
"    color: #b91c1c;\n"
"    font-size: 11px;\n"
"    line-height: 1.3;\n"
"}")
        self.layout = QVBoxLayout(FinishStarlessSettings)
        self.layout.setSpacing(10)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.unconfigured_box = QFrame(FinishStarlessSettings)
        self.unconfigured_box.setObjectName(u"unconfigured_box")
        self.unconf_layout = QVBoxLayout(self.unconfigured_box)
        self.unconf_layout.setSpacing(4)
        self.unconf_layout.setObjectName(u"unconf_layout")
        self.unconf_layout.setContentsMargins(6, 6, 6, 6)
        self.lbl_unconf_msg = QLabel(self.unconfigured_box)
        self.lbl_unconf_msg.setObjectName(u"lbl_unconf_msg")
        self.lbl_unconf_msg.setWordWrap(True)

        self.unconf_layout.addWidget(self.lbl_unconf_msg)


        self.layout.addWidget(self.unconfigured_box)

        self.configured_box = QFrame(FinishStarlessSettings)
        self.configured_box.setObjectName(u"configured_box")
        self.conf_layout = QHBoxLayout(self.configured_box)
        self.conf_layout.setSpacing(6)
        self.conf_layout.setObjectName(u"conf_layout")
        self.conf_layout.setContentsMargins(6, 4, 6, 4)
        self.lbl_provider_dot = QLabel(self.configured_box)
        self.lbl_provider_dot.setObjectName(u"lbl_provider_dot")

        self.conf_layout.addWidget(self.lbl_provider_dot)

        self.lbl_provider_info = QLabel(self.configured_box)
        self.lbl_provider_info.setObjectName(u"lbl_provider_info")
        self.lbl_provider_info.setWordWrap(True)

        self.conf_layout.addWidget(self.lbl_provider_info)

        self.conf_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.conf_layout.addItem(self.conf_spacer)


        self.layout.addWidget(self.configured_box)

        self.strength_container = QWidget(FinishStarlessSettings)
        self.strength_container.setObjectName(u"strength_container")
        self.strength_layout = QVBoxLayout(self.strength_container)
        self.strength_layout.setSpacing(4)
        self.strength_layout.setObjectName(u"strength_layout")
        self.strength_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout = QHBoxLayout()
        self.header_layout.setObjectName(u"header_layout")
        self.lbl_strength_title = QLabel(self.strength_container)
        self.lbl_strength_title.setObjectName(u"lbl_strength_title")

        self.header_layout.addWidget(self.lbl_strength_title)

        self.lbl_strength_value = QLabel(self.strength_container)
        self.lbl_strength_value.setObjectName(u"lbl_strength_value")
        self.lbl_strength_value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.header_layout.addWidget(self.lbl_strength_value)


        self.strength_layout.addLayout(self.header_layout)

        self.slider_strength = QSlider(self.strength_container)
        self.slider_strength.setObjectName(u"slider_strength")
        self.slider_strength.setOrientation(Qt.Orientation.Horizontal)
        self.slider_strength.setMaximum(100)
        self.slider_strength.setSingleStep(1)
        self.slider_strength.setPageStep(10)
        self.slider_strength.setValue(50)
        self.slider_strength.setTracking(True)

        self.strength_layout.addWidget(self.slider_strength)


        self.layout.addWidget(self.strength_container)

        self.scope_container = QWidget(FinishStarlessSettings)
        self.scope_container.setObjectName(u"scope_container")
        self.scope_layout = QVBoxLayout(self.scope_container)
        self.scope_layout.setSpacing(4)
        self.scope_layout.setObjectName(u"scope_layout")
        self.scope_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_scope_title = QLabel(self.scope_container)
        self.lbl_scope_title.setObjectName(u"lbl_scope_title")

        self.scope_layout.addWidget(self.lbl_scope_title)

        self.radio_layout = QHBoxLayout()
        self.radio_layout.setSpacing(12)
        self.radio_layout.setObjectName(u"radio_layout")
        self.radio_sky_only = QRadioButton(self.scope_container)
        self.radio_sky_only.setObjectName(u"radio_sky_only")
        self.radio_sky_only.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.radio_sky_only.setChecked(True)

        self.radio_layout.addWidget(self.radio_sky_only)

        self.radio_whole_image = QRadioButton(self.scope_container)
        self.radio_whole_image.setObjectName(u"radio_whole_image")
        self.radio_whole_image.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.radio_layout.addWidget(self.radio_whole_image)

        self.radio_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.radio_layout.addItem(self.radio_spacer)


        self.scope_layout.addLayout(self.radio_layout)


        self.layout.addWidget(self.scope_container)

        self.structure_container = QWidget(FinishStarlessSettings)
        self.structure_container.setObjectName(u"structure_container")
        self.structure_layout = QVBoxLayout(self.structure_container)
        self.structure_layout.setSpacing(4)
        self.structure_layout.setObjectName(u"structure_layout")
        self.structure_layout.setContentsMargins(0, 0, 0, 0)
        self.structure_header_layout = QHBoxLayout()
        self.structure_header_layout.setObjectName(u"structure_header_layout")
        self.lbl_structure_title = QLabel(self.structure_container)
        self.lbl_structure_title.setObjectName(u"lbl_structure_title")

        self.structure_header_layout.addWidget(self.lbl_structure_title)

        self.lbl_structure_value = QLabel(self.structure_container)
        self.lbl_structure_value.setObjectName(u"lbl_structure_value")
        self.lbl_structure_value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.structure_header_layout.addWidget(self.lbl_structure_value)


        self.structure_layout.addLayout(self.structure_header_layout)

        self.slider_structure = QSlider(self.structure_container)
        self.slider_structure.setObjectName(u"slider_structure")
        self.slider_structure.setOrientation(Qt.Orientation.Horizontal)
        self.slider_structure.setMaximum(100)
        self.slider_structure.setSingleStep(1)
        self.slider_structure.setPageStep(10)
        self.slider_structure.setValue(0)
        self.slider_structure.setTracking(True)

        self.structure_layout.addWidget(self.slider_structure)


        self.layout.addWidget(self.structure_container)

        self.detail_container = QWidget(FinishStarlessSettings)
        self.detail_container.setObjectName(u"detail_container")
        self.detail_layout = QVBoxLayout(self.detail_container)
        self.detail_layout.setSpacing(4)
        self.detail_layout.setObjectName(u"detail_layout")
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_header_layout = QHBoxLayout()
        self.detail_header_layout.setObjectName(u"detail_header_layout")
        self.lbl_detail_title = QLabel(self.detail_container)
        self.lbl_detail_title.setObjectName(u"lbl_detail_title")

        self.detail_header_layout.addWidget(self.lbl_detail_title)

        self.lbl_detail_value = QLabel(self.detail_container)
        self.lbl_detail_value.setObjectName(u"lbl_detail_value")
        self.lbl_detail_value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.detail_header_layout.addWidget(self.lbl_detail_value)


        self.detail_layout.addLayout(self.detail_header_layout)

        self.slider_detail = QSlider(self.detail_container)
        self.slider_detail.setObjectName(u"slider_detail")
        self.slider_detail.setOrientation(Qt.Orientation.Horizontal)
        self.slider_detail.setMaximum(100)
        self.slider_detail.setSingleStep(1)
        self.slider_detail.setPageStep(10)
        self.slider_detail.setValue(0)
        self.slider_detail.setTracking(True)

        self.detail_layout.addWidget(self.slider_detail)


        self.layout.addWidget(self.detail_container)

        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(6)
        self.action_layout.setObjectName(u"action_layout")
        self.btn_run_denoise = QPushButton(FinishStarlessSettings)
        self.btn_run_denoise.setObjectName(u"btn_run_denoise")
        self.btn_run_denoise.setEnabled(False)
        self.btn_run_denoise.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.action_layout.addWidget(self.btn_run_denoise)

        self.btn_reset = QPushButton(FinishStarlessSettings)
        self.btn_reset.setObjectName(u"btn_reset")
        self.btn_reset.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.action_layout.addWidget(self.btn_reset)


        self.layout.addLayout(self.action_layout)

        self.lbl_status = QLabel(FinishStarlessSettings)
        self.lbl_status.setObjectName(u"lbl_status")
        self.lbl_status.setWordWrap(True)

        self.layout.addWidget(self.lbl_status)


        self.retranslateUi(FinishStarlessSettings)

        QMetaObject.connectSlotsByName(FinishStarlessSettings)
    # setupUi

    def retranslateUi(self, FinishStarlessSettings):
        self.lbl_unconf_msg.setText(QCoreApplication.translate("FinishStarlessSettings", u"GraXpert AI model (3.0.2) is missing or unverified. Zero-strength finishing remains available.", None))
        self.lbl_provider_dot.setText(QCoreApplication.translate("FinishStarlessSettings", u"\u25cf", None))
        self.lbl_provider_info.setText(QCoreApplication.translate("FinishStarlessSettings", u"GraXpert AI 3.0.2", None))
        self.lbl_strength_title.setText(QCoreApplication.translate("FinishStarlessSettings", u"Denoise Strength", None))
        self.lbl_strength_value.setText(QCoreApplication.translate("FinishStarlessSettings", u"50%", None))
        self.lbl_scope_title.setText(QCoreApplication.translate("FinishStarlessSettings", u"Denoise Scope", None))
        self.radio_sky_only.setText(QCoreApplication.translate("FinishStarlessSettings", u"Sky Only", None))
        self.radio_whole_image.setText(QCoreApplication.translate("FinishStarlessSettings", u"Whole Image", None))
        self.lbl_structure_title.setText(QCoreApplication.translate("FinishStarlessSettings", u"Structure", None))
        self.lbl_structure_value.setText(QCoreApplication.translate("FinishStarlessSettings", u"0%", None))
        self.lbl_detail_title.setText(QCoreApplication.translate("FinishStarlessSettings", u"Detail", None))
        self.lbl_detail_value.setText(QCoreApplication.translate("FinishStarlessSettings", u"0%", None))
        self.btn_run_denoise.setText(QCoreApplication.translate("FinishStarlessSettings", u"Run Denoise", None))
        self.btn_reset.setText(QCoreApplication.translate("FinishStarlessSettings", u"Reset", None))
        self.lbl_status.setText("")
        pass
    # retranslateUi

Ui_finishStarlessSettings = Ui_FinishStarlessSettings
