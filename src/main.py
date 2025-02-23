from PySide6.QtWidgets import QMainWindow, QApplication
from startrails.ui.ui_wrap import *
import sys


if __name__ == "__main__":
    qapp = QApplication()
    app = App()
    window = MainWindow(app)

    sys.exit(qapp.exec())
