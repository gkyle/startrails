# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_stack_images.ui'
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
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSpinBox, QToolButton, QVBoxLayout,
    QWidget)
from . import resources_rc

class Ui_StackSettings(object):
    def setupUi(self, StackSettings):
        if not StackSettings.objectName():
            StackSettings.setObjectName(u"StackSettings")
        StackSettings.resize(258, 312)
        self.layout = QVBoxLayout(StackSettings)
        self.layout.setSpacing(6)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.fields = QGridLayout()
        self.fields.setSpacing(8)
        self.fields.setObjectName(u"fields")
        self.fields.setContentsMargins(0, 0, 0, 0)
        self.methodLabel = QLabel(StackSettings)
        self.methodLabel.setObjectName(u"methodLabel")
        self.methodLabel.setStyleSheet(u"QLabel#methodLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.fields.addWidget(self.methodLabel, 0, 0, 1, 1)

        self.method = QLabel(StackSettings)
        self.method.setObjectName(u"method")
        self.method.setStyleSheet(u"QLabel#method {\n"
"    color: #0f172a;\n"
"    font-size: 12px;\n"
"    font-weight: 500;\n"
"    background-color: #f8fafc;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 4px;\n"
"    padding: 3px 12px;\n"
"}")
        self.method.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.fields.addWidget(self.method, 0, 1, 1, 1, Qt.AlignmentFlag.AlignRight)

        self.streaksLabel = QLabel(StackSettings)
        self.streaksLabel.setObjectName(u"streaksLabel")
        self.streaksLabel.setStyleSheet(u"QLabel#streaksLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.fields.addWidget(self.streaksLabel, 1, 0, 1, 1)

        self.stackStreaksContainer = QFrame(StackSettings)
        self.stackStreaksContainer.setObjectName(u"stackStreaksContainer")
        self.stackStreaksContainer.setStyleSheet(u"QFrame#stackStreaksContainer {\n"
"    background-color: #f1f5f9;\n"
"    border-radius: 5px;\n"
"    padding: 2px;\n"
"}\n"
"QPushButton#stackStreaksKeep, QPushButton#stackStreaksRemove {\n"
"    background-color: transparent;\n"
"    color: #334155;\n"
"    border: 2px solid transparent;\n"
"    border-radius: 4px;\n"
"    font-size: 12px;\n"
"    font-weight: 500;\n"
"    padding: 4px 14px;\n"
"    min-height: 18px;\n"
"}\n"
"QPushButton#stackStreaksKeep:checked, QPushButton#stackStreaksRemove:checked {\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    font-weight: 600;\n"
"}\n"
"QPushButton#stackStreaksKeep:hover:!checked, QPushButton#stackStreaksRemove:hover:!checked {\n"
"    background-color: #e2e8f0;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton#stackStreaksRemove:disabled {\n"
"    color: #94a3b8;\n"
"    background-color: transparent;\n"
"}\n"
"QPushButton#stackStreaksKeep:focus:enabled, QPushButton#stackStreaksRemove:focus:enabled { border-color: #0f172a; }\n"
"QPushButton#stackStre"
                        "aksKeep:checked:focus:enabled, QPushButton#stackStreaksRemove:checked:focus:enabled { border-color: #ffffff; }")
        self.stackStreaksLayout = QHBoxLayout(self.stackStreaksContainer)
        self.stackStreaksLayout.setSpacing(2)
        self.stackStreaksLayout.setObjectName(u"stackStreaksLayout")
        self.stackStreaksLayout.setContentsMargins(0, 0, 0, 0)
        self.stackStreaksKeep = QPushButton(self.stackStreaksContainer)
        self.stackStreaksGroup = QButtonGroup(StackSettings)
        self.stackStreaksGroup.setObjectName(u"stackStreaksGroup")
        self.stackStreaksGroup.addButton(self.stackStreaksKeep)
        self.stackStreaksKeep.setObjectName(u"stackStreaksKeep")
        self.stackStreaksKeep.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackStreaksKeep.setCheckable(True)
        self.stackStreaksKeep.setChecked(True)

        self.stackStreaksLayout.addWidget(self.stackStreaksKeep)

        self.stackStreaksRemove = QPushButton(self.stackStreaksContainer)
        self.stackStreaksGroup.addButton(self.stackStreaksRemove)
        self.stackStreaksRemove.setObjectName(u"stackStreaksRemove")
        self.stackStreaksRemove.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackStreaksRemove.setCheckable(True)

        self.stackStreaksLayout.addWidget(self.stackStreaksRemove)


        self.fields.addWidget(self.stackStreaksContainer, 1, 1, 1, 1, Qt.AlignmentFlag.AlignRight)

        self.fadeLabel = QLabel(StackSettings)
        self.fadeLabel.setObjectName(u"fadeLabel")
        self.fadeLabel.setStyleSheet(u"QLabel#fadeLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.fields.addWidget(self.fadeLabel, 2, 0, 1, 1)

        self.stackFadeContainer = QFrame(StackSettings)
        self.stackFadeContainer.setObjectName(u"stackFadeContainer")
        self.stackFadeContainer.setStyleSheet(u"QFrame#stackFadeContainer {\n"
"    background-color: #f1f5f9;\n"
"    border-radius: 5px;\n"
"    padding: 2px;\n"
"}\n"
"QPushButton#stackFadeOff, QPushButton#stackFadeStart, QPushButton#stackFadeEnd, QPushButton#stackFadeBoth {\n"
"    background-color: transparent;\n"
"    color: #334155;\n"
"    border: 2px solid transparent;\n"
"    border-radius: 4px;\n"
"    font-size: 11px;\n"
"    font-weight: 500;\n"
"    padding: 4px 8px;\n"
"    min-height: 18px;\n"
"}\n"
"QPushButton#stackFadeOff:checked, QPushButton#stackFadeStart:checked, QPushButton#stackFadeEnd:checked, QPushButton#stackFadeBoth:checked {\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    font-weight: 600;\n"
"}\n"
"QPushButton#stackFadeOff:hover:!checked, QPushButton#stackFadeStart:hover:!checked, QPushButton#stackFadeEnd:hover:!checked, QPushButton#stackFadeBoth:hover:!checked {\n"
"    background-color: #e2e8f0;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton#stackFadeOff:focus:enabled, QPushButton#stackFadeStart:focus:enable"
                        "d, QPushButton#stackFadeEnd:focus:enabled, QPushButton#stackFadeBoth:focus:enabled { border-color: #0f172a; }\n"
"QPushButton#stackFadeOff:checked:focus:enabled, QPushButton#stackFadeStart:checked:focus:enabled, QPushButton#stackFadeEnd:checked:focus:enabled, QPushButton#stackFadeBoth:checked:focus:enabled { border-color: #ffffff; }")
        self.stackFadeLayout = QHBoxLayout(self.stackFadeContainer)
        self.stackFadeLayout.setSpacing(2)
        self.stackFadeLayout.setObjectName(u"stackFadeLayout")
        self.stackFadeLayout.setContentsMargins(0, 0, 0, 0)
        self.stackFadeOff = QPushButton(self.stackFadeContainer)
        self.stackFadeGroup = QButtonGroup(StackSettings)
        self.stackFadeGroup.setObjectName(u"stackFadeGroup")
        self.stackFadeGroup.addButton(self.stackFadeOff)
        self.stackFadeOff.setObjectName(u"stackFadeOff")
        self.stackFadeOff.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackFadeOff.setCheckable(True)

        self.stackFadeLayout.addWidget(self.stackFadeOff)

        self.stackFadeStart = QPushButton(self.stackFadeContainer)
        self.stackFadeGroup.addButton(self.stackFadeStart)
        self.stackFadeStart.setObjectName(u"stackFadeStart")
        self.stackFadeStart.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackFadeStart.setCheckable(True)

        self.stackFadeLayout.addWidget(self.stackFadeStart)

        self.stackFadeEnd = QPushButton(self.stackFadeContainer)
        self.stackFadeGroup.addButton(self.stackFadeEnd)
        self.stackFadeEnd.setObjectName(u"stackFadeEnd")
        self.stackFadeEnd.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackFadeEnd.setCheckable(True)

        self.stackFadeLayout.addWidget(self.stackFadeEnd)

        self.stackFadeBoth = QPushButton(self.stackFadeContainer)
        self.stackFadeGroup.addButton(self.stackFadeBoth)
        self.stackFadeBoth.setObjectName(u"stackFadeBoth")
        self.stackFadeBoth.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackFadeBoth.setCheckable(True)
        self.stackFadeBoth.setChecked(True)

        self.stackFadeLayout.addWidget(self.stackFadeBoth)


        self.fields.addWidget(self.stackFadeContainer, 2, 1, 1, 1, Qt.AlignmentFlag.AlignRight)

        self.amountLabel = QLabel(StackSettings)
        self.amountLabel.setObjectName(u"amountLabel")
        self.amountLabel.setStyleSheet(u"QLabel#amountLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"    margin-left: 12px;\n"
"    border-left: 2px solid #cbd5e1;\n"
"    padding-left: 8px;\n"
"}")

        self.fields.addWidget(self.amountLabel, 3, 0, 1, 1)

        self.fadeAmount = QSpinBox(StackSettings)
        self.fadeAmount.setObjectName(u"fadeAmount")
        self.fadeAmount.setStyleSheet(u"QSpinBox#fadeAmount {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #64748b;\n"
"    border-radius: 4px;\n"
"    padding: 4px 6px;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"    min-width: 75px;\n"
"    max-width: 75px;\n"
"}\n"
"QSpinBox#fadeAmount:focus {\n"
"    border: 2px solid #0369a1;\n"
"    padding: 3px 5px;\n"
"}\n"
"QSpinBox#fadeAmount:disabled {\n"
"    background-color: #f1f5f9;\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QSpinBox#fadeAmount::up-arrow { image: url(:/startrails/ui/arrow_up.svg); width: 10px; height: 6px; }\n"
"QSpinBox#fadeAmount::down-arrow { image: url(:/startrails/ui/arrow_down.svg); width: 10px; height: 6px; }")
        self.fadeAmount.setMaximum(100)
        self.fadeAmount.setValue(20)

        self.fields.addWidget(self.fadeAmount, 3, 1, 1, 1, Qt.AlignmentFlag.AlignRight)

        self.fields.setColumnStretch(0, 1)
        self.fields.setColumnStretch(1, 2)

        self.layout.addLayout(self.fields)

        self.runLayout = QHBoxLayout()
        self.runLayout.setSpacing(0)
        self.runLayout.setObjectName(u"runLayout")
        self.run = QPushButton(StackSettings)
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

        self.advancedToggle = QToolButton(StackSettings)
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

        self.advancedBody = QWidget(StackSettings)
        self.advancedBody.setObjectName(u"advancedBody")
        self.advancedBody.setStyleSheet(u"QWidget#advancedBody {\n"
"    background: transparent;\n"
"}")
        self.advancedLayout = QVBoxLayout(self.advancedBody)
        self.advancedLayout.setSpacing(6)
        self.advancedLayout.setObjectName(u"advancedLayout")
        self.advancedLayout.setContentsMargins(0, 0, 0, 0)
        self.gpuBatchGrid = QGridLayout()
        self.gpuBatchGrid.setSpacing(8)
        self.gpuBatchGrid.setObjectName(u"gpuBatchGrid")
        self.useGPULabel = QLabel(self.advancedBody)
        self.useGPULabel.setObjectName(u"useGPULabel")
        self.useGPULabel.setStyleSheet(u"QLabel#useGPULabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.gpuBatchGrid.addWidget(self.useGPULabel, 0, 0, 1, 1)

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

        self.gpuBatchGrid.addWidget(self.useGPU, 0, 1, 1, 1, Qt.AlignmentFlag.AlignRight)

        self.batchLabel = QLabel(self.advancedBody)
        self.batchLabel.setObjectName(u"batchLabel")
        self.batchLabel.setStyleSheet(u"QLabel#batchLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.gpuBatchGrid.addWidget(self.batchLabel, 1, 0, 1, 1)

        self.batchSize = QSpinBox(self.advancedBody)
        self.batchSize.setObjectName(u"batchSize")
        self.batchSize.setStyleSheet(u"QSpinBox#batchSize {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #64748b;\n"
"    border-radius: 4px;\n"
"    padding: 4px 6px;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"    min-width: 75px;\n"
"    max-width: 75px;\n"
"}\n"
"QSpinBox#batchSize:focus {\n"
"    border: 2px solid #0369a1;\n"
"    padding: 3px 5px;\n"
"}\n"
"QSpinBox#batchSize::up-arrow { image: url(:/startrails/ui/arrow_up.svg); width: 10px; height: 6px; }\n"
"QSpinBox#batchSize::down-arrow { image: url(:/startrails/ui/arrow_down.svg); width: 10px; height: 6px; }")
        self.batchSize.setMinimum(1)
        self.batchSize.setMaximum(2147483647)
        self.batchSize.setValue(16)

        self.gpuBatchGrid.addWidget(self.batchSize, 1, 1, 1, 1, Qt.AlignmentFlag.AlignRight)

        self.gpuBatchGrid.setColumnStretch(0, 1)
        self.gpuBatchGrid.setColumnStretch(1, 2)

        self.advancedLayout.addLayout(self.gpuBatchGrid)

        self.memory = QLabel(self.advancedBody)
        self.memory.setObjectName(u"memory")
        self.memory.setStyleSheet(u"QLabel#memory {\n"
"    font-size: 11px;\n"
"    color: #64748b;\n"
"    padding-top: 2px;\n"
"}")
        self.memory.setWordWrap(True)

        self.advancedLayout.addWidget(self.memory)


        self.layout.addWidget(self.advancedBody)

        self.error = QLabel(StackSettings)
        self.error.setObjectName(u"error")
        self.error.setStyleSheet(u"QLabel#error {\n"
"    font-size: 11px;\n"
"    color: #b91c1c;\n"
"}")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

#if QT_CONFIG(shortcut)
        self.amountLabel.setBuddy(self.fadeAmount)
        self.useGPULabel.setBuddy(self.useGPU)
        self.batchLabel.setBuddy(self.batchSize)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(StackSettings)

        QMetaObject.connectSlotsByName(StackSettings)
    # setupUi

    def retranslateUi(self, StackSettings):
        self.methodLabel.setText(QCoreApplication.translate("StackSettings", u"Method", None))
        self.method.setText(QCoreApplication.translate("StackSettings", u"Lighten", None))
        self.streaksLabel.setText(QCoreApplication.translate("StackSettings", u"Streaks", None))
        self.stackStreaksKeep.setText(QCoreApplication.translate("StackSettings", u"Keep", None))
        self.stackStreaksRemove.setText(QCoreApplication.translate("StackSettings", u"Remove", None))
        self.fadeLabel.setText(QCoreApplication.translate("StackSettings", u"Fade frames", None))
        self.stackFadeOff.setText(QCoreApplication.translate("StackSettings", u"Off", None))
        self.stackFadeStart.setText(QCoreApplication.translate("StackSettings", u"Start", None))
        self.stackFadeEnd.setText(QCoreApplication.translate("StackSettings", u"End", None))
        self.stackFadeBoth.setText(QCoreApplication.translate("StackSettings", u"Both", None))
        self.amountLabel.setText(QCoreApplication.translate("StackSettings", u"Amount", None))
#if QT_CONFIG(accessibility)
        self.fadeAmount.setAccessibleName(QCoreApplication.translate("StackSettings", u"Fade amount", None))
#endif // QT_CONFIG(accessibility)
        self.fadeAmount.setSuffix(QCoreApplication.translate("StackSettings", u"%", None))
        self.run.setText(QCoreApplication.translate("StackSettings", u"Stack Images", None))
#if QT_CONFIG(tooltip)
        self.advancedToggle.setToolTip(QCoreApplication.translate("StackSettings", u"Advanced settings", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.advancedToggle.setAccessibleName(QCoreApplication.translate("StackSettings", u"Advanced settings", None))
#endif // QT_CONFIG(accessibility)
        self.advancedToggle.setText("")
        self.useGPULabel.setText(QCoreApplication.translate("StackSettings", u"Use GPU", None))
#if QT_CONFIG(accessibility)
        self.useGPU.setAccessibleName(QCoreApplication.translate("StackSettings", u"Use GPU for stacking", None))
#endif // QT_CONFIG(accessibility)
        self.useGPU.setText("")
        self.batchLabel.setText(QCoreApplication.translate("StackSettings", u"&Batch size", None))
#if QT_CONFIG(accessibility)
        self.batchSize.setAccessibleName(QCoreApplication.translate("StackSettings", u"Batch size", None))
#endif // QT_CONFIG(accessibility)
        self.memory.setText(QCoreApplication.translate("StackSettings", u"Add input files for a batch suggestion.", None))
        self.error.setText("")
        pass
    # retranslateUi

Ui_stackSettings = Ui_StackSettings
