# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_denoise_tune.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QDoubleSpinBox, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSlider,
    QVBoxLayout, QWidget)
from . import resources_rc

class Ui_DenoiseTuneSettings(object):
    def setupUi(self, DenoiseTuneSettings):
        if not DenoiseTuneSettings.objectName():
            DenoiseTuneSettings.setObjectName(u"DenoiseTuneSettings")
        DenoiseTuneSettings.resize(300, 442)
        self.layout = QVBoxLayout(DenoiseTuneSettings)
        self.layout.setSpacing(6)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.enableCorrectionsRow = QHBoxLayout()
        self.enableCorrectionsRow.setObjectName(u"enableCorrectionsRow")
        self.enableCorrectionsLabel = QLabel(DenoiseTuneSettings)
        self.enableCorrectionsLabel.setObjectName(u"enableCorrectionsLabel")
        self.enableCorrectionsLabel.setStyleSheet(u"color: #334155; font-size: 12px;")

        self.enableCorrectionsRow.addWidget(self.enableCorrectionsLabel)

        self.enableCorrections = QCheckBox(DenoiseTuneSettings)
        self.enableCorrections.setObjectName(u"enableCorrections")
        self.enableCorrections.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.enableCorrections.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.enableCorrections.setStyleSheet(u"QCheckBox#enableCorrections { spacing: 0px;}\n"
"QCheckBox#enableCorrections::indicator { width: 36px; height: 20px; border-radius: 10px; }\n"
"QCheckBox#enableCorrections::indicator:unchecked { image: url(:/startrails/ui/switch_off.svg); }\n"
"QCheckBox#enableCorrections::indicator:checked { image: url(:/startrails/ui/switch_on.svg); }\n"
"")
        self.enableCorrections.setChecked(True)

        self.enableCorrectionsRow.addWidget(self.enableCorrections, 0, Qt.AlignmentFlag.AlignRight)


        self.layout.addLayout(self.enableCorrectionsRow)

        self.showGradientMaskRow = QHBoxLayout()
        self.showGradientMaskRow.setObjectName(u"showGradientMaskRow")
        self.showGradientMaskLabel = QLabel(DenoiseTuneSettings)
        self.showGradientMaskLabel.setObjectName(u"showGradientMaskLabel")
        self.showGradientMaskLabel.setStyleSheet(u"color: #334155; font-size: 12px;")

        self.showGradientMaskRow.addWidget(self.showGradientMaskLabel)

        self.showGradientMask = QCheckBox(DenoiseTuneSettings)
        self.showGradientMask.setObjectName(u"showGradientMask")
        self.showGradientMask.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.showGradientMask.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.showGradientMask.setStyleSheet(u"QCheckBox#showGradientMask { spacing: 0px;}\n"
"QCheckBox#showGradientMask::indicator { width: 36px; height: 20px; border-radius: 10px; }\n"
"QCheckBox#showGradientMask::indicator:unchecked { image: url(:/startrails/ui/switch_off.svg); }\n"
"QCheckBox#showGradientMask::indicator:checked { image: url(:/startrails/ui/switch_on.svg); }\n"
"")
        self.showGradientMask.setChecked(False)

        self.showGradientMaskRow.addWidget(self.showGradientMask, 0, Qt.AlignmentFlag.AlignRight)


        self.layout.addLayout(self.showGradientMaskRow)

        self.colorDenoiseRow = QHBoxLayout()
        self.colorDenoiseRow.setSpacing(6)
        self.colorDenoiseRow.setObjectName(u"colorDenoiseRow")
        self.colorDenoiseLabel = QLabel(DenoiseTuneSettings)
        self.colorDenoiseLabel.setObjectName(u"colorDenoiseLabel")
        self.colorDenoiseLabel.setMinimumSize(QSize(82, 0))
        self.colorDenoiseLabel.setMaximumSize(QSize(82, 16777215))

        self.colorDenoiseRow.addWidget(self.colorDenoiseLabel)

        self.colorDenoiseSlider = QSlider(DenoiseTuneSettings)
        self.colorDenoiseSlider.setObjectName(u"colorDenoiseSlider")
        self.colorDenoiseSlider.setMinimumSize(QSize(60, 0))
        self.colorDenoiseSlider.setMinimum(0)
        self.colorDenoiseSlider.setMaximum(200)
        self.colorDenoiseSlider.setValue(100)
        self.colorDenoiseSlider.setOrientation(Qt.Orientation.Horizontal)

        self.colorDenoiseRow.addWidget(self.colorDenoiseSlider)

        self.colorStrength = QDoubleSpinBox(DenoiseTuneSettings)
        self.colorStrength.setObjectName(u"colorStrength")
        self.colorStrength.setMaximumSize(QSize(62, 16777215))
        self.colorStrength.setStyleSheet(u"")
        self.colorStrength.setMinimum(0.000000000000000)
        self.colorStrength.setMaximum(2.000000000000000)
        self.colorStrength.setSingleStep(0.050000000000000)
        self.colorStrength.setValue(1.000000000000000)

        self.colorDenoiseRow.addWidget(self.colorStrength)


        self.layout.addLayout(self.colorDenoiseRow)

        self.valueDenoiseRow = QHBoxLayout()
        self.valueDenoiseRow.setSpacing(6)
        self.valueDenoiseRow.setObjectName(u"valueDenoiseRow")
        self.valueDenoiseLabel = QLabel(DenoiseTuneSettings)
        self.valueDenoiseLabel.setObjectName(u"valueDenoiseLabel")
        self.valueDenoiseLabel.setMinimumSize(QSize(82, 0))
        self.valueDenoiseLabel.setMaximumSize(QSize(82, 16777215))

        self.valueDenoiseRow.addWidget(self.valueDenoiseLabel)

        self.valueDenoiseSlider = QSlider(DenoiseTuneSettings)
        self.valueDenoiseSlider.setObjectName(u"valueDenoiseSlider")
        self.valueDenoiseSlider.setMinimumSize(QSize(60, 0))
        self.valueDenoiseSlider.setMinimum(0)
        self.valueDenoiseSlider.setMaximum(200)
        self.valueDenoiseSlider.setValue(20)
        self.valueDenoiseSlider.setOrientation(Qt.Orientation.Horizontal)

        self.valueDenoiseRow.addWidget(self.valueDenoiseSlider)

        self.valueStrength = QDoubleSpinBox(DenoiseTuneSettings)
        self.valueStrength.setObjectName(u"valueStrength")
        self.valueStrength.setMaximumSize(QSize(62, 16777215))
        self.valueStrength.setStyleSheet(u"")
        self.valueStrength.setMinimum(0.000000000000000)
        self.valueStrength.setMaximum(2.000000000000000)
        self.valueStrength.setSingleStep(0.050000000000000)
        self.valueStrength.setValue(0.200000000000000)

        self.valueDenoiseRow.addWidget(self.valueStrength)


        self.layout.addLayout(self.valueDenoiseRow)

        self.blendRow = QHBoxLayout()
        self.blendRow.setSpacing(6)
        self.blendRow.setObjectName(u"blendRow")
        self.blendLabel = QLabel(DenoiseTuneSettings)
        self.blendLabel.setObjectName(u"blendLabel")
        self.blendLabel.setMinimumSize(QSize(82, 0))
        self.blendLabel.setMaximumSize(QSize(82, 16777215))

        self.blendRow.addWidget(self.blendLabel)

        self.blendSlider = QSlider(DenoiseTuneSettings)
        self.blendSlider.setObjectName(u"blendSlider")
        self.blendSlider.setMinimumSize(QSize(60, 0))
        self.blendSlider.setMinimum(0)
        self.blendSlider.setMaximum(100)
        self.blendSlider.setValue(60)
        self.blendSlider.setOrientation(Qt.Orientation.Horizontal)

        self.blendRow.addWidget(self.blendSlider)

        self.blendPercent = QDoubleSpinBox(DenoiseTuneSettings)
        self.blendPercent.setObjectName(u"blendPercent")
        self.blendPercent.setMaximumSize(QSize(62, 16777215))
        self.blendPercent.setStyleSheet(u"")
        self.blendPercent.setDecimals(0)
        self.blendPercent.setMinimum(0.000000000000000)
        self.blendPercent.setMaximum(100.000000000000000)
        self.blendPercent.setSingleStep(5.000000000000000)
        self.blendPercent.setValue(60.000000000000000)

        self.blendRow.addWidget(self.blendPercent)


        self.layout.addLayout(self.blendRow)

        self.blurRow = QHBoxLayout()
        self.blurRow.setSpacing(6)
        self.blurRow.setObjectName(u"blurRow")
        self.blurLabel = QLabel(DenoiseTuneSettings)
        self.blurLabel.setObjectName(u"blurLabel")
        self.blurLabel.setMinimumSize(QSize(82, 0))
        self.blurLabel.setMaximumSize(QSize(82, 16777215))

        self.blurRow.addWidget(self.blurLabel)

        self.blurSlider = QSlider(DenoiseTuneSettings)
        self.blurSlider.setObjectName(u"blurSlider")
        self.blurSlider.setMinimumSize(QSize(60, 0))
        self.blurSlider.setMinimum(0)
        self.blurSlider.setMaximum(50)
        self.blurSlider.setValue(2)
        self.blurSlider.setOrientation(Qt.Orientation.Horizontal)

        self.blurRow.addWidget(self.blurSlider)

        self.blurRadius = QDoubleSpinBox(DenoiseTuneSettings)
        self.blurRadius.setObjectName(u"blurRadius")
        self.blurRadius.setMaximumSize(QSize(62, 16777215))
        self.blurRadius.setStyleSheet(u"")
        self.blurRadius.setDecimals(0)
        self.blurRadius.setMinimum(0.000000000000000)
        self.blurRadius.setMaximum(50.000000000000000)
        self.blurRadius.setSingleStep(0.500000000000000)
        self.blurRadius.setValue(2.000000000000000)

        self.blurRow.addWidget(self.blurRadius)


        self.layout.addLayout(self.blurRow)

        self.tuneHint = QLabel(DenoiseTuneSettings)
        self.tuneHint.setObjectName(u"tuneHint")
        self.tuneHint.setStyleSheet(u"color: #64748b; font-size: 11px;")
        self.tuneHint.setWordWrap(True)

        self.layout.addWidget(self.tuneHint)

        self.runLayout = QHBoxLayout()
        self.runLayout.setSpacing(0)
        self.runLayout.setObjectName(u"runLayout")
        self.run = QPushButton(DenoiseTuneSettings)
        self.run.setObjectName(u"run")
        self.run.setEnabled(False)
        self.run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.runLayout.addWidget(self.run)


        self.layout.addLayout(self.runLayout)

        self.tuneStatus = QLabel(DenoiseTuneSettings)
        self.tuneStatus.setObjectName(u"tuneStatus")
        self.tuneStatus.setStyleSheet(u"color: #64748b; font-size: 11px;")
        self.tuneStatus.setWordWrap(True)

        self.layout.addWidget(self.tuneStatus)

        self.error = QLabel(DenoiseTuneSettings)
        self.error.setObjectName(u"error")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

