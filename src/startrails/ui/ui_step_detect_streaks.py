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
    QSizePolicy, QToolButton, QVBoxLayout, QWidget)
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
"    border: 1px solid #64748b;\n"
"    border-radius: 4px;\n"
"    padding: 4px 6px;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"}\n"
"QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QLineEdit:focus {\n"
"    border: 2px solid #0369a1;\n"
"    padding: 3px 5px;\n"
"}\n"
"QCheckBox {\n"
"    font-size: 12px;\n"
"    color: #1e293b;\n"
"    spacing: 6px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"QLabel#error {\n"
"    font-size: 11px;\n"
"    color: #b91c1c;\n"
"}\n"
"QPushButton#run {\n"
"    font-weight: bold;\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    padding: 0px 12px;\n"
"    border-top-left-radius: 6px;\n"
"    border-bottom-left-radius: 6px;\n"
"    border-top-right-radius: 0px;\n"
"    border-bottom-right-radius: 0px;\n"
"    font-size: 13px;\n"
"    border: 2px solid transparent;\n"
"    min-height: 34px"
                        ";\n"
"    max-height: 34px;\n"
"}\n"
"QPushButton#run:hover {\n"
"    background-color: #075985;\n"
"}\n"
"QPushButton#run:disabled {\n"
"    background-color: #e2e8f0;\n"
"    color: #94a3b8;\n"
"}\n"
"QPushButton#run:focus:enabled { border-color: #ffffff; }\n"
"QToolButton#advancedToggle {\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    padding: 0px;\n"
"    border-top-left-radius: 0px;\n"
"    border-bottom-left-radius: 0px;\n"
"    border-top-right-radius: 6px;\n"
"    border-bottom-right-radius: 6px;\n"
"    border: 2px solid transparent;\n"
"    border-left: 1px solid #075985;\n"
"    min-height: 34px;\n"
"    max-height: 34px;\n"
"    min-width: 28px;\n"
"    max-width: 28px;\n"
"}\n"
"QToolButton#advancedToggle:hover {\n"
"    background-color: #075985;\n"
"}\n"
"QToolButton#advancedToggle:focus:enabled {\n"
"    border-color: #ffffff;\n"
"}\n"
"QToolButton#advancedToggle:disabled {\n"
"    background-color: #e2e8f0;\n"
"    color: #94a3b8;\n"
"    border-left: 1px solid #cbd5e1;\n"
""
                        "}\n"
