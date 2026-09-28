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
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QDoubleSpinBox,
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QToolButton, QVBoxLayout,
    QWidget)
from . import resources_rc

class Ui_DetectSettings(object):
    def setupUi(self, DetectSettings):
        if not DetectSettings.objectName():
            DetectSettings.setObjectName(u"DetectSettings")
        DetectSettings.resize(232, 204)
        DetectSettings.setStyleSheet(u"QLabel {\n"
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
"QDoubleSpinBox::up-arrow, QSpinBox::up-arrow { image: url(:/startrails/ui/arrow_up.svg); width: 10px; height: 6px; }\n"
"QDoubleSpinBox::down-arrow, QSpinBox::down-arrow { image: url(:/startrails/ui/arrow_down.svg); width: 10px; height: 6px; }")
        self.layout = QVBoxLayout(DetectSettings)
        self.layout.setSpacing(6)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.runLayout = QHBoxLayout()
        self.runLayout.setSpacing(0)
        self.runLayout.setObjectName(u"runLayout")
        self.run = QPushButton(DetectSettings)
        self.run.setObjectName(u"run")
        self.run.setEnabled(False)
        self.run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run.setStyleSheet(u"QPushButton#run {\n"
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
"    min-height: 34px;\n"
"    max-height: 34px;\n"
"}\n"
"QPushButton#run:hover {\n"
"    background-color: #075985;\n"
"}\n"
"QPushButton#run:disabled {\n"
"    background-color: #e2e8f0;\n"
"    color: #94a3b8;\n"
"}\n"
"QPushButton#run:focus:enabled { border-color: #ffffff; }")

        self.runLayout.addWidget(self.run)

        self.advancedToggle = QToolButton(DetectSettings)
        self.advancedToggle.setObjectName(u"advancedToggle")
        self.advancedToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.advancedToggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.advancedToggle.setStyleSheet(u"QToolButton#advancedToggle {\n"
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
"}")
        self.advancedToggle.setCheckable(True)
        self.advancedToggle.setChecked(True)
        self.advancedToggle.setArrowType(Qt.ArrowType.DownArrow)

        self.runLayout.addWidget(self.advancedToggle)


        self.layout.addLayout(self.runLayout)

        self.advancedBody = QWidget(DetectSettings)
        self.advancedBody.setObjectName(u"advancedBody")
        self.advancedBody.setStyleSheet(u"QWidget#advancedBody {\n"
"    background: transparent;\n"
"}")
        self.advancedLayout = QVBoxLayout(self.advancedBody)
        self.advancedLayout.setSpacing(6)
        self.advancedLayout.setObjectName(u"advancedLayout")
        self.advancedLayout.setContentsMargins(0, 0, 0, 0)
        self.fields = QGridLayout()
        self.fields.setSpacing(8)
        self.fields.setObjectName(u"fields")
        self.fields.setContentsMargins(0, 0, 0, 0)
        self.confidenceLabel = QLabel(self.advancedBody)
        self.confidenceLabel.setObjectName(u"confidenceLabel")

        self.fields.addWidget(self.confidenceLabel, 0, 0, 1, 1)

        self.confidence = QDoubleSpinBox(self.advancedBody)
        self.confidence.setObjectName(u"confidence")
        self.confidence.setMaximum(1.000000000000000)
        self.confidence.setSingleStep(0.050000000000000)
        self.confidence.setValue(0.300000000000000)

        self.fields.addWidget(self.confidence, 0, 1, 1, 1, Qt.AlignmentFlag.AlignRight)

        self.mergeLabel = QLabel(self.advancedBody)
        self.mergeLabel.setObjectName(u"mergeLabel")

        self.fields.addWidget(self.mergeLabel, 1, 0, 1, 1)

        self.detectMergeContainer = QFrame(self.advancedBody)
        self.detectMergeContainer.setObjectName(u"detectMergeContainer")
        self.detectMergeContainer.setStyleSheet(u"background-color: #f1f5f9;\n"
"border-radius: 6px;\n"
"padding: 2px;")
        self.detectMergeLayout = QHBoxLayout(self.detectMergeContainer)
        self.detectMergeLayout.setSpacing(2)
        self.detectMergeLayout.setObjectName(u"detectMergeLayout")
        self.detectMergeLayout.setContentsMargins(0, 0, 0, 0)
        self.detectMergeNMS = QPushButton(self.detectMergeContainer)
        self.detectMergeGroup = QButtonGroup(DetectSettings)
        self.detectMergeGroup.setObjectName(u"detectMergeGroup")
        self.detectMergeGroup.addButton(self.detectMergeNMS)
        self.detectMergeNMS.setObjectName(u"detectMergeNMS")
        self.detectMergeNMS.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.detectMergeNMS.setStyleSheet(u"QPushButton {\n"
"    padding: 3px 8px;\n"
"    border-radius: 4px;\n"
"    border: none;\n"
"    font-size: 11px;\n"
"    font-weight: 500;\n"
"    color: #334155;\n"
"}\n"
"QPushButton:checked {\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    font-weight: bold;\n"
"}\n"
"QPushButton:hover:!checked {\n"
"    background-color: #e2e8f0;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton:focus:enabled {\n"
"    border: 1px solid #0f172a;\n"
"}\n"
"QPushButton:checked:focus:enabled {\n"
"    border: 1px solid #ffffff;\n"
"}")
        self.detectMergeNMS.setCheckable(True)
        self.detectMergeNMS.setChecked(True)

        self.detectMergeLayout.addWidget(self.detectMergeNMS)

        self.detectMergeNMM = QPushButton(self.detectMergeContainer)
        self.detectMergeGroup.addButton(self.detectMergeNMM)
        self.detectMergeNMM.setObjectName(u"detectMergeNMM")
        self.detectMergeNMM.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.detectMergeNMM.setStyleSheet(u"QPushButton {\n"
"    padding: 3px 8px;\n"
"    border-radius: 4px;\n"
"    border: none;\n"
"    font-size: 11px;\n"
"    font-weight: 500;\n"
"    color: #334155;\n"
"}\n"
"QPushButton:checked {\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    font-weight: bold;\n"
"}\n"
"QPushButton:hover:!checked {\n"
"    background-color: #e2e8f0;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton:focus:enabled {\n"
"    border: 1px solid #0f172a;\n"
"}\n"
"QPushButton:checked:focus:enabled {\n"
"    border: 1px solid #ffffff;\n"
"}")
        self.detectMergeNMM.setCheckable(True)

        self.detectMergeLayout.addWidget(self.detectMergeNMM)


        self.fields.addWidget(self.detectMergeContainer, 1, 1, 1, 1, Qt.AlignmentFlag.AlignRight)

        self.thresholdLabel = QLabel(self.advancedBody)
        self.thresholdLabel.setObjectName(u"thresholdLabel")

        self.fields.addWidget(self.thresholdLabel, 2, 0, 1, 1)

        self.mergeThreshold = QDoubleSpinBox(self.advancedBody)
        self.mergeThreshold.setObjectName(u"mergeThreshold")
        self.mergeThreshold.setMaximum(1.000000000000000)
        self.mergeThreshold.setSingleStep(0.050000000000000)
        self.mergeThreshold.setValue(0.200000000000000)

        self.fields.addWidget(self.mergeThreshold, 2, 1, 1, 1, Qt.AlignmentFlag.AlignRight)

        self.useGPULabel = QLabel(self.advancedBody)
        self.useGPULabel.setObjectName(u"useGPULabel")

        self.fields.addWidget(self.useGPULabel, 3, 0, 1, 1)

        self.useGPU = QCheckBox(self.advancedBody)
        self.useGPU.setObjectName(u"useGPU")
        self.useGPU.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.useGPU.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.useGPU.setStyleSheet(u"QCheckBox#useGPU { spacing: 0px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"QCheckBox#useGPU::indicator { width: 36px; height: 20px; border: 1px solid #64748b; border-radius: 10px; }\n"
"QCheckBox#useGPU::indicator:unchecked { image: url(:/startrails/ui/switch_off.svg); }\n"
"QCheckBox#useGPU::indicator:checked { image: url(:/startrails/ui/switch_on.svg); }\n"
"QCheckBox#useGPU:focus:enabled { border-color: #0f172a; }")
        self.useGPU.setChecked(True)

        self.fields.addWidget(self.useGPU, 3, 1, 1, 1, Qt.AlignmentFlag.AlignRight)

        self.fields.setColumnStretch(0, 1)
        self.fields.setColumnStretch(1, 2)

        self.advancedLayout.addLayout(self.fields)


        self.layout.addWidget(self.advancedBody)

        self.error = QLabel(DetectSettings)
        self.error.setObjectName(u"error")
        self.error.setStyleSheet(u"font-size: 11px;\n"
"color: #b91c1c;")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

