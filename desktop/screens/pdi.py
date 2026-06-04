# desktop/screens/pdi.py
# ── G-Byke ERP — PDI Screen ───────────────────────────────────────────────────
# Matches the visual style of ManufacturingScreen and MasterDataScreen exactly.

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QDialog, QFormLayout, QLineEdit, QMessageBox,
    QAbstractItemView, QTabWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session


# ── SHARED HELPERS (match ManufacturingScreen exactly) ────────────────────────

def _stat_card(title: str, value: str, color: str) -> QFrame:
    card = QFrame()
    card.setFixedHeight(76)
    card.setStyleSheet(f"""
        QFrame {{
            background: white;
            border-radius: 8px;
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
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        gridline-color: #f3f4f6;
        background: white;
    }
    QHeaderView::section {
        background: #f8fafc;
        padding: 8px;
        border: none;
        border-bottom: 1px solid #e5e7eb;
        font-weight: 600;
        color: #374151;
    }
    QTableWidget::item          { padding: 6px 8px; color: #1a1a1a; }
    QTableWidget::item:alternate { background: #f9fafb; }
    QTableWidget::item:selected  { background: #eff6ff; color: #1a1a1a; }
"""

BTN_SUCCESS = """
    QPushButton {
        background: #16a34a; color: white; border: none;
        border-radius: 4px; font-size: 11px; padding: 0 10px;
    }
    QPushButton:hover { background: #15803d; }
"""
BTN_DANGER = """
    QPushButton {
        background: #dc2626; color: white; border: none;
        border-radius: 4px; font-size: 11px; padding: 0 10px;
    }
    QPushButton:hover { background: #b91c1c; }
"""
BTN_GHOST = (
    "border: 1px solid #ddd; border-radius: 6px; "
    "color: #666; font-size: 13px; background: white;"
)
INP_STYLE = (
    "border: 1px solid #ddd; border-radius: 4px; "
    "padding: 0 8px; color: #1a1a1a; background: white;"
)


# ── WORKERS ───────────────────────────────────────────────────────────────────

class PDIWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def run(self):
        try:
            data = APIClient.get("/pdi/pending")
            self.finished.emit(data if data else [])
        except APIError as e:
            self.error.emit(str(e))


class PDICompleteWorker(QThread):
    success = pyqtSignal()
    failure = pyqtSignal(str)

    def __init__(self, unit_id: str, payload: dict):
        super().__init__()
        self.unit_id = unit_id
        self.payload = payload

    def run(self):
        try:
            APIClient.post(f"/pdi/{self.unit_id}/complete", self.payload)
            self.success.emit()
        except APIError as e:
            self.failure.emit(e.message)


class PDIDeleteWorker(QThread):
    success = pyqtSignal()
    failure = pyqtSignal(str)

    def __init__(self, unit_id: str):
        super().__init__()
        self.unit_id = unit_id

    def run(self):
        try:
            APIClient.delete(f"/pdi/{self.unit_id}")
            self.success.emit()
        except APIError as e:
            self.failure.emit(e.message)


# ── PDI COMPLETE DIALOG ───────────────────────────────────────────────────────

class PDICompleteDialog(QDialog):
    def __init__(self, parent, unit: dict):
        super().__init__(parent)
        self.unit   = unit
        self.result = None
        self.setWindowTitle("Complete PDI Inspection")
        self.setFixedWidth(440)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_style = "font-size: 13px; font-weight: 500; color: #374151;"

        # Vehicle info banner
        model_name   = self.unit.get("model_name") or "Unknown Model"
        colour       = self.unit.get("color", "")
        power        = self.unit.get("power_spec", "")
        config_parts = [p for p in [colour, power] if p]
        config_str   = "  ·  ".join(config_parts) if config_parts else "—"

        banner = QFrame()
        banner.setStyleSheet(
            "background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px;"
        )
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(2)
        bt = QLabel(f"🛵  {model_name}")
        bt.setStyleSheet("font-size: 14px; font-weight: 600; color: #1e40af;")
        bs = QLabel(config_str)
        bs.setStyleSheet("font-size: 12px; color: #3b82f6;")
        bl.addWidget(bt)
        bl.addWidget(bs)
        layout.addWidget(banner)

        # Form fields
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)

        self.pdi_input     = QLineEdit()
        self.motor_input   = QLineEdit()
        self.chassis_input = QLineEdit()

        placeholders = [
            (self.pdi_input,     "e.g.  PDI-2024-0001"),
            (self.motor_input,   "e.g.  MTR-XXXXX"),
            (self.chassis_input, "e.g.  ME2XXXXXXXXXXXXX"),
        ]
        for inp, ph in placeholders:
            inp.setFixedHeight(36)
            inp.setStyleSheet(INP_STYLE)
            inp.setPlaceholderText(ph)

        form.addRow(QLabel("PDI Doc # *",        styleSheet=lbl_style), self.pdi_input)
        form.addRow(QLabel("Motor / Serial # *", styleSheet=lbl_style), self.motor_input)
        form.addRow(QLabel("Chassis # *",        styleSheet=lbl_style), self.chassis_input)
        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet(BTN_GHOST)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton("✅  Complete PDI")
        confirm_btn.setFixedHeight(38)
        confirm_btn.setDefault(True)
        confirm_btn.setStyleSheet(
            "background: #16a34a; color: white; border: none; "
            "border-radius: 6px; font-weight: 600; font-size: 13px;"
        )
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.clicked.connect(self._save)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def _save(self):
        pdi     = self.pdi_input.text().strip()
        motor   = self.motor_input.text().strip()
        chassis = self.chassis_input.text().strip()

        missing = []
        if not pdi:     missing.append("PDI Doc #")
        if not motor:   missing.append("Motor / Serial #")
        if not chassis: missing.append("Chassis #")

        if missing:
            QMessageBox.warning(
                self, "Missing Fields",
                "Please fill in:\n• " + "\n• ".join(missing)
            )
            return

        self.result = {
            "pdi_number":     pdi,
            "serial_number":  motor,
            "chassis_number": chassis,
        }
        self.accept()


