# desktop/screens/warehouses.py
# Warehouse & Godown Management Screen
# Matches the exact UI style of ManufacturingScreen / MasterDataScreen

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QDialog, QFormLayout, QLineEdit,
    QMessageBox, QAbstractItemView, QTabWidget,
    QComboBox, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session


# ── SHARED HELPERS (identical to other screens) ───────────────────────────────

def _stat_card(title: str, value: str, color: str) -> QFrame:
    card = QFrame()
    card.setFixedHeight(76)
    card.setStyleSheet(f"""
        QFrame {{
            background: white; border-radius: 8px;
            border-left:   4px solid {color};
            border-top:    1px solid #e5e7eb;
            border-right:  1px solid #e5e7eb;
            border-bottom: 1px solid #e5e7eb;
        }}
    """)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 8, 12, 8)
    val = QLabel(value)
    val.setFont(QFont("Arial", 18, QFont.Weight.Bold))
    val.setStyleSheet(f"color: {color}; border: none;")
    val.setObjectName("value")
    ttl = QLabel(title)
    ttl.setStyleSheet("color: #6b7280; font-size: 11px; border: none;")
    lay.addWidget(val)
    lay.addWidget(ttl)
    return card


def _update_card(card: QFrame, value):
    for child in card.findChildren(QLabel):
        if child.objectName() == "value":
            child.setText(str(value))
            break


TABLE_STYLE = """
    QTableWidget {
        border: 1px solid #e5e7eb; border-radius: 8px;
        gridline-color: #f3f4f6; background: white;
    }
    QHeaderView::section {
        background: #f8fafc; padding: 8px; border: none;
        border-bottom: 1px solid #e5e7eb;
        font-weight: 600; color: #374151;
    }
    QTableWidget::item          { padding: 6px 8px; color: #1a1a1a; }
    QTableWidget::item:alternate { background: #f9fafb; }
    QTableWidget::item:selected  { background: #eff6ff; color: #1a1a1a; }
"""

BTN_PRIMARY = """
    QPushButton {
        background: #2563eb; color: white; border: none;
        border-radius: 4px; font-size: 11px; padding: 0 10px;
    }
    QPushButton:hover { background: #1d4ed8; }
"""
BTN_SUCCESS = """
    QPushButton {
        background: #16a34a; color: white; border: none;
        border-radius: 4px; font-size: 11px; padding: 0 10px;
    }
    QPushButton:hover { background: #15803d; }
"""
BTN_GHOST = (
    "border: 1px solid #ddd; border-radius: 6px; "
    "color: #666; font-size: 13px; background: white;"
)
INP = (
    "border: 1px solid #ddd; border-radius: 4px; "
    "padding: 0 8px; color: #1a1a1a; background: white;"
)
LBL = "font-size: 13px; font-weight: 500; color: #374151;"

LOCATION_ICONS = {"factory": "🏭", "warehouse": "🏢", "godown": "📦"}
STATUS_LABELS  = {
    "manufacturing_pending": ("Mfg Pending",    "#f3f4f6", "#6b7280"),
    "manufacturing_done":    ("Mfg Done",       "#fef3c7", "#92400e"),
    "pdi_pending":           ("PDI Pending",    "#eff6ff", "#1d4ed8"),
    "pdi_in_progress":       ("PDI In Progress","#f0fdf4", "#166534"),
    "pdi_done":              ("PDI Done ✓",     "#dcfce7", "#15803d"),
    "delivered":             ("Delivered",      "#f3e8ff", "#7c3aed"),
}


# ── WORKERS ───────────────────────────────────────────────────────────────────

class LoadWarehousesWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.done.emit(APIClient.get("/warehouses/"))
        except APIError as e:
            self.error.emit(e.message)


class LoadUnitsWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, location_id: str):
        super().__init__()
        self.location_id = location_id

    def run(self):
        try:
            self.done.emit(
                APIClient.get(f"/warehouses/{self.location_id}/units")
            )
        except APIError as e:
            self.error.emit(e.message)


class TransferWorker(QThread):
    success = pyqtSignal(dict)
    failure = pyqtSignal(str)

    def __init__(self, payload: dict):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            self.success.emit(APIClient.post("/warehouses/transfer", self.payload))
        except APIError as e:
            self.failure.emit(e.message)


