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
        self.setFont(QFont("Segoe UI", 10))
        self._show_login()

    # ── LOGIN ──────────────────────────────────────────────────

    def _show_login(self):
        self.login_screen = LoginScreen()
        self.login_screen.login_successful.connect(self._on_login)
        self.setCentralWidget(self.login_screen)

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
            # No maximize button on login
        )
        self.setMinimumSize(0, 0)
        self.setMaximumSize(420, 580)
        self.resize(420, 580)
        self.show()

        try:
            screen_geo = self.screen().availableGeometry()
            x = (screen_geo.width()  - 420) // 2
            y = (screen_geo.height() - 580) // 2
            self.move(x, y)
        except Exception:
            pass
    def _on_login(self, role: str):
        # Re-enable maximize without calling show() twice
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumSize(1100, 680)
        self.setMaximumSize(16777215, 16777215)
        self.resize(1280, 800)

        # Center on screen
        try:
            screen_geo = self.screen().availableGeometry()
            x = (screen_geo.width()  - 1280) // 2
            y = (screen_geo.height() - 800)  // 2
            self.move(x, y)
        except Exception:
            pass

        self._show_main_app()
        self.show()  # single show() call AFTER setting up main app
    # ── MAIN APP ───────────────────────────────────────────────

    def _show_main_app(self):
        container = QWidget()
        layout    = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.nav_clicked.connect(self._on_nav)
        self.sidebar.logout_clicked.connect(self._on_logout)

        # Content area
        self.content = QStackedWidget()
        self.content.setStyleSheet("background-color:#f8fafc;")

        # Default dashboard
        if Session.role in ["superadmin", "manager"]:
            self.content.addWidget(AdminDashboard())
        else:
            self.content.addWidget(UserDashboard())

        layout.addWidget(self.sidebar)
        layout.addWidget(self.content, 1)

        self.setCentralWidget(container)

    def _on_nav(self, screen: str):
        if screen == "inventory":
            from desktop.screens.inventory import InventoryScreen
            widget = InventoryScreen()
        elif screen == "manufacturing":
            from desktop.screens.manufacturing import ManufacturingScreen
            widget = ManufacturingScreen()
        elif screen == "models":
            from desktop.screens.models import MasterDataScreen
            widget = MasterDataScreen()
        elif screen == "users":
            from desktop.screens.users import UsersScreen
            widget = UsersScreen()
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
            # Reset window flags for login
            self.setWindowFlag(
                Qt.WindowType.WindowMaximizeButtonHint, False
            )
            self.setMinimumSize(0, 0)
            self._show_login()