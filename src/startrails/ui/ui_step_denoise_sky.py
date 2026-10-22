# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_denoise_sky.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSlider,
    QSpinBox, QVBoxLayout, QWidget)

from startrails.ui.checkbox_label import CheckboxLabel
from . import resources_rc

class Ui_DenoiseSkySettings(object):
    def setupUi(self, DenoiseSkySettings):
        if not DenoiseSkySettings.objectName():
            DenoiseSkySettings.setObjectName(u"DenoiseSkySettings")
        DenoiseSkySettings.resize(300, 436)
        self.layout = QVBoxLayout(DenoiseSkySettings)
        self.layout.setSpacing(6)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.modelRow = QHBoxLayout()
        self.modelRow.setSpacing(6)
        self.modelRow.setObjectName(u"modelRow")
        self.modelLabel = QLabel(DenoiseSkySettings)
        self.modelLabel.setObjectName(u"modelLabel")

        self.modelRow.addWidget(self.modelLabel)

        self.modelType = QComboBox(DenoiseSkySettings)
        self.modelType.addItem("")
        self.modelType.addItem("")
        self.modelType.setObjectName(u"modelType")

        self.modelRow.addWidget(self.modelType)


        self.layout.addLayout(self.modelRow)

        self.actLayout = QHBoxLayout()
        self.actLayout.setSpacing(6)
        self.actLayout.setObjectName(u"actLayout")
        self.detect = QPushButton(DenoiseSkySettings)
        self.detect.setObjectName(u"detect")
        self.detect.setEnabled(False)
        self.detect.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.detect.setStyleSheet(u"QPushButton#detect {\n"
"    font-weight: bold;\n"
"    background-color: #2b5b84;\n"
"    color: #ffffff;\n"
"    padding: 6px 10px;\n"
"    border-radius: 4px;\n"
"    font-size: 12px;\n"
"    border: 1px solid transparent;\n"
"}\n"
"QPushButton#detect:hover {\n"
"    background-color: #3873a8;\n"
"}\n"
"QPushButton#detect:disabled {\n"
"    background-color: #cbd5e1;\n"
"    color: #94a3b8;\n"
"}")

        self.actLayout.addWidget(self.detect)

        self.refineMask = QPushButton(DenoiseSkySettings)
        self.refineMask.setObjectName(u"refineMask")
        self.refineMask.setEnabled(False)
        self.refineMask.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refineMask.setStyleSheet(u"QPushButton#refineMask {\n"
"    font-weight: bold;\n"
"    background-color: #3b6e4e;\n"
"    color: #ffffff;\n"
"    padding: 6px 10px;\n"
"    border-radius: 4px;\n"
"    font-size: 12px;\n"
"    border: 1px solid transparent;\n"
"}\n"
"QPushButton#refineMask:hover {\n"
"    background-color: #4b8c63;\n"
"}\n"
"QPushButton#refineMask:disabled {\n"
"    background-color: #cbd5e1;\n"
"    color: #94a3b8;\n"
"}")

        self.actLayout.addWidget(self.refineMask)


        self.layout.addLayout(self.actLayout)

        self.refineParamLayout = QHBoxLayout()
        self.refineParamLayout.setSpacing(6)
        self.refineParamLayout.setObjectName(u"refineParamLayout")
        self.searchRadiusLabel = QLabel(DenoiseSkySettings)
        self.searchRadiusLabel.setObjectName(u"searchRadiusLabel")

        self.refineParamLayout.addWidget(self.searchRadiusLabel)

        self.searchRadius = QSpinBox(DenoiseSkySettings)
        self.searchRadius.setObjectName(u"searchRadius")
        self.searchRadius.setMaximumSize(QSize(75, 16777215))
        self.searchRadius.setStyleSheet(u"")
        self.searchRadius.setMinimum(0)
        self.searchRadius.setMaximum(100)

        self.refineParamLayout.addWidget(self.searchRadius)

        self.erosionLabel = QLabel(DenoiseSkySettings)
        self.erosionLabel.setObjectName(u"erosionLabel")

        self.refineParamLayout.addWidget(self.erosionLabel)

        self.erosionPixels = QSpinBox(DenoiseSkySettings)
        self.erosionPixels.setObjectName(u"erosionPixels")
        self.erosionPixels.setMaximumSize(QSize(75, 16777215))
        self.erosionPixels.setStyleSheet(u"")
        self.erosionPixels.setMinimum(0)
        self.erosionPixels.setMaximum(50)

        self.refineParamLayout.addWidget(self.erosionPixels)


        self.layout.addLayout(self.refineParamLayout)

        self.showMaskOverlayRow = QHBoxLayout()
        self.showMaskOverlayRow.setObjectName(u"showMaskOverlayRow")
        self.showMaskOverlayLabel = CheckboxLabel(DenoiseSkySettings)
        self.showMaskOverlayLabel.setObjectName(u"showMaskOverlayLabel")
        self.showMaskOverlayLabel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.showMaskOverlayLabel.setStyleSheet(u"color: #334155; font-size: 12px;")

        self.showMaskOverlayRow.addWidget(self.showMaskOverlayLabel)

        self.showMaskOverlay = QCheckBox(DenoiseSkySettings)
        self.showMaskOverlay.setObjectName(u"showMaskOverlay")
        self.showMaskOverlay.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.showMaskOverlay.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.showMaskOverlay.setChecked(False)

        self.showMaskOverlayRow.addWidget(self.showMaskOverlay, 0, Qt.AlignmentFlag.AlignRight)


        self.layout.addLayout(self.showMaskOverlayRow)

        self.brushLayout = QHBoxLayout()
        self.brushLayout.setSpacing(6)
        self.brushLayout.setObjectName(u"brushLayout")
        self.brushLabel = QLabel(DenoiseSkySettings)
        self.brushLabel.setObjectName(u"brushLabel")

        self.brushLayout.addWidget(self.brushLabel)

        self.brushSlider = QSlider(DenoiseSkySettings)
        self.brushSlider.setObjectName(u"brushSlider")
        self.brushSlider.setMinimum(2)
        self.brushSlider.setMaximum(200)
        self.brushSlider.setOrientation(Qt.Orientation.Horizontal)

        self.brushLayout.addWidget(self.brushSlider)

        self.brushRadius = QSpinBox(DenoiseSkySettings)
        self.brushRadius.setObjectName(u"brushRadius")
        self.brushRadius.setStyleSheet(u"")
        self.brushRadius.setMinimum(2)
        self.brushRadius.setMaximum(200)

        self.brushLayout.addWidget(self.brushRadius)


        self.layout.addLayout(self.brushLayout)

        self.utilLayout = QHBoxLayout()
        self.utilLayout.setSpacing(6)
        self.utilLayout.setObjectName(u"utilLayout")
        self.clearMask = QPushButton(DenoiseSkySettings)
        self.clearMask.setObjectName(u"clearMask")
        self.clearMask.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clearMask.setStyleSheet(u"QPushButton#clearMask {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 4px;\n"
"    padding: 5px 8px;\n"
"    font-size: 11px;\n"
"    font-weight: 500;\n"
"}\n"
"QPushButton#clearMask:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}")

        self.utilLayout.addWidget(self.clearMask)

        self.fullFrameMask = QPushButton(DenoiseSkySettings)
        self.fullFrameMask.setObjectName(u"fullFrameMask")
        self.fullFrameMask.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.fullFrameMask.setStyleSheet(u"QPushButton#fullFrameMask {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 4px;\n"
"    padding: 5px 8px;\n"
"    font-size: 11px;\n"
"    font-weight: 500;\n"
"}\n"
"QPushButton#fullFrameMask:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}")

        self.utilLayout.addWidget(self.fullFrameMask)


        self.layout.addLayout(self.utilLayout)

        self.brushHint = QLabel(DenoiseSkySettings)
        self.brushHint.setObjectName(u"brushHint")
        self.brushHint.setStyleSheet(u"color: #64748b; font-size: 11px;")
        self.brushHint.setWordWrap(True)

        self.layout.addWidget(self.brushHint)

        self.error = QLabel(DenoiseSkySettings)
        self.error.setObjectName(u"error")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

