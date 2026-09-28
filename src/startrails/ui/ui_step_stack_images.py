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
    QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QSpinBox, QVBoxLayout, QWidget)
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
"    padding: 7px 12px;\n"
"    border-radius: 6px;\n"
"    font-size: 13px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"QPushButton#run:hover {\n"
"    background-color: #075985;\n"
"}\n"
""
                        "QPushButton#run:disabled {\n"
"    background-color: #e2e8f0;\n"
"    color: #94a3b8;\n"
"}\n"
"QCheckBox:focus:enabled { border-color: #0f172a; }\n"
"QPushButton#run:focus:enabled { border-color: #ffffff; }\n"
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

        self.gpuBatchRow = QHBoxLayout()
        self.gpuBatchRow.setSpacing(6)
        self.gpuBatchRow.setObjectName(u"gpuBatchRow")
        self.useGPU = QCheckBox(stackSettings)
        self.useGPU.setObjectName(u"useGPU")
        self.useGPU.setStyleSheet(u"QCheckBox#useGPU { spacing: 0px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"      QCheckBox#useGPU::indicator { width: 36px; height: 20px;  border: 1px solid #64748b; border-radius: 10px; }\n"
"      QCheckBox#useGPU::indicator:unchecked { image: url(:/startrails/ui/switch_off.png); }\n"
"      QCheckBox#useGPU::indicator:checked { image: url(:/startrails/ui/switch_on.png); }\n"
"QCheckBox#useGPU:focus:enabled { border-color: #0f172a; }")

        self.gpuBatchRow.addWidget(self.useGPU)

        self.gpuBatchSpacer = QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gpuBatchRow.addItem(self.gpuBatchSpacer)

        self.batchLabel = QLabel(stackSettings)
        self.batchLabel.setObjectName(u"batchLabel")

        self.gpuBatchRow.addWidget(self.batchLabel)

        self.batchSize = QSpinBox(stackSettings)
        self.batchSize.setObjectName(u"batchSize")
        self.batchSize.setMinimum(1)
        self.batchSize.setMaximum(2147483647)
        self.batchSize.setValue(1)

        self.gpuBatchRow.addWidget(self.batchSize)


        self.layout.addLayout(self.gpuBatchRow)

        self.memory = QLabel(stackSettings)
        self.memory.setObjectName(u"memory")
        self.memory.setWordWrap(True)

        self.layout.addWidget(self.memory)

        self.error = QLabel(stackSettings)
        self.error.setObjectName(u"error")
        self.error.setWordWrap(True)

        self.layout.addWidget(self.error)

        self.run = QPushButton(stackSettings)
        self.run.setObjectName(u"run")
        self.run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run.setEnabled(False)

        self.layout.addWidget(self.run)

#if QT_CONFIG(shortcut)
        self.streaksLabel.setBuddy(self.streaks)
        self.fadeLabel.setBuddy(self.fade)
        self.amountLabel.setBuddy(self.fadeAmount)
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
        self.fadeAmount.setSuffix(QCoreApplication.translate("StackSettings", u"%", None))
        self.useGPU.setText(QCoreApplication.translate("StackSettings", u"Use GPU", None))
        self.batchLabel.setText(QCoreApplication.translate("StackSettings", u"&Batch size", None))
        self.memory.setText(QCoreApplication.translate("StackSettings", u"Add input files for a batch suggestion.", None))
        self.error.setText("")
        self.run.setText(QCoreApplication.translate("StackSettings", u"Stack Images", None))
        pass
    # retranslateUi