"QCheckBox:focus:enabled { border-color: #0f172a; }\n"
"QDoubleSpinBox::up-arrow, QSpinBox::up-arrow { image: url(:/startrails/ui/arrow_up.svg); width: 10px; height: 6px; }\n"
"QDoubleSpinBox::down-arrow, QSpinBox::down-arrow { image: url(:/startrails/ui/arrow_down.svg); width: 10px; height: 6px; }")
        self.layout = QVBoxLayout(detectSettings)
        self.layout.setSpacing(6)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.runLayout = QHBoxLayout()
        self.runLayout.setSpacing(0)
        self.runLayout.setObjectName(u"runLayout")
        self.run = QPushButton(detectSettings)
        self.run.setObjectName(u"run")
        self.run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run.setEnabled(False)

        self.runLayout.addWidget(self.run)

        self.advancedToggle = QToolButton(detectSettings)
        self.advancedToggle.setObjectName(u"advancedToggle")
        self.advancedToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.advancedToggle.setFocusPolicy(Qt.StrongFocus)
        self.advancedToggle.setCheckable(True)
        self.advancedToggle.setChecked(True)
        self.advancedToggle.setArrowType(Qt.DownArrow)

        self.runLayout.addWidget(self.advancedToggle)


        self.layout.addLayout(self.runLayout)

        self.advancedBody = QWidget(detectSettings)
        self.advancedBody.setObjectName(u"advancedBody")
        self.advancedBody.setVisible(True)
        self.advancedLayout = QVBoxLayout(self.advancedBody)
        self.advancedLayout.setSpacing(6)
        self.advancedLayout.setObjectName(u"advancedLayout")
        self.advancedLayout.setContentsMargins(0, 0, 0, 0)
        self.fields = QFormLayout()
        self.fields.setObjectName(u"fields")
        self.fields.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.fields.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.fields.setHorizontalSpacing(8)
        self.fields.setVerticalSpacing(6)
        self.confidenceLabel = QLabel(self.advancedBody)
        self.confidenceLabel.setObjectName(u"confidenceLabel")

        self.fields.setWidget(0, QFormLayout.LabelRole, self.confidenceLabel)

        self.confidence = QDoubleSpinBox(self.advancedBody)
        self.confidence.setObjectName(u"confidence")
        self.confidence.setMaximum(1.000000000000000)
        self.confidence.setSingleStep(0.050000000000000)
        self.confidence.setValue(0.300000000000000)

        self.fields.setWidget(0, QFormLayout.FieldRole, self.confidence)

        self.mergeLabel = QLabel(self.advancedBody)
        self.mergeLabel.setObjectName(u"mergeLabel")

        self.fields.setWidget(1, QFormLayout.LabelRole, self.mergeLabel)

        self.mergeRow = QHBoxLayout()
        self.mergeRow.setSpacing(6)
        self.mergeRow.setObjectName(u"mergeRow")
        self.mergeMethod = QComboBox(self.advancedBody)
        self.mergeMethod.addItem("")
        self.mergeMethod.addItem("")
        self.mergeMethod.setObjectName(u"mergeMethod")

        self.mergeRow.addWidget(self.mergeMethod)

        self.thresholdLabel = QLabel(self.advancedBody)
        self.thresholdLabel.setObjectName(u"thresholdLabel")

        self.mergeRow.addWidget(self.thresholdLabel)

        self.mergeThreshold = QDoubleSpinBox(self.advancedBody)
        self.mergeThreshold.setObjectName(u"mergeThreshold")
        self.mergeThreshold.setMaximum(1.000000000000000)
        self.mergeThreshold.setSingleStep(0.050000000000000)
        self.mergeThreshold.setValue(0.200000000000000)

        self.mergeRow.addWidget(self.mergeThreshold)


        self.fields.setLayout(1, QFormLayout.FieldRole, self.mergeRow)


        self.advancedLayout.addLayout(self.fields)

        self.useGPU = QCheckBox(self.advancedBody)
        self.useGPU.setObjectName(u"useGPU")
        self.useGPU.setStyleSheet(u"QCheckBox#useGPU { spacing: 0px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"    QCheckBox#useGPU::indicator { width: 36px; height: 20px;  border: 1px solid #64748b; border-radius: 10px; }\n"
"    QCheckBox#useGPU::indicator:unchecked { image: url(:/startrails/ui/switch_off.png); }\n"
"    QCheckBox#useGPU::indicator:checked { image: url(:/startrails/ui/switch_on.png); }\n"
"QCheckBox#useGPU:focus:enabled { border-color: #0f172a; }")

        self.advancedLayout.addWidget(self.useGPU)


        self.layout.addWidget(self.advancedBody)

        self.error = QLabel(detectSettings)
        self.error.setObjectName(u"error")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

#if QT_CONFIG(shortcut)
        self.confidenceLabel.setBuddy(self.confidence)
        self.mergeLabel.setBuddy(self.mergeMethod)
        self.thresholdLabel.setBuddy(self.mergeThreshold)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(detectSettings)

        QMetaObject.connectSlotsByName(detectSettings)
    # setupUi

    def retranslateUi(self, detectSettings):
        self.run.setText(QCoreApplication.translate("DetectSettings", u"Detect Streaks", None))
#if QT_CONFIG(tooltip)
        self.advancedToggle.setToolTip(QCoreApplication.translate("DetectSettings", u"Advanced settings", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.advancedToggle.setAccessibleName(QCoreApplication.translate("DetectSettings", u"Advanced settings", None))
#endif // QT_CONFIG(accessibility)
        self.advancedToggle.setText("")
        self.confidenceLabel.setText(QCoreApplication.translate("DetectSettings", u"&Confidence", None))
        self.mergeLabel.setText(QCoreApplication.translate("DetectSettings", u"&Merging", None))
        self.mergeMethod.setItemText(0, QCoreApplication.translate("DetectSettings", u"NMS", None))
        self.mergeMethod.setItemText(1, QCoreApplication.translate("DetectSettings", u"Greedy NMM", None))

        self.thresholdLabel.setText(QCoreApplication.translate("DetectSettings", u"&Threshold", None))
#if QT_CONFIG(tooltip)
        self.thresholdLabel.setToolTip(QCoreApplication.translate("DetectSettings", u"Merge threshold", None))
#endif // QT_CONFIG(tooltip)
        self.useGPU.setText(QCoreApplication.translate("DetectSettings", u"Use GPU", None))
        self.error.setText("")
        pass
    # retranslateUi