#if QT_CONFIG(shortcut)
        self.showMaskOverlayLabel.setBuddy(self.showMaskOverlay)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(DenoiseSkySettings)

        QMetaObject.connectSlotsByName(DenoiseSkySettings)
    # setupUi

    def retranslateUi(self, DenoiseSkySettings):
        self.modelLabel.setText(QCoreApplication.translate("DenoiseSkySettings", u"Model:", None))
        self.modelType.setItemText(0, QCoreApplication.translate("DenoiseSkySettings", u"Nightstack (Fine-tuned SegFormer)", None))
        self.modelType.setItemText(1, QCoreApplication.translate("DenoiseSkySettings", u"SegFormer (ADE20K Pretrained)", None))

#if QT_CONFIG(tooltip)
        self.detect.setToolTip(QCoreApplication.translate("DenoiseSkySettings", u"Run automatic celestial sky detection and horizon refinement", None))
#endif // QT_CONFIG(tooltip)
        self.detect.setText(QCoreApplication.translate("DenoiseSkySettings", u"Detect Sky", None))
#if QT_CONFIG(tooltip)
        self.refineMask.setToolTip(QCoreApplication.translate("DenoiseSkySettings", u"Snap mask boundary edges to natural landscape horizon", None))
#endif // QT_CONFIG(tooltip)
        self.refineMask.setText(QCoreApplication.translate("DenoiseSkySettings", u"Refine Mask", None))
        self.searchRadiusLabel.setText(QCoreApplication.translate("DenoiseSkySettings", u"Radius:", None))
