# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_additional_tools.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_ToolsSettings(object):
    def setupUi(self, toolsSettings):
        if not toolsSettings.objectName():
            toolsSettings.setObjectName(u"toolsSettings")
        self.layout = QVBoxLayout(toolsSettings)
        self.layout.setSpacing(8)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.contributeHeading = QLabel(toolsSettings)
        self.contributeHeading.setObjectName(u"contributeHeading")
        self.contributeHeading.setStyleSheet(u"font-size: 11px;\n"
"font-weight: 600;\n"
"color: #475569;\n"
"text-transform: uppercase;\n"
"letter-spacing: 0.5px;\n"
"margin-top: 2px;")

        self.layout.addWidget(self.contributeHeading)

        self.contributeHint = QLabel(toolsSettings)
        self.contributeHint.setObjectName(u"contributeHint")
        self.contributeHint.setStyleSheet(u"font-size: 11px;\n"
"color: #64748b;\n"
"line-height: 1.3;")
        self.contributeHint.setWordWrap(True)

        self.layout.addWidget(self.contributeHint)

        self.contribute = QPushButton(toolsSettings)
        self.contribute.setObjectName(u"contribute")
        self.contribute.setEnabled(False)
        self.contribute.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.contribute.setStyleSheet(u"QPushButton#contribute {\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    border: 2px solid #0369a1;\n"
"    border-radius: 6px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 500;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#contribute:hover {\n"
"    background-color: #075985;\n"
"    border-color: #075985;\n"
"}\n"
"QPushButton#contribute:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QPushButton#contribute:focus:enabled { border-color: #0f172a; }")

        self.layout.addWidget(self.contribute)

        self.training = QPushButton(toolsSettings)
        self.training.setObjectName(u"training")
        self.training.setEnabled(False)
        self.training.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.training.setStyleSheet(u"QPushButton#training {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 2px solid #cbd5e1;\n"
"    border-radius: 6px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 500;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#training:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#training:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QPushButton#training:focus:enabled { border-color: #0f172a; }")

        self.layout.addWidget(self.training)

        self.sep1 = QFrame(toolsSettings)
        self.sep1.setObjectName(u"sep1")
        self.sep1.setStyleSheet(u"background-color: #f1f5f9;\n"
"max-height: 1px;")
        self.sep1.setFrameShape(QFrame.Shape.HLine)

        self.layout.addWidget(self.sep1)

        self.masksHeading = QLabel(toolsSettings)
        self.masksHeading.setObjectName(u"masksHeading")
        self.masksHeading.setStyleSheet(u"font-size: 11px;\n"
"font-weight: 600;\n"
"color: #475569;\n"
"text-transform: uppercase;\n"
"letter-spacing: 0.5px;\n"
"margin-top: 2px;")

        self.layout.addWidget(self.masksHeading)

        self.masksHint = QLabel(toolsSettings)
        self.masksHint.setObjectName(u"masksHint")
        self.masksHint.setStyleSheet(u"font-size: 11px;\n"
"color: #64748b;\n"
"line-height: 1.3;")
        self.masksHint.setWordWrap(True)

        self.layout.addWidget(self.masksHint)

        self.masks = QPushButton(toolsSettings)
        self.masks.setObjectName(u"masks")
        self.masks.setStyleSheet(u"QPushButton#masks {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 2px solid #cbd5e1;\n"
"    border-radius: 6px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 500;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#masks:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#masks:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QPushButton#masks:focus:enabled { border-color: #0f172a; }")
        self.masks.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.masks.setEnabled(False)

        self.layout.addWidget(self.masks)


        self.retranslateUi(toolsSettings)

        QMetaObject.connectSlotsByName(toolsSettings)
    # setupUi

    def retranslateUi(self, toolsSettings):
        self.contributeHeading.setText(QCoreApplication.translate("ToolsSettings", u"Optional: Contribute Corrections", None))
        self.contributeHint.setText(QCoreApplication.translate("ToolsSettings", u"Export manual additions and deletions to help improve future streak detection models.", None))
#if QT_CONFIG(tooltip)
        self.contribute.setToolTip(QCoreApplication.translate("ToolsSettings", u"Requires manually added or deleted streak masks.", None))
#endif // QT_CONFIG(tooltip)
        self.contribute.setText(QCoreApplication.translate("ToolsSettings", u"Contribute Corrections", None))
#if QT_CONFIG(tooltip)
        self.training.setToolTip(QCoreApplication.translate("ToolsSettings", u"Requires manually added or deleted streak masks.", None))
#endif // QT_CONFIG(tooltip)
        self.training.setText(QCoreApplication.translate("ToolsSettings", u"Export to Disk", None))
        self.masksHeading.setText(QCoreApplication.translate("ToolsSettings", u"Export Masks", None))
        self.masksHint.setText(QCoreApplication.translate("ToolsSettings", u"Save detected streak masks as image files.", None))
        self.masks.setText(QCoreApplication.translate("ToolsSettings", u"Export Masks", None))
#if QT_CONFIG(tooltip)
        self.masks.setToolTip(QCoreApplication.translate("ToolsSettings", u"Requires automatic or manual streak masks.", None))
#endif // QT_CONFIG(tooltip)
        pass
    # retranslateUi

Ui_toolsSettings = Ui_ToolsSettings
