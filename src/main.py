import sys
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QApplication, QMessageBox
from startrails.ui.ui_wrap import MainWindow, App


def create_main_window(app, project_path=None):
    load_error = None
    if project_path:
        try:
            app.loadProject(project_path)
        except Exception as error:
            load_error = error
    window = MainWindow(app, show_welcome=not project_path or load_error is not None)
    if load_error is not None:
        QMessageBox.warning(window, "Open Project", f"Could not open project '{project_path}':\n{load_error}")
    return window


if __name__ == "__main__":
    qapp = QApplication(sys.argv)
    qapp.setStyle("Fusion")
    QImageReader.setAllocationLimit(0)

    project_arg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    app = App()
    window = create_main_window(app, project_arg)

    sys.exit(qapp.exec())
