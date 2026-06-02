from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QLabel, QFrame, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from desktop.utils.session import Session


class Sidebar(QWidget):
    nav_clicked = pyqtSignal(str)  # emits screen name
    logout_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet("background-color: #1e293b;")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("background-color: #0f172a;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        from version import VERSION
        brand = QLabel(f"🛵 G-Byke ERP  v{VERSION}")
        brand.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        brand.setStyleSheet("color: white;")

        role_badge = Session.role.upper() if Session.role else ""
        role_label = QLabel(role_badge)
        role_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 1px;
        """)

        header_layout.addWidget(brand)
        header_layout.addWidget(role_label)
        layout.addWidget(header)

        # ── User info ─────────────────────────────────────────
        user_frame = QFrame()
        user_frame.setFixedHeight(56)
        user_frame.setStyleSheet(
            "background-color: #1e293b; border-bottom: 1px solid #334155;"
        )
        user_layout = QVBoxLayout(user_frame)
        user_layout.setContentsMargins(16, 8, 16, 8)

        user_name = QLabel(f"👤 {Session.full_name or 'User'}")
        user_name.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        user_layout.addWidget(user_name)
        layout.addWidget(user_frame)

        # ── Nav items ─────────────────────────────────────────
        nav_frame = QFrame()
        nav_frame.setStyleSheet("background-color: #1e293b;")
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(8, 12, 8, 12)
        nav_layout.setSpacing(2)

        # Nav items based on role
        nav_items = self._get_nav_items()
        for icon, label, screen in nav_items:
            btn = self._make_nav_btn(icon, label, screen)
            nav_layout.addWidget(btn)

        layout.addWidget(nav_frame)
        layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum,
                        QSizePolicy.Policy.Expanding)
        )

        # ── Logout ────────────────────────────────────────────
        logout_btn = QPushButton("⎋  Logout")
        logout_btn.setFixedHeight(40)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                text-align: left;
                padding-left: 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #dc2626;
                color: white;
                border-radius: 6px;
            }
        """)
        logout_btn.clicked.connect(self.logout_clicked.emit)
        layout.addWidget(logout_btn)
        layout.setContentsMargins(0, 0, 0, 8)

    def _get_nav_items(self):
        common = [
            ("📦", "Inventory",     "inventory"),
            ("🛵", "PDI",           "pdi"),
            ("🏭", "Manufacturing", "manufacturing"),
            ("🏢", "Warehouses",    "warehouses"),
            ("🚚", "Dealers",       "dealers"),
            ("📊", "Reports",       "reports"),
        ]
        admin_only = [
            ("📥", "Shipments",    "shipments"),
            ("🔧", "Spare Parts",  "spare_parts"),
            ("⚠️",  "Damage Log",  "damage"),
            ("👥", "Users",        "users"),
        ]
        if Session.is_admin():
            return common + admin_only
        return common

    def _make_nav_btn(self, icon: str, label: str,
                      screen: str) -> QPushButton:
        btn = QPushButton(f"  {icon}  {label}")
        btn.setFixedHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #cbd5e1;
                border: none;
                text-align: left;
                padding-left: 8px;
                font-size: 13px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: white;
            }
        """)
        btn.clicked.connect(lambda: self.nav_clicked.emit(screen))
        return btn