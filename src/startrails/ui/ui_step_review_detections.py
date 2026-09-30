# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_review_detections.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget)
from . import resources_rc

class Ui_reviewSettings(object):
    def setupUi(self, reviewSettings):
        if not reviewSettings.objectName():
            reviewSettings.setObjectName(u"reviewSettings")
        reviewSettings.resize(222, 334)
        self.layout = QVBoxLayout(reviewSettings)
        self.layout.setSpacing(8)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.countsLayout = QHBoxLayout()
        self.countsLayout.setSpacing(6)
        self.countsLayout.setObjectName(u"countsLayout")
        self.statAuto = QFrame(reviewSettings)
        self.statAuto.setObjectName(u"statAuto")
        self.statAuto.setStyleSheet(u"background-color: #f0fdf4;\n"
"border-radius: 6px;\n"
"padding: 1px;\n"
"\n"
"")
        self.statAutoLayout = QVBoxLayout(self.statAuto)
        self.statAutoLayout.setSpacing(0)
        self.statAutoLayout.setObjectName(u"statAutoLayout")
        self.statAutoLayout.setContentsMargins(2, 2, 2, 2)
        self.statAutoTitle = QLabel(self.statAuto)
        self.statAutoTitle.setObjectName(u"statAutoTitle")
        self.statAutoTitle.setStyleSheet(u"font-size: 11px;\n"
"font-weight: 600;\n"
"color: #15803d;")

        self.statAutoLayout.addWidget(self.statAutoTitle)

        self.statAutoNum = QLabel(self.statAuto)
        self.statAutoNum.setObjectName(u"statAutoNum")
        font = QFont()
        font.setBold(True)
        self.statAutoNum.setFont(font)
        self.statAutoNum.setStyleSheet(u"font-size: 11px;\n"
"font-weight: bold;\n"
"color: #166534;")

        self.statAutoLayout.addWidget(self.statAutoNum)


        self.countsLayout.addWidget(self.statAuto)

        self.statManual = QFrame(reviewSettings)
        self.statManual.setObjectName(u"statManual")
        self.statManual.setStyleSheet(u"background-color: #f0f9ff;\n"
"border-radius: 6px;\n"
"padding: 1px;")
        self.statManualLayout = QVBoxLayout(self.statManual)
        self.statManualLayout.setSpacing(0)
        self.statManualLayout.setObjectName(u"statManualLayout")
        self.statManualLayout.setContentsMargins(2, 2, 2, 2)
        self.statManualTitle = QLabel(self.statManual)
        self.statManualTitle.setObjectName(u"statManualTitle")
        self.statManualTitle.setStyleSheet(u"font-size: 11px;\n"
"font-weight: 600;\n"
"color: #0369a1;")

        self.statManualLayout.addWidget(self.statManualTitle)

        self.statManualNum = QLabel(self.statManual)
        self.statManualNum.setObjectName(u"statManualNum")
        self.statManualNum.setStyleSheet(u"font-size: 11px;\n"
"font-weight: bold;\n"
"color: #0369a1;")

        self.statManualLayout.addWidget(self.statManualNum)


        self.countsLayout.addWidget(self.statManual)

        self.statDeleted = QFrame(reviewSettings)
        self.statDeleted.setObjectName(u"statDeleted")
        self.statDeleted.setStyleSheet(u"background-color: #fffbeb;\n"
"border-radius: 6px;\n"
"padding: 1px;")
        self.statDeletedLayout = QVBoxLayout(self.statDeleted)
        self.statDeletedLayout.setSpacing(0)
        self.statDeletedLayout.setObjectName(u"statDeletedLayout")
        self.statDeletedLayout.setContentsMargins(2, 2, 2, 2)
        self.statDeletedTitle = QLabel(self.statDeleted)
        self.statDeletedTitle.setObjectName(u"statDeletedTitle")
        self.statDeletedTitle.setStyleSheet(u"font-size: 11px;\n"
"font-weight: 600;\n"
"color: #b45309;")

        self.statDeletedLayout.addWidget(self.statDeletedTitle)

        self.statDeletedNum = QLabel(self.statDeleted)
        self.statDeletedNum.setObjectName(u"statDeletedNum")
        self.statDeletedNum.setStyleSheet(u"font-size: 11px;\n"
"font-weight: bold;\n"
"color: #92400e;")

        self.statDeletedLayout.addWidget(self.statDeletedNum)


        self.countsLayout.addWidget(self.statDeleted)


        self.layout.addLayout(self.countsLayout)

        self.showDeletedMasksLayout = QHBoxLayout()
        self.showDeletedMasksLayout.setObjectName(u"showDeletedMasksLayout")
        self.showDeletedMasksLabel = QLabel(reviewSettings)
        self.showDeletedMasksLabel.setObjectName(u"showDeletedMasksLabel")
        self.showDeletedMasksLabel.setStyleSheet(u"color: #334155; font-size: 12px;")

        self.showDeletedMasksLayout.addWidget(self.showDeletedMasksLabel)

        self.showDeletedMasks = QCheckBox(reviewSettings)
        self.showDeletedMasks.setObjectName(u"showDeletedMasks")
        self.showDeletedMasks.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.showDeletedMasksLayout.addWidget(self.showDeletedMasks, 0, Qt.AlignmentFlag.AlignRight)


        self.layout.addLayout(self.showDeletedMasksLayout)

        self.sepFindBrightest = QFrame(reviewSettings)
        self.sepFindBrightest.setObjectName(u"sepFindBrightest")
        self.sepFindBrightest.setStyleSheet(u"background-color: #f1f5f9;\n"
"max-height: 1px;")
        self.sepFindBrightest.setFrameShape(QFrame.Shape.HLine)

        self.layout.addWidget(self.sepFindBrightest)

        self.findBrightestHeading = QLabel(reviewSettings)
        self.findBrightestHeading.setObjectName(u"findBrightestHeading")
        self.findBrightestHeading.setStyleSheet(u"font-size: 11px;\n"
"font-weight: 600;\n"
"color: #475569;\n"
"text-transform: uppercase;\n"
"letter-spacing: 0.5px;\n"
"margin-top: 2px;")

        self.layout.addWidget(self.findBrightestHeading)

        self.findBrightestHint = QLabel(reviewSettings)
        self.findBrightestHint.setObjectName(u"findBrightestHint")
        self.findBrightestHint.setStyleSheet(u"font-size: 11px;\n"
"color: #64748b;\n"
"line-height: 1.3;")
        self.findBrightestHint.setWordWrap(True)

        self.layout.addWidget(self.findBrightestHint)

        self.findBrightest = QPushButton(reviewSettings)
        self.findBrightest.setObjectName(u"findBrightest")
        self.findBrightest.setEnabled(False)
        self.findBrightest.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.findBrightest.setStyleSheet(u"QPushButton#findBrightest {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 2px solid #cbd5e1;\n"
"    border-radius: 6px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 500;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#findBrightest:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#findBrightest:checked {\n"
"    background-color: #e0f2fe;\n"
"    color: #0369a1;\n"
"    border-color: #0369a1;\n"
"    font-weight: 600;\n"
"}\n"
"QPushButton#findBrightest:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QPushButton#findBrightest:focus:enabled { border-color: #0f172a; }")
        self.findBrightest.setCheckable(True)

        self.layout.addWidget(self.findBrightest)

        self.sep1 = QFrame(reviewSettings)
        self.sep1.setObjectName(u"sep1")
        self.sep1.setStyleSheet(u"background-color: #f1f5f9;\n"
"max-height: 1px;")
        self.sep1.setFrameShape(QFrame.Shape.HLine)

        self.layout.addWidget(self.sep1)

        self.contributeHeading = QLabel(reviewSettings)
        self.contributeHeading.setObjectName(u"contributeHeading")
        self.contributeHeading.setStyleSheet(u"font-size: 11px;\n"
"font-weight: 600;\n"
"color: #475569;\n"
"text-transform: uppercase;\n"
"letter-spacing: 0.5px;\n"
"margin-top: 2px;")

        self.layout.addWidget(self.contributeHeading)

        self.contributeHint = QLabel(reviewSettings)
        self.contributeHint.setObjectName(u"contributeHint")
        self.contributeHint.setStyleSheet(u"font-size: 11px;\n"
"color: #64748b;\n"
"line-height: 1.3;")
        self.contributeHint.setWordWrap(True)

        self.layout.addWidget(self.contributeHint)

        self.training = QPushButton(reviewSettings)
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