#if QT_CONFIG(shortcut)
        self.enableCorrectionsLabel.setBuddy(self.enableCorrections)
        self.showGradientMaskLabel.setBuddy(self.showGradientMask)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(DenoiseTuneSettings)

        QMetaObject.connectSlotsByName(DenoiseTuneSettings)
    # setupUi

    def retranslateUi(self, DenoiseTuneSettings):
#if QT_CONFIG(tooltip)
        self.enableCorrectionsLabel.setToolTip(QCoreApplication.translate("DenoiseTuneSettings", u"Toggle all horizon gradient corrections (blend, denoise, blur) on or off", None))
#endif // QT_CONFIG(tooltip)
        self.enableCorrectionsLabel.setText(QCoreApplication.translate("DenoiseTuneSettings", u"Enable horizon corrections", None))
#if QT_CONFIG(tooltip)
        self.enableCorrections.setToolTip(QCoreApplication.translate("DenoiseTuneSettings", u"Toggle all horizon gradient corrections (blend, denoise, blur) on or off", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.enableCorrections.setAccessibleName(QCoreApplication.translate("DenoiseTuneSettings", u"Enable horizon corrections", None))
#endif // QT_CONFIG(accessibility)
        self.enableCorrections.setText("")
#if QT_CONFIG(tooltip)
        self.showGradientMaskLabel.setToolTip(QCoreApplication.translate("DenoiseTuneSettings", u"Render the sky coverage gradient mask as a translucent red overlay on the canvas", None))
#endif // QT_CONFIG(tooltip)
        self.showGradientMaskLabel.setText(QCoreApplication.translate("DenoiseTuneSettings", u"Show gradient mask (red overlay)", None))
#if QT_CONFIG(tooltip)
        self.showGradientMask.setToolTip(QCoreApplication.translate("DenoiseTuneSettings", u"Render the sky coverage gradient mask as a translucent red overlay on the canvas", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.showGradientMask.setAccessibleName(QCoreApplication.translate("DenoiseTuneSettings", u"Show gradient mask (red overlay)", None))
#endif // QT_CONFIG(accessibility)
        self.showGradientMask.setText("")
        self.colorDenoiseLabel.setText(QCoreApplication.translate("DenoiseTuneSettings", u"Color Denoise:", None))
        self.colorStrength.setSuffix(QCoreApplication.translate("DenoiseTuneSettings", u"x", None))
        self.valueDenoiseLabel.setText(QCoreApplication.translate("DenoiseTuneSettings", u"Value Denoise:", None))
        self.valueStrength.setSuffix(QCoreApplication.translate("DenoiseTuneSettings", u"x", None))
        self.blendLabel.setText(QCoreApplication.translate("DenoiseTuneSettings", u"Blend:", None))
        self.blendPercent.setSuffix(QCoreApplication.translate("DenoiseTuneSettings", u" %", None))
        self.blurLabel.setText(QCoreApplication.translate("DenoiseTuneSettings", u"Blur:", None))
        self.blurRadius.setSuffix(QCoreApplication.translate("DenoiseTuneSettings", u" px", None))
        self.tuneHint.setText(QCoreApplication.translate("DenoiseTuneSettings", u"Adjust sliders to configure settings. Live canvas update activates once base stacks are generated.", None))
#if QT_CONFIG(tooltip)
        self.run.setToolTip(QCoreApplication.translate("DenoiseTuneSettings", u"Apply horizon gradient corrections and generate final image", None))
#endif // QT_CONFIG(tooltip)
        self.run.setText(QCoreApplication.translate("DenoiseTuneSettings", u"Composite Final Image", None))
        self.tuneStatus.setText(QCoreApplication.translate("DenoiseTuneSettings", u"Requires base stacks", None))
        pass
    # retranslateUi

Ui_denoiseTuneSettings = Ui_DenoiseTuneSettings
