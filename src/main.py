import sys
from PySide6.QtWidgets import QApplication
from startrails.ui.ui_wrap import MainWindow, App


if __name__ == "__main__":
    qapp = QApplication(sys.argv)
    qapp.setStyle("Fusion")

    app = App()
    window = MainWindow(app)

    sys.exit(qapp.exec())