# ── TRANSFER DIALOG ───────────────────────────────────────────────────────────

class TransferDialog(QDialog):
    """Move a single scooter unit to a different location."""

    def __init__(self, parent, unit: dict, all_locations: list):
        super().__init__(parent)
        self.unit          = unit
        self.all_locations = all_locations
        self.result_data   = {}
        self.setWindowTitle("Transfer Scooter Unit")
        self.setFixedWidth(440)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Unit info banner
        banner = QFrame()
        banner.setStyleSheet(
            "background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px;"
        )
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(2)
        bt = QLabel(
            f"🛵  {self.unit.get('model_name') or 'Unknown Model'}"
        )
        bt.setStyleSheet("font-size: 14px; font-weight: 600; color: #1e40af;")
        bs = QLabel(
            f"S/N: {self.unit.get('serial_number', '—')}  ·  "
            f"{self.unit.get('color', '')}  ·  "
            f"{self.unit.get('power_spec', '')}"
        )
        bs.setStyleSheet("font-size: 12px; color: #3b82f6;")
        bl.addWidget(bt)
        bl.addWidget(bs)
        layout.addWidget(banner)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)

        self.dest_combo = QComboBox()
        self.dest_combo.setFixedHeight(36)
        self.dest_combo.setStyleSheet(INP)
        self.dest_combo.addItem("-- Select destination --", "")
        for loc in self.all_locations:
            if loc["id"] == self.unit.get("current_location_id"):
                continue  # skip current location
            icon = LOCATION_ICONS.get(loc.get("location_type", ""), "📍")
            label = f"{icon}  {loc['name']}"
            if loc.get("city"):
                label += f"  ({loc['city']})"
            self.dest_combo.addItem(label, loc["id"])
        form.addRow(
            QLabel("Move To *", styleSheet=LBL),
            self.dest_combo
        )

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)
        self.notes_input.setPlaceholderText("Optional reason for transfer...")
        self.notes_input.setStyleSheet(
            "color:#1a1a1a; background:white; border:1px solid #ddd; border-radius:4px;"
        )
        form.addRow(QLabel("Notes", styleSheet=LBL), self.notes_input)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet(BTN_GHOST)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton("Transfer Unit")
        confirm_btn.setFixedHeight(38)
        confirm_btn.setDefault(True)
        confirm_btn.setStyleSheet(
            "background: #2563eb; color: white; border: none; "
            "border-radius: 6px; font-weight: 600; font-size: 13px;"
        )
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.clicked.connect(self._save)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def _save(self):
        dest_id = self.dest_combo.currentData()
        if not dest_id:
            QMessageBox.warning(self, "Missing", "Please select a destination location.")
            return
        self.result_data = {
            "unit_id":        self.unit["id"],
            "to_location_id": dest_id,
            "notes":          self.notes_input.toPlainText().strip() or None,
        }
        self.accept()


# ── UNITS TAB — scooters at a specific warehouse ──────────────────────────────

