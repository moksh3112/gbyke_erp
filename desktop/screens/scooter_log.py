from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QDialog, QFormLayout,
    QMessageBox, QHeaderView, QFrame,
    QAbstractItemView, QSpinBox, QDateEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QColor
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session


# ── WORKERS ───────────────────────────────────────────────────

class LoadUnitsWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.done.emit(APIClient.get("/manufacturing/logged-units"))
        except APIError as e:
            self.error.emit(e.message)


# ── STATUS BADGES ─────────────────────────────────────────────

_STATUS_LABELS = {
    "manufacturing_done": ("Awaiting PDI", "#92400e"),
    "pdi_pending":        ("PDI Pending",  "#1d4ed8"),
    "pdi_in_progress":    ("PDI In Prog.", "#166534"),
    "pdi_done":           ("PDI Done ✓",   "#15803d"),
    "delivered":          ("Delivered",    "#7c3aed"),
}

_TABLE_STYLE = """
    QTableWidget { border:1px solid #e5e7eb; border-radius:8px; gridline-color:#f3f4f6; }
    QHeaderView::section {
        background:#f8fafc; padding:8px; border:none;
        border-bottom:1px solid #e5e7eb; font-weight:600; color:#374151;
    }
    QTableWidget::item { padding:6px 8px; color:#1a1a1a; }
    QTableWidget::item:alternate { background:#f9fafb; }
    QTableWidget::item:selected { background:#eff6ff; color:#1a1a1a; }
"""


# ── LOG SCOOTERS DIALOG ───────────────────────────────────────

