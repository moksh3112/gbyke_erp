from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QTabWidget,
    QAbstractItemView, QDateEdit, QSizePolicy,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont
from desktop.utils.api_client import APIClient, APIError


# ── WORKERS ───────────────────────────────────────────────────

class ReportWorker(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, endpoint: str, params: dict = None):
        super().__init__()
        self._endpoint = endpoint
        self._params   = params or {}

    def run(self):
        try:
            qs_parts = [f"{k}={v}" for k, v in self._params.items() if v]
            qs = "?" + "&".join(qs_parts) if qs_parts else ""
            self.done.emit(APIClient.get(f"/reports/{self._endpoint}{qs}"))
        except APIError as e:
            self.error.emit(e.message)


# ── SHARED HELPERS ────────────────────────────────────────────

_TABLE_STYLE = """
    QTableWidget {
        border: none; font-size: 13px;
        gridline-color: #f1f5f9; outline: none;
    }
    QHeaderView::section {
        background: #f8fafc; color: #374151;
        font-weight: 600; font-size: 12px;
        padding: 8px 8px; border: none;
        border-bottom: 2px solid #e2e8f0;
    }
    QTableWidget::item { padding: 8px 6px; border: none; }
    QTableWidget::item:alternate { background: #fafafa; }
    QTableWidget::item:selected { background: #eff6ff; color: #1e293b; }
"""

_DATE_STYLE  = "border:1px solid #d1d5db; border-radius:6px; padding:0 6px; font-size:13px; background:white;"
_LABEL_STYLE = "color:#374151; font-size:12px;"


def _cell(text, align=Qt.AlignmentFlag.AlignLeft, bold=False, color=None):
    item = QTableWidgetItem(str(text) if text is not None else "")
    item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    if color:
        from PyQt6.QtGui import QColor
        item.setForeground(QColor(color))
    return item


def _make_table(headers: list, stretch_cols: list = None) -> QTableWidget:
    t = QTableWidget()
    t.setColumnCount(len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.setStyleSheet(_TABLE_STYLE)
    hh = t.horizontalHeader()
    if stretch_cols:
        for col in stretch_cols:
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
    else:
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return t


def _make_kpi_row(kpis: list) -> QWidget:
    """kpis: list of (label, value, color)"""
    w = QWidget()
    w.setStyleSheet("background:transparent;")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)
    for label, value, color in kpis:
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background:white; border:none; border-radius:8px; }}")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cl = QHBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        accent = QFrame()
        accent.setFixedWidth(4)
        accent.setStyleSheet(f"background:{color}; border-radius:8px 0 0 8px;")
        content = QWidget()
        content.setStyleSheet("background:transparent;")
        cc = QVBoxLayout(content)
        cc.setContentsMargins(12, 10, 12, 10)
        cc.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet("color:#6b7280; font-size:11px; font-weight:500; background:transparent;")
        val = QLabel(str(value))
        val.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        val.setStyleSheet(f"color:{color}; background:transparent;")
        cc.addWidget(lbl)
        cc.addWidget(val)
        cl.addWidget(accent)
        cl.addWidget(content, 1)
        row.addWidget(card)
    return w


def _date_filter(default_months_back=6):
    """Returns (widget, from_edit, to_edit)"""
    w = QWidget()
    w.setStyleSheet("background:transparent;")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)

    from_lbl = QLabel("From:")
    from_lbl.setStyleSheet(_LABEL_STYLE)
    from_edit = QDateEdit()
    from_edit.setFixedHeight(34)
    from_edit.setFixedWidth(115)
    from_edit.setCalendarPopup(True)
    from_edit.setDate(QDate.currentDate().addMonths(-default_months_back))
    from_edit.setDisplayFormat("dd/MM/yyyy")
    from_edit.setStyleSheet(_DATE_STYLE)

    to_lbl = QLabel("To:")
    to_lbl.setStyleSheet(_LABEL_STYLE)
    to_edit = QDateEdit()
    to_edit.setFixedHeight(34)
    to_edit.setFixedWidth(115)
    to_edit.setCalendarPopup(True)
    to_edit.setDate(QDate.currentDate())
    to_edit.setDisplayFormat("dd/MM/yyyy")
    to_edit.setStyleSheet(_DATE_STYLE)

    row.addWidget(from_lbl)
    row.addWidget(from_edit)
    row.addWidget(to_lbl)
    row.addWidget(to_edit)
    row.addStretch()
    return w, from_edit, to_edit


def _run_btn(slot, color="#2563eb"):
    btn = QPushButton("↻  Run Report")
    btn.setFixedHeight(34)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"background:{color}; color:white; border:none; border-radius:6px;"
        " padding:0 16px; font-size:13px; font-weight:600;"
    )
    btn.clicked.connect(slot)
    return btn


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))
    lbl.setStyleSheet("color:#1e293b; background:transparent; margin-top:6px;")
    return lbl


