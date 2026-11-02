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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QSizePolicy, QSlider, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_FinishStarsSettings(object):
    def setupUi(self, FinishStarsSettings):
        if not FinishStarsSettings.objectName():
            FinishStarsSettings.setObjectName(u"FinishStarsSettings")
        FinishStarsSettings.resize(300, 560)
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
"QLabel#lbl_star_cutoff_info {\n"
"    color: #64748b;\n"
"    font-size: 11px;\n"
"    line-height: 1.3;\n"
"}\n"
"QLabel#lbl_round_stars_title, QLabel#lbl_glow_count_title, QLabel#lbl_glow_amount_title, QLabel#lbl_glow_radius_title, QLabel#lbl_star_cutoff_title, QLabel#lbl_preview_title {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #475569;\n"
"}\n"
"QLabel#lbl_round_stars_value, QLabel#lbl_glow_amount_value, QLabel#lbl_glow_radius_value {\n"
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
"    font-size: 11px;\n"
"    color: #334155;\n"
"    font-weight: 500;\n"
"    s"
                        "pacing: 5px;\n"
"}\n"
"QComboBox {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 4px;\n"
"    padding: 3px 8px;\n"
"    font-size: 11px;\n"
"    color: #1e293b;\n"
"}\n"
"QComboBox:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QPushButton#btn_reset, QPushButton#btn_compare {\n"
"    background-color: #ffffff;\n"
"    color: #475569;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 4px;\n"
"    padding: 6px 12px;\n"
"    font-size: 11px;\n"
"}\n"
"QPushButton#btn_compare:pressed {\n"
"    background-color: #e2e8f0;\n"
"    color: #0f172a;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#btn_reset:hover, QPushButton#btn_compare:hover {\n"
"    background-color: #f1f5f9;\n"
"}\n"
"QPushButton#btn_reset:disabled, QPushButton#btn_compare:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #cbd5e1;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QLabel#lbl_status {\n"
"    color: #b91c1c;\n"
""
                        "    font-size: 11px;\n"