#if QT_CONFIG(shortcut)
        self.showDeletedMasksLabel.setBuddy(self.showDeletedMasks)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(reviewSettings)

        QMetaObject.connectSlotsByName(reviewSettings)
    # setupUi

    def retranslateUi(self, reviewSettings):
        self.statAutoTitle.setText(QCoreApplication.translate("reviewSettings", u"Auto", None))
        self.statAutoNum.setText(QCoreApplication.translate("reviewSettings", u"0", None))
        self.statManualTitle.setText(QCoreApplication.translate("reviewSettings", u"Manual", None))
        self.statManualNum.setText(QCoreApplication.translate("reviewSettings", u"0", None))
        self.statDeletedTitle.setText(QCoreApplication.translate("reviewSettings", u"Deleted", None))
        self.statDeletedNum.setText(QCoreApplication.translate("reviewSettings", u"0", None))
        self.showDeletedMasksLabel.setText(QCoreApplication.translate("reviewSettings", u"Show Deleted Masks", None))
#if QT_CONFIG(accessibility)
        self.showDeletedMasks.setAccessibleName(QCoreApplication.translate("reviewSettings", u"Show Deleted Masks", None))
#endif // QT_CONFIG(accessibility)
        self.showDeletedMasks.setText("")
        self.findBrightestHeading.setText(QCoreApplication.translate("reviewSettings", u"Locate Streaks", None))
        self.findBrightestHint.setText(QCoreApplication.translate("reviewSettings", u"Click on a streak in a stacked or gap-filled image to locate its source frame.", None))
#if QT_CONFIG(tooltip)
        self.findBrightest.setToolTip(QCoreApplication.translate("reviewSettings", u"Select a stacked or gap-filled output image to enable finding the brightest frame at a point.", None))
#endif // QT_CONFIG(tooltip)
        self.findBrightest.setText(QCoreApplication.translate("reviewSettings", u"Find Brightest", None))
        self.contributeHeading.setText(QCoreApplication.translate("reviewSettings", u"Optional: Contribute Corrections", None))
        self.contributeHint.setText(QCoreApplication.translate("reviewSettings", u"Export manual additions and deletions to help improve future streak detection models.", None))
#if QT_CONFIG(tooltip)
        self.training.setToolTip(QCoreApplication.translate("reviewSettings", u"Requires manually added or deleted streak masks.", None))
#endif // QT_CONFIG(tooltip)
        self.training.setText(QCoreApplication.translate("reviewSettings", u"Export Training", None))
        pass
    # retranslateUi

Ui_ReviewSettings = Ui_reviewSettings
