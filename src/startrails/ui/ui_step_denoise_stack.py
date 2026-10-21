# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_denoise_stack.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpinBox, QToolButton, QVBoxLayout, QWidget)

from startrails.ui.checkbox_label import CheckboxLabel
from . import resources_rc

class Ui_DenoiseStackSettings(object):
    def setupUi(self, DenoiseStackSettings):
        if not DenoiseStackSettings.objectName():
            DenoiseStackSettings.setObjectName(u"DenoiseStackSettings")
        DenoiseStackSettings.resize(300, 270)
        self.layout = QVBoxLayout(DenoiseStackSettings)
        self.layout.setSpacing(6)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.methodRow = QHBoxLayout()
        self.methodRow.setSpacing(6)
        self.methodRow.setObjectName(u"methodRow")
        self.methodLabel = QLabel(DenoiseStackSettings)
        self.methodLabel.setObjectName(u"methodLabel")

        self.methodRow.addWidget(self.methodLabel)

        self.method = QComboBox(DenoiseStackSettings)
        self.method.addItem("")
        self.method.addItem("")
        self.method.setObjectName(u"method")

        self.methodRow.addWidget(self.method)


        self.layout.addLayout(self.methodRow)

        self.thresholdRow = QHBoxLayout()
        self.thresholdRow.setSpacing(6)
        self.thresholdRow.setObjectName(u"thresholdRow")
        self.sigmaThresholdLabel = QLabel(DenoiseStackSettings)
        self.sigmaThresholdLabel.setObjectName(u"sigmaThresholdLabel")

        self.thresholdRow.addWidget(self.sigmaThresholdLabel)

        self.sigmaThreshold = QDoubleSpinBox(DenoiseStackSettings)
        self.sigmaThreshold.setObjectName(u"sigmaThreshold")
        self.sigmaThreshold.setMaximumSize(QSize(80, 16777215))
        self.sigmaThreshold.setMinimum(0.500000000000000)
        self.sigmaThreshold.setMaximum(5.000000000000000)
        self.sigmaThreshold.setSingleStep(0.100000000000000)

        self.thresholdRow.addWidget(self.sigmaThreshold)


        self.layout.addLayout(self.thresholdRow)

        self.runLayout = QHBoxLayout()
        self.runLayout.setSpacing(0)
        self.runLayout.setObjectName(u"runLayout")
        self.run = QPushButton(DenoiseStackSettings)
        self.run.setObjectName(u"run")
        self.run.setEnabled(False)
        self.run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.runLayout.addWidget(self.run)

        self.advancedToggle = QToolButton(DenoiseStackSettings)
        self.advancedToggle.setObjectName(u"advancedToggle")
        self.advancedToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.advancedToggle.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.advancedToggle.setCheckable(True)
        self.advancedToggle.setChecked(False)
        self.advancedToggle.setArrowType(Qt.ArrowType.RightArrow)

        self.runLayout.addWidget(self.advancedToggle)


        self.layout.addLayout(self.runLayout)

        self.outputFileName = QLabel(DenoiseStackSettings)
        self.outputFileName.setObjectName(u"outputFileName")
        self.outputFileName.setStyleSheet(u"font-size: 11px; color: #64748b;")

        self.layout.addWidget(self.outputFileName)

        self.stackStatus = QLabel(DenoiseStackSettings)
        self.stackStatus.setObjectName(u"stackStatus")
        self.stackStatus.setStyleSheet(u"color: #64748b; font-size: 11px;")
        self.stackStatus.setWordWrap(True)

        self.layout.addWidget(self.stackStatus)

        self.advancedBody = QWidget(DenoiseStackSettings)
        self.advancedBody.setObjectName(u"advancedBody")
        self.advancedLayout = QVBoxLayout(self.advancedBody)
        self.advancedLayout.setSpacing(4)
        self.advancedLayout.setObjectName(u"advancedLayout")
        self.advancedLayout.setContentsMargins(4, 2, 4, 2)
        self.useGPURow = QHBoxLayout()
        self.useGPURow.setObjectName(u"useGPURow")
        self.useGPULabel = CheckboxLabel(self.advancedBody)
        self.useGPULabel.setObjectName(u"useGPULabel")
        self.useGPULabel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.useGPULabel.setStyleSheet(u"color: #334155; font-size: 12px;")

        self.useGPURow.addWidget(self.useGPULabel)

        self.useGPU = QCheckBox(self.advancedBody)
        self.useGPU.setObjectName(u"useGPU")
        self.useGPU.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.useGPU.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.useGPURow.addWidget(self.useGPU, 0, Qt.AlignmentFlag.AlignRight)


        self.advancedLayout.addLayout(self.useGPURow)

        self.compressionRow = QHBoxLayout()
        self.compressionRow.setObjectName(u"compressionRow")
        self.compressionLabel = CheckboxLabel(self.advancedBody)
        self.compressionLabel.setObjectName(u"compressionLabel")
        self.compressionLabel.setWordWrap(True)

        self.compressionRow.addWidget(self.compressionLabel)

        self.compressIntermediateTiffs = QCheckBox(self.advancedBody)
        self.compressIntermediateTiffs.setObjectName(u"compressIntermediateTiffs")
        self.compressIntermediateTiffs.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.compressIntermediateTiffs.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.compressionRow.addWidget(self.compressIntermediateTiffs, 0, Qt.AlignmentFlag.AlignRight)


        self.advancedLayout.addLayout(self.compressionRow)

        self.iterationsRow = QHBoxLayout()
        self.iterationsRow.setObjectName(u"iterationsRow")
        self.sigmaIterationsLabel = QLabel(self.advancedBody)
        self.sigmaIterationsLabel.setObjectName(u"sigmaIterationsLabel")

        self.iterationsRow.addWidget(self.sigmaIterationsLabel)

        self.sigmaIterations = QSpinBox(self.advancedBody)
        self.sigmaIterations.setObjectName(u"sigmaIterations")
        self.sigmaIterations.setMinimum(1)
        self.sigmaIterations.setMaximum(10)

        self.iterationsRow.addWidget(self.sigmaIterations)


        self.advancedLayout.addLayout(self.iterationsRow)


        self.layout.addWidget(self.advancedBody)

        self.error = QLabel(DenoiseStackSettings)
        self.error.setObjectName(u"error")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

