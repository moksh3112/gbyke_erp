from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QTabWidget,
    QAbstractItemView, QDateEdit, QSizePolicy,
    QScrollArea, QTreeWidget, QTreeWidgetItem,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QColor
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
        gridline-color: #f1f5f9; outline: none; color: #1a1a1a;
    }
    QHeaderView::section {
        background: #f8fafc; color: #374151;
        font-weight: 600; font-size: 12px;
        padding: 8px 8px; border: none;
        border-bottom: 2px solid #e2e8f0;
    }
    QTableWidget::item { padding: 8px 6px; border: none; color: #1a1a1a; }
    QTableWidget::item:alternate { background: #fafafa; color: #1a1a1a; }
    QTableWidget::item:selected { background: #eff6ff; color: #1e293b; }
"""

_DATE_STYLE  = "border:1px solid #d1d5db; border-radius:6px; padding:0 6px; font-size:13px; background:white; color:#1a1a1a;"
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


_TREE_STYLE = """
    QTreeWidget {
        border: 1px solid #e5e7eb; border-radius: 8px;
        font-size: 13px; outline: none; color: #1a1a1a; background: white;
    }
    QHeaderView::section {
        background: #f8fafc; color: #374151;
        font-weight: 600; font-size: 12px;
        padding: 10px 8px; border: none;
        border-bottom: 2px solid #e2e8f0;
    }
    QTreeWidget::item { padding: 8px 4px; color: #1a1a1a; min-height: 22px; }
    QTreeWidget::item:hover { background: #f8fafc; }
    QTreeWidget::item:selected { background: #eff6ff; color: #1e293b; }
"""

# PDI / build status → (label, colour)
_PDI_STATUS_LABELS = {
    "manufacturing_done": ("Mfg Done",        "#92400e"),
    "pdi_pending":        ("PDI Pending",     "#1d4ed8"),
    "pdi_in_progress":    ("PDI In Progress", "#166534"),
    "pdi_done":           ("PDI Done ✓",      "#15803d"),
    "delivered":          ("Delivered",       "#7c3aed"),
}


class FinishedGoodsModelTab(QWidget):
    """Colour-wise finished-goods breakdown for one model, with expandable unit details."""

    def __init__(self, model_id: str, model_name: str, parent=None):
        super().__init__(parent)
        self.model_id   = model_id
        self.model_name = model_name
        self.workers    = []
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        title = QLabel(f"🛵  {self.model_name} — Finished Goods by Colour")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        lay.addWidget(title)

        hint = QLabel("Click the ▸ arrow on a colour to see individual scooter details.")
        hint.setStyleSheet("color:#64748b; font-size:12px;")
        lay.addWidget(hint)

        self.status = QLabel("Loading…")
        self.status.setStyleSheet("color:#94a3b8; font-size:12px;")
        lay.addWidget(self.status)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(
            ["Colour / Serial No.", "Model", "Colour", "PDI No.", "PDI Status", "Location"]
        )
        self.tree.setAlternatingRowColors(False)
        self.tree.setIndentation(20)
        self.tree.setRootIsDecorated(True)
        self.tree.setStyleSheet(_TREE_STYLE)
        hh = self.tree.header()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.tree, 1)

    def _load(self):
        w = ReportWorker(f"finished-goods/{self.model_id}")
        w.done.connect(self._populate)
        w.error.connect(lambda e: self.status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    def _populate(self, data):
        colors = data.get("colors", [])
        total  = data.get("total", 0)
        self.status.setText(
            f"{total} finished unit(s) across {len(colors)} colour(s)"
        )
        self.tree.clear()
        for c in colors:
            parent = QTreeWidgetItem([
                f"{c['color']}    ({c['count']} unit{'s' if c['count'] != 1 else ''})",
                "", "", "", "", ""
            ])
            pf = parent.font(0)
            pf.setBold(True)
            pf.setPointSize(pf.pointSize() + 1)
            parent.setFont(0, pf)
            # Shaded header band for the colour group
            for col in range(6):
                parent.setBackground(col, QColor("#eef2f7"))
            parent.setForeground(0, QColor("#0e7490"))
            self.tree.addTopLevelItem(parent)

            for i, u in enumerate(c["units"]):
                label, color = _PDI_STATUS_LABELS.get(
                    u["pdi_status"], (u["pdi_status"], "#374151")
                )
                child = QTreeWidgetItem([
                    u["serial_number"],
                    self.model_name,
                    u["color"],
                    u["pdi_number"],
                    label,
                    u["location"],
                ])
                # Centre the PDI no. / status columns; status bold + coloured
                child.setTextAlignment(3, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                child.setTextAlignment(4, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                sf = child.font(4)
                sf.setBold(True)
                child.setFont(4, sf)
                child.setForeground(4, QColor(color))
                child.setForeground(0, QColor("#475569"))
                if i % 2 == 1:
                    for col in range(6):
                        child.setBackground(col, QColor("#fafafa"))
                parent.addChild(child)
            parent.setExpanded(True)


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
        self._tab_inventory = self._build_inventory_tab()
        self._tab_finished  = self._build_finished_goods_tab()
        self._tab_production = self._build_production_tab()
        self._tab_dispatch  = self._build_dispatch_tab()
        self._tab_pdi       = self._build_pdi_tab()
        self.tabs.addTab(self._tab_inventory,  "📦  Inventory")
        self.tabs.addTab(self._tab_finished,   "🛵  Finished Goods")
        self.tabs.addTab(self._tab_production, "🏭  Production")
        self.tabs.addTab(self._tab_dispatch,   "🚚  Dispatch")
        self.tabs.addTab(self._tab_pdi,        "🔍  PDI & Damage")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, 1)

        self._run_inventory()

    # ── INVENTORY TAB ─────────────────────────────────────────

    def _build_inventory_tab(self):
        w, scroll = self._scrollable()
        lay = scroll

        btn = _run_btn(self._run_inventory, "#2563eb")
        self._inv_btn_lay = QHBoxLayout()
        self._inv_btn_lay.addWidget(btn)
        self._inv_btn_lay.addStretch()
        lay.addLayout(self._inv_btn_lay)

        self._inv_kpi = QWidget()
        lay.addWidget(self._inv_kpi)

        lay.addWidget(_section_title("🏭  Max Buildable Scooters (by BOM)"))
        self._build_status = _status_lbl()
        lay.addWidget(self._build_status)
        self._build_table = _make_table(
            ["Model", "Max Buildable", "Bottleneck Part", "Part Stock", "Needed / Unit"]
        )
        self._build_table.setMaximumHeight(240)
        lay.addWidget(self._build_table)

        lay.addWidget(_section_title("⚠  Low Stock Items"))
        self._inv_low_status = _status_lbl()
        lay.addWidget(self._inv_low_status)
        self._inv_low_table = _make_table(
            ["Item Name", "SKU", "Remaining", "Threshold"]
        )
        self._inv_low_table.setMaximumHeight(200)
        lay.addWidget(self._inv_low_table)
        lay.addStretch()
        return w

    def _run_inventory(self):
        self._build_status.setText("Loading…")
        self._inv_low_status.setText("Loading…")
        w = ReportWorker("inventory")
        w.done.connect(self._populate_inventory)
        w.error.connect(lambda e: self._build_status.setText(f"Error: {e}"))
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

        severity_colors = {"critical": "#dc2626", "warning": "#ea580c", "ok": "#16a34a", "none": "#94a3b8"}
        rows = data.get("buildable", [])
        self._build_table.setRowCount(len(rows))
        self._build_status.setText(f"{len(rows)} model(s)")
        for r, row in enumerate(rows):
            color = severity_colors.get(row["severity"], "#1a1a1a")
            self._build_table.setItem(r, 0, _cell(row["model_name"], bold=True))
            self._build_table.setItem(r, 1, _cell(row["max_buildable"],
                                                   Qt.AlignmentFlag.AlignCenter, color=color))
            self._build_table.setItem(r, 2, _cell(row["bottleneck_part"]))
            self._build_table.setItem(r, 3, _cell(row["stock"],
                                                   Qt.AlignmentFlag.AlignCenter, color=color))
            self._build_table.setItem(r, 4, _cell(row["needed_per_unit"],
                                                   Qt.AlignmentFlag.AlignCenter))

        low = data["low_stock_items"]
        self._inv_low_table.setRowCount(len(low))
        self._inv_low_status.setText(f"{len(low)} item(s) at or below threshold")
        for r, row in enumerate(low):
            self._inv_low_table.setItem(r, 0, _cell(row["item_name"], bold=True))
            self._inv_low_table.setItem(r, 1, _cell(row["sku"]))
            self._inv_low_table.setItem(r, 2, _cell(row["remaining"], Qt.AlignmentFlag.AlignCenter,
                                                     color="#dc2626"))
            self._inv_low_table.setItem(r, 3, _cell(row["threshold"], Qt.AlignmentFlag.AlignCenter))

    # ── FINISHED GOODS TAB ────────────────────────────────────

    def _build_finished_goods_tab(self):
        w, lay = self._scrollable()

        btn = _run_btn(self._run_finished_goods, "#0891b2")
        self._fg_btn_lay = QHBoxLayout()
        self._fg_btn_lay.addWidget(btn)
        self._fg_btn_lay.addStretch()
        lay.addLayout(self._fg_btn_lay)

        self._fg_kpi = QWidget()
        lay.addWidget(self._fg_kpi)

        lay.addWidget(_section_title("🛵  Finished Scooters in Inventory (by Model)"))
        hint = QLabel("Click a model's “View →” to see the colour-wise breakdown and unit details.")
        hint.setStyleSheet("color:#64748b; font-size:12px;")
        lay.addWidget(hint)

        self._fg_status = _status_lbl()
        lay.addWidget(self._fg_status)

        self._fg_table = _make_table(["Model", "Finished Units", "Details"], stretch_cols=[0])
        self._fg_table.horizontalHeader().setStretchLastSection(False)
        self._fg_table.setColumnWidth(1, 130)
        self._fg_table.setColumnWidth(2, 150)
        self._fg_table.verticalHeader().setDefaultSectionSize(44)
        lay.addWidget(self._fg_table, 1)
        return w

    def _run_finished_goods(self):
        self._fg_status.setText("Loading…")
        self._fg_table.setRowCount(0)
        w = ReportWorker("finished-goods")
        w.done.connect(self._populate_finished_goods)
        w.error.connect(lambda e: self._fg_status.setText(f"Error: {e}"))
        self.workers.append(w)
        w.start()

    def _populate_finished_goods(self, data):
        kpis = [("Total Finished Scooters", data.get("total", 0), "#0891b2")]
        old = self._fg_kpi
        new = _make_kpi_row(kpis)
        old.parentWidget().layout().replaceWidget(old, new)
        old.deleteLater()
        self._fg_kpi = new

        models = data.get("models", [])
        self._fg_table.setRowCount(len(models))
        self._fg_status.setText(f"{len(models)} model(s) with finished stock")
        for r, m in enumerate(models):
            self._fg_table.setItem(r, 0, _cell(m["model_name"], bold=True))
            self._fg_table.setItem(r, 1, _cell(m["count"], Qt.AlignmentFlag.AlignCenter,
                                               color="#0891b2"))
            btn = QPushButton("View  →")
            btn.setFixedSize(96, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background:#ecfeff; color:#0e7490; border:1px solid #a5f3fc;"
                " border-radius:6px; font-size:12px; font-weight:600; }"
                "QPushButton:hover { background:#cffafe; }"
            )
            btn.clicked.connect(lambda _, mm=m: self._open_fg_model_tab(mm))
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(6, 6, 6, 6)
            wl.addStretch()
            wl.addWidget(btn)
            wl.addStretch()
            self._fg_table.setCellWidget(r, 2, wrap)

    def _open_fg_model_tab(self, model):
        label = f"🛵  {model['model_name']}"
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).strip() == label.strip():
                self.tabs.setCurrentIndex(i)
                return
        tab = FinishedGoodsModelTab(model["model_id"], model["model_name"])
        idx = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(idx)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#6b7280; border:none; font-size:10px; }"
            "QPushButton:hover { color:#dc2626; }"
        )
        close_btn.clicked.connect(lambda _, t=tab: self._close_fg_tab(t))
        self.tabs.tabBar().setTabButton(
            idx, self.tabs.tabBar().ButtonPosition.RightSide, close_btn
        )

    def _close_fg_tab(self, widget):
        idx = self.tabs.indexOf(widget)
        if idx != -1:
            self.tabs.removeTab(idx)

    # ── PRODUCTION TAB ────────────────────────────────────────

    def _build_production_tab(self):
        w, lay = self._scrollable()

        filter_w, self._prod_from, self._prod_to = _date_filter()
        btn = _run_btn(self._run_production, "#7c3aed")
        self._prod_filter_lay = QHBoxLayout()
        self._prod_filter_lay.addWidget(filter_w)
        self._prod_filter_lay.addWidget(btn)
        lay.addLayout(self._prod_filter_lay)

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
        self._disp_filter_lay = QHBoxLayout()
        self._disp_filter_lay.addWidget(filter_w)
        self._disp_filter_lay.addWidget(btn)
        lay.addLayout(self._disp_filter_lay)

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
        self._pdi_filter_lay = QHBoxLayout()
        self._pdi_filter_lay.addWidget(filter_w)
        self._pdi_filter_lay.addWidget(btn)
        lay.addLayout(self._pdi_filter_lay)

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

    # ── TAB AUTO-REFRESH ──────────────────────────────────────

    def _on_tab_changed(self, index: int):
        # Match against the widget so dynamically-opened model tabs are ignored.
        w = self.tabs.widget(index)
        if w is self._tab_inventory:
            self._run_inventory()
        elif w is self._tab_finished:
            self._run_finished_goods()
        elif w is self._tab_production:
            self._run_production()
        elif w is self._tab_dispatch:
            self._run_dispatch()
        elif w is self._tab_pdi:
            self._run_pdi()

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
