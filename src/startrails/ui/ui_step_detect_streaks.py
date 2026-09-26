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
    QFormLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget)

class Ui_DetectSettings(object):
    def setupUi(self, detectSettings):
        if not detectSettings.objectName():
            detectSettings.setObjectName(u"detectSettings")
        self.layout = QVBoxLayout(detectSettings)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.fields = QFormLayout()
        self.fields.setObjectName(u"fields")
        self.fields.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.fields.setRowWrapPolicy(QFormLayout.WrapLongRows)
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

        self.mergeMethod = QComboBox(detectSettings)
        self.mergeMethod.addItem("")
        self.mergeMethod.addItem("")
        self.mergeMethod.setObjectName(u"mergeMethod")

        self.fields.setWidget(1, QFormLayout.FieldRole, self.mergeMethod)

        self.thresholdLabel = QLabel(detectSettings)
        self.thresholdLabel.setObjectName(u"thresholdLabel")

        self.fields.setWidget(2, QFormLayout.LabelRole, self.thresholdLabel)

        self.mergeThreshold = QDoubleSpinBox(detectSettings)
        self.mergeThreshold.setObjectName(u"mergeThreshold")
        self.mergeThreshold.setMaximum(1.000000000000000)
        self.mergeThreshold.setSingleStep(0.050000000000000)
        self.mergeThreshold.setValue(0.200000000000000)

        self.fields.setWidget(2, QFormLayout.FieldRole, self.mergeThreshold)


        self.layout.addLayout(self.fields)

        self.useGPU = QCheckBox(detectSettings)
        self.useGPU.setObjectName(u"useGPU")

        self.layout.addWidget(self.useGPU)

        self.deviceHint = QLabel(detectSettings)
        self.deviceHint.setObjectName(u"deviceHint")
        self.deviceHint.setWordWrap(True)

        self.layout.addWidget(self.deviceHint)

        self.error = QLabel(detectSettings)
        self.error.setObjectName(u"error")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

        self.run = QPushButton(detectSettings)
        self.run.setObjectName(u"run")
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

        self.thresholdLabel.setText(QCoreApplication.translate("DetectSettings", u"Merge &threshold", None))
        self.useGPU.setText(QCoreApplication.translate("DetectSettings", u"Use GPU", None))
        self.deviceHint.setText(QCoreApplication.translate("DetectSettings", u"Add input files to check the device.", None))
        self.error.setText("")
        self.run.setText(QCoreApplication.translate("DetectSettings", u"Detect Streaks", None))
        pass
    # retranslateUi