class UnitsTab(QWidget):
    """Shows all scooter units at one location, with transfer action."""

    def __init__(self, location: dict, all_locations: list, parent=None):
        super().__init__(parent)
        self.location      = location
        self.all_locations = all_locations
        self._units        = []
        self._workers      = []
        self._has_span     = False
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        # Top row
        top = QHBoxLayout()
        top.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "🔍  Search by model, serial, colour or status…"
        )
        self._search.setFixedHeight(34)
        self._search.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; "
            "padding:0 10px; color:#1a1a1a; background:white; font-size:13px;"
        )
        self._search.textChanged.connect(self._apply_filter)
        top.addWidget(self._search, 1)

        self._status_filter = QComboBox()
        self._status_filter.setFixedHeight(34)
        self._status_filter.setFixedWidth(160)
        self._status_filter.setStyleSheet(INP)
        self._status_filter.addItem("All Statuses", "")
        for val, (label, _, _) in STATUS_LABELS.items():
            self._status_filter.addItem(label, val)
        self._status_filter.currentIndexChanged.connect(self._load_data)
        top.addWidget(self._status_filter)

        refresh_btn = QPushButton("⟳  Refresh")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setStyleSheet(BTN_GHOST)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._load_data)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Serial #", "Model", "Colour", "Battery / Power",
            "PDI #", "Status", "Actions"
        ])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(6, 120)
        self._table.verticalHeader().setDefaultSectionSize(42)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(TABLE_STYLE)
        layout.addWidget(self._table)

        self._status_lbl = QLabel("Loading…")
        self._status_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self._status_lbl)

    def _load_data(self):
        status_val = self._status_filter.currentData() if hasattr(self, '_status_filter') else ""
        endpoint = f"/warehouses/{self.location['id']}/units"
        if status_val:
            endpoint += f"?status={status_val}"

        worker = LoadUnitsWorker(self.location["id"])
        worker.done.connect(self._on_loaded)
        worker.error.connect(
            lambda e: self._status_lbl.setText(f"Error: {e}")
        )
        self._workers.append(worker)
        worker.start()

    def _on_loaded(self, units: list):
        self._units = units
        self._populate_table(units)
        self._status_lbl.setText(f"{len(units)} unit(s) at this location")

    def _populate_table(self, units: list):
        self._table.clearContents()
        self._table.setRowCount(0)

        if not units:
            self._table.setRowCount(1)
            empty = QTableWidgetItem("No scooters at this location.")
            empty.setForeground(QColor("#94a3b8"))
            empty.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(0, 0, empty)
            self._table.setSpan(0, 0, 1, 7)
            self._table.setRowHeight(0, 80)
            self._has_span = True
            return

        if self._has_span:
            self._table.setSpan(0, 0, 1, 1)
            self._has_span = False

        for row, u in enumerate(units):
            self._table.insertRow(row)

            def cell(text, align=Qt.AlignmentFlag.AlignLeft):
                it = QTableWidgetItem(str(text) if text else "—")
                it.setForeground(QColor("#1a1a1a"))
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return it

            ctr = Qt.AlignmentFlag.AlignCenter

            self._table.setItem(row, 0, cell(u.get("serial_number", "—")))
            self._table.setItem(row, 1, cell(u.get("model_name", "—")))
            self._table.setItem(row, 2, cell(u.get("color", "—"), ctr))

            battery = u.get("battery_type", "")
            power   = u.get("power_spec", "")
            config  = " / ".join(filter(None, [battery, power])) or "—"
            self._table.setItem(row, 3, cell(config, ctr))
            self._table.setItem(row, 4, cell(u.get("pdi_number", "—"), ctr))

            # Status badge
            status_val = u.get("status", "")
            label, bg, fg = STATUS_LABELS.get(
                status_val, (status_val, "#f3f4f6", "#6b7280")
            )
            status_item = QTableWidgetItem(label)
            status_item.setForeground(QColor(fg))
            status_item.setBackground(QColor(bg))
            status_item.setTextAlignment(ctr | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 5, status_item)

            # Transfer button (managers only)
            btn_w = QWidget()
            btn_l = QHBoxLayout(btn_w)
            btn_l.setContentsMargins(4, 2, 4, 2)
            btn_l.setSpacing(4)

            if Session.role in ["superadmin", "manager"]:
                transfer_btn = QPushButton("⇄  Transfer")
                transfer_btn.setFixedHeight(30)
                transfer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                transfer_btn.setStyleSheet(BTN_PRIMARY)
                transfer_btn.clicked.connect(
                    lambda _, unit=u: self._transfer_unit(unit)
                )
                btn_l.addWidget(transfer_btn)

            self._table.setCellWidget(row, 6, btn_w)

    def _apply_filter(self, text: str):
        query = text.strip().lower()
        for row in range(self._table.rowCount()):
            match = not query
            if query:
                for col in range(self._table.columnCount() - 1):
                    item = self._table.item(row, col)
                    if item and query in item.text().lower():
                        match = True
                        break
            self._table.setRowHidden(row, not match)

    def _transfer_unit(self, unit: dict):
        dlg = TransferDialog(self, unit, self.all_locations)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self._status_lbl.setText("Transferring…")

        worker = TransferWorker(dlg.result_data)
        worker.success.connect(self._on_transfer_success)
        worker.failure.connect(
            lambda msg: QMessageBox.critical(self, "Transfer Failed", msg)
        )
        self._workers.append(worker)
        worker.start()

    def _on_transfer_success(self, result: dict):
        QMessageBox.information(
            self, "Transferred",
            f"✅  Unit transferred.\n"
            f"From : {result.get('from', '')}\n"
            f"To   : {result.get('to', '')}"
        )
        self._load_data()


