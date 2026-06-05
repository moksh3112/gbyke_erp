from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session


class SummaryWorker(QThread):
    done = pyqtSignal(dict)

    def run(self):
        try:
            data = APIClient.get("/inventory/summary")
            self.done.emit(data)
        except APIError:
            self.done.emit({})


def _stat_card(title, value, color):
    card = QFrame()
    card.setFixedHeight(100)
    card.setStyleSheet(f"""
        QFrame {{
            background:white; border-radius:10px;
            border-left:4px solid {color};
            border-top:1px solid #e5e7eb;
            border-right:1px solid #e5e7eb;
            border-bottom:1px solid #e5e7eb;
        }}
    """)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 12, 16, 12)
    val = QLabel(value)
    val.setFont(QFont("Arial", 24, QFont.Weight.Bold))
    val.setStyleSheet(f"color:{color}; border:none;")
    val.setObjectName("val")
    ttl = QLabel(title)
    ttl.setStyleSheet("color:#6b7280; font-size:12px; border:none;")
    lay.addWidget(val)
    lay.addWidget(ttl)
    return card


class AdminDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = {}
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = QLabel(f"Welcome back, {Session.username} 👋")
        header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        header.setStyleSheet("color:#1e293b;")
        layout.addWidget(header)

        sub = QLabel("Here's what's happening at G-Byke today.")
        sub.setStyleSheet("color:#64748b; font-size:13px;")
        layout.addWidget(sub)

        grid = QGridLayout()
        grid.setSpacing(12)

        card_defs = [
            ("total_items",    "Total Inventory Items", "—", "#2563eb"),
            ("low_stock",      "Low Stock Alerts",      "—", "#dc2626"),
            ("total_consumed", "Total Consumed",        "—", "#f59e0b"),
            ("total_defective","Total Defective",       "—", "#7c3aed"),
        ]

        for i, (key, title, value, color) in enumerate(card_defs):
            card = _stat_card(title, value, color)
            self.cards[key] = card
            grid.addWidget(card, i // 3, i % 3)

        layout.addLayout(grid)

        info = QLabel("📌  Select a module from the sidebar to get started.")
        info.setStyleSheet("""
            background:#eff6ff; color:#1d4ed8;
            padding:12px 16px; border-radius:8px; font-size:13px;
        """)
        layout.addWidget(info)

    def _load_data(self):
        self.workers = []
        worker = SummaryWorker()
        worker.done.connect(self._update_cards)
        self.workers.append(worker)
        worker.start()

    def _update_cards(self, data):
        mapping = {
            "total_items":     data.get("total_items", "—"),
            "low_stock":       data.get("low_stock_count", "—"),
            "total_consumed":  data.get("total_consumed", "—"),
            "total_defective": data.get("total_defective", "—"),
        }
        for key, card in self.cards.items():
            for child in card.findChildren(QLabel):
                if child.objectName() == "val":
                    child.setText(str(mapping.get(key, "—")))