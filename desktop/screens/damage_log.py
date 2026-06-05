from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QHeaderView, QFrame,
    QTabWidget, QAbstractItemView, QDateEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QColor
from desktop.utils.api_client import APIClient, APIError


# ── WORKERS ───────────────────────────────────────────────────

class LoadSummaryWorker(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            self.done.emit(APIClient.get("/damage-log/summary"))
        except APIError as e:
            self.error.emit(e.message)


class LoadPartsWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, from_date="", to_date="", search=""):
        super().__init__()
        self.from_date = from_date
        self.to_date   = to_date
        self.search    = search

    def run(self):
        try:
            params = []
            if self.from_date:
                params.append(f"from_date={self.from_date}")
            if self.to_date:
                params.append(f"to_date={self.to_date}")
            if self.search:
                params.append(f"search={self.search}")
            qs = "?" + "&".join(params) if params else ""
            self.done.emit(APIClient.get(f"/damage-log/parts{qs}"))
        except APIError as e:
            self.error.emit(e.message)


class LoadDealerDamagesWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, search="", parent=None):
        super().__init__(parent)
        self.search = search

    def run(self):
        try:
            qs = f"?search={self.search}" if self.search else ""
            self.done.emit(APIClient.get(f"/damage-log/dealer-damages{qs}"))
        except APIError as e:
            self.error.emit(e.message)


# ── HELPERS ───────────────────────────────────────────────────

_TABLE_STYLE = """
    QTableWidget {
        border: none; font-size: 13px;
        gridline-color: #f1f5f9; outline: none; color: #1a1a1a;
    }
    QHeaderView::section {
        background: #f8fafc; color: #374151;
        font-weight: 600; font-size: 12px;
        padding: 8px 6px; border: none;
        border-bottom: 2px solid #e2e8f0;
    }
    QTableWidget::item { padding: 8px 6px; border: none; color: #1a1a1a; }
    QTableWidget::item:alternate { background: #fafafa; color: #1a1a1a; }
    QTableWidget::item:selected { background: #fff1f2; color: #1e293b; }
"""

_INPUT_STYLE = (
    "border:1px solid #d1d5db; border-radius:6px; padding:0 10px;"
    " font-size:13px; background:white; color:#1a1a1a;"
)
_DATE_STYLE = (
    "border:1px solid #d1d5db; border-radius:6px; padding:0 6px;"
    " font-size:13px; background:white; color:#1a1a1a;"
)


def _make_card(label: str, color: str):
    outer = QFrame()
    outer.setMinimumHeight(82)
    outer.setStyleSheet("QFrame { background:white; border:none; border-radius:10px; }")
    row = QHBoxLayout(outer)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)

    accent = QFrame()
    accent.setFixedWidth(5)
    accent.setStyleSheet(f"background:{color}; border-radius:10px 0 0 10px;")

    content = QWidget()
    content.setStyleSheet("background:transparent;")
    c = QVBoxLayout(content)
    c.setContentsMargins(14, 12, 14, 12)
    c.setSpacing(4)

    lbl = QLabel(label)
    lbl.setStyleSheet("color:#6b7280; font-size:12px; font-weight:500; background:transparent;")
    val = QLabel("—")
    val.setFont(QFont("Arial", 22, QFont.Weight.Bold))
    val.setStyleSheet(f"color:{color}; background:transparent;")

    c.addWidget(lbl)
    c.addWidget(val)
    row.addWidget(accent)
    row.addWidget(content, 1)
    return outer, val


def _cell(text, align=Qt.AlignmentFlag.AlignLeft, color=None):
    item = QTableWidgetItem(str(text) if text is not None else "")
    item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    if color:
        item.setForeground(QColor(color))
    return item


def _setup_table(table: QTableWidget):
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setStyleSheet(_TABLE_STYLE)


# ── MAIN SCREEN ───────────────────────────────────────────────

class DamageLogScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers = []
        self.setStyleSheet("background:#f8fafc;")
        self._build_ui()
        self._load_summary()
        self._load_parts()

    def _build_ui(self):
        self._main_lay = QVBoxLayout(self)
        self._main_lay.setContentsMargins(28, 20, 28, 20)
        self._main_lay.setSpacing(18)

        # Header
        title = QLabel("⚠️  Damage Log")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b; background:transparent;")
        self._main_lay.addWidget(title)

        # Stat cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)
        self._card_before, self._val_before = _make_card("Parts Damaged (Before Dispatch)", "#dc2626")
        self._card_after,  self._val_after  = _make_card("After Sale / Transit Incidents",  "#ea580c")
        cards_row.addWidget(self._card_before)
        cards_row.addWidget(self._card_after)
        self._main_lay.addLayout(cards_row)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e2e8f0; border-radius: 8px; background: white;
            }
            QTabBar::tab {
                background: #f1f5f9; color: #64748b;
                border: 1px solid #e2e8f0;
                padding: 8px 22px; font-size: 13px;
                border-radius: 6px 6px 0 0; margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: white; color: #1e293b;
                font-weight: 600; border-bottom-color: white;
            }
        """)
        self.tabs.addTab(self._build_before_tab(), "📦  Before Sale to Dealer")
        self.tabs.addTab(self._build_after_tab(),  "🚚  After Sale / Transit")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._main_lay.addWidget(self.tabs, 1)

    # ── BEFORE SALE TAB (inventory defective/damaged movements) ──

    def _build_before_tab(self):
        w = QWidget()
        w.setStyleSheet("background:white;")
        self._before_lay = QVBoxLayout(w)
        self._before_lay.setContentsMargins(16, 16, 16, 16)
        self._before_lay.setSpacing(10)

        info = QLabel("Parts marked as defective or damaged in inventory — before dispatch to any dealer.")
        info.setStyleSheet("color:#64748b; font-size:12px;")
        self._before_lay.addWidget(info)

        fr = QHBoxLayout()
        fr.setSpacing(8)

        self.parts_search = QLineEdit()
        self.parts_search.setPlaceholderText("Search part name, model or colour…")
        self.parts_search.setFixedHeight(36)
        self.parts_search.setStyleSheet(_INPUT_STYLE)
        self.parts_search.returnPressed.connect(self._load_parts)

        self.parts_from = QDateEdit()
        self.parts_from.setFixedHeight(36)
        self.parts_from.setFixedWidth(120)
        self.parts_from.setCalendarPopup(True)
        self.parts_from.setDate(QDate.currentDate().addMonths(-6))
        self.parts_from.setDisplayFormat("dd/MM/yyyy")
        self.parts_from.setStyleSheet(_DATE_STYLE)

        self.parts_to = QDateEdit()
        self.parts_to.setFixedHeight(36)
        self.parts_to.setFixedWidth(120)
        self.parts_to.setCalendarPopup(True)
        self.parts_to.setDate(QDate.currentDate())
        self.parts_to.setDisplayFormat("dd/MM/yyyy")
        self.parts_to.setStyleSheet(_DATE_STYLE)

        search_btn = self._action_btn("🔍  Search", "#dc2626", self._load_parts)
        clear_btn  = self._clear_btn_widget(lambda: [
            self.parts_search.clear(),
            self.parts_from.setDate(QDate.currentDate().addMonths(-6)),
            self.parts_to.setDate(QDate.currentDate()),
            self._load_parts(),
        ])

        fr.addWidget(self.parts_search, 1)
        fr.addWidget(QLabel("From:"))
        fr.addWidget(self.parts_from)
        fr.addWidget(QLabel("To:"))
        fr.addWidget(self.parts_to)
        fr.addWidget(search_btn)
        fr.addWidget(clear_btn)
        self._before_lay.addLayout(fr)

        self.parts_status = QLabel("Loading…")
        self.parts_status.setStyleSheet("color:#94a3b8; font-size:12px;")
        self._before_lay.addWidget(self.parts_status)

        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(7)
        self.parts_table.setHorizontalHeaderLabels(
            ["Date", "Part Name", "SKU", "Type", "Qty", "Notes", "Reported By"]
        )
        hh = self.parts_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.parts_table.setColumnWidth(4, 50)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.parts_table.setColumnWidth(3, 90)
        _setup_table(self.parts_table)
        self._before_lay.addWidget(self.parts_table, 1)
        return w

    # ── AFTER SALE / TRANSIT TAB (DamageRecord) ──────────────

    def _build_after_tab(self):
        w = QWidget()
        w.setStyleSheet("background:white;")
        self._after_lay = QVBoxLayout(w)
        self._after_lay.setContentsMargins(16, 16, 16, 16)
        self._after_lay.setSpacing(10)

        info = QLabel("Damage logged from the Dealers screen — during transit to dealer or after sale.")
        info.setStyleSheet("color:#64748b; font-size:12px;")
        self._after_lay.addWidget(info)

        afr = QHBoxLayout()
        afr.setSpacing(8)
        self.after_search = QLineEdit()
        self.after_search.setPlaceholderText("Search part/damage, model, serial or colour…")
        self.after_search.setFixedHeight(36)
        self.after_search.setStyleSheet(_INPUT_STYLE)
        self.after_search.returnPressed.connect(self._load_after)
        after_search_btn = self._action_btn("🔍  Search", "#dc2626", self._load_after)
        after_clear_btn  = self._clear_btn_widget(lambda: [
            self.after_search.clear(),
            self._load_after(),
        ])
        afr.addWidget(self.after_search, 1)
        afr.addWidget(after_search_btn)
        afr.addWidget(after_clear_btn)
        self._after_lay.addLayout(afr)

        self.after_status = QLabel("Loading…")
        self.after_status.setStyleSheet("color:#94a3b8; font-size:12px;")
        self._after_lay.addWidget(self.after_status)

        self.after_table = QTableWidget()
        self.after_table.setColumnCount(7)
        self.after_table.setHorizontalHeaderLabels(
            ["Date", "Serial No.", "Model", "Stage", "Part / Damage", "Notes", "Reported By"]
        )
        hh = self.after_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.after_table.setColumnWidth(3, 145)
        _setup_table(self.after_table)
        self._after_lay.addWidget(self.after_table, 1)
        return w

    # ── HELPERS ───────────────────────────────────────────────

    def _action_btn(self, text, color, slot):
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"background:{color}; color:white; border:none; border-radius:6px;"
            " padding:0 16px; font-size:13px; font-weight:600;"
        )
        btn.clicked.connect(slot)
        return btn

    def _clear_btn_widget(self, slot):
        btn = QPushButton("✕  Clear")
        btn.setFixedHeight(36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            "border:1px solid #d1d5db; border-radius:6px; padding:0 14px;"
            " font-size:13px; color:#555; background:white;"
        )
        btn.clicked.connect(lambda: slot())
        return btn

    # ── DATA LOADING ──────────────────────────────────────────

    def _load_summary(self):
        w = LoadSummaryWorker(self)
        w.done.connect(self._on_summary)
        w.error.connect(lambda e: [
            self._val_before.setText("Err"),
            self._val_after.setText("Err"),
        ])
        self.workers.append(w)
        w.start()

    def _on_summary(self, data):
        self._val_before.setText(str(data.get("damaged_parts_qty", 0)))
        self._val_after.setText(str(data.get("after_sale_events", 0)))

    def _load_parts(self):
        self.parts_status.setText("Loading…")
        self.parts_table.setRowCount(0)
        w = LoadPartsWorker(
            from_date = self.parts_from.date().toString("yyyy-MM-dd"),
            to_date   = self.parts_to.date().toString("yyyy-MM-dd"),
            search    = self.parts_search.text().strip(),
        )
        w.done.connect(self._populate_parts)
        w.error.connect(lambda e: self.parts_status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    def _load_after(self):
        self.after_status.setText("Loading…")
        self.after_table.setRowCount(0)
        w = LoadDealerDamagesWorker(search=self.after_search.text().strip())
        w.done.connect(self._populate_after)
        w.error.connect(lambda e: self.after_status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    def _on_tab_changed(self, index):
        if index == 0:
            self._load_parts()
        elif index == 1:
            self._load_after()

    # ── POPULATE ──────────────────────────────────────────────

    def _populate_parts(self, rows):
        self.parts_table.setRowCount(len(rows))
        self.parts_status.setText(f"{len(rows)} record(s)")
        type_colors = {"defective": "#dc2626", "damaged": "#ea580c"}
        for r, row in enumerate(rows):
            t = row["type"]
            self.parts_table.setItem(r, 0, _cell(row["date"]))
            self.parts_table.setItem(r, 1, _cell(row["item_name"]))
            self.parts_table.setItem(r, 2, _cell(row["sku"]))
            self.parts_table.setItem(r, 3, _cell(t.capitalize(), color=type_colors.get(t)))
            self.parts_table.setItem(r, 4, _cell(row["quantity"], Qt.AlignmentFlag.AlignCenter))
            self.parts_table.setItem(r, 5, _cell(row["notes"]))
            self.parts_table.setItem(r, 6, _cell(row["reported_by"]))

    def _populate_after(self, rows):
        self.after_table.setRowCount(len(rows))
        self.after_status.setText(f"{len(rows)} record(s)")
        stage_labels = {"transit": "During Transit", "dealer": "After Sale"}
        stage_colors = {"transit": "#ea580c",        "dealer": "#dc2626"}
        for r, row in enumerate(rows):
            stage = row["stage"]
            self.after_table.setItem(r, 0, _cell(row["created_at"]))
            serial_cell = _cell(row["serial_number"])
            if row.get("is_spare_part"):
                serial_cell = _cell("🔧 Spare Part", color="#7c3aed")
            self.after_table.setItem(r, 1, serial_cell)
            self.after_table.setItem(r, 2, _cell(row["model_name"]))
            self.after_table.setItem(r, 3, _cell(
                stage_labels.get(stage, stage), color=stage_colors.get(stage)
            ))
            self.after_table.setItem(r, 4, _cell(row["part_name"]))
            self.after_table.setItem(r, 5, _cell(row["notes"]))
            self.after_table.setItem(r, 6, _cell(row["reported_by"]))
