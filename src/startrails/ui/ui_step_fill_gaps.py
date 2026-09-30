# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_fill_gaps.ui'
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
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget)

class Ui_FillSettings(object):
    def setupUi(self, fillSettings):
        if not fillSettings.objectName():
            fillSettings.setObjectName(u"fillSettings")
        self.layout = QVBoxLayout(fillSettings)
        self.layout.setSpacing(8)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.target = QLabel(fillSettings)
        self.target.setObjectName(u"target")
        self.target.setStyleSheet(u"font-size: 12px;\n"
"color: #475569;")
        self.target.setWordWrap(True)

        self.layout.addWidget(self.target)

        self.run = QPushButton(fillSettings)
        self.run.setObjectName(u"run")
        self.run.setStyleSheet(u"QPushButton#run {\n"
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
"QPushButton#run:disabled {\n"
"    background-color: #e2e8f0;\n"
"    color: #94a3b8;\n"
"}\n"
"QPushButton#run:focus:enabled { border-color: #ffffff; }")
        self.run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run.setEnabled(False)

        self.layout.addWidget(self.run)


        self.retranslateUi(fillSettings)

        QMetaObject.connectSlotsByName(fillSettings)
    # setupUi

    def retranslateUi(self, fillSettings):
        self.target.setText(QCoreApplication.translate("FillSettings", u"Select a stacked output image to fill its gaps.", None))
        self.run.setText(QCoreApplication.translate("FillSettings", u"Fill Gaps", None))
        pass
    # retranslateUi

Ui_fillSettings = Ui_FillSettings
