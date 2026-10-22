"""Dialog for contributing streak corrections."""

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from startrails.lib.contrib import EMAIL_PATTERN


class ContributeCorrectionsDialog(QDialog):
    """Dialog prompting for optional contact email and comments prior to upload."""

    def __init__(
        self,
        title: str,
        info_text: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #334155; font-size: 12px; line-height: 1.4;")
        layout.addWidget(info_label)

        # Email field
        email_heading = QLabel("Contact Email (optional):")
        email_heading.setStyleSheet("font-weight: 600; color: #1e293b; font-size: 12px;")
        layout.addWidget(email_heading)

        settings = QSettings("StarTrails", "StarTrails")
        saved_email = settings.value("contribute_email", "")

        self.email_input = QLineEdit(self)
        self.email_input.setPlaceholderText("user@example.com")
        if saved_email:
            self.email_input.setText(str(saved_email))
        layout.addWidget(self.email_input)

        # Comments field
        comments_heading = QLabel("Notes / Comments (optional):")
        comments_heading.setStyleSheet("font-weight: 600; color: #1e293b; font-size: 12px;")
        layout.addWidget(comments_heading)

        self.comments_input = QTextEdit(self)
        self.comments_input.setPlaceholderText("Optional notes about camera, lens, sky conditions, or corrections...")
        self.comments_input.setMaximumHeight(80)
        layout.addWidget(self.comments_input)

        # Disclosure note
        disclosure = QLabel(
            "Submissions are voluntary contributions. Email is optional and only used "
            "if the maintainer needs to contact you regarding your submission or verify "
            "a removal request. A submission receipt ID will be provided upon upload."
        )
        disclosure.setWordWrap(True)
        disclosure.setStyleSheet("color: #64748b; font-size: 11px; line-height: 1.3;")
        layout.addWidget(disclosure)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Contribute")
        ok_button.setStyleSheet(
            "QPushButton { background-color: #0369a1; color: white; border: none; "
            "border-radius: 4px; padding: 6px 16px; font-weight: 500; } "
            "QPushButton:hover { background-color: #075985; }"
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _on_accept(self):
        email = self.email_input.text().strip()
        if email and not EMAIL_PATTERN.fullmatch(email):
            QMessageBox.warning(
                self,
                "Invalid Email",
                "Please enter a valid email address or leave the field blank.",
            )
            self.email_input.setFocus()
            return

        settings = QSettings("StarTrails", "StarTrails")
        if email:
            settings.setValue("contribute_email", email)

        self.accept()

    def values(self) -> tuple[str | None, str | None]:
        email = self.email_input.text().strip() or None
        comments = self.comments_input.toPlainText().strip() or None
        return email, comments
