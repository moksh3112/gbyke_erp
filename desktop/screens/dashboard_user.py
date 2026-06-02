from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from desktop.utils.session import Session


class UserDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = QLabel(f"Welcome, {Session.full_name} 👋")
        header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #1e293b;")
        layout.addWidget(header)

        sub = QLabel("Use the sidebar to access your assigned modules.")
        sub.setStyleSheet("color: #64748b; font-size: 13px;")
        layout.addWidget(sub)

        # Quick action cards
        actions = [
            ("📦", "Mark Inventory Consumed",  "#2563eb"),
            ("⚠️",  "Mark Inventory Defective", "#dc2626"),
            ("🛵", "Update PDI Status",         "#16a34a"),
        ]

        for icon, label, color in actions:
            card = QFrame()
            card.setFixedHeight(64)
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: white;
                    border-radius: 8px;
                    border-left: 4px solid {color};
                    border-top: 1px solid #e5e7eb;
                    border-right: 1px solid #e5e7eb;
                    border-bottom: 1px solid #e5e7eb;
                }}
            """)
            row = QHBoxLayout(card)
            row.setContentsMargins(16, 0, 16, 0)

            lbl = QLabel(f"{icon}  {label}")
            lbl.setStyleSheet(
                f"color: {color}; font-size: 14px; font-weight: 500; border: none;"
            )
            row.addWidget(lbl)
            layout.addWidget(card)

        info = QLabel("📌  Click a module in the sidebar to begin.")
        info.setStyleSheet("""
            background-color: #f0fdf4;
            color: #15803d;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 13px;
        """)
        layout.addWidget(info)