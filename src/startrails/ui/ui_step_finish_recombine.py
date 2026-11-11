# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_finish_recombine.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QSlider, QSpinBox,
    QVBoxLayout, QWidget)
from . import resources_rc

class Ui_FinishRecombineSettings(object):
    def setupUi(self, FinishRecombineSettings):
        if not FinishRecombineSettings.objectName():
            FinishRecombineSettings.setObjectName(u"FinishRecombineSettings")
        FinishRecombineSettings.resize(300, 260)
        FinishRecombineSettings.setStyleSheet(u"QLabel#lbl_fin_mode {\n"
"    font-size: 11px;\n"
"    font-weight: 500;\n"
"    color: #64748b;\n"
"}\n"
"QComboBox#combo_star_blend_mode {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 4px;\n"
"    padding: 2px 6px;\n"
"    font-size: 11px;\n"
"    color: #1e293b;\n"
"    min-height: 20px;\n"
"    max-height: 24px;\n"
"}\n"
"QComboBox#combo_star_blend_mode:focus {\n"
"    border: 1px solid #0369a1;\n"
"    outline: none;\n"
"}")
        self.layout = QVBoxLayout(FinishRecombineSettings)
        self.layout.setSpacing(8)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.star_amount_row = QHBoxLayout()
        self.star_amount_row.setSpacing(6)
        self.star_amount_row.setObjectName(u"star_amount_row")
        self.lbl_star_amount_title = QLabel(FinishRecombineSettings)
        self.lbl_star_amount_title.setObjectName(u"lbl_star_amount_title")
        self.lbl_star_amount_title.setMinimumSize(QSize(68, 0))
        self.lbl_star_amount_title.setMaximumSize(QSize(68, 16777215))

        self.star_amount_row.addWidget(self.lbl_star_amount_title)

        self.slider_star_amount = QSlider(FinishRecombineSettings)
        self.slider_star_amount.setObjectName(u"slider_star_amount")
        self.slider_star_amount.setMinimumSize(QSize(60, 0))
        self.slider_star_amount.setOrientation(Qt.Orientation.Horizontal)
        self.slider_star_amount.setMinimum(0)
        self.slider_star_amount.setMaximum(100)
        self.slider_star_amount.setSingleStep(1)
        self.slider_star_amount.setPageStep(10)
        self.slider_star_amount.setValue(100)
        self.slider_star_amount.setTracking(True)

        self.star_amount_row.addWidget(self.slider_star_amount)

        self.spin_star_amount = QSpinBox(FinishRecombineSettings)
        self.spin_star_amount.setObjectName(u"spin_star_amount")
        self.spin_star_amount.setMaximumSize(QSize(62, 16777215))
        self.spin_star_amount.setStyleSheet(u"")
        self.spin_star_amount.setMinimum(0)
        self.spin_star_amount.setMaximum(100)
        self.spin_star_amount.setSingleStep(1)
        self.spin_star_amount.setValue(100)

        self.star_amount_row.addWidget(self.spin_star_amount)


        self.layout.addLayout(self.star_amount_row)

        self.star_threshold_row = QHBoxLayout()
        self.star_threshold_row.setSpacing(6)
        self.star_threshold_row.setObjectName(u"star_threshold_row")
        self.lbl_star_threshold_title = QLabel(FinishRecombineSettings)
        self.lbl_star_threshold_title.setObjectName(u"lbl_star_threshold_title")
        self.lbl_star_threshold_title.setMinimumSize(QSize(68, 0))
        self.lbl_star_threshold_title.setMaximumSize(QSize(68, 16777215))

        self.star_threshold_row.addWidget(self.lbl_star_threshold_title)

        self.slider_star_threshold = QSlider(FinishRecombineSettings)
        self.slider_star_threshold.setObjectName(u"slider_star_threshold")
        self.slider_star_threshold.setMinimumSize(QSize(60, 0))
        self.slider_star_threshold.setOrientation(Qt.Orientation.Horizontal)
        self.slider_star_threshold.setMinimum(0)
        self.slider_star_threshold.setMaximum(100)
        self.slider_star_threshold.setSingleStep(1)
        self.slider_star_threshold.setPageStep(10)
        self.slider_star_threshold.setValue(0)
        self.slider_star_threshold.setTracking(True)

        self.star_threshold_row.addWidget(self.slider_star_threshold)

        self.spin_star_threshold = QSpinBox(FinishRecombineSettings)
        self.spin_star_threshold.setObjectName(u"spin_star_threshold")
        self.spin_star_threshold.setMaximumSize(QSize(62, 16777215))
        self.spin_star_threshold.setStyleSheet(u"")
        self.spin_star_threshold.setMinimum(0)
        self.spin_star_threshold.setMaximum(100)
        self.spin_star_threshold.setSingleStep(1)
        self.spin_star_threshold.setValue(0)

        self.star_threshold_row.addWidget(self.spin_star_threshold)


        self.layout.addLayout(self.star_threshold_row)

        self.fin_mode_layout = QHBoxLayout()
        self.fin_mode_layout.setObjectName(u"fin_mode_layout")
        self.lbl_fin_mode = QLabel(FinishRecombineSettings)
        self.lbl_fin_mode.setObjectName(u"lbl_fin_mode")

        self.fin_mode_layout.addWidget(self.lbl_fin_mode)

        self.combo_star_blend_mode = QComboBox(FinishRecombineSettings)
        self.combo_star_blend_mode.addItem("")
        self.combo_star_blend_mode.addItem("")
        self.combo_star_blend_mode.setObjectName(u"combo_star_blend_mode")

        self.fin_mode_layout.addWidget(self.combo_star_blend_mode)


        self.layout.addLayout(self.fin_mode_layout)

        self.lbl_status = QLabel(FinishRecombineSettings)
        self.lbl_status.setObjectName(u"lbl_status")
        self.lbl_status.setWordWrap(True)

        self.layout.addWidget(self.lbl_status)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(6)
        self.actions_layout.setObjectName(u"actions_layout")
        self.btn_save_output = QPushButton(FinishRecombineSettings)
        self.btn_save_output.setObjectName(u"btn_save_output")
        self.btn_save_output.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.actions_layout.addWidget(self.btn_save_output)

        self.btn_export_layers = QPushButton(FinishRecombineSettings)
        self.btn_export_layers.setObjectName(u"btn_export_layers")
        self.btn_export_layers.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.actions_layout.addWidget(self.btn_export_layers)


        self.layout.addLayout(self.actions_layout)

