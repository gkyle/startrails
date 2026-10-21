"""Shared filesystem isolation, model-settings isolation, and Qt lifecycle helpers."""

from contextlib import chdir
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["YOLO_AUTOINSTALL"] = "false"
_model_settings = TemporaryDirectory(prefix="startrails_model_settings_")
os.environ["YOLO_CONFIG_DIR"] = _model_settings.name


class IsolatedTestCase(TestCase):
    def setUp(self):
        super().setUp()
        directory = TemporaryDirectory(prefix="startrails_test_")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.enterContext(chdir(self.root))
        # Redirect the persistence boundary, retaining real QSettings behavior.
        from PySide6.QtCore import QSettings

        self.enterContext(
            patch(
                "startrails.lib.recent.QSettings",
                side_effect=lambda *args: QSettings(str(self.root / "recent.ini"), QSettings.Format.IniFormat),
            )
        )

    def make_app(self, project=None):
        """Use real workflows without starting GPU discovery or default projects."""
        from startrails.app import App
        from startrails.lib.project import Project

        app = App.__new__(App)
        app.project = project if project is not None else Project(projectFile=str(self.root / "test.proj_startrails"))
        app.state = {}
        app.stateFile = str(self.root / "app.json")
        app.activeOperation = None
        app.gpuInfo = SimpleNamespace(get_gpu_present=lambda: False, getGpuPresent=lambda: False)
        app._workflow = None
        return app


_qt_app = None


def qt_app():
    global _qt_app
    from PySide6.QtWidgets import QApplication

    _qt_app = QApplication.instance() or QApplication([])
    return _qt_app


class QtTestCase(IsolatedTestCase):
    def setUp(self):
        super().setUp()
        self.qt = qt_app()
        before = set(self.qt.topLevelWidgets())

        def dispose():
            from PySide6.QtCore import QCoreApplication, QEvent

            for widget in set(self.qt.topLevelWidgets()) - before:
                widget.close()
                widget.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.qt.processEvents()

        self.addCleanup(dispose)
