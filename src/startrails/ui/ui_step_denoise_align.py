# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_denoise_align.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QToolButton, QVBoxLayout,
    QWidget)

from startrails.ui.checkbox_label import CheckboxLabel
from . import resources_rc

class Ui_DenoiseAlignSettings(object):
    def setupUi(self, DenoiseAlignSettings):
        if not DenoiseAlignSettings.objectName():
            DenoiseAlignSettings.setObjectName(u"DenoiseAlignSettings")
        DenoiseAlignSettings.resize(300, 261)
        self.layout = QVBoxLayout(DenoiseAlignSettings)
        self.layout.setSpacing(6)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.refLayout = QHBoxLayout()
        self.refLayout.setSpacing(6)
        self.refLayout.setObjectName(u"refLayout")
        self.refFrameLabel = QLabel(DenoiseAlignSettings)
        self.refFrameLabel.setObjectName(u"refFrameLabel")

        self.refLayout.addWidget(self.refFrameLabel)

        self.referenceFile = QLabel(DenoiseAlignSettings)
        self.referenceFile.setObjectName(u"referenceFile")
        self.referenceFile.setStyleSheet(u"QLabel#referenceFile {\n"
"    color: #1d4ed8;\n"
"    font-weight: 600;\n"
"    font-size: 12px;\n"
"    background-color: #eff6ff;\n"
"    border: 1px solid #bfdbfe;\n"
"    border-radius: 4px;\n"
"    padding: 2px 6px;\n"
"}")
        self.referenceFile.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.refLayout.addWidget(self.referenceFile)


        self.layout.addLayout(self.refLayout)

        self.runLayout = QHBoxLayout()
        self.runLayout.setSpacing(0)
        self.runLayout.setObjectName(u"runLayout")
        self.run = QPushButton(DenoiseAlignSettings)
        self.run.setObjectName(u"run")
        self.run.setEnabled(False)
        self.run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.runLayout.addWidget(self.run)

        self.advancedToggle = QToolButton(DenoiseAlignSettings)
        self.advancedToggle.setObjectName(u"advancedToggle")
        self.advancedToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.advancedToggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.advancedToggle.setCheckable(True)
        self.advancedToggle.setChecked(False)
        self.advancedToggle.setArrowType(Qt.ArrowType.RightArrow)

        self.runLayout.addWidget(self.advancedToggle)


        self.layout.addLayout(self.runLayout)

        self.alignStatus = QLabel(DenoiseAlignSettings)
        self.alignStatus.setObjectName(u"alignStatus")
        self.alignStatus.setStyleSheet(u"color: #64748b; font-size: 11px;")
        self.alignStatus.setWordWrap(True)

        self.layout.addWidget(self.alignStatus)

        self.advancedBody = QWidget(DenoiseAlignSettings)
        self.advancedBody.setObjectName(u"advancedBody")
        self.advancedLayout = QVBoxLayout(self.advancedBody)
        self.advancedLayout.setSpacing(6)
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
        self.useGPU.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.useGPU.setStyleSheet(u"QCheckBox#useGPU { spacing: 0px;}\n"
"QCheckBox#useGPU::indicator { width: 36px; height: 20px; border-radius: 10px; }\n"
"QCheckBox#useGPU::indicator:unchecked { image: url(:/startrails/ui/switch_off.svg); }\n"
"QCheckBox#useGPU::indicator:checked { image: url(:/startrails/ui/switch_on.svg); }\n"
"")
        self.useGPU.setChecked(True)

        self.useGPURow.addWidget(self.useGPU, 0, Qt.AlignmentFlag.AlignRight)


        self.advancedLayout.addLayout(self.useGPURow)


        self.layout.addWidget(self.advancedBody)

        self.error = QLabel(DenoiseAlignSettings)
        self.error.setObjectName(u"error")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

#if QT_CONFIG(shortcut)
        self.useGPULabel.setBuddy(self.useGPU)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(DenoiseAlignSettings)

        QMetaObject.connectSlotsByName(DenoiseAlignSettings)
    # setupUi

    def retranslateUi(self, DenoiseAlignSettings):
        self.refFrameLabel.setText(QCoreApplication.translate("DenoiseAlignSettings", u"Reference Frame:", None))
        self.referenceFile.setText(QCoreApplication.translate("DenoiseAlignSettings", u"None", None))
#if QT_CONFIG(tooltip)
        self.run.setToolTip(QCoreApplication.translate("DenoiseAlignSettings", u"Compute star alignment transforms and generate gradient mask", None))
#endif // QT_CONFIG(tooltip)
        self.run.setText(QCoreApplication.translate("DenoiseAlignSettings", u"Align Stars", None))
#if QT_CONFIG(tooltip)
        self.advancedToggle.setToolTip(QCoreApplication.translate("DenoiseAlignSettings", u"Show advanced settings", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.advancedToggle.setAccessibleName(QCoreApplication.translate("DenoiseAlignSettings", u"Show advanced settings", None))
#endif // QT_CONFIG(accessibility)
        self.advancedToggle.setText("")
        self.alignStatus.setText(QCoreApplication.translate("DenoiseAlignSettings", u"Homographies: 0 computed", None))
        self.useGPULabel.setText(QCoreApplication.translate("DenoiseAlignSettings", u"Use GPU Acceleration", None))
#if QT_CONFIG(accessibility)
        self.useGPU.setAccessibleName(QCoreApplication.translate("DenoiseAlignSettings", u"Use GPU Acceleration", None))
#endif // QT_CONFIG(accessibility)
        self.useGPU.setText("")
        pass
    # retranslateUi

Ui_denoiseAlignSettings = Ui_DenoiseAlignSettings
