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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout,
    QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSpinBox, QToolButton, QVBoxLayout,
    QWidget)
from . import resources_rc

class Ui_StackSettings(object):
    def setupUi(self, stackSettings):
        if not stackSettings.objectName():
            stackSettings.setObjectName(u"stackSettings")
        stackSettings.setStyleSheet(u"QLabel {\n"
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
"QLabel#memory {\n"
"    font-size: 11px;\n"
"    color: #64748b;\n"
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
"    font-"
                        "size: 13px;\n"
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
"    background-color: #"
                        "e2e8f0;\n"
"    color: #94a3b8;\n"
"    border-left: 1px solid #cbd5e1;\n"
"}\n"
"QCheckBox:focus:enabled { border-color: #0f172a; }\n"
"QDoubleSpinBox::up-arrow, QSpinBox::up-arrow { image: url(:/startrails/ui/arrow_up.svg); width: 10px; height: 6px; }\n"
"QDoubleSpinBox::down-arrow, QSpinBox::down-arrow { image: url(:/startrails/ui/arrow_down.svg); width: 10px; height: 6px; }")
        self.layout = QVBoxLayout(stackSettings)
        self.layout.setSpacing(6)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.fields = QFormLayout()
        self.fields.setObjectName(u"fields")
        self.fields.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.fields.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.fields.setHorizontalSpacing(8)
        self.fields.setVerticalSpacing(6)
        self.methodLabel = QLabel(stackSettings)
        self.methodLabel.setObjectName(u"methodLabel")

        self.fields.setWidget(0, QFormLayout.LabelRole, self.methodLabel)

        self.method = QLabel(stackSettings)
        self.method.setObjectName(u"method")
        font = QFont()
        font.setBold(True)
        self.method.setFont(font)

        self.fields.setWidget(0, QFormLayout.FieldRole, self.method)

        self.streaksLabel = QLabel(stackSettings)
        self.streaksLabel.setObjectName(u"streaksLabel")

        self.fields.setWidget(1, QFormLayout.LabelRole, self.streaksLabel)

        self.streaks = QComboBox(stackSettings)
        self.streaks.addItem("")
        self.streaks.addItem("")
        self.streaks.setObjectName(u"streaks")

        self.fields.setWidget(1, QFormLayout.FieldRole, self.streaks)

        self.fadeLabel = QLabel(stackSettings)
        self.fadeLabel.setObjectName(u"fadeLabel")

        self.fields.setWidget(2, QFormLayout.LabelRole, self.fadeLabel)

        self.fadeRow = QHBoxLayout()
        self.fadeRow.setSpacing(6)
        self.fadeRow.setObjectName(u"fadeRow")
        self.fade = QComboBox(stackSettings)
        self.fade.addItem("")
        self.fade.addItem("")
        self.fade.addItem("")
        self.fade.addItem("")
        self.fade.setObjectName(u"fade")

        self.fadeRow.addWidget(self.fade)

        self.amountLabel = QLabel(stackSettings)
        self.amountLabel.setObjectName(u"amountLabel")

        self.fadeRow.addWidget(self.amountLabel)

        self.fadeAmount = QSpinBox(stackSettings)
        self.fadeAmount.setObjectName(u"fadeAmount")
        self.fadeAmount.setMaximum(100)
        self.fadeAmount.setValue(20)

        self.fadeRow.addWidget(self.fadeAmount)


        self.fields.setLayout(2, QFormLayout.FieldRole, self.fadeRow)


        self.layout.addLayout(self.fields)

        self.runLayout = QHBoxLayout()
        self.runLayout.setSpacing(0)
        self.runLayout.setObjectName(u"runLayout")
        self.run = QPushButton(stackSettings)
        self.run.setObjectName(u"run")
        self.run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run.setEnabled(False)

        self.runLayout.addWidget(self.run)

        self.advancedToggle = QToolButton(stackSettings)
        self.advancedToggle.setObjectName(u"advancedToggle")
        self.advancedToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.advancedToggle.setFocusPolicy(Qt.StrongFocus)
        self.advancedToggle.setCheckable(True)
        self.advancedToggle.setChecked(True)
        self.advancedToggle.setArrowType(Qt.DownArrow)

        self.runLayout.addWidget(self.advancedToggle)


        self.layout.addLayout(self.runLayout)

        self.advancedBody = QWidget(stackSettings)
        self.advancedBody.setObjectName(u"advancedBody")
        self.advancedBody.setVisible(True)
        self.advancedLayout = QVBoxLayout(self.advancedBody)
        self.advancedLayout.setSpacing(6)
        self.advancedLayout.setObjectName(u"advancedLayout")
        self.advancedLayout.setContentsMargins(0, 0, 0, 0)
        self.gpuBatchGrid = QGridLayout()
        self.gpuBatchGrid.setSpacing(8)
        self.gpuBatchGrid.setObjectName(u"gpuBatchGrid")
        self.useGPULabel = QLabel(self.advancedBody)
        self.useGPULabel.setObjectName(u"useGPULabel")

        self.gpuBatchGrid.addWidget(self.useGPULabel, 0, 0, 1, 1)

        self.useGPU = QCheckBox(self.advancedBody)
        self.useGPU.setObjectName(u"useGPU")
        self.useGPU.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.useGPU.setStyleSheet(u"QCheckBox#useGPU { spacing: 0px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"QCheckBox#useGPU::indicator { width: 36px; height: 20px;  border: 1px solid #64748b; border-radius: 10px; }\n"
"QCheckBox#useGPU::indicator:unchecked { image: url(:/startrails/ui/switch_off.png); }\n"
"QCheckBox#useGPU::indicator:checked { image: url(:/startrails/ui/switch_on.png); }\n"
"QCheckBox#useGPU:focus:enabled { border-color: #0f172a; }")

        self.gpuBatchGrid.addWidget(self.useGPU, 0, 1, 1, 1, Qt.AlignRight)

        self.batchLabel = QLabel(self.advancedBody)
        self.batchLabel.setObjectName(u"batchLabel")

        self.gpuBatchGrid.addWidget(self.batchLabel, 1, 0, 1, 1)

        self.batchSize = QSpinBox(self.advancedBody)
        self.batchSize.setObjectName(u"batchSize")
        self.batchSize.setMinimum(1)
        self.batchSize.setMaximum(2147483647)
        self.batchSize.setValue(1)

        self.gpuBatchGrid.addWidget(self.batchSize, 1, 1, 1, 1, Qt.AlignRight)

        self.gpuBatchGrid.setColumnStretch(0, 1)
        self.gpuBatchGrid.setColumnStretch(1, 2)

        self.advancedLayout.addLayout(self.gpuBatchGrid)

        self.memory = QLabel(self.advancedBody)
        self.memory.setObjectName(u"memory")
        self.memory.setWordWrap(True)

        self.advancedLayout.addWidget(self.memory)


        self.layout.addWidget(self.advancedBody)

        self.error = QLabel(stackSettings)
        self.error.setObjectName(u"error")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

