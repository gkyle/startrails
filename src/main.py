import sys
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QApplication
from startrails.ui.ui_wrap import MainWindow, App


if __name__ == "__main__":
    qapp = QApplication(sys.argv)
    qapp.setStyle("Fusion")
    QImageReader.setAllocationLimit(0)

    app = App()
    window = MainWindow(app)

    sys.exit(qapp.exec())
