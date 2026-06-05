from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter
from PyQt6.QtCore import QByteArray
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session


class LoginWorker(QThread):
    success = pyqtSignal(dict)
    failure = pyqtSignal(str)

    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        try:
            data = APIClient.login(self.username, self.password)
            self.success.emit(data)
        except APIError as e:
            self.failure.emit(e.message)


# ── EYE ICON BUTTON ───────────────────────────────────────────

EYE_OPEN_SVG = b"""
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" 
     viewBox="0 0 24 24" fill="none" stroke="#9ca3af" 
     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
  <circle cx="12" cy="12" r="3"/>
</svg>
"""

EYE_CLOSED_SVG = b"""
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" 
     viewBox="0 0 24 24" fill="none" stroke="#9ca3af" 
     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8
           a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 
           12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07
           a3 3 0 1 1-4.24-4.24"/>
  <line x1="1" y1="1" x2="23" y2="23"/>
</svg>
"""


class EyeButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._visible = False
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 0;
            }
            QPushButton:hover {
                background: transparent;
            }
        """)
        self._update_icon()
        self.clicked.connect(self._toggle)

    def _update_icon(self):
        svg_data = EYE_OPEN_SVG if self._visible else EYE_CLOSED_SVG
        pixmap   = self._svg_to_pixmap(svg_data)
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(20, 20))

    def _svg_to_pixmap(self, svg_bytes: bytes) -> QPixmap:
        from PyQt6.QtSvg import QSvgRenderer
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        pixmap   = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter  = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return pixmap

    def _toggle(self):
        self._visible = not self._visible
        self._update_icon()

    def is_visible(self) -> bool:
        return self._visible


# ── LOGIN SCREEN ──────────────────────────────────────────────

class LoginScreen(QWidget):
    login_successful = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self._build_ui()
        self._check_server()

    def _build_ui(self):
        # Outer layout — centers the card
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Card
        card = QFrame()
        card.setFixedWidth(360)
        card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 40, 36, 40)
        card_layout.setSpacing(0)

        # Logo / Title
        title = QLabel("G-Byke ERP")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#1e293b; border:none;")
        card_layout.addWidget(title)

        subtitle = QLabel("Factory Management System")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "color:#64748b; font-size:13px; border:none; margin-bottom:32px;"
        )
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(28)

        # Server status
        self.server_status = QLabel("● Checking server...")
        self.server_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.server_status.setStyleSheet(
            "color:#f59e0b; font-size:12px; border:none; margin-bottom:16px;"
        )
        card_layout.addWidget(self.server_status)
        card_layout.addSpacing(8)

        # Username
        user_lbl = QLabel("Username")
        user_lbl.setStyleSheet(
            "color:#374151; font-size:13px; font-weight:500; border:none;"
        )
        card_layout.addWidget(user_lbl)
        card_layout.addSpacing(6)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setFixedHeight(42)
        self.username_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
                color: #1a1a1a;
                background: white;
            }
            QLineEdit:focus {
                border-color: #2563eb;
            }
        """)
        card_layout.addWidget(self.username_input)
        card_layout.addSpacing(16)

        # Password
        pass_lbl = QLabel("Password")
        pass_lbl.setStyleSheet(
            "color:#374151; font-size:13px; font-weight:500; border:none;"
        )
        card_layout.addWidget(pass_lbl)
        card_layout.addSpacing(6)

        # Password row with eye button
        pass_row = QHBoxLayout()
        pass_row.setSpacing(0)
        pass_row.setContentsMargins(0, 0, 0, 0)

        pass_container = QFrame()
        pass_container.setFixedHeight(42)
        pass_container.setStyleSheet("""
            QFrame {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                background: white;
            }
            QFrame:focus-within {
                border-color: #2563eb;
            }
        """)
        pass_inner = QHBoxLayout(pass_container)
        pass_inner.setContentsMargins(12, 0, 4, 0)
        pass_inner.setSpacing(0)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 14px;
                color: #1a1a1a;
            }
        """)
        self.password_input.returnPressed.connect(self._do_login)

        self.eye_btn = EyeButton()
        self.eye_btn.clicked.disconnect()
        self.eye_btn.clicked.connect(self._toggle_password)

        pass_inner.addWidget(self.password_input, 1)
        pass_inner.addWidget(self.eye_btn)

        pass_row.addWidget(pass_container)
        card_layout.addLayout(pass_row)
        card_layout.addSpacing(8)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(
            "color:#dc2626; font-size:12px; border:none;"
        )
        card_layout.addWidget(self.error_label)
        card_layout.addSpacing(16)

        # Login button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setFixedHeight(44)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #93c5fd; }
        """)
        self.login_btn.clicked.connect(self._do_login)
        card_layout.addWidget(self.login_btn)

        card_layout.addSpacing(20)

        # Version
        from version import VERSION
        ver = QLabel(f"v{VERSION}")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(
            "color:#cbd5e1; font-size:11px; border:none;"
        )
        card_layout.addWidget(ver)

        outer.addWidget(card)

        # Page background
        self.setStyleSheet("background:#f1f5f9;")

    def _toggle_password(self):
        self.eye_btn._toggle()
        if self.eye_btn.is_visible():
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

    def _check_server(self):
        class ServerCheckWorker(QThread):
            done = pyqtSignal(bool)
            def run(self):
                try:
                    APIClient.get("/health")
                    self.done.emit(True)
                except APIError:
                    self.done.emit(False)

        self._server_worker = ServerCheckWorker()
        self._server_worker.done.connect(self._on_server_check)
        self._server_worker.start()

    def _on_server_check(self, online: bool):
        if online:
            self.server_status.setText("● Server online")
            self.server_status.setStyleSheet(
                "color:#16a34a; font-size:12px; border:none;"
            )
            self.login_btn.setEnabled(True)
        else:
            self.server_status.setText("● Server offline — cannot login")
            self.server_status.setStyleSheet(
                "color:#dc2626; font-size:12px; border:none;"
            )
            self.login_btn.setEnabled(False)

    def _do_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self.error_label.setText("Please enter username and password.")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Signing in...")
        self.error_label.setText("")

        self.worker = LoginWorker(username, password)
        self.worker.success.connect(self._on_login_success)
        self.worker.failure.connect(self._on_login_failure)
        self.worker.start()
    def _on_login_success(self, data: dict):
        Session.token     = data.get("access_token")
        Session.role      = data.get("role")
        Session.full_name = data.get("full_name")  # ← correct
        Session.user_id   = data.get("user_id")
        Session.username  = self.username_input.text().strip()
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Sign In")
        self.login_successful.emit(Session.role)
    
    def _on_login_failure(self, message: str):
        self.error_label.setText(message)
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Sign In")
        self.password_input.clear()
        self.password_input.setFocus()