#if QT_CONFIG(shortcut)
        self.confidenceLabel.setBuddy(self.confidence)
        self.thresholdLabel.setBuddy(self.mergeThreshold)
        self.useGPULabel.setBuddy(self.useGPU)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(DetectSettings)

        QMetaObject.connectSlotsByName(DetectSettings)
    # setupUi

    def retranslateUi(self, DetectSettings):
        self.run.setText(QCoreApplication.translate("DetectSettings", u"Detect Streaks", None))
#if QT_CONFIG(tooltip)
        self.advancedToggle.setToolTip(QCoreApplication.translate("DetectSettings", u"Advanced settings", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.advancedToggle.setAccessibleName(QCoreApplication.translate("DetectSettings", u"Advanced settings", None))
#endif // QT_CONFIG(accessibility)
        self.advancedToggle.setText("")
        self.confidenceLabel.setText(QCoreApplication.translate("DetectSettings", u"Confidence", None))
#if QT_CONFIG(accessibility)
        self.confidence.setAccessibleName(QCoreApplication.translate("DetectSettings", u"Confidence threshold", None))
#endif // QT_CONFIG(accessibility)
        self.mergeLabel.setText(QCoreApplication.translate("DetectSettings", u"Merging", None))
        self.detectMergeNMS.setText(QCoreApplication.translate("DetectSettings", u"NMS", None))
        self.detectMergeNMM.setText(QCoreApplication.translate("DetectSettings", u"Greedy NMM", None))
#if QT_CONFIG(tooltip)
        self.thresholdLabel.setToolTip(QCoreApplication.translate("DetectSettings", u"Merge threshold", None))
#endif // QT_CONFIG(tooltip)
        self.thresholdLabel.setText(QCoreApplication.translate("DetectSettings", u"Threshold", None))
#if QT_CONFIG(accessibility)
        self.mergeThreshold.setAccessibleName(QCoreApplication.translate("DetectSettings", u"Merge threshold", None))
#endif // QT_CONFIG(accessibility)
        self.useGPULabel.setText(QCoreApplication.translate("DetectSettings", u"Use GPU", None))
#if QT_CONFIG(accessibility)
        self.useGPU.setAccessibleName(QCoreApplication.translate("DetectSettings", u"Use GPU for detection", None))
#endif // QT_CONFIG(accessibility)
        self.useGPU.setText("")
        self.error.setText("")
        pass
    # retranslateUi

Ui_detectSettings = Ui_DetectSettings
