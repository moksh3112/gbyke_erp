from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout,
    QStackedWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from desktop.screens.login import LoginScreen
from desktop.screens.dashboard_admin import AdminDashboard
from desktop.screens.dashboard_user import UserDashboard
from desktop.components.sidebar import Sidebar
from desktop.utils.session import Session


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from version import VERSION
        self.setWindowTitle(f"G-Byke ERP — v{VERSION}")
        self.setMinimumSize(1100, 680)
        self.setFont(QFont("Segoe UI", 10))
        self._show_login()

    # ── LOGIN ──────────────────────────────────────────────────

    def _show_login(self):
        self.login_screen = LoginScreen()
        self.login_screen.login_successful.connect(self._on_login)
        self.setCentralWidget(self.login_screen)
        self.resize(420, 520)

    def _on_login(self, role: str):
        self.resize(1200, 750)
        self._show_main_app()

    # ── MAIN APP ───────────────────────────────────────────────

    def _show_main_app(self):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.nav_clicked.connect(self._on_nav)
        self.sidebar.logout_clicked.connect(self._on_logout)

        # Content area
        self.content = QStackedWidget()
        self.content.setStyleSheet("background-color: #f8fafc;")

        # Default dashboard
        if Session.is_admin():
            self.content.addWidget(AdminDashboard())
        else:
            self.content.addWidget(UserDashboard())

        layout.addWidget(self.sidebar)
        layout.addWidget(self.content, 1)

        self.setCentralWidget(container)

    def _on_nav(self, screen: str):
    # Import screens
        if screen == "inventory":
            from desktop.screens.inventory import InventoryScreen
            widget = InventoryScreen()
        elif screen == "models":
            from desktop.screens.models import MasterDataScreen
            widget = MasterDataScreen()
        else:
            widget = QWidget()
            from PyQt6.QtWidgets import QLabel
            lay = QHBoxLayout(widget)
            lbl = QLabel(f"📋  {screen.title()} module — coming soon")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color:#94a3b8; font-size:16px;")
            lay.addWidget(lbl)

        self.content.addWidget(widget)
        self.content.setCurrentWidget(widget)
        
    def _on_logout(self):
        reply = QMessageBox.question(
            self, "Logout",
            "Are you sure you want to logout?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            Session.clear()
            self._show_login()
            self.resize(420, 520)