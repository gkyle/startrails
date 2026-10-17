import sys
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QApplication
from startrails.ui.ui_wrap import MainWindow, App


if __name__ == "__main__":
    qapp = QApplication(sys.argv)
    qapp.setStyle("Fusion")
    QImageReader.setAllocationLimit(0)

    project_arg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    app = App()
    if project_arg:
        try:
            app.loadProject(project_arg)
        except Exception:
            pass
        window = MainWindow(app, project_path=project_arg, show_welcome=False)
    else:
        window = MainWindow(app, show_welcome=True)

    sys.exit(qapp.exec())
