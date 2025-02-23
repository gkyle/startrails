# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_dialog_stackLgSEiK.ui'
##
## Created by: Qt User Interface Compiler version 6.4.2
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QDialog,
    QDialogButtonBox, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QRadioButton,
    QSizePolicy, QSlider, QVBoxLayout, QWidget)

class Ui_Dialog_StackImages(object):
    def setupUi(self, Dialog_StackImages):
        if not Dialog_StackImages.objectName():
            Dialog_StackImages.setObjectName(u"Dialog_StackImages")
        Dialog_StackImages.resize(400, 408)
        self.gridLayout = QGridLayout(Dialog_StackImages)
        self.gridLayout.setObjectName(u"gridLayout")
        self.buttonBox = QDialogButtonBox(Dialog_StackImages)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout.addWidget(self.buttonBox, 2, 0, 1, 2, Qt.AlignHCenter)

        self.frame = QFrame(Dialog_StackImages)
        self.frame.setObjectName(u"frame")
        self.frame.setMinimumSize(QSize(0, 250))
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.formLayout = QFormLayout(self.frame)
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setHorizontalSpacing(12)
        self.label_method = QLabel(self.frame)
        self.label_method.setObjectName(u"label_method")

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.label_method)

        self.label_2 = QLabel(self.frame)
        self.label_2.setObjectName(u"label_2")

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.label_2)

        self.label_streaks = QLabel(self.frame)
        self.label_streaks.setObjectName(u"label_streaks")

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.label_streaks)

        self.frame_3 = QFrame(self.frame)
        self.frame_3.setObjectName(u"frame_3")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame_3.sizePolicy().hasHeightForWidth())
        self.frame_3.setSizePolicy(sizePolicy)
        self.frame_3.setFrameShape(QFrame.StyledPanel)
        self.frame_3.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.frame_3)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(9, 9, 9, 9)
        self.radioButton_streaks_keep = QRadioButton(self.frame_3)
        self.radioButton_streaks_keep.setObjectName(u"radioButton_streaks_keep")

        self.verticalLayout_2.addWidget(self.radioButton_streaks_keep)

        self.radioButton_streaks_remove = QRadioButton(self.frame_3)
        self.radioButton_streaks_remove.setObjectName(u"radioButton_streaks_remove")
        self.radioButton_streaks_remove.setEnabled(False)

        self.verticalLayout_2.addWidget(self.radioButton_streaks_remove)


        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.frame_3)

        self.label_fade = QLabel(self.frame)
        self.label_fade.setObjectName(u"label_fade")

        self.formLayout.setWidget(3, QFormLayout.LabelRole, self.label_fade)

        self.frame_2 = QFrame(self.frame)
        self.frame_2.setObjectName(u"frame_2")
        sizePolicy.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy)
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.verticalLayout = QVBoxLayout(self.frame_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(9, 9, 9, 9)
        self.radioButton_fade_none = QRadioButton(self.frame_2)
        self.radioButton_fade_none.setObjectName(u"radioButton_fade_none")

        self.verticalLayout.addWidget(self.radioButton_fade_none)

        self.radioButton_fade_start = QRadioButton(self.frame_2)
        self.radioButton_fade_start.setObjectName(u"radioButton_fade_start")

        self.verticalLayout.addWidget(self.radioButton_fade_start)

        self.radioButton_fade_end = QRadioButton(self.frame_2)
        self.radioButton_fade_end.setObjectName(u"radioButton_fade_end")

        self.verticalLayout.addWidget(self.radioButton_fade_end)

        self.radioButton_fade_both = QRadioButton(self.frame_2)
        self.radioButton_fade_both.setObjectName(u"radioButton_fade_both")

        self.verticalLayout.addWidget(self.radioButton_fade_both)


        self.formLayout.setWidget(3, QFormLayout.FieldRole, self.frame_2)

        self.label_fadeAmount = QLabel(self.frame)
        self.label_fadeAmount.setObjectName(u"label_fadeAmount")

        self.formLayout.setWidget(4, QFormLayout.LabelRole, self.label_fadeAmount)

        self.frame_4 = QFrame(self.frame)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.StyledPanel)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.frame_4)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(9, 0, 9, 0)
        self.horizontalSlider_fade_amount = QSlider(self.frame_4)
        self.horizontalSlider_fade_amount.setObjectName(u"horizontalSlider_fade_amount")
        self.horizontalSlider_fade_amount.setMaximum(50)
        self.horizontalSlider_fade_amount.setValue(20)
        self.horizontalSlider_fade_amount.setOrientation(Qt.Horizontal)
        self.horizontalSlider_fade_amount.setTickPosition(QSlider.TicksAbove)

        self.verticalLayout_3.addWidget(self.horizontalSlider_fade_amount)

        self.label_fade_amount = QLabel(self.frame_4)
        self.label_fade_amount.setObjectName(u"label_fade_amount")

        self.verticalLayout_3.addWidget(self.label_fade_amount, 0, Qt.AlignHCenter)


        self.formLayout.setWidget(4, QFormLayout.FieldRole, self.frame_4)

        self.frame_6 = QFrame(self.frame)
        self.frame_6.setObjectName(u"frame_6")
        self.frame_6.setFrameShape(QFrame.StyledPanel)
        self.frame_6.setFrameShadow(QFrame.Raised)
        self.verticalLayout_4 = QVBoxLayout(self.frame_6)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.frame_5 = QFrame(self.frame_6)
        self.frame_5.setObjectName(u"frame_5")
        self.frame_5.setFrameShape(QFrame.NoFrame)
        self.frame_5.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame_5)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.lineEdit_batchSize = QLineEdit(self.frame_5)
        self.lineEdit_batchSize.setObjectName(u"lineEdit_batchSize")
        self.lineEdit_batchSize.setMinimumSize(QSize(50, 0))
        self.lineEdit_batchSize.setMaximumSize(QSize(50, 16777215))

        self.horizontalLayout.addWidget(self.lineEdit_batchSize)

        self.checkBox_useGPU = QCheckBox(self.frame_5)
        self.checkBox_useGPU.setObjectName(u"checkBox_useGPU")

        self.horizontalLayout.addWidget(self.checkBox_useGPU)


        self.verticalLayout_4.addWidget(self.frame_5)

        self.label_memory = QLabel(self.frame_6)
        self.label_memory.setObjectName(u"label_memory")
        self.label_memory.setAlignment(Qt.AlignCenter)

        self.verticalLayout_4.addWidget(self.label_memory)


        self.formLayout.setWidget(5, QFormLayout.FieldRole, self.frame_6)

        self.label_batchSize = QLabel(self.frame)
        self.label_batchSize.setObjectName(u"label_batchSize")

        self.formLayout.setWidget(5, QFormLayout.LabelRole, self.label_batchSize)


        self.gridLayout.addWidget(self.frame, 0, 0, 1, 2)


        self.retranslateUi(Dialog_StackImages)
        self.buttonBox.accepted.connect(Dialog_StackImages.accept)
        self.buttonBox.rejected.connect(Dialog_StackImages.reject)

        QMetaObject.connectSlotsByName(Dialog_StackImages)
    # setupUi

    def retranslateUi(self, Dialog_StackImages):
        Dialog_StackImages.setWindowTitle(QCoreApplication.translate("Dialog_StackImages", u"Stack Images", None))
        self.label_method.setText(QCoreApplication.translate("Dialog_StackImages", u"Method:", None))
        self.label_2.setText(QCoreApplication.translate("Dialog_StackImages", u"Lighten", None))
        self.label_streaks.setText(QCoreApplication.translate("Dialog_StackImages", u"Streaks:", None))
        self.radioButton_streaks_keep.setText(QCoreApplication.translate("Dialog_StackImages", u"Keep", None))
        self.radioButton_streaks_remove.setText(QCoreApplication.translate("Dialog_StackImages", u"Remove", None))
        self.label_fade.setText(QCoreApplication.translate("Dialog_StackImages", u"Fade Frames:", None))
        self.radioButton_fade_none.setText(QCoreApplication.translate("Dialog_StackImages", u"None", None))
        self.radioButton_fade_start.setText(QCoreApplication.translate("Dialog_StackImages", u"Start Only", None))
        self.radioButton_fade_end.setText(QCoreApplication.translate("Dialog_StackImages", u"End Only", None))
        self.radioButton_fade_both.setText(QCoreApplication.translate("Dialog_StackImages", u"Start and End", None))
        self.label_fadeAmount.setText(QCoreApplication.translate("Dialog_StackImages", u"Fade Amount:", None))
        self.label_fade_amount.setText(QCoreApplication.translate("Dialog_StackImages", u"Gradient: 20%", None))
        self.lineEdit_batchSize.setText(QCoreApplication.translate("Dialog_StackImages", u"1", None))
        self.checkBox_useGPU.setText(QCoreApplication.translate("Dialog_StackImages", u"Use GPU", None))
        self.label_memory.setText("")
        self.label_batchSize.setText(QCoreApplication.translate("Dialog_StackImages", u"Batch Size:", None))
    # retranslateUi