#if QT_CONFIG(tooltip)
        self.searchRadius.setToolTip(QCoreApplication.translate("DenoiseSkySettings", u"Search ribbon radius around rough boundary (0 = Adaptive)", None))
#endif // QT_CONFIG(tooltip)
        self.searchRadius.setSpecialValueText(QCoreApplication.translate("DenoiseSkySettings", u"Auto", None))
        self.searchRadius.setSuffix(QCoreApplication.translate("DenoiseSkySettings", u" px", None))
        self.erosionLabel.setText(QCoreApplication.translate("DenoiseSkySettings", u"Erosion:", None))
#if QT_CONFIG(tooltip)
        self.erosionPixels.setToolTip(QCoreApplication.translate("DenoiseSkySettings", u"Inward erosion radius in pixels to prevent sky mask bleeding onto foreground", None))
#endif // QT_CONFIG(tooltip)
        self.erosionPixels.setSpecialValueText(QCoreApplication.translate("DenoiseSkySettings", u"None (0 px)", None))
        self.erosionPixels.setSuffix(QCoreApplication.translate("DenoiseSkySettings", u" px", None))
#if QT_CONFIG(tooltip)
        self.showMaskOverlayLabel.setToolTip(QCoreApplication.translate("DenoiseSkySettings", u"Show sky mask on canvas and enable interactive brush editing tools", None))
#endif // QT_CONFIG(tooltip)
        self.showMaskOverlayLabel.setText(QCoreApplication.translate("DenoiseSkySettings", u"Show Mask Overlay", None))
#if QT_CONFIG(tooltip)
        self.showMaskOverlay.setToolTip(QCoreApplication.translate("DenoiseSkySettings", u"Show sky mask on canvas and enable interactive brush editing tools", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.showMaskOverlay.setAccessibleName(QCoreApplication.translate("DenoiseSkySettings", u"Show and edit mask overlay", None))
#endif // QT_CONFIG(accessibility)
        self.showMaskOverlay.setText("")
        self.brushLabel.setText(QCoreApplication.translate("DenoiseSkySettings", u"Brush:", None))
        self.brushRadius.setSuffix(QCoreApplication.translate("DenoiseSkySettings", u" px", None))
#if QT_CONFIG(tooltip)
        self.clearMask.setToolTip(QCoreApplication.translate("DenoiseSkySettings", u"Clear the entire sky mask (set to all ground)", None))
#endif // QT_CONFIG(tooltip)
        self.clearMask.setText(QCoreApplication.translate("DenoiseSkySettings", u"Clear", None))
#if QT_CONFIG(tooltip)
        self.fullFrameMask.setToolTip(QCoreApplication.translate("DenoiseSkySettings", u"Set entire image frame as sky (100% sky for deep sky scenes)", None))
#endif // QT_CONFIG(tooltip)
        self.fullFrameMask.setText(QCoreApplication.translate("DenoiseSkySettings", u"Full Frame", None))
        self.brushHint.setText(QCoreApplication.translate("DenoiseSkySettings", u"Brush: Left-click paint sky, Right-click erase.\n"
"Hotkeys: [ / ] or Ctrl+Wheel to resize.", None))
        pass
    # retranslateUi

Ui_denoiseSkySettings = Ui_DenoiseSkySettings
