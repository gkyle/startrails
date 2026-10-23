import logging
from logging.handlers import RotatingFileHandler
import sys
from PySide6.QtCore import QLoggingCategory
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import QApplication, QMessageBox
from startrails.paths import configure_work_directory
from startrails.windows import configure_taskbar_identity
import startrails.ui.resources_rc

LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3


def create_main_window(app, project_path=None):
    from startrails.ui.ui_wrap import MainWindow

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


def main():
    if sys.platform == "win32":
        configure_taskbar_identity()
    QLoggingCategory.setFilterRules("qt.gui.icc.warning=false")
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("StarTrails")
    qapp.setOrganizationName("StarTrails")
    qapp.setStyle("Fusion")
    qapp.setWindowIcon(QIcon(":/startrails/ui/startrails_desktop.png"))
    QImageReader.setAllocationLimit(0)

    project_arg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    try:
        project_arg = configure_work_directory(project_arg)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[
                RotatingFileHandler(
                    "startrails.log",
                    maxBytes=LOG_MAX_BYTES,
                    backupCount=LOG_BACKUP_COUNT,
                    encoding="utf-8",
                )
            ],
        )
        from startrails.app import App

        app = App()
        window = create_main_window(app, project_arg)
    except Exception as error:
        logging.exception("Application startup failed")
        QMessageBox.critical(None, "StarTrails AI", f"Could not start StarTrails AI:\n{error}")
        return 1

    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
