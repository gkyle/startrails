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
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout,
    QLabel, QRadioButton, QSizePolicy, QSlider,
    QSpacerItem, QSpinBox, QVBoxLayout, QWidget)

from startrails.ui.checkbox_label import CheckboxLabel
from . import resources_rc

class Ui_FinishStarlessSettings(object):
    def setupUi(self, FinishStarlessSettings):
        if not FinishStarlessSettings.objectName():
            FinishStarlessSettings.setObjectName(u"FinishStarlessSettings")
        FinishStarlessSettings.resize(300, 340)
        FinishStarlessSettings.setStyleSheet(u"QLabel#lbl_enable_denoise, QLabel#lbl_enable_sharpen {\n"
"    font-weight: 600;\n"
"}\n"
"QLabel#lbl_scope_title {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #475569;\n"
"}\n"
"QRadioButton {\n"
"    font-size: 11px;\n"
"    color: #334155;\n"
"    font-weight: 500;\n"
"    spacing: 5px;\n"
"}\n"
"QRadioButton:focus {\n"
"    border: none;\n"
"    outline: none;\n"
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

        self.enableDenoiseRow = QHBoxLayout()
        self.enableDenoiseRow.setObjectName(u"enableDenoiseRow")
        self.lbl_enable_denoise = CheckboxLabel(FinishStarlessSettings)
        self.lbl_enable_denoise.setObjectName(u"lbl_enable_denoise")
        self.lbl_enable_denoise.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.enableDenoiseRow.addWidget(self.lbl_enable_denoise)

        self.check_enable_denoise = QCheckBox(FinishStarlessSettings)
        self.check_enable_denoise.setObjectName(u"check_enable_denoise")
        self.check_enable_denoise.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.check_enable_denoise.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.check_enable_denoise.setChecked(True)

        self.enableDenoiseRow.addWidget(self.check_enable_denoise, 0, Qt.AlignmentFlag.AlignRight)


        self.layout.addLayout(self.enableDenoiseRow)

        self.strength_row = QHBoxLayout()
        self.strength_row.setSpacing(6)
        self.strength_row.setObjectName(u"strength_row")
        self.lbl_strength_title = QLabel(FinishStarlessSettings)
        self.lbl_strength_title.setObjectName(u"lbl_strength_title")
        self.lbl_strength_title.setMinimumSize(QSize(68, 0))
        self.lbl_strength_title.setMaximumSize(QSize(68, 16777215))

        self.strength_row.addWidget(self.lbl_strength_title)

        self.slider_strength = QSlider(FinishStarlessSettings)
        self.slider_strength.setObjectName(u"slider_strength")
        self.slider_strength.setMinimumSize(QSize(60, 0))
        self.slider_strength.setOrientation(Qt.Orientation.Horizontal)
        self.slider_strength.setMinimum(0)
        self.slider_strength.setMaximum(100)
        self.slider_strength.setSingleStep(1)
        self.slider_strength.setPageStep(10)
        self.slider_strength.setValue(50)
        self.slider_strength.setTracking(True)

        self.strength_row.addWidget(self.slider_strength)

        self.spin_strength = QSpinBox(FinishStarlessSettings)
        self.spin_strength.setObjectName(u"spin_strength")
        self.spin_strength.setMaximumSize(QSize(62, 16777215))
        self.spin_strength.setStyleSheet(u"")
        self.spin_strength.setMinimum(0)
        self.spin_strength.setMaximum(100)
        self.spin_strength.setSingleStep(1)
        self.spin_strength.setValue(50)

        self.strength_row.addWidget(self.spin_strength)


        self.layout.addLayout(self.strength_row)

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

        self.enableSharpenRow = QHBoxLayout()
        self.enableSharpenRow.setObjectName(u"enableSharpenRow")
        self.lbl_enable_sharpen = CheckboxLabel(FinishStarlessSettings)
        self.lbl_enable_sharpen.setObjectName(u"lbl_enable_sharpen")
        self.lbl_enable_sharpen.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.enableSharpenRow.addWidget(self.lbl_enable_sharpen)

        self.check_enable_sharpen = QCheckBox(FinishStarlessSettings)
        self.check_enable_sharpen.setObjectName(u"check_enable_sharpen")
        self.check_enable_sharpen.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.check_enable_sharpen.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.check_enable_sharpen.setChecked(True)

        self.enableSharpenRow.addWidget(self.check_enable_sharpen, 0, Qt.AlignmentFlag.AlignRight)


        self.layout.addLayout(self.enableSharpenRow)

        self.structure_row = QHBoxLayout()
        self.structure_row.setSpacing(6)
        self.structure_row.setObjectName(u"structure_row")
        self.lbl_structure_title = QLabel(FinishStarlessSettings)
        self.lbl_structure_title.setObjectName(u"lbl_structure_title")
        self.lbl_structure_title.setMinimumSize(QSize(68, 0))
        self.lbl_structure_title.setMaximumSize(QSize(68, 16777215))

        self.structure_row.addWidget(self.lbl_structure_title)

        self.slider_structure = QSlider(FinishStarlessSettings)
        self.slider_structure.setObjectName(u"slider_structure")
        self.slider_structure.setMinimumSize(QSize(60, 0))
        self.slider_structure.setOrientation(Qt.Orientation.Horizontal)
        self.slider_structure.setMinimum(0)
        self.slider_structure.setMaximum(100)
        self.slider_structure.setSingleStep(1)
        self.slider_structure.setPageStep(10)
        self.slider_structure.setValue(0)
        self.slider_structure.setTracking(True)

        self.structure_row.addWidget(self.slider_structure)

        self.spin_structure = QSpinBox(FinishStarlessSettings)
        self.spin_structure.setObjectName(u"spin_structure")
        self.spin_structure.setMaximumSize(QSize(62, 16777215))
        self.spin_structure.setStyleSheet(u"")
        self.spin_structure.setMinimum(0)
        self.spin_structure.setMaximum(100)
        self.spin_structure.setSingleStep(1)
        self.spin_structure.setValue(0)

        self.structure_row.addWidget(self.spin_structure)


        self.layout.addLayout(self.structure_row)

        self.detail_row = QHBoxLayout()
        self.detail_row.setSpacing(6)
        self.detail_row.setObjectName(u"detail_row")
        self.lbl_detail_title = QLabel(FinishStarlessSettings)
        self.lbl_detail_title.setObjectName(u"lbl_detail_title")
        self.lbl_detail_title.setMinimumSize(QSize(68, 0))
        self.lbl_detail_title.setMaximumSize(QSize(68, 16777215))

        self.detail_row.addWidget(self.lbl_detail_title)

        self.slider_detail = QSlider(FinishStarlessSettings)
        self.slider_detail.setObjectName(u"slider_detail")
        self.slider_detail.setMinimumSize(QSize(60, 0))
        self.slider_detail.setOrientation(Qt.Orientation.Horizontal)
        self.slider_detail.setMinimum(0)
        self.slider_detail.setMaximum(100)
        self.slider_detail.setSingleStep(1)
        self.slider_detail.setPageStep(10)
        self.slider_detail.setValue(0)
        self.slider_detail.setTracking(True)

        self.detail_row.addWidget(self.slider_detail)

        self.spin_detail = QSpinBox(FinishStarlessSettings)
        self.spin_detail.setObjectName(u"spin_detail")
        self.spin_detail.setMaximumSize(QSize(62, 16777215))
        self.spin_detail.setStyleSheet(u"")
        self.spin_detail.setMinimum(0)
        self.spin_detail.setMaximum(100)
        self.spin_detail.setSingleStep(1)
        self.spin_detail.setValue(0)

        self.detail_row.addWidget(self.spin_detail)


        self.layout.addLayout(self.detail_row)

        self.lbl_status = QLabel(FinishStarlessSettings)
        self.lbl_status.setObjectName(u"lbl_status")
        self.lbl_status.setWordWrap(True)

        self.layout.addWidget(self.lbl_status)

#if QT_CONFIG(shortcut)
        self.lbl_enable_denoise.setBuddy(self.check_enable_denoise)
        self.lbl_strength_title.setBuddy(self.spin_strength)
        self.lbl_enable_sharpen.setBuddy(self.check_enable_sharpen)
        self.lbl_structure_title.setBuddy(self.spin_structure)
        self.lbl_detail_title.setBuddy(self.spin_detail)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(FinishStarlessSettings)

        QMetaObject.connectSlotsByName(FinishStarlessSettings)
    # setupUi

    def retranslateUi(self, FinishStarlessSettings):
        self.lbl_unconf_msg.setText(QCoreApplication.translate("FinishStarlessSettings", u"GraXpert AI model (3.0.2) is missing or unverified. Zero-strength finishing remains available.", None))
        self.lbl_enable_denoise.setText(QCoreApplication.translate("FinishStarlessSettings", u"Enable denoise", None))
#if QT_CONFIG(accessibility)
        self.check_enable_denoise.setAccessibleName(QCoreApplication.translate("FinishStarlessSettings", u"Enable denoise", None))
#endif // QT_CONFIG(accessibility)
        self.check_enable_denoise.setText("")
        self.lbl_strength_title.setText(QCoreApplication.translate("FinishStarlessSettings", u"Strength:", None))
#if QT_CONFIG(accessibility)
        self.spin_strength.setAccessibleName(QCoreApplication.translate("FinishStarlessSettings", u"Denoise strength", None))
#endif // QT_CONFIG(accessibility)
        self.spin_strength.setSuffix(QCoreApplication.translate("FinishStarlessSettings", u"%", None))
        self.lbl_scope_title.setText(QCoreApplication.translate("FinishStarlessSettings", u"Denoise Scope", None))
        self.radio_sky_only.setText(QCoreApplication.translate("FinishStarlessSettings", u"Sky Only", None))
        self.radio_whole_image.setText(QCoreApplication.translate("FinishStarlessSettings", u"Whole Image", None))
        self.lbl_enable_sharpen.setText(QCoreApplication.translate("FinishStarlessSettings", u"Enable post-denoise sharpen", None))
#if QT_CONFIG(accessibility)
        self.check_enable_sharpen.setAccessibleName(QCoreApplication.translate("FinishStarlessSettings", u"Enable post-denoise sharpen", None))
#endif // QT_CONFIG(accessibility)
        self.check_enable_sharpen.setText("")
        self.lbl_structure_title.setText(QCoreApplication.translate("FinishStarlessSettings", u"Structure:", None))
#if QT_CONFIG(accessibility)
        self.spin_structure.setAccessibleName(QCoreApplication.translate("FinishStarlessSettings", u"Structure", None))
#endif // QT_CONFIG(accessibility)
        self.spin_structure.setSuffix(QCoreApplication.translate("FinishStarlessSettings", u"%", None))
        self.lbl_detail_title.setText(QCoreApplication.translate("FinishStarlessSettings", u"Detail:", None))
#if QT_CONFIG(accessibility)
        self.spin_detail.setAccessibleName(QCoreApplication.translate("FinishStarlessSettings", u"Detail", None))
#endif // QT_CONFIG(accessibility)
        self.spin_detail.setSuffix(QCoreApplication.translate("FinishStarlessSettings", u"%", None))
        self.lbl_status.setText("")
        pass
    # retranslateUi

Ui_finishStarlessSettings = Ui_FinishStarlessSettings
