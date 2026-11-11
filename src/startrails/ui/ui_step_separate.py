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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget)

from startrails.ui.checkbox_label import CheckboxLabel
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
"QLabel#lbl_stride {\n"
"    font-size: 11px;\n"
"    color: #475569;\n"
"}\n"
"QComboBox#combo_stride {\n"
"    font-size: 11px;\n"
"    padding: 2px 4px;\n"
"}\n"
"QCheckBox#check_chroma_postfilter {\n"
"    spacing: 0px;\n"
"    border: none;\n"
"    padding: 0px;\n"
"}\n"
"QCheckBox#check_chroma_postfilter::indicator {\n"
"    width: 36px;\n"
"    height: 20px;\n"
"    border-radius: 10px;\n"
"}\n"
"QCheckBox#check_chroma_postfilter::indicator:unchecked {\n"
"    image: url(:/startrails/ui/switch_off.svg);\n"
"}\n"
"QCheckBox#check_chroma_postfilter::indicator:checked {\n"
"    image: url(:/startrails/ui/switch_on.svg);\n"
"}\n"
"QCheckBox#check_chroma_postfilter:focus,\n"
"QCheckBox#check_chroma_postfilter:focus:enabled {\n"
"    border: none;\n"
""
                        "    outline: none;\n"
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


        self.layout.addWidget(self.unconfigured_box)

        self.configured_box = QWidget(SeparateStarsSettings)
        self.configured_box.setObjectName(u"configured_box")
        self.conf_layout = QVBoxLayout(self.configured_box)
        self.conf_layout.setSpacing(6)
        self.conf_layout.setObjectName(u"conf_layout")
        self.conf_layout.setContentsMargins(0, 0, 0, 0)
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

        self.chroma_row = QHBoxLayout()
        self.chroma_row.setObjectName(u"chroma_row")
        self.lbl_chroma_postfilter = CheckboxLabel(self.configured_box)
        self.lbl_chroma_postfilter.setObjectName(u"lbl_chroma_postfilter")
        self.lbl_chroma_postfilter.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.lbl_chroma_postfilter.setStyleSheet(u"color: #475569; font-size: 11px;")

        self.chroma_row.addWidget(self.lbl_chroma_postfilter)

        self.check_chroma_postfilter = QCheckBox(self.configured_box)
        self.check_chroma_postfilter.setObjectName(u"check_chroma_postfilter")
        self.check_chroma_postfilter.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.check_chroma_postfilter.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.check_chroma_postfilter.setChecked(True)

        self.chroma_row.addWidget(self.check_chroma_postfilter, 0, Qt.AlignmentFlag.AlignRight)


        self.conf_layout.addLayout(self.chroma_row)

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

#if QT_CONFIG(shortcut)
        self.lbl_chroma_postfilter.setBuddy(self.check_chroma_postfilter)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(SeparateStarsSettings)

        QMetaObject.connectSlotsByName(SeparateStarsSettings)
    # setupUi

    def retranslateUi(self, SeparateStarsSettings):
        self.lbl_unconf_msg.setText(QCoreApplication.translate("SeparateStarsSettings", u"Star removal model is missing or unavailable.", None))
        self.lbl_stride.setText(QCoreApplication.translate("SeparateStarsSettings", u"Stride:", None))
        self.lbl_chroma_postfilter.setText(QCoreApplication.translate("SeparateStarsSettings", u"Chroma postfilter", None))
#if QT_CONFIG(accessibility)
        self.check_chroma_postfilter.setAccessibleName(QCoreApplication.translate("SeparateStarsSettings", u"Chroma postfilter", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(tooltip)
        self.check_chroma_postfilter.setToolTip(QCoreApplication.translate("SeparateStarsSettings", u"Suppress residual color halos around removed stars while preserving sky background.", None))
#endif // QT_CONFIG(tooltip)
        self.check_chroma_postfilter.setText("")
        self.btn_separate.setText(QCoreApplication.translate("SeparateStarsSettings", u"Separate Stars", None))
        self.lbl_status.setText("")
        pass
    # retranslateUi

Ui_separateStarsSettings = Ui_SeparateStarsSettings
