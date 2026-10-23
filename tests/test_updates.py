"""Release checks update the welcome overlay without interrupting project selection."""

import json
from unittest import TestCase
from unittest.mock import patch

from PySide6.QtCore import QByteArray, QObject, Signal
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QMainWindow, QMessageBox

from support import QtTestCase
from startrails.ui import updates
from startrails.ui.project_overlay import ProjectWelcomeOverlay


class FakeReply(QObject):
    finished = Signal()

    def __init__(self, payload: bytes):
        super().__init__()
        self.payload = payload

    def error(self):
        return QNetworkReply.NetworkError.NoError

    def readAll(self):
        return QByteArray(self.payload)


class FakeNetwork:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.reply = None
        self.requests = []

    def get(self, request):
        self.requests.append(request)
        self.reply = FakeReply(self.payload)
        return self.reply


class ReleaseVersionTests(TestCase):
    def test_only_strictly_newer_numeric_release_tags_are_offered(self):
        for tag, expected in (
            ("v0.1.2", True),
            ("v0.2.0", True),
            ("v0.1.1", False),
            ("v0.1.0", False),
        ):
            with self.subTest(tag=tag):
                result = updates.newer_release(json.dumps({"tag_name": tag}).encode(), "0.1.1")
                self.assertEqual(result is not None, expected)
                if result is not None:
                    self.assertEqual(result.url, f"https://github.com/gkyle/startrails/releases/tag/{tag}")
        self.assertIsNotNone(updates.newer_release(b'{"tag_name": "v0.1.10"}', "0.1.9"))

    def test_unrecognized_release_tag_is_not_misreported_as_current(self):
        with self.assertRaisesRegex(ValueError, "Invalid release tag"):
            updates.newer_release(b'{"tag_name": "v0.1.10-rc.1"}', "0.1.1")


class UpdateOverlayTests(QtTestCase):
    def setUp(self):
        super().setUp()
        (self.root / "pyproject.toml").write_text('[project]\nversion = "0.1.1"\n', encoding="utf-8")
        self.enterContext(patch.object(updates, "APPLICATION_DIR", self.root))
        self.window = QMainWindow()
        self.window.resize(1000, 750)
        self.overlay = ProjectWelcomeOverlay(self.window)
        self.overlay.set_overlay_mode("welcome")
        self.overlay.setGeometry(self.window.rect())
        self.window.show()
        self.overlay.show()
        self.network = FakeNetwork(b'{"tag_name": "v0.1.2"}')
        self.enterContext(patch.object(updates, "QNetworkAccessManager", return_value=self.network))
        self.checker = updates.UpdateChecker(self.window)
        self.checker.status_changed.connect(self.overlay.set_update_status)
        self.checker.release_found.connect(self.overlay.set_update_release)

    def finish_check(self):
        self.network.reply.finished.emit()
        self.qt.processEvents()

    def test_new_release_is_a_link_at_the_bottom_of_the_welcome_overlay(self):
        self.checker.check()
        self.assertEqual(self.overlay.lbl_update_status.text(), "Checking for updates...")
        self.assertEqual(len(self.network.requests), 1)
        self.assertEqual(self.network.requests[0].url().toString(), updates.LATEST_RELEASE_API)
        self.finish_check()

        self.assertEqual(self.overlay.lbl_update_status.text(), "🎉 StarTrails AI v0.1.2 is available.")
        self.assertTrue(self.overlay.btn_update_release.isVisible())
        self.assertEqual(self.overlay.btn_update_release.text(), "View release v0.1.2")
        group = self.overlay.lbl_update_status.geometry().united(self.overlay.btn_update_release.geometry())
        self.assertLessEqual(abs(group.center().x() - self.overlay.update_row.rect().center().x()), 2)
        self.assertFalse(any(isinstance(widget, QMessageBox) for widget in self.qt.topLevelWidgets()))
        with patch("startrails.ui.project_overlay.QDesktopServices.openUrl", return_value=True) as open_url:
            self.overlay.btn_update_release.click()
        self.assertEqual(
            open_url.call_args.args[0].toString(),
            "https://github.com/gkyle/startrails/releases/tag/v0.1.2",
        )

        self.overlay.set_overlay_mode("new")
        self.assertFalse(self.overlay.update_row.isVisible())
        self.overlay.set_overlay_mode("welcome")
        self.assertTrue(self.overlay.update_row.isVisible())
        self.assertTrue(self.overlay.btn_update_release.isVisible())

    def test_current_release_shows_a_quiet_status_without_link(self):
        self.network.payload = b'{"tag_name": "v0.1.1"}'
        self.checker.check()
        self.finish_check()
        self.assertEqual(self.overlay.lbl_update_status.text(), "StarTrails AI v0.1.1 is up to date.")
        self.assertFalse(self.overlay.btn_update_release.isVisible())

    def test_unavailable_github_leaves_only_a_quiet_status(self):
        self.checker.check()
        self.network.reply.error = lambda: QNetworkReply.NetworkError.HostNotFoundError
        self.network.reply.errorString = lambda: "Host not found"
        self.finish_check()
        self.assertEqual(self.overlay.lbl_update_status.text(), "Could not check for updates.")
        self.assertFalse(self.overlay.btn_update_release.isVisible())
        self.assertFalse(any(isinstance(widget, QMessageBox) for widget in self.qt.topLevelWidgets()))