# ── PDI UNITS TAB ─────────────────────────────────────────────────────────────

class PDIUnitsTab(QWidget):

    # signal so PDIScreen can update stat card
    units_loaded = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._units   = []
        self._workers = []
        self._has_span = False          # track whether span is currently active
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(12)

        # Top row: search + refresh
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "🔍  Search by model, colour, power spec or serial number…"
        )
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(
            "border: 1px solid #ddd; border-radius: 6px; "
            "padding: 0 10px; color: #1a1a1a; background: white; font-size: 13px;"
        )
        self._search.textChanged.connect(self._apply_filter)
        top_row.addWidget(self._search, 1)

        self._refresh_btn = QPushButton("⟳  Refresh")
        self._refresh_btn.setFixedHeight(36)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setStyleSheet(BTN_GHOST)
        self._refresh_btn.clicked.connect(self._load_data)
        top_row.addWidget(self._refresh_btn)
        layout.addLayout(top_row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Serial #", "Model", "Colour", "Battery / Power", "Status", "Actions"
        ])

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(5, 170)

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

    # ── Data ──────────────────────────────────────────────────

    def _load_data(self):
        self._refresh_btn.setEnabled(False)
        self._status_lbl.setText("Loading…")

        worker = PDIWorker()
        worker.finished.connect(self._on_loaded)
        worker.error.connect(self._on_error)
        self._workers.append(worker)
        worker.start()

    def _on_loaded(self, units: list):
        self._units = units
        self._populate_table(units)
        self._refresh_btn.setEnabled(True)
        n = len(units)
        self._status_lbl.setText(
            f"{n} vehicle(s) awaiting inspection" if n else "No vehicles awaiting PDI."
        )
        self.units_loaded.emit(n)

    def _on_error(self, msg: str):
        self._refresh_btn.setEnabled(True)
        self._status_lbl.setText(f"Error: {msg}")

    # ── Table ─────────────────────────────────────────────────

    def _populate_table(self, units: list):
        # Clear everything cleanly
        self._table.clearContents()
        self._table.setRowCount(0)

        if not units:
            # Show a single spanned empty-state row
            self._table.setRowCount(1)
            empty = QTableWidgetItem("No vehicles awaiting PDI inspection.")
            empty.setForeground(QColor("#94a3b8"))
            empty.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(0, 0, empty)
            self._table.setSpan(0, 0, 1, 6)   # span all 6 columns
            self._table.setRowHeight(0, 80)
            self._has_span = True
            return

        # If a span was previously set, clear it by resetting to 1×1 ONLY when needed
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

            self._table.setItem(row, 0, cell(u.get("serial_number", "—")))
            # model_name is now populated by the fixed backend
            self._table.setItem(row, 1, cell(u.get("model_name", "—")))
            self._table.setItem(
                row, 2,
                cell(u.get("color", "—"), Qt.AlignmentFlag.AlignCenter)
            )

            battery = u.get("battery_type", "")
            power   = u.get("power_spec", "")
            config  = " / ".join(filter(None, [battery, power])) or "—"
            self._table.setItem(
                row, 3,
                cell(config, Qt.AlignmentFlag.AlignCenter)
            )

            # Status badge
            status_item = QTableWidgetItem("Awaiting PDI")
            status_item.setForeground(QColor("#92400e"))
            status_item.setBackground(QColor("#fef3c7"))
            status_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 4, status_item)

            # Action buttons
            btn_widget = QWidget()
            btn_lay    = QHBoxLayout(btn_widget)
            btn_lay.setContentsMargins(4, 2, 4, 2)
            btn_lay.setSpacing(4)

            inspect_btn = QPushButton("✓  Inspect")
            inspect_btn.setFixedHeight(30)
            inspect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            inspect_btn.setStyleSheet(BTN_SUCCESS)
            inspect_btn.clicked.connect(lambda _, unit=u: self._process_pdi(unit))

            delete_btn = QPushButton("Delete")
            delete_btn.setFixedHeight(30)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setStyleSheet(BTN_DANGER)
            delete_btn.clicked.connect(lambda _, unit=u: self._delete_unit(unit))

            btn_lay.addWidget(inspect_btn)
            btn_lay.addWidget(delete_btn)
            self._table.setCellWidget(row, 5, btn_widget)

    def _apply_filter(self, text: str):
        query = text.strip().lower()
        for row in range(self._table.rowCount()):
            if not query:
                self._table.setRowHidden(row, False)
                continue
            match = False
            for col in range(self._table.columnCount() - 1):   # skip Actions
                item = self._table.item(row, col)
                if item and query in item.text().lower():
                    match = True
                    break
            self._table.setRowHidden(row, not match)

    # ── Actions ───────────────────────────────────────────────

    def _process_pdi(self, unit: dict):
        dlg = PDICompleteDialog(self, unit)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self._status_lbl.setText("Submitting…")
        self._refresh_btn.setEnabled(False)

        worker = PDICompleteWorker(unit["id"], dlg.result)
        worker.success.connect(lambda: self._on_pdi_success(unit))
        worker.failure.connect(self._on_pdi_failure)
        self._workers.append(worker)
        worker.start()

    def _on_pdi_success(self, unit: dict):
        model = unit.get("model_name") or "Vehicle"
        QMessageBox.information(
            self, "PDI Complete",
            f"✅  {model} marked as PDI Done.\n"
            "The unit is now ready for warehouse allocation."
        )
        self._load_data()

    def _on_pdi_failure(self, msg: str):
        self._refresh_btn.setEnabled(True)
        QMessageBox.critical(self, "Submission Failed", f"Could not complete PDI:\n{msg}")
        self._status_lbl.setText("Error — please try again.")

    def _delete_unit(self, unit: dict):
        model  = unit.get("model_name") or "this vehicle"
        serial = unit.get("serial_number", "?")
        reply  = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{model}'\nS/N: {serial}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        worker = PDIDeleteWorker(unit["id"])
        worker.success.connect(self._load_data)
        worker.failure.connect(
            lambda msg: QMessageBox.critical(self, "Delete Failed", msg)
        )
        self._workers.append(worker)
        worker.start()


