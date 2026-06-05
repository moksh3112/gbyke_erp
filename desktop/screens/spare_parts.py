from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QHeaderView, QFrame,
    QTabWidget, QAbstractItemView, QDateEdit,
    QDialog, QDialogButtonBox,
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
            self.done.emit(APIClient.get("/spare-parts/summary"))
        except APIError as e:
            self.error.emit(e.message)


class LoadDispatchesWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, dealer_id="", from_date="", to_date="", search=""):
        super().__init__()
        self.dealer_id = dealer_id
        self.from_date = from_date
        self.to_date   = to_date
        self.search    = search

    def run(self):
        try:
            params = []
            if self.dealer_id:
                params.append(f"dealer_id={self.dealer_id}")
            if self.from_date:
                params.append(f"from_date={self.from_date}")
            if self.to_date:
                params.append(f"to_date={self.to_date}")
            if self.search:
                params.append(f"search={self.search}")
            qs = "?" + "&".join(params) if params else ""
            self.done.emit(APIClient.get(f"/spare-parts/dispatches{qs}"))
        except APIError as e:
            self.error.emit(e.message)


class LoadByDealerWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            self.done.emit(APIClient.get("/spare-parts/by-dealer"))
        except APIError as e:
            self.error.emit(e.message)


class LoadDealersWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            self.done.emit(APIClient.get("/dealers/?active_only=true"))
        except APIError as e:
            self.error.emit(e.message)


# ── STAT CARD ─────────────────────────────────────────────────

def _make_card(label: str, color: str):
    """Returns (outer_frame, value_label) tuple."""
    outer = QFrame()
    outer.setStyleSheet(f"""
        QFrame {{
            background: white;
            border: none;
            border-radius: 10px;
        }}
    """)

    # Coloured accent bar on the left via a child frame
    inner_row = QHBoxLayout(outer)
    inner_row.setContentsMargins(0, 0, 0, 0)
    inner_row.setSpacing(0)

    accent = QFrame()
    accent.setFixedWidth(5)
    accent.setStyleSheet(f"background:{color}; border-radius:10px 0 0 10px;")

    content = QWidget()
    content.setStyleSheet("background:transparent;")
    c_lay = QVBoxLayout(content)
    c_lay.setContentsMargins(14, 12, 14, 12)
    c_lay.setSpacing(4)

    lbl = QLabel(label)
    lbl.setStyleSheet("color:#6b7280; font-size:12px; font-weight:500; background:transparent;")

    val = QLabel("—")
    val.setFont(QFont("Arial", 22, QFont.Weight.Bold))
    val.setStyleSheet(f"color:{color}; background:transparent;")

    c_lay.addWidget(lbl)
    c_lay.addWidget(val)

    inner_row.addWidget(accent)
    inner_row.addWidget(content, 1)

    return outer, val


# ── TABLE HELPERS ─────────────────────────────────────────────

_TABLE_STYLE = """
    QTableWidget {
        border: none;
        font-size: 13px;
        gridline-color: #f1f5f9;
        outline: none;
        color: #1a1a1a;
    }
    QHeaderView::section {
        background: #f8fafc;
        color: #374151;
        font-weight: 600;
        font-size: 12px;
        padding: 8px 6px;
        border: none;
        border-bottom: 2px solid #e2e8f0;
    }
    QTableWidget::item { padding: 8px 6px; border: none; color: #1a1a1a; }
    QTableWidget::item:alternate { background: #fafafa; color: #1a1a1a; }
    QTableWidget::item:selected { background: #eff6ff; color: #1e293b; }
"""

_INPUT_STYLE  = "border:1px solid #d1d5db; border-radius:6px; padding:0 10px; font-size:13px; background:white; color:#1a1a1a;"
_COMBO_STYLE  = "border:1px solid #d1d5db; border-radius:6px; padding:0 6px; font-size:13px; background:white; color:#1a1a1a;"