#if QT_CONFIG(shortcut)
        self.lbl_star_amount_title.setBuddy(self.spin_star_amount)
        self.lbl_star_threshold_title.setBuddy(self.spin_star_threshold)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(FinishRecombineSettings)

        QMetaObject.connectSlotsByName(FinishRecombineSettings)
    # setupUi

    def retranslateUi(self, FinishRecombineSettings):
        self.lbl_star_amount_title.setText(QCoreApplication.translate("FinishRecombineSettings", u"Stars:", None))
#if QT_CONFIG(accessibility)
        self.spin_star_amount.setAccessibleName(QCoreApplication.translate("FinishRecombineSettings", u"Stars", None))
#endif // QT_CONFIG(accessibility)
        self.spin_star_amount.setSuffix(QCoreApplication.translate("FinishRecombineSettings", u"%", None))
        self.lbl_star_threshold_title.setText(QCoreApplication.translate("FinishRecombineSettings", u"Threshold:", None))
#if QT_CONFIG(accessibility)
        self.spin_star_threshold.setAccessibleName(QCoreApplication.translate("FinishRecombineSettings", u"Star threshold", None))
#endif // QT_CONFIG(accessibility)
        self.spin_star_threshold.setSuffix(QCoreApplication.translate("FinishRecombineSettings", u"%", None))
        self.lbl_fin_mode.setText(QCoreApplication.translate("FinishRecombineSettings", u"Blend Mode", None))
        self.combo_star_blend_mode.setItemText(0, QCoreApplication.translate("FinishRecombineSettings", u"Add", None))
        self.combo_star_blend_mode.setItemText(1, QCoreApplication.translate("FinishRecombineSettings", u"Screen", None))

        self.lbl_status.setText("")
        self.btn_save_output.setText(QCoreApplication.translate("FinishRecombineSettings", u"Save Image", None))
#if QT_CONFIG(tooltip)
        self.btn_export_layers.setToolTip(QCoreApplication.translate("FinishRecombineSettings", u"Export separated and finished layers to disk. Stars is positive-only (the internal Add negative correction is not exported), so external layer recombination or JPEG export may not reconstruct the source exactly.", None))
#endif // QT_CONFIG(tooltip)
        self.btn_export_layers.setText(QCoreApplication.translate("FinishRecombineSettings", u"Export Layers", None))
        pass
    # retranslateUi

Ui_finishRecombineSettings = Ui_FinishRecombineSettings
