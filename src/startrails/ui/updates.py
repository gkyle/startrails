"""Check for a newer published release without delaying startup."""

from dataclasses import dataclass
import json
import logging
import re
import tomllib

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QWidget

from startrails.paths import APPLICATION_DIR

logger = logging.getLogger(__name__)

# GitHub's Latest designation is the promotion gate for user update notices.
LATEST_RELEASE_API = "https://api.github.com/repos/gkyle/startrails/releases/latest"
RELEASE_PAGE_BASE = "https://github.com/gkyle/startrails/releases/tag/"
REQUEST_TIMEOUT_MS = 5000
VERSION_PATTERN = re.compile(r"v?([0-9]+)\.([0-9]+)\.([0-9]+)")


@dataclass(frozen=True)
class LatestRelease:
    tag: str
    url: str


def version_parts(version: str) -> tuple[int, int, int] | None:
    match = VERSION_PATTERN.fullmatch(version)
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def newer_release(response: bytes, installed_version: str) -> LatestRelease | None:
    release = json.loads(response)
    if not isinstance(release, dict):
        raise ValueError("GitHub release response is not an object")
    tag = release.get("tag_name")
    remote = version_parts(tag) if isinstance(tag, str) else None
    installed = version_parts(installed_version)
    if installed is None:
        raise ValueError(f"Invalid installed version: {installed_version!r}")
    if remote is None:
        raise ValueError(f"Invalid release tag: {tag!r}")
    if remote <= installed:
        return None
    return LatestRelease(tag, RELEASE_PAGE_BASE + tag)


class UpdateChecker(QObject):
    status_changed = Signal(str)
    release_found = Signal(str, str)

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.network = QNetworkAccessManager(self)
        self.reply: QNetworkReply | None = None
        self.installed_version: str | None = None

    def check(self) -> None:
        if self.reply is not None and self.reply.isRunning():
            return
        self.status_changed.emit("Checking for updates...")
        try:
            with (APPLICATION_DIR / "pyproject.toml").open("rb") as stream:
                self.installed_version = tomllib.load(stream)["project"]["version"]
            request = QNetworkRequest(QUrl(LATEST_RELEASE_API))
            request.setRawHeader(b"Accept", b"application/vnd.github+json")
            request.setRawHeader(b"User-Agent", b"StarTrailsAI-update-check")
            request.setTransferTimeout(REQUEST_TIMEOUT_MS)
            self.reply = self.network.get(request)
            self.reply.finished.connect(self._on_finished)
        except (OSError, KeyError, TypeError, ValueError):
            logger.exception("Could not start update check")
            self.status_changed.emit("Could not check for updates.")

    def _on_finished(self) -> None:
        reply = self.reply
        self.reply = None
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                logger.info("Could not check for updates: %s", reply.errorString())
                self.status_changed.emit("Could not check for updates.")
                return
            release = newer_release(reply.readAll().data(), self.installed_version)
            if release is None:
                self.status_changed.emit(f"StarTrails AI v{self.installed_version} is up to date.")
            else:
                self.release_found.emit(release.tag, release.url)
        except (TypeError, ValueError, AttributeError):
            logger.exception("Could not read the latest GitHub release")
            self.status_changed.emit("Could not check for updates.")
        finally:
            reply.deleteLater()