def _cell(text, align=Qt.AlignmentFlag.AlignLeft):
    item = QTableWidgetItem(str(text) if text is not None else "")
    item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    return item


# ── DEALER DRILL-DOWN DIALOG ──────────────────────────────────

class DealerSparePartsDialog(QDialog):
    def __init__(self, dealer_id: str, dealer_name: str, parent=None):
        super().__init__(parent)
        self.dealer_id   = dealer_id
        self.dealer_name = dealer_name
        self.workers     = []
        self.setWindowTitle(f"Spare Parts — {dealer_name}")
        self.resize(820, 520)
        self._build()
        self._load()

    def _build(self):
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(12)

        hdr = QLabel(f"🏪  {self.dealer_name} — Spare Parts Received")
        hdr.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        hdr.setStyleSheet("color:#1e293b;")
        self._lay.addWidget(hdr)

        self.status = QLabel("Loading…")
        self.status.setStyleSheet("color:#94a3b8; font-size:12px;")
        self._lay.addWidget(self.status)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Part Name", "Qty", "Location", "Notes", "Dispatch Note"]
        )
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 55)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(_TABLE_STYLE)
        self._lay.addWidget(self.table, 1)

        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self.reject)
        self._lay.addWidget(close_btn)

    def _load(self):
        w = LoadDispatchesWorker(dealer_id=self.dealer_id)
        w.done.connect(self._populate)
        w.error.connect(lambda e: self.status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    def _populate(self, rows):
        self.table.setRowCount(len(rows))
        self.status.setText(f"{len(rows)} dispatch record(s)")
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, _cell(row["dispatch_date"]))
            self.table.setItem(r, 1, _cell(row["part_name"]))
            self.table.setItem(r, 2, _cell(row["quantity"], Qt.AlignmentFlag.AlignCenter))
            self.table.setItem(r, 3, _cell(row.get("location_name") or "—"))
            self.table.setItem(r, 4, _cell(row.get("notes") or ""))
            self.table.setItem(r, 5, _cell(row.get("dealer_code") or "—"))


# ── MAIN SCREEN ───────────────────────────────────────────────

class SparePartsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers = []
        self._by_dealer_loaded = False
        self.setStyleSheet("background:#f8fafc;")
        self._build_ui()
        self._load_dealers()
        self._load_summary()
        self._search()

    # ── BUILD ─────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(18)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("🔧  Spare Parts")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b; background:transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Stat cards
        cards = QHBoxLayout()
        cards.setSpacing(14)
        self._card_qty,     self._val_qty     = _make_card("Total Qty Dispatched", "#2563eb")
        self._card_parts,   self._val_parts   = _make_card("Unique Part Types",    "#7c3aed")
        self._card_dealers, self._val_dealers = _make_card("Dealers Served",       "#0891b2")
        cards.addWidget(self._card_qty)
        cards.addWidget(self._card_parts)
        cards.addWidget(self._card_dealers)
        layout.addLayout(cards)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #64748b;
                border: 1px solid #e2e8f0;
                padding: 8px 22px;
                font-size: 13px;
                border-radius: 6px 6px 0 0;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #1e293b;
                font-weight: 600;
                border-bottom-color: white;
            }
        """)
        self.tabs.addTab(self._build_log_tab(),    "📋  Dispatch Log")
        self.tabs.addTab(self._build_dealer_tab(), "🏪  By Dealer")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, 1)

    # ── DISPATCH LOG TAB ──────────────────────────────────────

    def _build_log_tab(self):
        w = QWidget()
        w.setStyleSheet("background:white;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # Filter row
        fr = QHBoxLayout()
        fr.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search part name, model or colour...")
        self.search_input.setFixedHeight(36)
        self.search_input.setStyleSheet(_INPUT_STYLE)
        self.search_input.returnPressed.connect(self._search)

        self.dealer_filter = QComboBox()
        self.dealer_filter.setFixedHeight(36)
        self.dealer_filter.setMinimumWidth(170)
        self.dealer_filter.setStyleSheet(_COMBO_STYLE)
        self.dealer_filter.addItem("All Dealers", "")

        self.from_date = QDateEdit()
        self.from_date.setFixedHeight(36)
        self.from_date.setFixedWidth(120)
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-3))
        self.from_date.setDisplayFormat("dd/MM/yyyy")
        self.from_date.setStyleSheet(_COMBO_STYLE)

        self.to_date = QDateEdit()
        self.to_date.setFixedHeight(36)
        self.to_date.setFixedWidth(120)
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        self.to_date.setDisplayFormat("dd/MM/yyyy")
        self.to_date.setStyleSheet(_COMBO_STYLE)

        search_btn = QPushButton("🔍  Search")
        search_btn.setFixedHeight(36)
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setStyleSheet(
            "background:#2563eb; color:white; border:none; border-radius:6px;"
            " padding:0 16px; font-size:13px; font-weight:600;"
        )
        search_btn.clicked.connect(self._search)

        clear_btn = QPushButton("✕  Clear")
        clear_btn.setFixedHeight(36)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            "border:1px solid #d1d5db; border-radius:6px; padding:0 14px;"
            " font-size:13px; color:#555; background:white;"
        )
        clear_btn.clicked.connect(self._clear_filters)

        fr.addWidget(self.search_input, 1)
        fr.addWidget(self.dealer_filter)
        fr.addWidget(QLabel("From:"))
        fr.addWidget(self.from_date)
        fr.addWidget(QLabel("To:"))
        fr.addWidget(self.to_date)
        fr.addWidget(search_btn)
        fr.addWidget(clear_btn)
        lay.addLayout(fr)

        self.log_status = QLabel("Loading…")
        self.log_status.setStyleSheet("color:#94a3b8; font-size:12px;")
        lay.addWidget(self.log_status)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(7)
        self.log_table.setHorizontalHeaderLabels(
            ["Date", "Dealer", "Part Name", "Qty", "Location", "Notes", "Dealer Code"]
        )
        hh = self.log_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.log_table.setColumnWidth(3, 55)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.log_table.setColumnWidth(6, 100)
        self.log_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setStyleSheet(_TABLE_STYLE)
        lay.addWidget(self.log_table, 1)
        return w

    # ── BY DEALER TAB ─────────────────────────────────────────

    def _build_dealer_tab(self):
        w = QWidget()
        w.setStyleSheet("background:white;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        hint = QLabel("Click a dealer name to see all spare parts sent to that dealer.")
        hint.setStyleSheet("color:#64748b; font-size:12px;")
        lay.addWidget(hint)

        self.dealer_status = QLabel("Loading…")
        self.dealer_status.setStyleSheet("color:#94a3b8; font-size:12px;")
        lay.addWidget(self.dealer_status)

        self.dealer_table = QTableWidget()
        self.dealer_table.setColumnCount(5)
        self.dealer_table.setHorizontalHeaderLabels(
            ["Dealer", "Code", "Unique Parts", "Total Qty Sent", "Last Dispatch"]
        )
        self.dealer_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dealer_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dealer_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dealer_table.setAlternatingRowColors(True)
        self.dealer_table.verticalHeader().setVisible(False)
        self.dealer_table.setStyleSheet(_TABLE_STYLE)
        self.dealer_table.cellClicked.connect(self._on_dealer_cell_clicked)
        lay.addWidget(self.dealer_table, 1)
        self._dealer_rows_data = []
        return w

    # ── DATA LOADING ──────────────────────────────────────────

    def _load_dealers(self):
        w = LoadDealersWorker(self)
        w.done.connect(self._on_dealers_loaded)
        self.workers.append(w)
        w.start()

    def _on_dealers_loaded(self, dealers):
        self.dealer_filter.clear()
        self.dealer_filter.addItem("All Dealers", "")
        for d in dealers:
            self.dealer_filter.addItem(d["dealer_name"], d["id"])

    def _load_summary(self):
        w = LoadSummaryWorker(self)
        w.done.connect(self._on_summary)
        self.workers.append(w)
        w.start()

    def _on_summary(self, data):
        self._val_qty.setText(str(data.get("total_qty", 0)))
        self._val_parts.setText(str(data.get("unique_parts", 0)))
        self._val_dealers.setText(str(data.get("unique_dealers", 0)))

    def _search(self):
        self.log_status.setText("Loading…")
        self.log_table.setRowCount(0)
        w = LoadDispatchesWorker(
            dealer_id = self.dealer_filter.currentData() or "",
            from_date = self.from_date.date().toString("yyyy-MM-dd"),
            to_date   = self.to_date.date().toString("yyyy-MM-dd"),
            search    = self.search_input.text().strip(),
        )
        w.done.connect(self._populate_log)
        w.error.connect(lambda e: self.log_status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    def _clear_filters(self):
        self.search_input.clear()
        self.dealer_filter.setCurrentIndex(0)
        self.from_date.setDate(QDate.currentDate().addMonths(-3))
        self.to_date.setDate(QDate.currentDate())
        self._search()

    def _on_tab_changed(self, index):
        if index == 0:
            self._search()
        elif index == 1 and not self._by_dealer_loaded:
            self._load_by_dealer()

    def _load_by_dealer(self):
        self.dealer_status.setText("Loading…")
        self.dealer_table.setRowCount(0)
        w = LoadByDealerWorker(self)
        w.done.connect(self._populate_by_dealer)
        w.error.connect(lambda e: self.dealer_status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    # ── POPULATE ──────────────────────────────────────────────

    def _populate_log(self, rows):
        self.log_table.setRowCount(len(rows))
        self.log_status.setText(f"{len(rows)} record(s) found")
        for r, row in enumerate(rows):
            self.log_table.setItem(r, 0, _cell(row["dispatch_date"]))
            self.log_table.setItem(r, 1, _cell(row["dealer_name"]))
            self.log_table.setItem(r, 2, _cell(row["part_name"]))
            self.log_table.setItem(r, 3, _cell(row["quantity"], Qt.AlignmentFlag.AlignCenter))
            self.log_table.setItem(r, 4, _cell(row["location_name"] or "—"))
            self.log_table.setItem(r, 5, _cell(row["notes"]))
            self.log_table.setItem(r, 6, _cell(row["dealer_code"]))

    def _populate_by_dealer(self, rows):
        self._by_dealer_loaded = True
        self._dealer_rows_data = rows
        self.dealer_table.setRowCount(len(rows))
        self.dealer_status.setText(f"{len(rows)} dealer(s) — click a name to view parts")
        for r, row in enumerate(rows):
            name_item = QTableWidgetItem(row["dealer_name"])
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_item.setForeground(QColor("#2563eb"))
            font = name_item.font()
            font.setUnderline(True)
            name_item.setFont(font)
            self.dealer_table.setItem(r, 0, name_item)
            self.dealer_table.setItem(r, 1, _cell(row["dealer_code"]))
            self.dealer_table.setItem(r, 2, _cell(row["unique_parts"], Qt.AlignmentFlag.AlignCenter))
            self.dealer_table.setItem(r, 3, _cell(row["total_qty"],    Qt.AlignmentFlag.AlignCenter))
            self.dealer_table.setItem(r, 4, _cell(row["last_dispatch"]))
        self.dealer_table.setCursor(Qt.CursorShape.PointingHandCursor)

    def _on_dealer_cell_clicked(self, row: int, col: int):
        if col != 0 or row >= len(self._dealer_rows_data):
            return
        d = self._dealer_rows_data[row]
        dlg = DealerSparePartsDialog(d["dealer_id"], d["dealer_name"], self)
        dlg.exec()
