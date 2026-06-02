from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session
from desktop.utils.updater import check_for_updates


class LoginWorker(QThread):
    """Runs login in background so UI doesn't freeze."""
    success = pyqtSignal(dict)
    failure = pyqtSignal(str)

    def __init__(self, username: str, password: str):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        try:
            result = APIClient.login(self.username, self.password)
            self.success.emit(result)
        except APIError as e:
            self.failure.emit(e.message)


class LoginScreen(QWidget):
    login_successful = pyqtSignal(str)  # emits role

    def __init__(self):
        super().__init__()
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("G-Byke ERP — Login")
        self.setFixedSize(420, 540)
        self.setStyleSheet("background-color: #f5f5f5;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ── Card ──────────────────────────────────────────────
        card = QFrame()
        card.setFixedWidth(340)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 36, 32, 36)
        card_layout.setSpacing(16)

        # Logo / title
        logo_label = QLabel("🛵")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setFont(QFont("Arial", 36))

        title = QLabel("G-Byke ERP")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a1a1a; border: none;")

        subtitle = QLabel("Sign in to your account")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #888; font-size: 13px; border: none;")

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #eee;")

        # Username
        username_label = QLabel("Username")
        username_label.setStyleSheet(
            "font-size: 13px; font-weight: 500; color: #333; border: none;"
        )
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setFixedHeight(40)
        self.username_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 14px;
                background: #fafafa;
                color: #1a1a1a;
            }
            QLineEdit:focus {
                border: 1px solid #2563eb;
                background: white;
                color: #1a1a1a;
            }
        """)

        # Password
        password_label = QLabel("Password")
        password_label.setStyleSheet(
            "font-size: 13px; font-weight: 500; color: #333; border: none;"
        )

        # Password row with show/hide toggle
        password_row = QHBoxLayout()
        password_row.setSpacing(0)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(40)
        self.password_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 6px 0px 0px 6px;
                padding: 0 12px;
                font-size: 14px;
                background: #fafafa;
                color: #1a1a1a;
            }
            QLineEdit:focus {
                border: 1px solid #2563eb;
                background: white;
                color: #1a1a1a;
            }
        """)
        self.password_input.returnPressed.connect(self._do_login)

        self.toggle_btn = QPushButton("👁")
        self.toggle_btn.setFixedSize(40, 40)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #ddd;
                border-left: none;
                border-radius: 0px 6px 6px 0px;
                background: #fafafa;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
            QPushButton:checked {
                background: #eff6ff;
                border-color: #2563eb;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle_password)

        password_row.addWidget(self.password_input)
        password_row.addWidget(self.toggle_btn)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet(
            "color: #dc2626; font-size: 12px; border: none;"
        )
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        # Login button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setFixedHeight(42)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QPushButton:disabled {
                background-color: #93c5fd;
            }
        """)
        self.login_btn.clicked.connect(self._do_login)

        # Version label
        from version import VERSION
        version_label = QLabel(f"v{VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(
            "color: #cbd5e1; font-size: 10px; border: none;"
)

        # Server status
        self.server_label = QLabel("● Checking server...")
        self.server_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.server_label.setStyleSheet(
            "color: #f59e0b; font-size: 11px; border: none;"
)

        # ── Assemble card ──────────────────────────────────────
        card_layout.addWidget(logo_label)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(divider)
        card_layout.addWidget(username_label)
        card_layout.addWidget(self.username_input)
        card_layout.addWidget(password_label)
        card_layout.addLayout(password_row)
        card_layout.addWidget(self.error_label)
        card_layout.addWidget(self.login_btn)
        card_layout.addWidget(self.server_label)
        card_layout.addWidget(version_label)

        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        self._check_server()

    def _check_server(self):
        is_up = APIClient.check_server()
        if is_up:
            self.server_label.setText("● Server connected")
            self.server_label.setStyleSheet(
                "color: #16a34a; font-size: 11px; border: none;"
            )
            # Check for updates silently
            self._check_updates()
        else:
            self.server_label.setText("● Server unreachable — contact IT")
            self.server_label.setStyleSheet(
                "color: #dc2626; font-size: 11px; border: none;"
            )

    def _check_updates(self):
        update = check_for_updates()
        if update["update_available"]:
            if update["force_update"]:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "Update Required",
                    f"A required update is available (v{update['server_version']}).\n\n"
                    f"Please ask IT to run the update script on this laptop.\n\n"
                    f"{update['message']}"
            )
            else:
                self.server_label.setText(
                   f"● Server connected  •  Update available v{update['server_version']}"
                )
                self.server_label.setStyleSheet(
                    "color: #f59e0b; font-size: 11px; border: none;"
                )

    def _toggle_password(self, checked: bool):
        if checked:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setText("🙈")
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setText("👁")

    def _do_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            self._show_error("Please enter both username and password.")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Signing in...")
        self.error_label.hide()

        self.worker = LoginWorker(username, password)
        self.worker.success.connect(self._on_login_success)
        self.worker.failure.connect(self._on_login_failure)
        self.worker.start()

    def _on_login_success(self, data: dict):
        Session.set(
            token=data["access_token"],
            role=data["role"],
            full_name=data["full_name"],
            user_id=data["user_id"]
        )
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Sign In")
        self.login_successful.emit(data["role"])

    def _on_login_failure(self, message: str):
        self._show_error(message)
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Sign In")
        self.password_input.clear()
        self.password_input.setFocus()

    def _show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()