# ── OVERVIEW TAB — all warehouses in one table ────────────────────────────────

class OverviewTab(QWidget):
    """Shows every location with its scooter counts. Click 'View' to drill down."""

    location_selected = pyqtSignal(dict)  # emits location dict when View is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self._locations = []
        self._workers   = []
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.addStretch()
        refresh_btn = QPushButton("⟳  Refresh")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setStyleSheet(BTN_GHOST)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._load_data)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Location", "Type", "City", "State",
            "Total Units", "PDI Done", "Actions"
        ])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 100)
        self._table.setColumnWidth(2, 110)
        self._table.setColumnWidth(3, 110)
        self._table.setColumnWidth(4, 90)
        self._table.setColumnWidth(5, 90)
        self._table.setColumnWidth(6, 100)
        self._table.verticalHeader().setDefaultSectionSize(42)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(TABLE_STYLE)
        layout.addWidget(self._table)

        self._status_lbl = QLabel("Loading…")
        self._status_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self._status_lbl)

    def _load_data(self):
        self._status_lbl.setText("Loading…")
        worker = LoadWarehousesWorker()
        worker.done.connect(self._on_loaded)
        worker.error.connect(
            lambda e: self._status_lbl.setText(f"Error: {e}")
        )
        self._workers.append(worker)
        worker.start()

    def _on_loaded(self, locations: list):
        self._locations = locations
        self._populate_table(locations)
        total_units = sum(loc.get("total_units", 0) for loc in locations)
        self._status_lbl.setText(
            f"{len(locations)} location(s)  ·  {total_units} total units"
        )

    def _populate_table(self, locations: list):
        self._table.setRowCount(len(locations))

        for row, loc in enumerate(locations):
            def cell(text, align=Qt.AlignmentFlag.AlignLeft):
                it = QTableWidgetItem(str(text) if text else "—")
                it.setForeground(QColor("#1a1a1a"))
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return it

            ctr = Qt.AlignmentFlag.AlignCenter

            icon = LOCATION_ICONS.get(loc.get("location_type", ""), "📍")
            self._table.setItem(row, 0, cell(f"{icon}  {loc['name']}"))

            loc_type = loc.get("location_type", "").capitalize()
            type_item = QTableWidgetItem(loc_type)
            type_item.setTextAlignment(ctr | Qt.AlignmentFlag.AlignVCenter)
            type_colors = {
                "Factory":   ("#eff6ff", "#1d4ed8"),
                "Warehouse": ("#f0fdf4", "#166534"),
                "Godown":    ("#fff7ed", "#c2410c"),
            }
            bg, fg = type_colors.get(loc_type, ("#f3f4f6", "#374151"))
            type_item.setBackground(QColor(bg))
            type_item.setForeground(QColor(fg))
            self._table.setItem(row, 1, type_item)

            self._table.setItem(row, 2, cell(loc.get("city", "—")))
            self._table.setItem(row, 3, cell(loc.get("state", "—")))

            total    = loc.get("total_units", 0)
            pdi_done = loc.get("pdi_done", 0)

            total_item = QTableWidgetItem(str(total))
            total_item.setTextAlignment(ctr | Qt.AlignmentFlag.AlignVCenter)
            total_item.setForeground(
                QColor("#2563eb") if total > 0 else QColor("#94a3b8")
            )
            self._table.setItem(row, 4, total_item)

            pdi_item = QTableWidgetItem(str(pdi_done))
            pdi_item.setTextAlignment(ctr | Qt.AlignmentFlag.AlignVCenter)
            pdi_item.setForeground(
                QColor("#16a34a") if pdi_done > 0 else QColor("#94a3b8")
            )
            self._table.setItem(row, 5, pdi_item)

            # View button
            btn_w = QWidget()
            btn_l = QHBoxLayout(btn_w)
            btn_l.setContentsMargins(4, 2, 4, 2)

            view_btn = QPushButton("View →")
            view_btn.setFixedHeight(30)
            view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            view_btn.setStyleSheet(BTN_PRIMARY)
            view_btn.clicked.connect(
                lambda _, l=loc: self.location_selected.emit(l)
            )
            btn_l.addWidget(view_btn)
            self._table.setCellWidget(row, 6, btn_w)

    def get_all_locations(self) -> list:
        return self._locations