# ── MAIN PDI SCREEN ───────────────────────────────────────────────────────────

class PDIScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Page header — identical pattern to ManufacturingScreen / MasterDataScreen
        title = QLabel("🛵  Pre-Delivery Inspection (PDI)")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #1e293b;")
        layout.addWidget(title)

        sub = QLabel("Inspect and certify scooters before they leave the factory.")
        sub.setStyleSheet("color: #64748b; font-size: 13px;")
        layout.addWidget(sub)

        # Stat cards — same _stat_card helper as ManufacturingScreen
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self.card_awaiting  = _stat_card("Awaiting PDI",       "—", "#f59e0b")
        self.card_done      = _stat_card("PDI Done (All Time)", "—", "#16a34a")
        self.card_delivered = _stat_card("Delivered",           "—", "#2563eb")
        for c in [self.card_awaiting, self.card_done, self.card_delivered]:
            cards_row.addWidget(c)
        layout.addLayout(cards_row)

        # Tab widget — same stylesheet as MasterDataScreen
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                background: white;
                padding: 16px;
            }
            QTabBar::tab {
                padding: 8px 20px;
                font-size: 13px;
                color: #64748b;
                border: none;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                color: #2563eb;
                font-weight: 600;
                border-bottom: 2px solid #2563eb;
            }
            QTabBar::tab:hover { color: #374151; }
        """)

        self._units_tab = PDIUnitsTab()
        self._units_tab.units_loaded.connect(
            lambda n: _update_card(self.card_awaiting, n)
        )
        tabs.addTab(self._units_tab, "⏳  Awaiting Inspection")
        layout.addWidget(tabs)