# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_finish_stars.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout,
    QLabel, QPushButton, QRadioButton, QSizePolicy,
    QSlider, QSpacerItem, QVBoxLayout, QWidget)

class Ui_FinishStarsSettings(object):
    def setupUi(self, FinishStarsSettings):
        if not FinishStarsSettings.objectName():
            FinishStarsSettings.setObjectName(u"FinishStarsSettings")
        FinishStarsSettings.resize(300, 520)
        FinishStarsSettings.setStyleSheet(u"QFrame#help_box {\n"
"    background-color: #f8fafc;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 6px;\n"
"    padding: 6px 8px;\n"
"}\n"
"QLabel#lbl_help {\n"
"    color: #64748b;\n"
"    font-size: 11px;\n"
"    line-height: 1.3;\n"
"}\n"
"QLabel#lbl_preview_note {\n"
"    color: #94a3b8;\n"
"    font-size: 10px;\n"
"    font-style: italic;\n"
"}\n"
"QLabel#lbl_round_stars_title, QLabel#lbl_faint_suppression_title, QLabel#lbl_glow_amount_title, QLabel#lbl_glow_radius_title, QLabel#lbl_star_amount_title, QLabel#lbl_preview_title {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #475569;\n"
"}\n"
"QLabel#lbl_round_stars_value, QLabel#lbl_faint_suppression_value, QLabel#lbl_glow_amount_value, QLabel#lbl_glow_radius_value, QLabel#lbl_star_amount_value {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #0369a1;\n"
"}\n"
"QCheckBox {\n"
"    font-size: 11px;\n"
"    color: #1e293b;\n"
"    font-weight: 600;\n"
"    spacing: 6px;\n"
"}\n"
"QRadioButton {\n"
"    font-"
                        "size: 11px;\n"
"    color: #334155;\n"
"    font-weight: 500;\n"
"    spacing: 5px;\n"
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
        self.layout = QVBoxLayout(FinishStarsSettings)
        self.layout.setSpacing(10)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.round_stars_container = QWidget(FinishStarsSettings)
        self.round_stars_container.setObjectName(u"round_stars_container")
        self.round_stars_layout = QVBoxLayout(self.round_stars_container)
        self.round_stars_layout.setSpacing(4)
        self.round_stars_layout.setObjectName(u"round_stars_layout")
        self.round_stars_layout.setContentsMargins(0, 0, 0, 0)
        self.check_round_stars = QCheckBox(self.round_stars_container)
        self.check_round_stars.setObjectName(u"check_round_stars")
        self.check_round_stars.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.round_stars_layout.addWidget(self.check_round_stars)

        self.round_stars_header = QHBoxLayout()
        self.round_stars_header.setObjectName(u"round_stars_header")
        self.round_stars_header.setContentsMargins(16, -1, -1, -1)
        self.lbl_round_stars_title = QLabel(self.round_stars_container)
        self.lbl_round_stars_title.setObjectName(u"lbl_round_stars_title")

        self.round_stars_header.addWidget(self.lbl_round_stars_title)

        self.lbl_round_stars_value = QLabel(self.round_stars_container)
        self.lbl_round_stars_value.setObjectName(u"lbl_round_stars_value")
        self.lbl_round_stars_value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.round_stars_header.addWidget(self.lbl_round_stars_value)


        self.round_stars_layout.addLayout(self.round_stars_header)

        self.round_stars_slider_layout = QHBoxLayout()
        self.round_stars_slider_layout.setObjectName(u"round_stars_slider_layout")
        self.round_stars_slider_layout.setContentsMargins(16, -1, -1, -1)
        self.slider_round_stars = QSlider(self.round_stars_container)
        self.slider_round_stars.setObjectName(u"slider_round_stars")
        self.slider_round_stars.setEnabled(False)
        self.slider_round_stars.setOrientation(Qt.Orientation.Horizontal)
        self.slider_round_stars.setMaximum(100)
        self.slider_round_stars.setSingleStep(1)
        self.slider_round_stars.setPageStep(10)
        self.slider_round_stars.setValue(50)
        self.slider_round_stars.setTracking(True)

        self.round_stars_slider_layout.addWidget(self.slider_round_stars)


        self.round_stars_layout.addLayout(self.round_stars_slider_layout)


        self.layout.addWidget(self.round_stars_container)

        self.faint_suppression_container = QWidget(FinishStarsSettings)
        self.faint_suppression_container.setObjectName(u"faint_suppression_container")
        self.faint_suppression_layout = QVBoxLayout(self.faint_suppression_container)
        self.faint_suppression_layout.setSpacing(4)
        self.faint_suppression_layout.setObjectName(u"faint_suppression_layout")
        self.faint_suppression_layout.setContentsMargins(0, 0, 0, 0)
        self.check_faint_suppression = QCheckBox(self.faint_suppression_container)
        self.check_faint_suppression.setObjectName(u"check_faint_suppression")
        self.check_faint_suppression.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.faint_suppression_layout.addWidget(self.check_faint_suppression)

        self.faint_suppression_header = QHBoxLayout()
        self.faint_suppression_header.setObjectName(u"faint_suppression_header")
        self.faint_suppression_header.setContentsMargins(16, -1, -1, -1)
        self.lbl_faint_suppression_title = QLabel(self.faint_suppression_container)
        self.lbl_faint_suppression_title.setObjectName(u"lbl_faint_suppression_title")

        self.faint_suppression_header.addWidget(self.lbl_faint_suppression_title)

        self.lbl_faint_suppression_value = QLabel(self.faint_suppression_container)
        self.lbl_faint_suppression_value.setObjectName(u"lbl_faint_suppression_value")
        self.lbl_faint_suppression_value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.faint_suppression_header.addWidget(self.lbl_faint_suppression_value)


        self.faint_suppression_layout.addLayout(self.faint_suppression_header)

        self.faint_suppression_slider_layout = QHBoxLayout()
        self.faint_suppression_slider_layout.setObjectName(u"faint_suppression_slider_layout")
        self.faint_suppression_slider_layout.setContentsMargins(16, -1, -1, -1)
        self.slider_faint_suppression = QSlider(self.faint_suppression_container)
        self.slider_faint_suppression.setObjectName(u"slider_faint_suppression")
        self.slider_faint_suppression.setEnabled(False)
        self.slider_faint_suppression.setOrientation(Qt.Orientation.Horizontal)
        self.slider_faint_suppression.setMaximum(100)
        self.slider_faint_suppression.setSingleStep(1)
        self.slider_faint_suppression.setPageStep(10)
        self.slider_faint_suppression.setValue(0)
        self.slider_faint_suppression.setTracking(True)

        self.faint_suppression_slider_layout.addWidget(self.slider_faint_suppression)


        self.faint_suppression_layout.addLayout(self.faint_suppression_slider_layout)


        self.layout.addWidget(self.faint_suppression_container)

        self.glow_container = QWidget(FinishStarsSettings)
        self.glow_container.setObjectName(u"glow_container")
        self.glow_layout = QVBoxLayout(self.glow_container)
        self.glow_layout.setSpacing(4)
        self.glow_layout.setObjectName(u"glow_layout")
        self.glow_layout.setContentsMargins(0, 0, 0, 0)
        self.check_star_glow = QCheckBox(self.glow_container)
        self.check_star_glow.setObjectName(u"check_star_glow")
        self.check_star_glow.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.glow_layout.addWidget(self.check_star_glow)

        self.glow_amount_header = QHBoxLayout()
        self.glow_amount_header.setObjectName(u"glow_amount_header")
        self.glow_amount_header.setContentsMargins(16, -1, -1, -1)
        self.lbl_glow_amount_title = QLabel(self.glow_container)
        self.lbl_glow_amount_title.setObjectName(u"lbl_glow_amount_title")

        self.glow_amount_header.addWidget(self.lbl_glow_amount_title)

        self.lbl_glow_amount_value = QLabel(self.glow_container)
        self.lbl_glow_amount_value.setObjectName(u"lbl_glow_amount_value")
        self.lbl_glow_amount_value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.glow_amount_header.addWidget(self.lbl_glow_amount_value)


        self.glow_layout.addLayout(self.glow_amount_header)

        self.glow_amount_slider_layout = QHBoxLayout()
        self.glow_amount_slider_layout.setObjectName(u"glow_amount_slider_layout")
        self.glow_amount_slider_layout.setContentsMargins(16, -1, -1, -1)
        self.slider_glow_amount = QSlider(self.glow_container)
        self.slider_glow_amount.setObjectName(u"slider_glow_amount")
        self.slider_glow_amount.setEnabled(False)
        self.slider_glow_amount.setOrientation(Qt.Orientation.Horizontal)
        self.slider_glow_amount.setMaximum(100)
        self.slider_glow_amount.setSingleStep(1)
        self.slider_glow_amount.setPageStep(10)
        self.slider_glow_amount.setValue(0)
        self.slider_glow_amount.setTracking(True)

        self.glow_amount_slider_layout.addWidget(self.slider_glow_amount)


        self.glow_layout.addLayout(self.glow_amount_slider_layout)

        self.glow_radius_header = QHBoxLayout()
        self.glow_radius_header.setObjectName(u"glow_radius_header")
        self.glow_radius_header.setContentsMargins(16, -1, -1, -1)
        self.lbl_glow_radius_title = QLabel(self.glow_container)
        self.lbl_glow_radius_title.setObjectName(u"lbl_glow_radius_title")

        self.glow_radius_header.addWidget(self.lbl_glow_radius_title)

        self.lbl_glow_radius_value = QLabel(self.glow_container)
        self.lbl_glow_radius_value.setObjectName(u"lbl_glow_radius_value")
        self.lbl_glow_radius_value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.glow_radius_header.addWidget(self.lbl_glow_radius_value)


        self.glow_layout.addLayout(self.glow_radius_header)

        self.glow_radius_slider_layout = QHBoxLayout()
        self.glow_radius_slider_layout.setObjectName(u"glow_radius_slider_layout")
        self.glow_radius_slider_layout.setContentsMargins(16, -1, -1, -1)
        self.slider_glow_radius = QSlider(self.glow_container)
        self.slider_glow_radius.setObjectName(u"slider_glow_radius")
        self.slider_glow_radius.setEnabled(False)
        self.slider_glow_radius.setOrientation(Qt.Orientation.Horizontal)
        self.slider_glow_radius.setMinimum(1)
        self.slider_glow_radius.setMaximum(50)
        self.slider_glow_radius.setSingleStep(1)
        self.slider_glow_radius.setPageStep(5)
        self.slider_glow_radius.setValue(15)
        self.slider_glow_radius.setTracking(True)

        self.glow_radius_slider_layout.addWidget(self.slider_glow_radius)


        self.glow_layout.addLayout(self.glow_radius_slider_layout)


        self.layout.addWidget(self.glow_container)

        self.star_amount_container = QWidget(FinishStarsSettings)
        self.star_amount_container.setObjectName(u"star_amount_container")
        self.star_amount_layout = QVBoxLayout(self.star_amount_container)
        self.star_amount_layout.setSpacing(4)
        self.star_amount_layout.setObjectName(u"star_amount_layout")
        self.star_amount_layout.setContentsMargins(0, 0, 0, 0)
        self.star_amount_header = QHBoxLayout()
        self.star_amount_header.setObjectName(u"star_amount_header")
        self.lbl_star_amount_title = QLabel(self.star_amount_container)
        self.lbl_star_amount_title.setObjectName(u"lbl_star_amount_title")

        self.star_amount_header.addWidget(self.lbl_star_amount_title)

        self.lbl_star_amount_value = QLabel(self.star_amount_container)
        self.lbl_star_amount_value.setObjectName(u"lbl_star_amount_value")
        self.lbl_star_amount_value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.star_amount_header.addWidget(self.lbl_star_amount_value)


        self.star_amount_layout.addLayout(self.star_amount_header)

        self.slider_star_amount = QSlider(self.star_amount_container)
        self.slider_star_amount.setObjectName(u"slider_star_amount")
        self.slider_star_amount.setOrientation(Qt.Orientation.Horizontal)
        self.slider_star_amount.setMaximum(100)
        self.slider_star_amount.setSingleStep(1)
        self.slider_star_amount.setPageStep(10)
        self.slider_star_amount.setValue(100)
        self.slider_star_amount.setTracking(True)

        self.star_amount_layout.addWidget(self.slider_star_amount)


        self.layout.addWidget(self.star_amount_container)

        self.preview_container = QWidget(FinishStarsSettings)
        self.preview_container.setObjectName(u"preview_container")
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setSpacing(4)
        self.preview_layout.setObjectName(u"preview_layout")
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_preview_title = QLabel(self.preview_container)
        self.lbl_preview_title.setObjectName(u"lbl_preview_title")

        self.preview_layout.addWidget(self.lbl_preview_title)

        self.preview_radios = QHBoxLayout()
        self.preview_radios.setSpacing(12)
        self.preview_radios.setObjectName(u"preview_radios")
        self.radio_preview_composite = QRadioButton(self.preview_container)
        self.radio_preview_composite.setObjectName(u"radio_preview_composite")
        self.radio_preview_composite.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.radio_preview_composite.setChecked(True)

        self.preview_radios.addWidget(self.radio_preview_composite)

        self.radio_preview_stars = QRadioButton(self.preview_container)
        self.radio_preview_stars.setObjectName(u"radio_preview_stars")
        self.radio_preview_stars.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.preview_radios.addWidget(self.radio_preview_stars)

        self.preview_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.preview_radios.addItem(self.preview_spacer)


        self.preview_layout.addLayout(self.preview_radios)

        self.lbl_preview_note = QLabel(self.preview_container)
        self.lbl_preview_note.setObjectName(u"lbl_preview_note")
        self.lbl_preview_note.setWordWrap(True)

        self.preview_layout.addWidget(self.lbl_preview_note)


        self.layout.addWidget(self.preview_container)

        self.help_box = QFrame(FinishStarsSettings)
        self.help_box.setObjectName(u"help_box")
        self.help_layout = QVBoxLayout(self.help_box)
        self.help_layout.setSpacing(2)
        self.help_layout.setObjectName(u"help_layout")
        self.help_layout.setContentsMargins(6, 6, 6, 6)
        self.lbl_help = QLabel(self.help_box)
        self.lbl_help.setObjectName(u"lbl_help")
        self.lbl_help.setWordWrap(True)

        self.help_layout.addWidget(self.lbl_help)


        self.layout.addWidget(self.help_box)

        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(6)
        self.action_layout.setObjectName(u"action_layout")
        self.btn_reset = QPushButton(FinishStarsSettings)
        self.btn_reset.setObjectName(u"btn_reset")
        self.btn_reset.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.action_layout.addWidget(self.btn_reset)

        self.action_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.action_layout.addItem(self.action_spacer)


        self.layout.addLayout(self.action_layout)

        self.lbl_status = QLabel(FinishStarsSettings)
        self.lbl_status.setObjectName(u"lbl_status")
        self.lbl_status.setWordWrap(True)

        self.layout.addWidget(self.lbl_status)


        self.retranslateUi(FinishStarsSettings)

        QMetaObject.connectSlotsByName(FinishStarsSettings)
    # setupUi

    def retranslateUi(self, FinishStarsSettings):
        self.check_round_stars.setText(QCoreApplication.translate("FinishStarsSettings", u"Round Stars", None))
        self.lbl_round_stars_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Correction Amount", None))
        self.lbl_round_stars_value.setText(QCoreApplication.translate("FinishStarsSettings", u"50%", None))
        self.check_faint_suppression.setText(QCoreApplication.translate("FinishStarsSettings", u"Faint Star Suppression", None))
        self.lbl_faint_suppression_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Suppression Amount", None))
        self.lbl_faint_suppression_value.setText(QCoreApplication.translate("FinishStarsSettings", u"0%", None))
        self.check_star_glow.setText(QCoreApplication.translate("FinishStarsSettings", u"Star Glow", None))
        self.lbl_glow_amount_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Glow Amount", None))
        self.lbl_glow_amount_value.setText(QCoreApplication.translate("FinishStarsSettings", u"0%", None))
        self.lbl_glow_radius_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Glow Radius", None))
        self.lbl_glow_radius_value.setText(QCoreApplication.translate("FinishStarsSettings", u"15 px", None))
        self.lbl_star_amount_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Stars Amount", None))
        self.lbl_star_amount_value.setText(QCoreApplication.translate("FinishStarsSettings", u"100%", None))
        self.lbl_preview_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Preview Layer", None))
        self.radio_preview_composite.setText(QCoreApplication.translate("FinishStarsSettings", u"Composite", None))
        self.radio_preview_stars.setText(QCoreApplication.translate("FinishStarsSettings", u"Stars Only", None))
        self.lbl_preview_note.setText(QCoreApplication.translate("FinishStarsSettings", u"Finished stars layer is stored pre-global amount; amount is applied during composite blend.", None))
        self.lbl_help.setText(QCoreApplication.translate("FinishStarsSettings", u"Rounding is cosmetic and applies to isolated stars only. Crowded, saturated, or border stars may be skipped; close unresolved pairs cannot be reliably distinguished.", None))
        self.btn_reset.setText(QCoreApplication.translate("FinishStarsSettings", u"Reset", None))
        self.lbl_status.setText("")
        pass
    # retranslateUi

Ui_finishStarsSettings = Ui_FinishStarsSettings
