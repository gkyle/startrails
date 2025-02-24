import sys
from PySide6.QtWidgets import QApplication
from startrails.ui.ui_wrap import *
from PySide6.QtGui import QPalette, QColor


if __name__ == "__main__":
    qapp = QApplication(sys.argv)
    qapp.setStyle('Fusion')
    qapp.setPalette(QPalette(QColor("#444444")))

    app = App()
    window = MainWindow(app)

    sys.exit(qapp.exec())
