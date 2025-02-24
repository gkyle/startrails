# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_dialog_streaksxRsmOp.ui'
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
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_Dialog_DetectStreaks(object):
    def setupUi(self, Dialog_DetectStreaks):
        if not Dialog_DetectStreaks.objectName():
            Dialog_DetectStreaks.setObjectName(u"Dialog_DetectStreaks")
        Dialog_DetectStreaks.resize(361, 300)
        self.gridLayout = QGridLayout(Dialog_DetectStreaks)
        self.gridLayout.setObjectName(u"gridLayout")
        self.buttonBox = QDialogButtonBox(Dialog_DetectStreaks)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout.addWidget(self.buttonBox, 2, 0, 1, 2, Qt.AlignHCenter)

        self.frame = QFrame(Dialog_DetectStreaks)
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

        self.lineEdit_confThreshold = QLineEdit(self.frame)
        self.lineEdit_confThreshold.setObjectName(u"lineEdit_confThreshold")
        self.lineEdit_confThreshold.setMinimumSize(QSize(100, 0))
        self.lineEdit_confThreshold.setMaximumSize(QSize(100, 16777215))

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.lineEdit_confThreshold)

        self.label_fade = QLabel(self.frame)
        self.label_fade.setObjectName(u"label_fade")

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.label_fade)

        self.frame_2 = QFrame(self.frame)
        self.frame_2.setObjectName(u"frame_2")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy)
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.verticalLayout = QVBoxLayout(self.frame_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(9, 9, 9, 9)
        self.radioButton_merge_nms = QRadioButton(self.frame_2)
        self.radioButton_merge_nms.setObjectName(u"radioButton_merge_nms")

        self.verticalLayout.addWidget(self.radioButton_merge_nms)

        self.radioButton_merge_greedy_nmm = QRadioButton(self.frame_2)
        self.radioButton_merge_greedy_nmm.setObjectName(u"radioButton_merge_greedy_nmm")

        self.verticalLayout.addWidget(self.radioButton_merge_greedy_nmm)


        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.frame_2)

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
        self.checkBox_useGPU = QCheckBox(self.frame_5)
        self.checkBox_useGPU.setObjectName(u"checkBox_useGPU")

        self.horizontalLayout.addWidget(self.checkBox_useGPU)


        self.verticalLayout_4.addWidget(self.frame_5)

        self.label_memory = QLabel(self.frame_6)
        self.label_memory.setObjectName(u"label_memory")
        self.label_memory.setAlignment(Qt.AlignCenter)

        self.verticalLayout_4.addWidget(self.label_memory)


        self.formLayout.setWidget(4, QFormLayout.FieldRole, self.frame_6)

        self.label_batchSize = QLabel(self.frame)
        self.label_batchSize.setObjectName(u"label_batchSize")

        self.formLayout.setWidget(4, QFormLayout.LabelRole, self.label_batchSize)

        self.label = QLabel(self.frame)
        self.label.setObjectName(u"label")

        self.formLayout.setWidget(2, QFormLayout.LabelRole, self.label)

        self.lineEdit_mergeThreshold = QLineEdit(self.frame)
        self.lineEdit_mergeThreshold.setObjectName(u"lineEdit_mergeThreshold")
        self.lineEdit_mergeThreshold.setMinimumSize(QSize(100, 0))
        self.lineEdit_mergeThreshold.setMaximumSize(QSize(100, 16777215))

        self.formLayout.setWidget(2, QFormLayout.FieldRole, self.lineEdit_mergeThreshold)


        self.gridLayout.addWidget(self.frame, 0, 0, 1, 2)


        self.retranslateUi(Dialog_DetectStreaks)
        self.buttonBox.accepted.connect(Dialog_DetectStreaks.accept)
        self.buttonBox.rejected.connect(Dialog_DetectStreaks.reject)

        QMetaObject.connectSlotsByName(Dialog_DetectStreaks)
    # setupUi

    def retranslateUi(self, Dialog_DetectStreaks):
        Dialog_DetectStreaks.setWindowTitle(QCoreApplication.translate("Dialog_DetectStreaks", u"Detect Streaks", None))
        self.label_method.setText(QCoreApplication.translate("Dialog_DetectStreaks", u"Confidence Threshold:", None))
        self.lineEdit_confThreshold.setText(QCoreApplication.translate("Dialog_DetectStreaks", u"0.3", None))
        self.label_fade.setText(QCoreApplication.translate("Dialog_DetectStreaks", u"Merging Strategy:", None))
        self.radioButton_merge_nms.setText(QCoreApplication.translate("Dialog_DetectStreaks", u"NMS", None))
        self.radioButton_merge_greedy_nmm.setText(QCoreApplication.translate("Dialog_DetectStreaks", u"Greedy NMM", None))
        self.checkBox_useGPU.setText(QCoreApplication.translate("Dialog_DetectStreaks", u"Use GPU", None))
        self.label_memory.setText("")
        self.label_batchSize.setText(QCoreApplication.translate("Dialog_DetectStreaks", u"Device:", None))
        self.label.setText(QCoreApplication.translate("Dialog_DetectStreaks", u"Merge Threshold:", None))
        self.lineEdit_mergeThreshold.setText(QCoreApplication.translate("Dialog_DetectStreaks", u"0.2", None))
    # retranslateUi

