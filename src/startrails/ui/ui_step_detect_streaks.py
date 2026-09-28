# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_detect_streaks.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget)
from . import resources_rc

class Ui_DetectSettings(object):
    def setupUi(self, detectSettings):
        if not detectSettings.objectName():
            detectSettings.setObjectName(u"detectSettings")
        detectSettings.setStyleSheet(u"QLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}\n"
"QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 4px;\n"
"    padding: 4px 6px;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"}\n"
"QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QLineEdit:focus {\n"
"    border-color: #0284c7;\n"
"}\n"
"QCheckBox {\n"
"    font-size: 12px;\n"
"    color: #1e293b;\n"
"    spacing: 6px;\n"
"}\n"
"QLabel#error {\n"
"    font-size: 11px;\n"
"    color: #ef4444;\n"
"}\n"
"QPushButton#run {\n"
"    font-weight: bold;\n"
"    background-color: #0284c7;\n"
"    color: #ffffff;\n"
"    padding: 7px 12px;\n"
"    border-radius: 6px;\n"
"    font-size: 13px;\n"
"    border: none;\n"
"}\n"
"QPushButton#run:hover {\n"
"    background-color: #0369a1;\n"
"}\n"
"QPushButton#run:disabled {\n"
"    background-color: #e2e8f0;\n"
"    color: #94a3b8;\n"
"}")
        self.layout = QVBoxLayout(detectSettings)
        self.layout.setSpacing(6)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.fields = QFormLayout()
        self.fields.setObjectName(u"fields")
        self.fields.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.fields.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.fields.setHorizontalSpacing(8)
        self.fields.setVerticalSpacing(6)
        self.confidenceLabel = QLabel(detectSettings)
        self.confidenceLabel.setObjectName(u"confidenceLabel")

        self.fields.setWidget(0, QFormLayout.LabelRole, self.confidenceLabel)

        self.confidence = QDoubleSpinBox(detectSettings)
        self.confidence.setObjectName(u"confidence")
        self.confidence.setMaximum(1.000000000000000)
        self.confidence.setSingleStep(0.050000000000000)
        self.confidence.setValue(0.300000000000000)

        self.fields.setWidget(0, QFormLayout.FieldRole, self.confidence)

        self.mergeLabel = QLabel(detectSettings)
        self.mergeLabel.setObjectName(u"mergeLabel")

        self.fields.setWidget(1, QFormLayout.LabelRole, self.mergeLabel)

        self.mergeRow = QHBoxLayout()
        self.mergeRow.setSpacing(6)
        self.mergeRow.setObjectName(u"mergeRow")
        self.mergeMethod = QComboBox(detectSettings)
        self.mergeMethod.addItem("")
        self.mergeMethod.addItem("")
        self.mergeMethod.setObjectName(u"mergeMethod")

        self.mergeRow.addWidget(self.mergeMethod)

        self.thresholdLabel = QLabel(detectSettings)
        self.thresholdLabel.setObjectName(u"thresholdLabel")

        self.mergeRow.addWidget(self.thresholdLabel)

        self.mergeThreshold = QDoubleSpinBox(detectSettings)
        self.mergeThreshold.setObjectName(u"mergeThreshold")
        self.mergeThreshold.setMaximum(1.000000000000000)
        self.mergeThreshold.setSingleStep(0.050000000000000)
        self.mergeThreshold.setValue(0.200000000000000)

        self.mergeRow.addWidget(self.mergeThreshold)


        self.fields.setLayout(1, QFormLayout.FieldRole, self.mergeRow)


        self.layout.addLayout(self.fields)

        self.useGPU = QCheckBox(detectSettings)
        self.useGPU.setObjectName(u"useGPU")
        self.useGPU.setStyleSheet(u"QCheckBox#useGPU { spacing: 0px; }\n"
"    QCheckBox#useGPU::indicator { width: 36px; height: 20px; }\n"
"    QCheckBox#useGPU::indicator:unchecked { image: url(:/startrails/ui/switch_off.png); }\n"
"    QCheckBox#useGPU::indicator:checked { image: url(:/startrails/ui/switch_on.png); }")

        self.layout.addWidget(self.useGPU)

        self.error = QLabel(detectSettings)
        self.error.setObjectName(u"error")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

        self.run = QPushButton(detectSettings)
        self.run.setObjectName(u"run")
        self.run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run.setEnabled(False)

        self.layout.addWidget(self.run)

#if QT_CONFIG(shortcut)
        self.confidenceLabel.setBuddy(self.confidence)
        self.mergeLabel.setBuddy(self.mergeMethod)
        self.thresholdLabel.setBuddy(self.mergeThreshold)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(detectSettings)

        QMetaObject.connectSlotsByName(detectSettings)
    # setupUi

    def retranslateUi(self, detectSettings):
        self.confidenceLabel.setText(QCoreApplication.translate("DetectSettings", u"&Confidence threshold", None))
        self.mergeLabel.setText(QCoreApplication.translate("DetectSettings", u"&Merging strategy", None))
        self.mergeMethod.setItemText(0, QCoreApplication.translate("DetectSettings", u"NMS", None))
        self.mergeMethod.setItemText(1, QCoreApplication.translate("DetectSettings", u"Greedy NMM", None))

        self.thresholdLabel.setText(QCoreApplication.translate("DetectSettings", u"&Threshold", None))
#if QT_CONFIG(tooltip)
        self.thresholdLabel.setToolTip(QCoreApplication.translate("DetectSettings", u"Merge threshold", None))
#endif // QT_CONFIG(tooltip)
        self.useGPU.setText(QCoreApplication.translate("DetectSettings", u"Use GPU", None))
        self.error.setText("")
        self.run.setText(QCoreApplication.translate("DetectSettings", u"Detect Streaks", None))
        pass
    # retranslateUi