def _status_lbl() -> QLabel:
    lbl = QLabel("")
    lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
    return lbl


# ── MAIN SCREEN ───────────────────────────────────────────────

class ReportsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers = []
        self.setStyleSheet("background:#f8fafc;")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        title = QLabel("📊  Reports")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b; background:transparent;")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e2e8f0; border-radius: 8px; background: white;
            }
            QTabBar::tab {
                background: #f1f5f9; color: #64748b;
                border: 1px solid #e2e8f0;
                padding: 8px 20px; font-size: 13px;
                border-radius: 6px 6px 0 0; margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: white; color: #1e293b;
                font-weight: 600; border-bottom-color: white;
            }
        """)
        self.tabs.addTab(self._build_inventory_tab(),   "📦  Inventory")
        self.tabs.addTab(self._build_production_tab(),  "🏭  Production")
        self.tabs.addTab(self._build_dispatch_tab(),    "🚚  Dispatch")
        self.tabs.addTab(self._build_pdi_tab(),         "🔍  PDI & Damage")
        layout.addWidget(self.tabs, 1)

        # Auto-run first tab
        self._run_inventory()

    # ── INVENTORY TAB ─────────────────────────────────────────

    def _build_inventory_tab(self):
        w, scroll = self._scrollable()
        lay = scroll

        btn = _run_btn(self._run_inventory, "#2563eb")
        brow = QHBoxLayout()
        brow.addWidget(btn)
        brow.addStretch()
        lay.addLayout(brow)

        self._inv_kpi = QWidget()
        lay.addWidget(self._inv_kpi)

        lay.addWidget(_section_title("By Category"))
        self._inv_cat_status = _status_lbl()
        lay.addWidget(self._inv_cat_status)
        self._inv_cat_table = _make_table(
            ["Category", "Items", "Remaining Stock", "Consumed"]
        )
        self._inv_cat_table.setMaximumHeight(220)
        lay.addWidget(self._inv_cat_table)

        lay.addWidget(_section_title("⚠ Low Stock Items"))
        self._inv_low_status = _status_lbl()
        lay.addWidget(self._inv_low_status)
        self._inv_low_table = _make_table(
            ["Item Name", "SKU", "Category", "Remaining", "Threshold"]
        )
        self._inv_low_table.setMaximumHeight(200)
        lay.addWidget(self._inv_low_table)
        lay.addStretch()
        return w

    def _run_inventory(self):
        self._inv_cat_status.setText("Loading…")
        self._inv_low_status.setText("Loading…")
        w = ReportWorker("inventory")
        w.done.connect(self._populate_inventory)
        w.error.connect(lambda e: self._inv_cat_status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    def _populate_inventory(self, data):
        s = data["summary"]
        kpis = [
            ("Total Items",       s["total_items"],     "#2563eb"),
            ("Remaining Stock",   s["total_remaining"], "#16a34a"),
            ("Total Consumed",    s["total_consumed"],  "#7c3aed"),
            ("Defective/Damaged", s["total_defective"], "#dc2626"),
            ("Low Stock Items",   s["low_stock_count"], "#ea580c"),
        ]
        old = self._inv_kpi
        new = _make_kpi_row(kpis)
        old.parentWidget().layout().replaceWidget(old, new)
        old.deleteLater()
        self._inv_kpi = new

        cats = data["by_category"]
        self._inv_cat_table.setRowCount(len(cats))
        self._inv_cat_status.setText(f"{len(cats)} categories")
        for r, row in enumerate(cats):
            self._inv_cat_table.setItem(r, 0, _cell(row["category"], bold=True))
            self._inv_cat_table.setItem(r, 1, _cell(row["items"],     Qt.AlignmentFlag.AlignCenter))
            self._inv_cat_table.setItem(r, 2, _cell(row["remaining"], Qt.AlignmentFlag.AlignCenter))
            self._inv_cat_table.setItem(r, 3, _cell(row["consumed"],  Qt.AlignmentFlag.AlignCenter))

        low = data["low_stock_items"]
        self._inv_low_table.setRowCount(len(low))
        self._inv_low_status.setText(f"{len(low)} item(s) at or below threshold")
        for r, row in enumerate(low):
            self._inv_low_table.setItem(r, 0, _cell(row["item_name"], bold=True))
            self._inv_low_table.setItem(r, 1, _cell(row["sku"]))
            self._inv_low_table.setItem(r, 2, _cell(row["category"]))
            self._inv_low_table.setItem(r, 3, _cell(row["remaining"], Qt.AlignmentFlag.AlignCenter,
                                                     color="#dc2626"))
            self._inv_low_table.setItem(r, 4, _cell(row["threshold"], Qt.AlignmentFlag.AlignCenter))

    # ── PRODUCTION TAB ────────────────────────────────────────

    def _build_production_tab(self):
        w, lay = self._scrollable()

        filter_w, self._prod_from, self._prod_to = _date_filter()
        btn = _run_btn(self._run_production, "#7c3aed")
        fr = QHBoxLayout()
        fr.addWidget(filter_w)
        fr.addWidget(btn)
        lay.addLayout(fr)

        self._prod_kpi = QWidget()
        lay.addWidget(self._prod_kpi)

        lay.addWidget(_section_title("By Model"))
        self._prod_status = _status_lbl()
        lay.addWidget(self._prod_status)
        self._prod_table = _make_table(
            ["Model", "Total Jobs", "Assembled", "Damaged", "Cancelled"]
        )
        lay.addWidget(self._prod_table, 1)
        return w

    def _run_production(self):
        self._prod_status.setText("Loading…")
        self._prod_table.setRowCount(0)
        w = ReportWorker("manufacturing", {
            "from_date": self._prod_from.date().toString("yyyy-MM-dd"),
            "to_date":   self._prod_to.date().toString("yyyy-MM-dd"),
        })
        w.done.connect(self._populate_production)
        w.error.connect(lambda e: self._prod_status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    def _populate_production(self, data):
        s = data["summary"]
        kpis = [
            ("Total Jobs",      s["total_jobs"],      "#7c3aed"),
            ("Completed",       s["completed"],       "#16a34a"),
            ("Cancelled",       s["cancelled"],       "#ea580c"),
            ("Scooters Built",  s["total_assembled"], "#2563eb"),
            ("Units Damaged",   s["total_damaged"],   "#dc2626"),
        ]
        old = self._prod_kpi
        new = _make_kpi_row(kpis)
        old.parentWidget().layout().replaceWidget(old, new)
        old.deleteLater()
        self._prod_kpi = new

        rows = data["by_model"]
        self._prod_table.setRowCount(len(rows))
        self._prod_status.setText(f"{len(rows)} model(s)")
        for r, row in enumerate(rows):
            self._prod_table.setItem(r, 0, _cell(row["model"], bold=True))
            self._prod_table.setItem(r, 1, _cell(row["jobs"],      Qt.AlignmentFlag.AlignCenter))
            self._prod_table.setItem(r, 2, _cell(row["assembled"], Qt.AlignmentFlag.AlignCenter))
            self._prod_table.setItem(r, 3, _cell(row["damaged"],   Qt.AlignmentFlag.AlignCenter,
                                                  color="#dc2626" if row["damaged"] > 0 else None))
            self._prod_table.setItem(r, 4, _cell(row["cancelled"], Qt.AlignmentFlag.AlignCenter,
                                                  color="#ea580c" if row["cancelled"] > 0 else None))

    # ── DISPATCH TAB ──────────────────────────────────────────

    def _build_dispatch_tab(self):
        w, lay = self._scrollable()

        filter_w, self._disp_from, self._disp_to = _date_filter()
        btn = _run_btn(self._run_dispatch, "#0891b2")
        fr = QHBoxLayout()
        fr.addWidget(filter_w)
        fr.addWidget(btn)
        lay.addLayout(fr)

        self._disp_kpi = QWidget()
        lay.addWidget(self._disp_kpi)

        lay.addWidget(_section_title("By Dealer"))
        self._disp_status = _status_lbl()
        lay.addWidget(self._disp_status)
        self._disp_table = _make_table(
            ["Dealer", "Code", "Dispatches", "Scooters Sent", "Parts Qty", "Last Dispatch"]
        )
        lay.addWidget(self._disp_table, 1)
        return w

    def _run_dispatch(self):
        self._disp_status.setText("Loading…")
        self._disp_table.setRowCount(0)
        w = ReportWorker("dispatch", {
            "from_date": self._disp_from.date().toString("yyyy-MM-dd"),
            "to_date":   self._disp_to.date().toString("yyyy-MM-dd"),
        })
        w.done.connect(self._populate_dispatch)
        w.error.connect(lambda e: self._disp_status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    def _populate_dispatch(self, data):
        s = data["summary"]
        kpis = [
            ("Total Dispatches", s["total_dispatches"], "#0891b2"),
            ("Scooters Sent",    s["total_scooters"],   "#2563eb"),
            ("Parts Qty Sent",   s["total_parts_qty"],  "#7c3aed"),
            ("Dealers Served",   s["dealers_served"],   "#16a34a"),
        ]
        old = self._disp_kpi
        new = _make_kpi_row(kpis)
        old.parentWidget().layout().replaceWidget(old, new)
        old.deleteLater()
        self._disp_kpi = new

        rows = data["by_dealer"]
        self._disp_table.setRowCount(len(rows))
        self._disp_status.setText(f"{len(rows)} dealer(s)")
        for r, row in enumerate(rows):
            self._disp_table.setItem(r, 0, _cell(row["dealer_name"], bold=True))
            self._disp_table.setItem(r, 1, _cell(row["dealer_code"]))
            self._disp_table.setItem(r, 2, _cell(row["dispatches"],  Qt.AlignmentFlag.AlignCenter))
            self._disp_table.setItem(r, 3, _cell(row["scooters"],    Qt.AlignmentFlag.AlignCenter))
            self._disp_table.setItem(r, 4, _cell(row["parts_qty"],   Qt.AlignmentFlag.AlignCenter))
            self._disp_table.setItem(r, 5, _cell(row["last_dispatch"]))

    # ── PDI & DAMAGE TAB ──────────────────────────────────────

    def _build_pdi_tab(self):
        w, lay = self._scrollable()

        filter_w, self._pdi_from, self._pdi_to = _date_filter()
        btn = _run_btn(self._run_pdi, "#dc2626")
        fr = QHBoxLayout()
        fr.addWidget(filter_w)
        fr.addWidget(btn)
        lay.addLayout(fr)

        self._pdi_kpi = QWidget()
        lay.addWidget(self._pdi_kpi)

        cols_row = QHBoxLayout()
        cols_row.setSpacing(16)

        # Scooter status breakdown
        left = QVBoxLayout()
        left.addWidget(_section_title("Scooter Status Breakdown"))
        self._status_status = _status_lbl()
        left.addWidget(self._status_status)
        self._status_table = _make_table(["Status", "Count"])
        self._status_table.setMaximumHeight(230)
        left.addWidget(self._status_table)
        left_w = QWidget()
        left_w.setStyleSheet("background:transparent;")
        left_w.setLayout(left)
        cols_row.addWidget(left_w, 1)

        # Damage by stage
        right = QVBoxLayout()
        right.addWidget(_section_title("Damage Records by Stage"))
        self._dmg_stage_status = _status_lbl()
        right.addWidget(self._dmg_stage_status)
        self._dmg_stage_table = _make_table(["Stage", "Count"])
        self._dmg_stage_table.setMaximumHeight(230)
        right.addWidget(self._dmg_stage_table)
        right_w = QWidget()
        right_w.setStyleSheet("background:transparent;")
        right_w.setLayout(right)
        cols_row.addWidget(right_w, 1)

        lay.addLayout(cols_row)
        lay.addStretch()
        return w

    def _run_pdi(self):
        self._status_status.setText("Loading…")
        self._dmg_stage_status.setText("Loading…")
        w = ReportWorker("pdi-damage", {
            "from_date": self._pdi_from.date().toString("yyyy-MM-dd"),
            "to_date":   self._pdi_to.date().toString("yyyy-MM-dd"),
        })
        w.done.connect(self._populate_pdi)
        w.error.connect(lambda e: self._status_status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    def _populate_pdi(self, data):
        p = data["pdi"]
        kpis = [
            ("PDI Completed",        p["total_completed"], "#2563eb"),
            ("Passed",               p["passed"],          "#16a34a"),
            ("Failed",               p["failed"],          "#dc2626"),
            ("Pending PDI",          p["pending"],         "#ea580c"),
            ("Pass Rate",            f"{p['pass_rate']}%", "#7c3aed"),
            ("Inventory Dmg (qty)",  data["inventory_damage_qty"], "#dc2626"),
        ]
        old = self._pdi_kpi
        new = _make_kpi_row(kpis)
        old.parentWidget().layout().replaceWidget(old, new)
        old.deleteLater()
        self._pdi_kpi = new

        statuses = data["scooter_status"]
        self._status_table.setRowCount(len(statuses))
        self._status_status.setText(f"{len(statuses)} status type(s)")
        for r, row in enumerate(statuses):
            self._status_table.setItem(r, 0, _cell(row["status"], bold=True))
            self._status_table.setItem(r, 1, _cell(row["count"], Qt.AlignmentFlag.AlignCenter))

        stages = data["damage_by_stage"]
        self._dmg_stage_table.setRowCount(len(stages))
        self._dmg_stage_status.setText(f"{len(stages)} stage(s) with damage")
        for r, row in enumerate(stages):
            self._dmg_stage_table.setItem(r, 0, _cell(row["stage"], bold=True))
            self._dmg_stage_table.setItem(r, 1, _cell(row["count"], Qt.AlignmentFlag.AlignCenter,
                                                        color="#dc2626"))

    # ── UTILITY ───────────────────────────────────────────────

    def _scrollable(self):
        """Returns (outer QWidget, inner QVBoxLayout) with scroll."""
        outer = QWidget()
        outer.setStyleSheet("background:white;")
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:white;")

        inner = QWidget()
        inner.setStyleSheet("background:white;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        scroll.setWidget(inner)
        outer_lay.addWidget(scroll)
        return outer, lay