"    line-height: 1.3;\n"
"}")
        self.layout = QVBoxLayout(FinishStarsSettings)
        self.layout.setSpacing(10)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.included_stars_container = QWidget(FinishStarsSettings)
        self.included_stars_container.setObjectName(u"included_stars_container")
        self.included_stars_layout = QVBoxLayout(self.included_stars_container)
        self.included_stars_layout.setSpacing(4)
        self.included_stars_layout.setObjectName(u"included_stars_layout")
        self.included_stars_layout.setContentsMargins(0, 0, 0, 0)
        self.included_stars_header = QHBoxLayout()
        self.included_stars_header.setObjectName(u"included_stars_header")
        self.lbl_star_cutoff_title = QLabel(self.included_stars_container)
        self.lbl_star_cutoff_title.setObjectName(u"lbl_star_cutoff_title")

        self.included_stars_header.addWidget(self.lbl_star_cutoff_title)

        self.combo_star_cutoff = QComboBox(self.included_stars_container)
        self.combo_star_cutoff.addItem("")
        self.combo_star_cutoff.addItem("")
        self.combo_star_cutoff.addItem("")
        self.combo_star_cutoff.addItem("")
        self.combo_star_cutoff.setObjectName(u"combo_star_cutoff")
        self.combo_star_cutoff.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.included_stars_header.addWidget(self.combo_star_cutoff)


        self.included_stars_layout.addLayout(self.included_stars_header)

        self.lbl_star_cutoff_info = QLabel(self.included_stars_container)
        self.lbl_star_cutoff_info.setObjectName(u"lbl_star_cutoff_info")
        self.lbl_star_cutoff_info.setWordWrap(True)

        self.included_stars_layout.addWidget(self.lbl_star_cutoff_info)


        self.layout.addWidget(self.included_stars_container)

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

        self.glow_count_header = QHBoxLayout()
        self.glow_count_header.setObjectName(u"glow_count_header")
        self.glow_count_header.setContentsMargins(16, -1, -1, -1)
        self.lbl_glow_count_title = QLabel(self.glow_container)
        self.lbl_glow_count_title.setObjectName(u"lbl_glow_count_title")

        self.glow_count_header.addWidget(self.lbl_glow_count_title)

        self.combo_glow_count = QComboBox(self.glow_container)
        self.combo_glow_count.addItem("")
        self.combo_glow_count.addItem("")
        self.combo_glow_count.addItem("")
        self.combo_glow_count.setObjectName(u"combo_glow_count")
        self.combo_glow_count.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.glow_count_header.addWidget(self.combo_glow_count)


        self.glow_layout.addLayout(self.glow_count_header)

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

        self.preview_container = QWidget(FinishStarsSettings)
        self.preview_container.setObjectName(u"preview_container")
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setSpacing(4)
        self.preview_layout.setObjectName(u"preview_layout")
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_preview_title = QLabel(self.preview_container)
        self.lbl_preview_title.setObjectName(u"lbl_preview_title")

        self.preview_layout.addWidget(self.lbl_preview_title)

        self.preview_radios = QGridLayout()
        self.preview_radios.setSpacing(6)
        self.preview_radios.setObjectName(u"preview_radios")
        self.radio_preview_composite = QRadioButton(self.preview_container)
        self.radio_preview_composite.setObjectName(u"radio_preview_composite")
        self.radio_preview_composite.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.radio_preview_composite.setChecked(True)

        self.preview_radios.addWidget(self.radio_preview_composite, 0, 0, 1, 1)

        self.radio_preview_finished_stars = QRadioButton(self.preview_container)
        self.radio_preview_finished_stars.setObjectName(u"radio_preview_finished_stars")
        self.radio_preview_finished_stars.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.preview_radios.addWidget(self.radio_preview_finished_stars, 0, 1, 1, 1)

        self.radio_preview_original_stars = QRadioButton(self.preview_container)
        self.radio_preview_original_stars.setObjectName(u"radio_preview_original_stars")
        self.radio_preview_original_stars.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.preview_radios.addWidget(self.radio_preview_original_stars, 1, 0, 1, 1)

        self.radio_preview_excluded_stars = QRadioButton(self.preview_container)
        self.radio_preview_excluded_stars.setObjectName(u"radio_preview_excluded_stars")
        self.radio_preview_excluded_stars.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.preview_radios.addWidget(self.radio_preview_excluded_stars, 1, 1, 1, 1)


        self.preview_layout.addLayout(self.preview_radios)

        self.compare_layout = QHBoxLayout()
        self.compare_layout.setObjectName(u"compare_layout")
        self.compare_layout.setContentsMargins(-1, 4, -1, -1)
        self.btn_compare = QPushButton(self.preview_container)
        self.btn_compare.setObjectName(u"btn_compare")
        self.btn_compare.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.compare_layout.addWidget(self.btn_compare)

        self.compare_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.compare_layout.addItem(self.compare_spacer)


        self.preview_layout.addLayout(self.compare_layout)


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
        self.lbl_star_cutoff_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Included Stars", None))
        self.combo_star_cutoff.setItemText(0, QCoreApplication.translate("FinishStarsSettings", u"All", None))
        self.combo_star_cutoff.setItemText(1, QCoreApplication.translate("FinishStarsSettings", u"100,000", None))
        self.combo_star_cutoff.setItemText(2, QCoreApplication.translate("FinishStarsSettings", u"10,000", None))
        self.combo_star_cutoff.setItemText(3, QCoreApplication.translate("FinishStarsSettings", u"1,000", None))

        self.lbl_star_cutoff_info.setText(QCoreApplication.translate("FinishStarsSettings", u"\u2014", None))
        self.check_round_stars.setText(QCoreApplication.translate("FinishStarsSettings", u"Round Stars", None))
        self.lbl_round_stars_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Correction Amount", None))
        self.lbl_round_stars_value.setText(QCoreApplication.translate("FinishStarsSettings", u"50%", None))
        self.check_star_glow.setText(QCoreApplication.translate("FinishStarsSettings", u"Star Glow", None))
        self.lbl_glow_count_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Glow Stars", None))
        self.combo_glow_count.setItemText(0, QCoreApplication.translate("FinishStarsSettings", u"25", None))
        self.combo_glow_count.setItemText(1, QCoreApplication.translate("FinishStarsSettings", u"100", None))
        self.combo_glow_count.setItemText(2, QCoreApplication.translate("FinishStarsSettings", u"500", None))

        self.lbl_glow_amount_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Glow Amount", None))
        self.lbl_glow_amount_value.setText(QCoreApplication.translate("FinishStarsSettings", u"0%", None))
        self.lbl_glow_radius_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Glow Radius", None))
        self.lbl_glow_radius_value.setText(QCoreApplication.translate("FinishStarsSettings", u"15 px", None))
        self.lbl_preview_title.setText(QCoreApplication.translate("FinishStarsSettings", u"Preview Layer", None))
        self.radio_preview_composite.setText(QCoreApplication.translate("FinishStarsSettings", u"Composite", None))
        self.radio_preview_finished_stars.setText(QCoreApplication.translate("FinishStarsSettings", u"Finished Stars", None))
        self.radio_preview_original_stars.setText(QCoreApplication.translate("FinishStarsSettings", u"Original Stars", None))
        self.radio_preview_excluded_stars.setText(QCoreApplication.translate("FinishStarsSettings", u"Excluded Stars", None))
#if QT_CONFIG(tooltip)
        self.btn_compare.setToolTip(QCoreApplication.translate("FinishStarsSettings", u"Press and hold to view included stars without effects", None))
#endif // QT_CONFIG(tooltip)
        self.btn_compare.setText(QCoreApplication.translate("FinishStarsSettings", u"Hold to Compare", None))
        self.lbl_help.setText(QCoreApplication.translate("FinishStarsSettings", u"Rounding circularizes isolated stars. Glow adds an atmospheric halo to top stars. Hold to Compare previews included stars without cosmetic effects.", None))
        self.btn_reset.setText(QCoreApplication.translate("FinishStarsSettings", u"Reset", None))
        self.lbl_status.setText("")
        pass
    # retranslateUi

Ui_finishStarsSettings = Ui_FinishStarsSettings
