# desktop/app.py
# FIX 14: Named "coming soon" stubs for all sidebar nav items that have no screen yet.
#         Each shows the module name and a friendly message instead of blank nothing.

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout,
    QStackedWidget, QMessageBox, QVBoxLayout, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from desktop.screens.login import LoginScreen
from desktop.screens.dashboard_admin import AdminDashboard
from desktop.screens.dashboard_user import UserDashboard
from desktop.components.sidebar import Sidebar
from desktop.utils.session import Session


def _coming_soon_screen(icon: str, title: str, description: str) -> QWidget:
    """Reusable placeholder for modules not yet built."""
    w = QWidget()
    w.setStyleSheet("background: #f8fafc;")
    lay = QVBoxLayout(w)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.setSpacing(8)

    icon_lbl = QLabel(icon)
    icon_lbl.setFont(QFont("Arial", 48))
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

    title_lbl = QLabel(title)
    title_lbl.setFont(QFont("Arial", 18, QFont.Weight.Bold))
    title_lbl.setStyleSheet("color: #1e293b;")
    title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

    desc_lbl = QLabel(description)
    desc_lbl.setStyleSheet("color: #64748b; font-size: 13px;")
    desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

    badge = QLabel("🚧  Coming Soon")
    badge.setStyleSheet(
        "background: #fef3c7; color: #92400e; border-radius: 6px; "
        "padding: 6px 16px; font-size: 12px; font-weight: 600;"
    )
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

    lay.addWidget(icon_lbl)
    lay.addWidget(title_lbl)
    lay.addWidget(desc_lbl)
    lay.addSpacing(12)
    lay.addWidget(badge)
    return w


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from version import VERSION
        self.setWindowTitle(f"G-Byke ERP — v{VERSION}")
        self.setFont(QFont("Segoe UI", 10))
        self._show_login()

    def _show_login(self):
        self.login_screen = LoginScreen()
        self.login_screen.login_successful.connect(self._on_login)
        self.setCentralWidget(self.login_screen)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumSize(0, 0)
        self.setMaximumSize(420, 580)
        self.resize(420, 580)
        self.show()
        try:
            geo = self.screen().availableGeometry()
            self.move((geo.width() - 420) // 2, (geo.height() - 580) // 2)
        except Exception:
            pass

    def _on_login(self, role: str):
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumSize(1100, 680)
        self.setMaximumSize(16777215, 16777215)
        self.resize(1280, 800)
        try:
            geo = self.screen().availableGeometry()
            self.move((geo.width() - 1280) // 2, (geo.height() - 800) // 2)
        except Exception:
            pass
        self._show_main_app()
        self.show()

    def _show_main_app(self):
        container = QWidget()
        layout    = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.nav_clicked.connect(self._on_nav)
        self.sidebar.logout_clicked.connect(self._on_logout)

        self.content = QStackedWidget()
        self.content.setStyleSheet("background-color: #f8fafc;")

        if Session.role in ["superadmin", "manager"]:
            self.content.addWidget(AdminDashboard())
        else:
            self.content.addWidget(UserDashboard())

        layout.addWidget(self.sidebar)
        layout.addWidget(self.content, 1)
        self.setCentralWidget(container)

    def _on_nav(self, screen: str):
        # ── Built screens ──────────────────────────────────────
        if screen == "inventory":
            from desktop.screens.inventory import InventoryScreen
            widget = InventoryScreen()
        elif screen == "manufacturing":
            from desktop.screens.manufacturing import ManufacturingScreen
            widget = ManufacturingScreen()
        elif screen == "scooter_log":
            from desktop.screens.scooter_log import ScooterLogScreen
            widget = ScooterLogScreen()
        elif screen == "models":
            from desktop.screens.models import MasterDataScreen
            widget = MasterDataScreen()
        elif screen == "users":
            from desktop.screens.users import UsersScreen
            widget = UsersScreen()
        elif screen == "pdi":
            from desktop.screens.pdi import PDIScreen
            widget = PDIScreen()
        elif screen == "warehouses":
            from desktop.screens.warehouses import WarehousesScreen
            widget = WarehousesScreen()

        elif screen == "dealers":
            from desktop.screens.dealers import DealersScreen
            widget = DealersScreen()
        elif screen == "shipments":
            from desktop.screens.shipments import ShipmentsScreen
            widget = ShipmentsScreen()
        elif screen == "spare_parts":
            from desktop.screens.spare_parts import SparePartsScreen
            widget = SparePartsScreen()
        elif screen == "damage":
            from desktop.screens.damage_log import DamageLogScreen
            widget = DamageLogScreen()
        elif screen == "reports":
            from desktop.screens.reports import ReportsScreen
            widget = ReportsScreen()
        else:
            widget = _coming_soon_screen(
                "📋", screen.replace("_", " ").title(),
                "This module is under development."
            )

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
            self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
            self.setMinimumSize(0, 0)
            self._show_login()