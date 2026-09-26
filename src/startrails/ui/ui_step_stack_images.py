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
    QLabel, QPushButton, QSizePolicy, QSpinBox,
    QVBoxLayout, QWidget)

class Ui_StackSettings(object):
    def setupUi(self, stackSettings):
        if not stackSettings.objectName():
            stackSettings.setObjectName(u"stackSettings")
        self.layout = QVBoxLayout(stackSettings)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.fields = QFormLayout()
        self.fields.setObjectName(u"fields")
        self.fields.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.fields.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.methodLabel = QLabel(stackSettings)
        self.methodLabel.setObjectName(u"methodLabel")

        self.fields.setWidget(0, QFormLayout.LabelRole, self.methodLabel)

        self.method = QLabel(stackSettings)
        self.method.setObjectName(u"method")

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

        self.fade = QComboBox(stackSettings)
        self.fade.addItem("")
        self.fade.addItem("")
        self.fade.addItem("")
        self.fade.addItem("")
        self.fade.setObjectName(u"fade")

        self.fields.setWidget(2, QFormLayout.FieldRole, self.fade)

        self.amountLabel = QLabel(stackSettings)
        self.amountLabel.setObjectName(u"amountLabel")

        self.fields.setWidget(3, QFormLayout.LabelRole, self.amountLabel)

        self.fadeAmount = QSpinBox(stackSettings)
        self.fadeAmount.setObjectName(u"fadeAmount")
        self.fadeAmount.setMaximum(100)
        self.fadeAmount.setValue(20)

        self.fields.setWidget(3, QFormLayout.FieldRole, self.fadeAmount)

        self.batchLabel = QLabel(stackSettings)
        self.batchLabel.setObjectName(u"batchLabel")

        self.fields.setWidget(4, QFormLayout.LabelRole, self.batchLabel)

        self.batchSize = QSpinBox(stackSettings)
        self.batchSize.setObjectName(u"batchSize")
        self.batchSize.setMinimum(1)
        self.batchSize.setMaximum(2147483647)
        self.batchSize.setValue(1)

        self.fields.setWidget(4, QFormLayout.FieldRole, self.batchSize)


        self.layout.addLayout(self.fields)

        self.useGPU = QCheckBox(stackSettings)
        self.useGPU.setObjectName(u"useGPU")

        self.layout.addWidget(self.useGPU)

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

        self.amountLabel.setText(QCoreApplication.translate("StackSettings", u"Fade &amount", None))
        self.fadeAmount.setSuffix(QCoreApplication.translate("StackSettings", u"%", None))
        self.batchLabel.setText(QCoreApplication.translate("StackSettings", u"&Batch size", None))
        self.useGPU.setText(QCoreApplication.translate("StackSettings", u"Use GPU", None))
        self.memory.setText(QCoreApplication.translate("StackSettings", u"Add input files for a batch suggestion.", None))
        self.error.setText("")
        self.run.setText(QCoreApplication.translate("StackSettings", u"Stack Images", None))
        pass
    # retranslateUi

