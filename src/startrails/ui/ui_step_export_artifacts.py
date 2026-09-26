# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_export_artifacts.ui'
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

class Ui_ExportSettings(object):
    def setupUi(self, exportSettings):
        if not exportSettings.objectName():
            exportSettings.setObjectName(u"exportSettings")
        self.layout = QVBoxLayout(exportSettings)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.hint = QLabel(exportSettings)
        self.hint.setObjectName(u"hint")
        self.hint.setWordWrap(True)

        self.layout.addWidget(self.hint)

        self.masks = QPushButton(exportSettings)
        self.masks.setObjectName(u"masks")
        self.masks.setEnabled(False)

        self.layout.addWidget(self.masks)

        self.training = QPushButton(exportSettings)
        self.training.setObjectName(u"training")
        self.training.setEnabled(False)

        self.layout.addWidget(self.training)


        self.retranslateUi(exportSettings)

        QMetaObject.connectSlotsByName(exportSettings)
    # setupUi

    def retranslateUi(self, exportSettings):
        self.hint.setText(QCoreApplication.translate("ExportSettings", u"Export masks or manually reviewed training samples. These exports are optional.", None))
        self.masks.setText(QCoreApplication.translate("ExportSettings", u"Export Masks", None))
#if QT_CONFIG(tooltip)
        self.masks.setToolTip(QCoreApplication.translate("ExportSettings", u"Requires automatic or manual streak masks.", None))
#endif // QT_CONFIG(tooltip)
        self.training.setText(QCoreApplication.translate("ExportSettings", u"Export Training", None))
#if QT_CONFIG(tooltip)
        self.training.setToolTip(QCoreApplication.translate("ExportSettings", u"Requires manually added or deleted streak masks.", None))
#endif // QT_CONFIG(tooltip)
        pass
    # retranslateUi