# ── MAIN WAREHOUSES SCREEN ────────────────────────────────────────────────────

class WarehousesScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers      = []
        self._all_locations = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Page header
        title = QLabel("🏢  Warehouse & Godown Management")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #1e293b;")
        layout.addWidget(title)

        sub = QLabel(
            "Track finished scooter inventory across all factory locations, "
            "warehouses, and godowns. Transfer units between locations."
        )
        sub.setStyleSheet("color: #64748b; font-size: 13px;")
        layout.addWidget(sub)

        # Stat cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self.card_locations = _stat_card("Total Locations",   "—", "#2563eb")
        self.card_units     = _stat_card("Total Units",       "—", "#0891b2")
        self.card_pdi_done  = _stat_card("PDI Done",          "—", "#16a34a")
        self.card_delivered = _stat_card("Delivered",         "—", "#7c3aed")
        for c in [self.card_locations, self.card_units,
                  self.card_pdi_done, self.card_delivered]:
            cards_row.addWidget(c)
        layout.addLayout(cards_row)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e5e7eb; border-radius: 8px;
                background: white; padding: 16px;
            }
            QTabBar::tab {
                padding: 8px 20px; font-size: 13px; color: #64748b;
                border: none; margin-right: 4px;
            }
            QTabBar::tab:selected {
                color: #2563eb; font-weight: 600;
                border-bottom: 2px solid #2563eb;
            }
            QTabBar::tab:hover { color: #374151; }
        """)

        # Overview tab — always present
        self._overview_tab = OverviewTab()
        self._overview_tab.location_selected.connect(self._open_location_tab)
        self._tabs.addTab(self._overview_tab, "🗺️  All Locations")

        layout.addWidget(self._tabs)

        # Load summary counts
        self._load_summary()

    def _load_summary(self):
        class SummaryWorker(QThread):
            done = pyqtSignal(list)
            def run(self):
                try:
                    self.done.emit(APIClient.get("/warehouses/"))
                except APIError:
                    self.done.emit([])

        sw = SummaryWorker()
        sw.done.connect(self._on_summary)
        self._workers.append(sw)
        sw.start()

    def _on_summary(self, locations: list):
        self._all_locations = locations
        n_loc      = len(locations)
        n_units    = sum(loc.get("total_units", 0) for loc in locations)
        n_pdi_done = sum(loc.get("pdi_done", 0)    for loc in locations)
        n_delivered = sum(loc.get("delivered", 0)  for loc in locations)

        _update_card(self.card_locations, n_loc)
        _update_card(self.card_units,     n_units)
        _update_card(self.card_pdi_done,  n_pdi_done)
        _update_card(self.card_delivered, n_delivered)

    def _open_location_tab(self, location: dict):
        """Open a drill-down tab for a specific location when View → is clicked."""
        loc_name = location["name"]

        # Don't open duplicate tabs
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i).endswith(loc_name):
                self._tabs.setCurrentIndex(i)
                return

        icon = LOCATION_ICONS.get(location.get("location_type", ""), "📍")
        tab  = UnitsTab(location, self._all_locations)
        idx  = self._tabs.addTab(tab, f"{icon}  {loc_name}")

        # Add a close button to the tab
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#94a3b8; border:none; font-size:11px; }"
            "QPushButton:hover { color:#ef4444; }"
        )
        close_btn.clicked.connect(lambda: self._close_tab(idx))
        self._tabs.tabBar().setTabButton(
            idx, self._tabs.tabBar().ButtonPosition.RightSide, close_btn
        )

        self._tabs.setCurrentIndex(idx)

    def _close_tab(self, idx: int):
        if idx > 0:  # never close the Overview tab
            self._tabs.removeTab(idx)