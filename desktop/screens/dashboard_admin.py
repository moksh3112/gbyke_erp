from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from desktop.utils.session import Session


def _stat_card(title: str, value: str, color: str) -> QFrame:
    card = QFrame()
    card.setFixedHeight(100)
    card.setStyleSheet(f"""
        QFrame {{
            background-color: white;
            border-radius: 10px;
            border-left: 4px solid {color};
            border-top: 1px solid #e5e7eb;
            border-right: 1px solid #e5e7eb;
            border-bottom: 1px solid #e5e7eb;
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 12)

    val_label = QLabel(value)
    val_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
    val_label.setStyleSheet(f"color: {color}; border: none;")

    title_label = QLabel(title)
    title_label.setStyleSheet("color: #6b7280; font-size: 12px; border: none;")

    layout.addWidget(val_label)
    layout.addWidget(title_label)
    return card


class AdminDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header
        header = QLabel(f"Welcome back, {Session.full_name} 👋")
        header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #1e293b;")
        layout.addWidget(header)

        sub = QLabel("Here's what's happening at G-Byke today.")
        sub.setStyleSheet("color: #64748b; font-size: 13px;")
        layout.addWidget(sub)

        # Stat cards grid
        grid = QGridLayout()
        grid.setSpacing(12)

        cards = [
            ("Total Inventory Items", "—", "#2563eb"),
            ("Low Stock Alerts",      "—", "#dc2626"),
            ("Vehicles in PDI",       "—", "#f59e0b"),
            ("PDI Completed Today",   "—", "#16a34a"),
            ("Pending Dispatches",    "—", "#7c3aed"),
            ("Active Dealers",        "—", "#0891b2"),
        ]

        for i, (title, value, color) in enumerate(cards):
            card = _stat_card(title, value, color)
            grid.addWidget(card, i // 3, i % 3)

        layout.addLayout(grid)

        # Quick info
        info = QLabel(
            "📌  Select a module from the sidebar to get started."
        )
        info.setStyleSheet("""
            background-color: #eff6ff;
            color: #1d4ed8;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 13px;
        """)
        layout.addWidget(info)