class LogScootersDialog(QDialog):
    def __init__(self, parent, models, colors, batteries, locations):
        super().__init__(parent)
        self._models    = models
        self._colors    = colors
        self._batteries = batteries
        self._locations = locations
        self.result_data = {}
        self.setWindowTitle("Log Manufactured Scooters")
        self.setFixedWidth(480)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("🏭  Log Existing Scooters")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        layout.addWidget(title)

        sub = QLabel("Add already-manufactured scooters into inventory in bulk.")
        sub.setStyleSheet("color:#6b7280; font-size:12px;")
        layout.addWidget(sub)

        lbl = "font-size:13px; font-weight:500; color:#374151;"
        inp = "border:1px solid #ddd; border-radius:4px; padding:0 8px; color:#1a1a1a; background:white;"
        spin = "color:#1a1a1a; background:white; border:1px solid #ddd; border-radius:4px; padding:0 8px;"

        form = QFormLayout()
        form.setSpacing(11)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)

        # Model
        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(36)
        self.model_combo.setStyleSheet(inp)
        self.model_combo.addItem("-- Select Model --", "")
        for m in self._models:
            self.model_combo.addItem(m["model_name"], m["id"])
        ml = QLabel("Scooter Model *"); ml.setStyleSheet(lbl)
        form.addRow(ml, self.model_combo)

        # Colour (optional)
        self.colour_combo = QComboBox()
        self.colour_combo.setFixedHeight(36)
        self.colour_combo.setStyleSheet(inp)
        self.colour_combo.addItem("— No colour —", "")
        for c in self._colors:
            self.colour_combo.addItem(c, c)
        cl = QLabel("Colour"); cl.setStyleSheet(lbl)
        form.addRow(cl, self.colour_combo)

        # Battery (optional)
        self.battery_combo = QComboBox()
        self.battery_combo.setFixedHeight(36)
        self.battery_combo.setStyleSheet(inp)
        self.battery_combo.addItem("— None —", None)
        for b in self._batteries:
            btype = b.get("battery_type", "")
            spec  = b.get("power_spec", "")
            label = f"{btype}  {spec}".strip()
            self.battery_combo.addItem(label, {"battery_type": btype, "power_spec": spec})
        bl = QLabel("Battery / Power"); bl.setStyleSheet(lbl)
        form.addRow(bl, self.battery_combo)

        # Location
        self.location_combo = QComboBox()
        self.location_combo.setFixedHeight(36)
        self.location_combo.setStyleSheet(inp)
        self.location_combo.addItem("-- Select Location --", "")
        for loc in self._locations:
            icon = {"factory": "🏭", "warehouse": "🏢", "godown": "📦"}.get(
                loc.get("location_type", ""), "📍"
            )
            self.location_combo.addItem(f"{icon}  {loc['name']}", loc["id"])
        ll = QLabel("Location *"); ll.setStyleSheet(lbl)
        form.addRow(ll, self.location_combo)

        # Quantity
        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(10000)
        self.qty_spin.setValue(1)
        self.qty_spin.setStyleSheet(spin)
        ql = QLabel("Quantity *"); ql.setStyleSheet(lbl)
        form.addRow(ql, self.qty_spin)

        # Status
        self.status_combo = QComboBox()
        self.status_combo.setFixedHeight(36)
        self.status_combo.setStyleSheet(inp)
        self.status_combo.addItem("Awaiting PDI (needs inspection)", "manufacturing_done")
        self.status_combo.addItem("PDI Done (already inspected)",    "pdi_done")
        sl = QLabel("Status *"); sl.setStyleSheet(lbl)
        form.addRow(sl, self.status_combo)

        # Manufactured date
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        self.date_input.setFixedHeight(36)
        self.date_input.setStyleSheet(inp)
        dl = QLabel("Manufactured On"); dl.setStyleSheet(lbl)
        form.addRow(dl, self.date_input)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet("border:1px solid #ddd; border-radius:6px; color:#666;")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("✅  Log Scooters")
        save_btn.setFixedHeight(38)
        save_btn.setDefault(True)
        save_btn.setStyleSheet(
            "background:#16a34a; color:white; border:none; border-radius:6px; font-weight:600;"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _save(self):
        model_id = self.model_combo.currentData()
        if not model_id:
            QMessageBox.warning(self, "Missing", "Please select a scooter model.")
            return
        if not self.location_combo.currentData():
            QMessageBox.warning(self, "Missing", "Please select a location.")
            return

        bat = self.battery_combo.currentData()
        self.result_data = {
            "model_id":          model_id,
            "color":             self.colour_combo.currentData() or None,
            "battery_type":      bat.get("battery_type") if isinstance(bat, dict) else None,
            "power_spec":        bat.get("power_spec")   if isinstance(bat, dict) else None,
            "location_id":       self.location_combo.currentData(),
            "quantity":          self.qty_spin.value(),
            "status":            self.status_combo.currentData(),
            "manufactured_date": self.date_input.date().toString("yyyy-MM-dd"),
        }
        self.accept()


# ── MAIN SCREEN ───────────────────────────────────────────────

class ScooterLogScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers   = []
        self._units    = []
        self._models   = []
        self._colors   = []
        self._batteries = []
        self._locations = []
        self.setStyleSheet("background:#f8fafc;")
        self._build_ui()
        self._load_master_data()
        self._load_units()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("📝  Manufactured Scooter Log")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        hdr.addWidget(title)
        hdr.addStretch()

        if Session.role in ["superadmin", "manager"]:
            self.add_btn = QPushButton("＋ Log Scooters")
            self.add_btn.setFixedHeight(36)
            self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.add_btn.setStyleSheet("""
                QPushButton {
                    background:#16a34a; color:white; border:none;
                    border-radius:6px; padding:0 16px; font-weight:600;
                }
                QPushButton:hover { background:#15803d; }
            """)
            self.add_btn.clicked.connect(self._log_scooters)
            hdr.addWidget(self.add_btn)
        layout.addLayout(hdr)

        sub = QLabel("Log scooters that were already manufactured (existing stock) directly into inventory.")
        sub.setStyleSheet("color:#64748b; font-size:13px;")
        layout.addWidget(sub)

        # Stat cards
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.card_total    = self._stat_card("Logged Scooters",  "—", "#2563eb")
        self.card_awaiting = self._stat_card("Awaiting PDI",     "—", "#f59e0b")
        self.card_done     = self._stat_card("PDI Done",         "—", "#16a34a")
        for c in [self.card_total, self.card_awaiting, self.card_done]:
            cards.addWidget(c)
        layout.addLayout(cards)

        # Search
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search serial, model, colour or status…")
        self.search_input.setFixedHeight(34)
        self.search_input.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 10px; color:#1a1a1a; background:white;"
        )
        self.search_input.textChanged.connect(self._filter)
        search_row.addWidget(self.search_input, 1)

        refresh_btn = QPushButton("⟳  Refresh")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 12px; color:#666; background:white;"
        )
        refresh_btn.clicked.connect(self._load_units)
        search_row.addWidget(refresh_btn)
        layout.addLayout(search_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Serial No.", "Model", "Colour", "Battery / Power",
            "Status", "Location", "Mfg Date", "Actions"
        ])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setStretchLastSection(False)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 100)
        self.table.setColumnWidth(7, 90)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(_TABLE_STYLE)
        layout.addWidget(self.table, 1)

        self.status_lbl = QLabel("Loading…")
        self.status_lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
        layout.addWidget(self.status_lbl)

    # ── Helpers ───────────────────────────────────────────────

    def _stat_card(self, title, value, color):
        card = QFrame()
        card.setFixedHeight(76)
        card.setStyleSheet(f"""
            QFrame {{
                background:white; border-radius:8px;
                border-left:4px solid {color};
                border-top:1px solid #e5e7eb;
                border-right:1px solid #e5e7eb;
                border-bottom:1px solid #e5e7eb;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        val = QLabel(value)
        val.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        val.setStyleSheet(f"color:{color}; border:none;")
        val.setObjectName("value")
        ttl = QLabel(title)
        ttl.setStyleSheet("color:#6b7280; font-size:11px; border:none;")
        lay.addWidget(val)
        lay.addWidget(ttl)
        return card

    def _update_card(self, card, value):
        for child in card.findChildren(QLabel):
            if child.objectName() == "value":
                child.setText(str(value))
                break

    # ── Data loading ──────────────────────────────────────────

    def _load_master_data(self):
        try:
            self._models = APIClient.get("/master/models")
        except APIError:
            self._models = []
        try:
            self._colors = [c.get("name", "") for c in APIClient.get("/master/colors")]
        except APIError:
            self._colors = []
        try:
            self._batteries = APIClient.get("/master/batteries")
        except APIError:
            self._batteries = []
        try:
            self._locations = APIClient.get("/master/locations")
        except APIError:
            self._locations = []

    def _load_units(self):
        self.status_lbl.setText("Loading…")
        self.table.setRowCount(0)
        worker = LoadUnitsWorker()
        worker.done.connect(self._populate)
        worker.error.connect(lambda e: self.status_lbl.setText(f"Error: {e}"))
        self.workers.append(worker)
        worker.start()

    def _populate(self, units):
        self._units = units
        # Update cards
        total    = len(units)
        awaiting = sum(1 for u in units if u.get("status") == "manufacturing_done")
        done     = sum(1 for u in units if u.get("status") == "pdi_done")
        self._update_card(self.card_total,    total)
        self._update_card(self.card_awaiting, awaiting)
        self._update_card(self.card_done,     done)
        self._render(units)

    def _filter(self, text):
        q = text.strip().lower()
        filtered = [
            u for u in self._units
            if not q
            or q in u.get("serial_number", "").lower()
            or q in (u.get("model_name") or "").lower()
            or q in (u.get("color") or "").lower()
            or q in (u.get("status") or "").lower()
        ]
        self._render(filtered)

    def _render(self, units):
        self.table.setRowCount(len(units))

        def cell(text, align=Qt.AlignmentFlag.AlignLeft):
            c = QTableWidgetItem(str(text) if text else "—")
            c.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            return c

        for row, u in enumerate(units):
            self.table.setItem(row, 0, cell(u.get("serial_number", "")))
            self.table.setItem(row, 1, cell(u.get("model_name", "")))
            self.table.setItem(row, 2, cell(u.get("color", ""), Qt.AlignmentFlag.AlignCenter))

            bat = u.get("battery_type", "—")
            spec = u.get("power_spec", "")
            config = " / ".join(x for x in [bat, spec] if x and x != "—") or "—"
            self.table.setItem(row, 3, cell(config, Qt.AlignmentFlag.AlignCenter))

            label, color = _STATUS_LABELS.get(
                u.get("status", ""), (u.get("status", "—"), "#374151")
            )
            st = QTableWidgetItem(label)
            st.setForeground(QColor(color))
            st.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 4, st)

            self.table.setItem(row, 5, cell(u.get("location", ""), Qt.AlignmentFlag.AlignCenter))
            self.table.setItem(row, 6, cell(u.get("manufactured_date", ""), Qt.AlignmentFlag.AlignCenter))

            if Session.role in ["superadmin", "manager"]:
                del_btn = QPushButton("🗑")
                del_btn.setFixedSize(36, 28)
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.setStyleSheet(
                    "QPushButton { background:#fee2e2; color:#dc2626; border:1px solid #fecaca;"
                    " border-radius:4px; font-size:12px; }"
                    "QPushButton:hover { background:#fecaca; }"
                )
                del_btn.clicked.connect(lambda _, unit=u: self._delete_unit(unit))
                wrap = QWidget()
                wl = QHBoxLayout(wrap)
                wl.setContentsMargins(4, 4, 4, 4)
                wl.addStretch()
                wl.addWidget(del_btn)
                wl.addStretch()
                self.table.setCellWidget(row, 7, wrap)

        total = len(self._units)
        shown = len(units)
        if shown == total:
            self.status_lbl.setText(f"{total} logged unit(s)")
        else:
            self.status_lbl.setText(f"{shown} of {total} units")

    # ── Actions ───────────────────────────────────────────────

    def _log_scooters(self):
        if not self._models:
            QMessageBox.warning(self, "No Models", "No scooter models found. Add a model in Master Data first.")
            return
        dlg = LogScootersDialog(self, self._models, self._colors, self._batteries, self._locations)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                result = APIClient.post("/manufacturing/log-existing", dlg.result_data)
                QMessageBox.information(
                    self, "Logged",
                    f"{result.get('count', 0)} scooter(s) logged into inventory."
                )
                self._load_units()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _delete_unit(self, unit):
        reply = QMessageBox.question(
            self, "Delete Unit",
            f"Delete scooter '{unit.get('serial_number', '')}'?\n\n"
            "⚠️ This permanently removes the unit. Use only to fix a logging mistake.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.delete(f"/pdi/{unit['id']}")
                self._load_units()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)