#if QT_CONFIG(shortcut)
        self.streaksLabel.setBuddy(self.streaks)
        self.fadeLabel.setBuddy(self.fade)
        self.amountLabel.setBuddy(self.fadeAmount)
        self.useGPULabel.setBuddy(self.useGPU)
        self.batchLabel.setBuddy(self.batchSize)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(stackSettings)

        self.fade.setCurrentIndex(3)


        QMetaObject.connectSlotsByName(stackSettings)
    # setupUi

    def retranslateUi(self, stackSettings):
        self.methodLabel.setText(QCoreApplication.translate("StackSettings", u"Method", None))
        self.method.setText(QCoreApplication.translate("StackSettings", u"Lighten", None))
        self.streaksLabel.setText(QCoreApplication.translate("StackSettings", u"&Streaks", None))
        self.streaks.setItemText(0, QCoreApplication.translate("StackSettings", u"Keep", None))
        self.streaks.setItemText(1, QCoreApplication.translate("StackSettings", u"Remove", None))

        self.fadeLabel.setText(QCoreApplication.translate("StackSettings", u"&Fade frames", None))
        self.fade.setItemText(0, QCoreApplication.translate("StackSettings", u"None", None))
        self.fade.setItemText(1, QCoreApplication.translate("StackSettings", u"Start only", None))
        self.fade.setItemText(2, QCoreApplication.translate("StackSettings", u"End only", None))
        self.fade.setItemText(3, QCoreApplication.translate("StackSettings", u"Start and end", None))

        self.amountLabel.setText(QCoreApplication.translate("StackSettings", u"&Amount", None))
#if QT_CONFIG(tooltip)
        self.amountLabel.setToolTip(QCoreApplication.translate("StackSettings", u"Fade amount", None))
#endif // QT_CONFIG(tooltip)
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
