"""Dialogs for StarNet terms acceptance, automated managed setup, and manual installation discovery."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from startrails.lib.starnet_setup import (
    STARNET_TERMS_REVISION,
    STARNET_TERMS_TEXT,
    StarNetInstallation,
    install_starnet_managed,
    probe_starnet_installation,
    record_starnet_installation,
    validate_starnet_installation,
    smoke_test_starnet_installation,
    starnet_terms_accepted,
)


class StarNetTermsDialog(QDialog):
    """Modal dialog presenting StarNet terms and requiring affirmative acceptance."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("StarNet2 License and Integration Terms")
        self.setMinimumSize(560, 420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel(f"StarNet2 Terms (Revision {STARNET_TERMS_REVISION})")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #0f172a;")
        layout.addWidget(header)

        info = QLabel(
            "StarNet2 is an external tool used to separate stars from the sky background. "
            "Please read and agree to the license terms before downloading or using StarNet2 with StarTrails:"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(info)

        self.text_terms = QTextEdit(self)
        self.text_terms.setPlainText(STARNET_TERMS_TEXT)
        self.text_terms.setReadOnly(True)
        self.text_terms.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; "
            "font-family: monospace; font-size: 11px; padding: 6px;"
        )
        layout.addWidget(self.text_terms)

        self.checkbox_agree = QCheckBox(
            "I understand and affirmatively accept the StarNet2 license and integration terms.",
            self,
        )
        self.checkbox_agree.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e293b;")
        layout.addWidget(self.checkbox_agree)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self.btn_accept = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_accept.setText("Accept & Continue")
        self.btn_accept.setEnabled(False)
        self.btn_accept.setStyleSheet(
            "QPushButton { background-color: #0284c7; color: white; border-radius: 4px; padding: 6px 14px; font-weight: 600; } "
            "QPushButton:disabled { background-color: #94a3b8; } "
            "QPushButton:hover:!disabled { background-color: #0369a1; }"
        )

        self.checkbox_agree.toggled.connect(self.btn_accept.setEnabled)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)


class StarNetInstallWorker(QThread):
    """Background worker for downloading, extracting, validating, and publishing StarNet."""

    progress_changed = Signal(int, int, str)  # current, total, description
    finished_installation = Signal(object)  # StarNetInstallation
    failed_error = Signal(str)

    def __init__(self, operation: Callable, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.operation = operation
        self._cancel_event = Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def run(self) -> None:
        def on_download_progress(current: int, total: int) -> None:
            self.progress_changed.emit(current, total, "Downloading official StarNet2 package...")

        try:
            installation = self.operation(
                progress_callback=on_download_progress,
                cancel_check=self.is_cancelled,
            )
            # The installer returned only after publication committed. A late
            # cancel cannot discard that successfully published installation.
            self.finished_installation.emit(installation)
        except Exception as exc:
            if not self.is_cancelled():
                self.failed_error.emit(str(exc))


class StarNetSetupDialog(QDialog):
    """Progress dialog managing download, verification, and atomic publication of StarNet."""

    def __init__(self, parent: Optional[QWidget] = None, *, operation: Callable = install_starnet_managed):
        super().__init__(parent)
        self.setWindowTitle("StarNet2 Setup")
        self.setMinimumWidth(440)
        self.setModal(True)
        self.installation: Optional[StarNetInstallation] = None
        self._error: Optional[str] = None
        self._cancelling = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.lbl_title = QLabel("Setting up StarNet2...", self)
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #0f172a;")
        layout.addWidget(self.lbl_title)

        self.lbl_status = QLabel("Initializing download...", self)
        self.lbl_status.setStyleSheet("font-size: 12px; color: #475569;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self.btn_cancel, alignment=Qt.AlignmentFlag.AlignRight)

        self.worker = StarNetInstallWorker(operation, self)
        self.worker.progress_changed.connect(self._on_progress)
        self.worker.finished_installation.connect(self._on_finished)
        self.worker.failed_error.connect(self._on_failed)
        self.worker.finished.connect(self._on_worker_finished)

    def start(self) -> None:
        self.worker.start()

    def _on_progress(self, current: int, total: int, desc: str) -> None:
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            mb_cur = current / (1024 * 1024)
            mb_tot = total / (1024 * 1024)
            self.lbl_status.setText(f"{desc} ({mb_cur:.1f} MB / {mb_tot:.1f} MB)")
        else:
            self.lbl_status.setText(desc)

    def _on_finished(self, installation: StarNetInstallation) -> None:
        self.installation = installation
        self.lbl_status.setText("StarNet2 installation verified and ready.")
        self.progress_bar.setValue(100)

    def _on_failed(self, error: str) -> None:
        self._error = error
        self.lbl_status.setText(f"Setup failed: {error}")

    def _on_worker_finished(self) -> None:
        # Dialog ownership may end only after the QThread actually stops.
        self.worker.wait()
        if self.installation is not None:
            self.accept()
        elif self._cancelling:
            super().reject()
        elif self._error is not None:
            QMessageBox.critical(self, "Setup Error", f"StarNet2 setup encountered an error:\n\n{self._error}")
            super().reject()
        else:
            super().reject()

    def _on_cancel_clicked(self) -> None:
        self.reject()

    def reject(self) -> None:
        if self.worker.isRunning():
            self._cancelling = True
            self.lbl_status.setText("Cancelling setup...")
            self.btn_cancel.setEnabled(False)
            self.worker.cancel()
            return
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker.isRunning():
            event.ignore()
            self.reject()
        else:
            super().closeEvent(event)


def choose_existing_starnet(
    parent: QWidget,
    app_state: Dict[str, Any],
    on_installed: Optional[Callable[[StarNetInstallation], None]] = None,
) -> bool:
    """Prompt user to select existing StarNet directory or executable, validate, and record."""
    file_or_dir, _ = QFileDialog.getOpenFileName(
        parent,
        "Select StarNet2 Executable",
        filter="Executables (starnet2* starnet++* *.exe);;All Files (*)",
    )
    if not file_or_dir:
        return False

    if not starnet_terms_accepted(app_state):
        terms_dlg = StarNetTermsDialog(parent)
        if terms_dlg.exec() != QDialog.DialogCode.Accepted:
            return False

    def verify_existing(*, progress_callback, cancel_check):
        installation = validate_starnet_installation(Path(file_or_dir))
        probe_starnet_installation(installation, cancel_check=cancel_check)
        smoke_test_starnet_installation(installation, cancel_check=cancel_check)
        return installation

    setup = StarNetSetupDialog(parent, operation=verify_existing)
    setup.start()
    if setup.exec() != QDialog.DialogCode.Accepted or setup.installation is None:
        return False
    installation = setup.installation
    if on_installed is not None:
        on_installed(installation)
    else:
        record_starnet_installation(app_state, installation, managed=False, terms_accepted=True)

    QMessageBox.information(
        parent,
        "StarNet Configured",
        f"Configured StarNet2 {installation.package.version} (build {installation.package.build}, {installation.package.backend_id}).",
    )
    return True


__all__ = [
    "StarNetInstallWorker",
    "StarNetSetupDialog",
    "StarNetTermsDialog",
    "choose_existing_starnet",
]