#if QT_CONFIG(shortcut)
        self.useGPULabel.setBuddy(self.useGPU)
        self.compressionLabel.setBuddy(self.compressIntermediateTiffs)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(DenoiseStackSettings)

        QMetaObject.connectSlotsByName(DenoiseStackSettings)
    # setupUi

    def retranslateUi(self, DenoiseStackSettings):
        self.methodLabel.setText(QCoreApplication.translate("DenoiseStackSettings", u"Method", None))
        self.method.setItemText(0, QCoreApplication.translate("DenoiseStackSettings", u"Sigma Clipped Mean", None))
        self.method.setItemText(1, QCoreApplication.translate("DenoiseStackSettings", u"Arithmetic Mean", None))

        self.sigmaThresholdLabel.setText(QCoreApplication.translate("DenoiseStackSettings", u"Threshold", None))
        self.sigmaThreshold.setSuffix(QCoreApplication.translate("DenoiseStackSettings", u" \u03c3", None))
#if QT_CONFIG(tooltip)
        self.run.setToolTip(QCoreApplication.translate("DenoiseStackSettings", u"Stack sky and ground base frames without blend or denoise", None))
#endif // QT_CONFIG(tooltip)
        self.run.setText(QCoreApplication.translate("DenoiseStackSettings", u"Generate Base Stack", None))
#if QT_CONFIG(tooltip)
        self.advancedToggle.setToolTip(QCoreApplication.translate("DenoiseStackSettings", u"Show advanced settings", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.advancedToggle.setAccessibleName(QCoreApplication.translate("DenoiseStackSettings", u"Show advanced settings", None))
#endif // QT_CONFIG(accessibility)
        self.advancedToggle.setText("")
        self.outputFileName.setText(QCoreApplication.translate("DenoiseStackSettings", u"Output: project.tif", None))
        self.stackStatus.setText(QCoreApplication.translate("DenoiseStackSettings", u"Base stacks: Not generated", None))
        self.useGPULabel.setText(QCoreApplication.translate("DenoiseStackSettings", u"Use GPU Acceleration", None))
#if QT_CONFIG(accessibility)
        self.useGPU.setAccessibleName(QCoreApplication.translate("DenoiseStackSettings", u"Use GPU Acceleration", None))
#endif // QT_CONFIG(accessibility)
        self.useGPU.setText("")
        self.compressionLabel.setText(QCoreApplication.translate("DenoiseStackSettings", u"Compress intermediate TIFFs", None))
#if QT_CONFIG(tooltip)
        self.compressionLabel.setToolTip(QCoreApplication.translate("DenoiseStackSettings", u"Smaller sky, ground, and base TIFF files. Turning this off saves faster and uses more disk space. Final TIFF exports remain compressed.", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.compressIntermediateTiffs.setAccessibleName(QCoreApplication.translate("DenoiseStackSettings", u"Compress intermediate TIFFs", None))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(tooltip)
        self.compressIntermediateTiffs.setToolTip(QCoreApplication.translate("DenoiseStackSettings", u"Save smaller intermediate TIFFs with lossless compression. Final TIFF exports remain compressed.", None))
#endif // QT_CONFIG(tooltip)
        self.compressIntermediateTiffs.setText("")
        self.sigmaIterationsLabel.setText(QCoreApplication.translate("DenoiseStackSettings", u"Iterations:", None))
        pass
    # retranslateUi

Ui_denoiseStackSettings = Ui_DenoiseStackSettings
