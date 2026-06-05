from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QDialog, QFormLayout,
    QMessageBox, QHeaderView, QFrame,
    QTextEdit, QAbstractItemView, QTabWidget,
    QSpinBox, QDateEdit, QMenu, QSizePolicy,
    QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate, QPoint, QTimer
from PyQt6.QtGui import QFont, QColor, QAction
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session


# ── WORKERS ───────────────────────────────────────────────────

class LoadShipmentsWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, dealer_id="", from_date="", to_date=""):
        super().__init__()
        self.dealer_id = dealer_id
        self.from_date = from_date
        self.to_date   = to_date

    def run(self):
        try:
            params = []
            if self.dealer_id:
                params.append(f"dealer_id={self.dealer_id}")
            if self.from_date:
                params.append(f"from_date={self.from_date}")
            if self.to_date:
                params.append(f"to_date={self.to_date}")
            qs = "?" + "&".join(params) if params else ""
            self.done.emit(APIClient.get(f"/shipments/{qs}"))
        except APIError as e:
            self.error.emit(e.message)


class LoadShipmentDetailWorker(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, note_id):
        super().__init__()
        self.note_id = note_id

    def run(self):
        try:
            self.done.emit(APIClient.get(f"/shipments/{self.note_id}"))
        except APIError as e:
            self.error.emit(e.message)


class LoadSummaryWorker(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            self.done.emit(APIClient.get("/shipments/summary"))
        except APIError as e:
            self.error.emit(e.message)


class LoadDealersWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.done.emit(APIClient.get("/dealers/?active_only=true"))
        except APIError as e:
            self.error.emit(e.message)


class VerifyPDIWorker(QThread):
    done  = pyqtSignal(str, dict)   # pdi_number, unit data
    error = pyqtSignal(str, str)    # pdi_number, error msg

    def __init__(self, pdi_number):
        super().__init__()
        self.pdi_number = pdi_number

    def run(self):
        try:
            units = APIClient.get(f"/pdi/units?pdi_number={self.pdi_number}")
            if units:
                self.done.emit(self.pdi_number, units[0])
            else:
                self.error.emit(self.pdi_number, "PDI number not found.")
        except APIError as e:
            self.error.emit(self.pdi_number, e.message)


# ── CREATE DISPATCH DIALOG ────────────────────────────────────

class CreateDispatchDialog(QDialog):
    def __init__(self, parent, dealers):
        super().__init__(parent)
        self.dealers       = dealers
        self.result_data   = {}
        self.workers       = []
        self._models       = []    # [{id, model_name, model_code}]
        self._batteries    = []    # [{id, name}]
        self._scooter_rows = []
        self._part_rows    = []    # structured part rows
        self._battery_rows = []    # battery rows
        self.setWindowTitle("New Dispatch")
        self.setFixedWidth(780)
        self.setMinimumHeight(580)
        self.setModal(True)
        self._load_master_data()
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setSpacing(12)
        outer.setContentsMargins(20, 20, 20, 20)

        # ── Scroll area so content never clips
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout  = QVBoxLayout(content)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 0, 8, 0)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        inp = "border:1px solid #ddd; border-radius:4px; padding:0 8px; color:#1a1a1a; background:white;"
        lbl = "font-size:13px; font-weight:500; color:#374151;"

        # Header info
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(16)

        self.dealer_combo = QComboBox()
        self.dealer_combo.setFixedHeight(36)
        self.dealer_combo.setStyleSheet(inp)
        self.dealer_combo.addItem("-- Select Dealer --", "")
        for d in self.dealers:
            self.dealer_combo.addItem(
                f"{d['dealer_name']}  ({d.get('city') or d.get('dealer_code', '')})",
                d["id"]
            )
        dl = QLabel("Dealer *"); dl.setStyleSheet(lbl)
        form.addRow(dl, self.dealer_combo)

        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setFixedHeight(36)
        self.date_input.setStyleSheet(inp)
        dtl = QLabel("Dispatch Date *"); dtl.setStyleSheet(lbl)
        form.addRow(dtl, self.date_input)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(48)
        self.notes_input.setPlaceholderText("Optional notes...")
        self.notes_input.setStyleSheet(
            "color:#1a1a1a; background:white; border:1px solid #ddd; border-radius:4px;"
        )
        nl = QLabel("Notes"); nl.setStyleSheet(lbl)
        form.addRow(nl, self.notes_input)
        layout.addLayout(form)

        # ── Scooters section
        sec_lbl = QLabel("Scooters")
        sec_lbl.setStyleSheet("font-size:13px; font-weight:700; color:#1e293b; margin-top:4px;")
        layout.addWidget(sec_lbl)

        self.scooters_layout = QVBoxLayout()
        self.scooters_layout.setSpacing(6)
        layout.addLayout(self.scooters_layout)

        add_scooter_btn = QPushButton("+ Add Scooter")
        add_scooter_btn.setFixedHeight(30)
        add_scooter_btn.setStyleSheet(
            "border:1px solid #2563eb; color:#2563eb; border-radius:4px; font-size:12px; padding:0 10px;"
        )
        add_scooter_btn.clicked.connect(self._add_scooter_row)
        layout.addWidget(add_scooter_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # ── Parts section
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e5e7eb; margin:4px 0;")
        layout.addWidget(sep)

        parts_lbl = QLabel("Spare Parts & Batteries")
        parts_lbl.setStyleSheet("font-size:13px; font-weight:700; color:#1e293b;")
        layout.addWidget(parts_lbl)

        self.parts_layout = QVBoxLayout()
        self.parts_layout.setSpacing(6)
        layout.addLayout(self.parts_layout)

        parts_btn_row = QHBoxLayout()
        parts_btn_row.setSpacing(8)

        add_part_btn = QPushButton("+ Add Spare Part")
        add_part_btn.setFixedHeight(30)
        add_part_btn.setStyleSheet(
            "border:1px solid #7c3aed; color:#7c3aed; border-radius:4px; font-size:12px; padding:0 10px;"
        )
        add_part_btn.clicked.connect(self._add_part_row)
        parts_btn_row.addWidget(add_part_btn)

        add_battery_btn = QPushButton("🔋 Add Battery")
        add_battery_btn.setFixedHeight(30)
        add_battery_btn.setStyleSheet(
            "border:1px solid #f59e0b; color:#b45309; border-radius:4px; font-size:12px; padding:0 10px;"
        )
        add_battery_btn.clicked.connect(self._add_battery_row)
        parts_btn_row.addWidget(add_battery_btn)
        parts_btn_row.addStretch()

        layout.addLayout(parts_btn_row)

        # ── Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("border:1px solid #ddd; border-radius:6px; color:#666;")
        confirm_btn = QPushButton("✅ Confirm Dispatch")
        confirm_btn.setFixedHeight(38)
        confirm_btn.setDefault(True)
        confirm_btn.setStyleSheet(
            "background:#16a34a; color:white; border:none; border-radius:6px; font-weight:600;"
        )
        confirm_btn.clicked.connect(self._confirm)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        outer.addLayout(btn_row)

        # Add one blank scooter row to start
        self._add_scooter_row()

    # ── Scooter rows ──────────────────────────────────────────

    def _add_scooter_row(self):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        pdi_input = QLineEdit()
        pdi_input.setFixedHeight(32)
        pdi_input.setFixedWidth(140)
        pdi_input.setPlaceholderText("PDI Number")
        pdi_input.setStyleSheet(
            "border:1px solid #ddd; border-radius:4px; padding:0 8px; color:#1a1a1a; background:white;"
        )
        row_layout.addWidget(pdi_input)

        verify_btn = QPushButton("Verify")
        verify_btn.setFixedHeight(32)
        verify_btn.setFixedWidth(62)
        verify_btn.setStyleSheet(
            "background:#2563eb; color:white; border:none; border-radius:4px; font-size:11px;"
        )

        info_lbl = QLabel("—")
        info_lbl.setStyleSheet("color:#94a3b8; font-size:11px;")
        info_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        row_data = {"pdi_input": pdi_input, "info_lbl": info_lbl, "verified": False, "unit_id": None}
        self._scooter_rows.append(row_data)

        verify_btn.clicked.connect(lambda _, rd=row_data: self._verify_pdi(rd))
        pdi_input.returnPressed.connect(lambda rd=row_data: self._verify_pdi(rd))

        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(28, 28)
        remove_btn.setStyleSheet(
            "QPushButton { background:#fee2e2; color:#dc2626; border:none; border-radius:4px; font-size:11px; }"
            "QPushButton:hover { background:#fecaca; }"
        )
        remove_btn.clicked.connect(lambda _, rw=row_widget, rd=row_data: self._remove_scooter_row(rw, rd))

        row_layout.addWidget(verify_btn)
        row_layout.addWidget(info_lbl, 1)
        row_layout.addWidget(remove_btn)

        self.scooters_layout.addWidget(row_widget)

    def _verify_pdi(self, row_data):
        pdi_no = row_data["pdi_input"].text().strip()
        if not pdi_no:
            return
        row_data["info_lbl"].setText("Checking...")
        row_data["info_lbl"].setStyleSheet("color:#94a3b8; font-size:11px;")
        row_data["verified"] = False
        row_data["unit_id"]  = None

        try:
            units = APIClient.get(f"/pdi/units?pdi_number={pdi_no}")
            if not units:
                row_data["info_lbl"].setText("❌ Not found")
                row_data["info_lbl"].setStyleSheet("color:#dc2626; font-size:11px;")
                return
            unit = units[0]
            if unit.get("status") != "pdi_done":
                row_data["info_lbl"].setText(f"❌ Status: {unit.get('status', '?')} (need pdi_done)")
                row_data["info_lbl"].setStyleSheet("color:#dc2626; font-size:11px;")
                return
            if unit.get("current_dealer_id"):
                row_data["info_lbl"].setText("❌ Already dispatched")
                row_data["info_lbl"].setStyleSheet("color:#dc2626; font-size:11px;")
                return
            row_data["verified"] = True
            row_data["unit_id"]  = unit.get("id")
            model = unit.get("model_name", "")
            color = unit.get("color", "")
            serial = unit.get("serial_number", "")
            row_data["info_lbl"].setText(f"✅ {model}  {color}  —  {serial}")
            row_data["info_lbl"].setStyleSheet("color:#16a34a; font-size:11px; font-weight:600;")
        except APIError as e:
            row_data["info_lbl"].setText(f"❌ {e.message}")
            row_data["info_lbl"].setStyleSheet("color:#dc2626; font-size:11px;")

    def _remove_scooter_row(self, row_widget, row_data):
        if row_data in self._scooter_rows:
            self._scooter_rows.remove(row_data)
        row_widget.setParent(None)
        row_widget.deleteLater()

    # ── Master data loading ───────────────────────────────────

    def _load_master_data(self):
        try:
            self._models = APIClient.get("/master/models")
        except APIError:
            self._models = []
        try:
            self._batteries = APIClient.get("/master/batteries")
        except APIError:
            self._batteries = []
        # Pre-load all inventory items keyed by name and SKU for matching
        self._inv_by_name = {}
        self._inv_by_sku  = {}
        try:
            items = APIClient.get("/inventory/items")
            for item in items:
                name = item.get("item_name", "").strip().lower()
                sku  = item.get("sku", "").strip().lower()
                if name:
                    self._inv_by_name[name] = item
                if sku:
                    self._inv_by_sku[sku] = item
        except APIError:
            pass

    # ── Part rows (structured) ────────────────────────────────

    def _make_combo(self, height=32):
        c = QComboBox()
        c.setFixedHeight(height)
        c.setStyleSheet(
            "border:1px solid #ddd; border-radius:4px; padding:0 6px; color:#1a1a1a; background:white;"
        )
        return c

    def _make_spinbox(self, width=70):
        s = QSpinBox()
        s.setFixedHeight(32)
        s.setFixedWidth(width)
        s.setMinimum(1)
        s.setMaximum(99999)
        s.setValue(1)
        s.setStyleSheet("""
            QSpinBox {
                color:#1a1a1a; background:white;
                border:1px solid #ddd; border-radius:4px; padding:0 6px;
            }
            QSpinBox::up-button   { width:0; border:none; }
            QSpinBox::down-button { width:0; border:none; }
        """)
        return s

    def _load_locations_for_item(self, inv_id, combo):
        """Populate a location combo with stock locations for the given inventory item."""
        combo.clear()
        combo.addItem("-- Location --", None)
        if not inv_id:
            return
        try:
            locs = APIClient.get(f"/inventory/items/{inv_id}/locations")
            for loc in locs:
                label = f"{loc['location_name']}  ({loc['quantity']} in stock)"
                combo.addItem(label, loc["location_id"])
        except APIError:
            pass

    def _make_remove_btn(self):
        btn = QPushButton("✕")
        btn.setFixedSize(28, 28)
        btn.setStyleSheet(
            "QPushButton { background:#fee2e2; color:#dc2626; border:none; border-radius:4px; font-size:11px; }"
            "QPushButton:hover { background:#fecaca; }"
        )
        return btn

    def _add_part_row(self):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        # Model combo
        model_combo = self._make_combo()
        model_combo.setFixedWidth(160)
        model_combo.addItem("-- Model --", "")
        for m in self._models:
            model_combo.addItem(m["model_name"], m["id"])

        # Part combo (loaded from BOM when model selected)
        part_combo = self._make_combo()
        part_combo.setFixedWidth(160)
        part_combo.addItem("-- Select Part --", None)

        # Colour input
        colour_input = QLineEdit()
        colour_input.setFixedHeight(32)
        colour_input.setFixedWidth(80)
        colour_input.setPlaceholderText("Colour")
        colour_input.setStyleSheet(
            "border:1px solid #ddd; border-radius:4px; padding:0 6px; color:#1a1a1a; background:white;"
        )

        # Location combo (populated after part selected)
        loc_combo = self._make_combo()
        loc_combo.setFixedWidth(160)
        loc_combo.addItem("-- Location --", None)

        qty_spin = self._make_spinbox()

        row_data = {
            "model_combo":  model_combo,
            "part_combo":   part_combo,
            "loc_combo":    loc_combo,
            "colour_input": colour_input,
            "qty":          qty_spin,
            "type":         "part",
        }
        self._part_rows.append(row_data)

        def on_model_changed(index, mc=model_combo, pc=part_combo, lc=loc_combo, dlg=self):
            model_id = mc.currentData()
            pc.clear()
            pc.addItem("-- Select Part --", None)
            if not model_id:
                return
            try:
                bom = APIClient.get(f"/manufacturing/bom/{model_id}")
                for item in bom:
                    name = item.get("part_name") or item.get("item_name", "")
                    inv_id = item.get("inventory_item_id")
                    # BOM item may not be explicitly linked — fall back to name/SKU match
                    if not inv_id:
                        sku = item.get("sku", "")
                        matched = (
                            (name  and dlg._inv_by_name.get(name.strip().lower())) or
                            (sku   and dlg._inv_by_sku.get(sku.strip().lower()))
                        )
                        if matched:
                            inv_id = matched.get("id")
                    if name:
                        pc.addItem(name, inv_id)
                lc.clear()
                lc.addItem("-- Location --", None)
            except APIError:
                pass

        def on_part_changed(index, pc=part_combo, lc=loc_combo, dlg=self):
            inv_id = pc.currentData()
            dlg._load_locations_for_item(inv_id, lc)

        model_combo.currentIndexChanged.connect(on_model_changed)
        part_combo.currentIndexChanged.connect(on_part_changed)

        remove_btn = self._make_remove_btn()
        remove_btn.clicked.connect(lambda _, rw=row_widget, rd=row_data: self._remove_part_row(rw, rd))

        row_layout.addWidget(model_combo)
        row_layout.addWidget(part_combo)
        row_layout.addWidget(loc_combo)
        row_layout.addWidget(colour_input)
        qty_lbl = QLabel("Qty:")
        qty_lbl.setStyleSheet("color:#374151; font-size:12px;")
        row_layout.addWidget(qty_lbl)
        row_layout.addWidget(qty_spin)
        row_layout.addWidget(remove_btn)

        self.parts_layout.addWidget(row_widget)

    def _add_battery_row(self):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        battery_lbl = QLabel("🔋")
        battery_lbl.setStyleSheet("font-size:14px;")
        row_layout.addWidget(battery_lbl)

        battery_combo = self._make_combo()
        battery_combo.setMinimumWidth(200)
        battery_combo.addItem("-- Select Battery --", None)
        for b in self._batteries:
            label = f"{b.get('battery_type', '')}  {b.get('power_spec', '')}".strip()
            inv_item = self._inv_by_name.get(label.lower())
            inv_id = inv_item.get("id") if inv_item else None
            battery_combo.addItem(label, inv_id)

        bat_loc_combo = self._make_combo()
        bat_loc_combo.setFixedWidth(160)
        bat_loc_combo.addItem("-- Location --", None)

        def on_battery_changed(index, bc=battery_combo, lc=bat_loc_combo, dlg=self):
            inv_id = bc.currentData()
            dlg._load_locations_for_item(inv_id, lc)

        battery_combo.currentIndexChanged.connect(on_battery_changed)

        qty_spin = self._make_spinbox()

        row_data = {"battery_combo": battery_combo, "loc_combo": bat_loc_combo, "qty": qty_spin, "type": "battery"}
        self._battery_rows.append(row_data)

        remove_btn = self._make_remove_btn()
        remove_btn.clicked.connect(lambda _, rw=row_widget, rd=row_data: self._remove_battery_row(rw, rd))

        row_layout.addWidget(battery_combo, 1)
        row_layout.addWidget(bat_loc_combo)
        qty_lbl = QLabel("Qty:")
        qty_lbl.setStyleSheet("color:#374151; font-size:12px;")
        row_layout.addWidget(qty_lbl)
        row_layout.addWidget(qty_spin)
        row_layout.addWidget(remove_btn)

        self.parts_layout.addWidget(row_widget)

    def _remove_part_row(self, row_widget, row_data):
        if row_data in self._part_rows:
            self._part_rows.remove(row_data)
        row_widget.setParent(None)
        row_widget.deleteLater()

    def _remove_battery_row(self, row_widget, row_data):
        if row_data in self._battery_rows:
            self._battery_rows.remove(row_data)
        row_widget.setParent(None)
        row_widget.deleteLater()

    # ── Confirm ───────────────────────────────────────────────

    def _confirm(self):
        dealer_id = self.dealer_combo.currentData()
        if not dealer_id:
            QMessageBox.warning(self, "Missing", "Please select a dealer.")
            return

        scooters = []
        for rd in self._scooter_rows:
            pdi_no = rd["pdi_input"].text().strip()
            if not pdi_no:
                continue
            if not rd.get("verified"):
                QMessageBox.warning(
                    self, "Unverified Scooter",
                    f"PDI number '{pdi_no}' has not been verified. Verify or remove it before confirming."
                )
                return
            scooters.append({"pdi_number": pdi_no})

        parts = []
        for pd in self._part_rows:
            model_name = pd["model_combo"].currentText().strip()
            part_name  = pd["part_combo"].currentText().strip()
            inv_id     = pd["part_combo"].currentData()
            colour     = pd["colour_input"].text().strip()
            if not part_name or part_name == "-- Select Part --":
                QMessageBox.warning(self, "Missing", "Please select a part name for all part rows.")
                return
            if not inv_id:
                QMessageBox.warning(
                    self, "Not in Inventory",
                    f"'{part_name}' could not be matched to an inventory item.\n\n"
                    "Check that the part name or SKU in the BOM exactly matches\n"
                    "an item name or SKU in Inventory."
                )
                return
            label = part_name
            if colour:
                label += f" ({colour})"
            if model_name and model_name != "-- Model --":
                label += f" — {model_name}"
            parts.append({
                "part_name":         label,
                "quantity":          pd["qty"].value(),
                "inventory_item_id": inv_id,
                "location_id":       pd["loc_combo"].currentData(),
                "notes":             None,
            })

        for bd in self._battery_rows:
            battery = bd["battery_combo"].currentText().strip()
            inv_id  = bd["battery_combo"].currentData()
            if not battery or battery == "-- Select Battery --":
                QMessageBox.warning(self, "Missing", "Please select a battery type for all battery rows.")
                return
            if not inv_id:
                QMessageBox.warning(
                    self, "Not in Inventory",
                    f"Battery '{battery}' was not found in inventory.\n"
                    "Add it to inventory first before dispatching."
                )
                return
            parts.append({
                "part_name":         f"Battery — {battery}",
                "quantity":          bd["qty"].value(),
                "inventory_item_id": inv_id,
                "location_id":       bd["loc_combo"].currentData(),
                "notes":             None,
            })

        if not scooters and not parts:
            QMessageBox.warning(self, "Empty Dispatch", "Add at least one scooter or one part.")
            return

        self.result_data = {
            "dealer_id":     dealer_id,
            "dispatch_date": self.date_input.date().toString("yyyy-MM-dd"),
            "notes":         self.notes_input.toPlainText().strip() or None,
            "scooters":      scooters,
            "parts":         parts,
        }
        self.accept()


# ── DISPATCH DETAIL TAB ───────────────────────────────────────

class DispatchDetailTab(QWidget):
    def __init__(self, note_id, dealer_name, parent=None):
        super().__init__(parent)
        self.note_id     = note_id
        self.dealer_name = dealer_name
        self.workers     = []
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        title = QLabel(f"📦  Dispatch Detail — {self.dealer_name}")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        layout.addWidget(title)

        self.status_lbl = QLabel("Loading...")
        self.status_lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
        layout.addWidget(self.status_lbl)

        # Scooters table
        scooter_lbl = QLabel("Scooters")
        scooter_lbl.setStyleSheet("font-size:12px; font-weight:700; color:#374151; margin-top:4px;")
        layout.addWidget(scooter_lbl)

        self.scooter_table = QTableWidget()
        self.scooter_table.setColumnCount(4)
        self.scooter_table.setHorizontalHeaderLabels(["Serial No.", "PDI No.", "Model", "Colour"])
        self.scooter_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.scooter_table.setColumnWidth(1, 100)
        self.scooter_table.setColumnWidth(2, 130)
        self.scooter_table.setColumnWidth(3, 80)
        self.scooter_table.verticalHeader().setVisible(False)
        self.scooter_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.scooter_table.setAlternatingRowColors(True)
        self.scooter_table.setMaximumHeight(200)
        self.scooter_table.setStyleSheet("""
            QTableWidget { border:1px solid #e5e7eb; border-radius:6px; gridline-color:#f3f4f6; }
            QHeaderView::section {
                background:#f8fafc; padding:6px; border:none;
                border-bottom:1px solid #e5e7eb; font-weight:600; color:#374151;
            }
            QTableWidget::item { padding:4px 8px; color:#1a1a1a; }
            QTableWidget::item:alternate { background:#f9fafb; }
        """)
        layout.addWidget(self.scooter_table)

        # Parts table
        parts_lbl = QLabel("Parts / Batteries")
        parts_lbl.setStyleSheet("font-size:12px; font-weight:700; color:#374151; margin-top:4px;")
        layout.addWidget(parts_lbl)

        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(3)
        self.parts_table.setHorizontalHeaderLabels(["Part Name", "Qty", "Notes"])
        self.parts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.parts_table.setColumnWidth(1, 60)
        self.parts_table.setColumnWidth(2, 200)
        self.parts_table.verticalHeader().setVisible(False)
        self.parts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.parts_table.setAlternatingRowColors(True)
        self.parts_table.setMaximumHeight(180)
        self.parts_table.setStyleSheet("""
            QTableWidget { border:1px solid #e5e7eb; border-radius:6px; gridline-color:#f3f4f6; }
            QHeaderView::section {
                background:#f8fafc; padding:6px; border:none;
                border-bottom:1px solid #e5e7eb; font-weight:600; color:#374151;
            }
            QTableWidget::item { padding:4px 8px; color:#1a1a1a; }
            QTableWidget::item:alternate { background:#f9fafb; }
        """)
        layout.addWidget(self.parts_table)
        layout.addStretch()

    def _load(self):
        worker = LoadShipmentDetailWorker(self.note_id)
        worker.done.connect(self._populate)
        worker.error.connect(lambda e: self.status_lbl.setText(f"Error: {e}"))
        self.workers.append(worker)
        worker.start()

    def _populate(self, note):
        def cell(text, align=Qt.AlignmentFlag.AlignLeft):
            c = QTableWidgetItem(str(text) if text else "—")
            c.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            return c

        scooters = note.get("scooters", [])
        self.scooter_table.setRowCount(len(scooters))
        for row, s in enumerate(scooters):
            self.scooter_table.setItem(row, 0, cell(s.get("serial_number", "")))
            self.scooter_table.setItem(row, 1, cell(s.get("pdi_number", ""), Qt.AlignmentFlag.AlignCenter))
            self.scooter_table.setItem(row, 2, cell(s.get("model_name", "")))
            self.scooter_table.setItem(row, 3, cell(s.get("color", "")))

        parts = note.get("parts", [])
        self.parts_table.setRowCount(len(parts))
        for row, p in enumerate(parts):
            self.parts_table.setItem(row, 0, cell(p.get("part_name", "")))
            self.parts_table.setItem(row, 1, cell(str(p.get("quantity", "")), Qt.AlignmentFlag.AlignCenter))
            self.parts_table.setItem(row, 2, cell(p.get("notes", "")))

        sc = len(scooters)
        pt = len(parts)
        self.status_lbl.setText(
            f"Dispatched on {note.get('dispatch_date', '')}  •  "
            f"{sc} scooter{'s' if sc != 1 else ''}  •  {pt} part line{'s' if pt != 1 else ''}"
        )


# ── MAIN SHIPMENTS SCREEN ─────────────────────────────────────

class ShipmentsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers  = []
        self.notes    = []
        self._dealers = []
        self._build_ui()
        self._load_summary()
        self._load_dealers()
        self._load_notes()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("📦 Shipments")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        hdr.addWidget(title)
        hdr.addStretch()

        if Session.role in ["superadmin", "manager"]:
            new_btn = QPushButton("＋ New Dispatch")
            new_btn.setFixedHeight(36)
            new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            new_btn.setStyleSheet("""
                QPushButton {
                    background:#16a34a; color:white; border:none;
                    border-radius:6px; padding:0 16px; font-weight:600;
                }
                QPushButton:hover { background:#15803d; }
            """)
            new_btn.clicked.connect(self._new_dispatch)
            hdr.addWidget(new_btn)

        layout.addLayout(hdr)

        # Stat cards
        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)
        self.card_total    = self._stat_card("Total Dispatches",     "—", "#2563eb")
        self.card_scooters = self._stat_card("Scooters Dispatched",  "—", "#16a34a")
        self.card_parts    = self._stat_card("Parts / Batteries Sent","—", "#7c3aed")
        for c in [self.card_total, self.card_scooters, self.card_parts]:
            summary_row.addWidget(c)
        layout.addLayout(summary_row)

        # Filters row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.dealer_filter = QComboBox()
        self.dealer_filter.setFixedHeight(34)
        self.dealer_filter.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 8px; color:#1a1a1a; background:white;"
        )
        self.dealer_filter.addItem("All Dealers", "")
        filter_row.addWidget(self.dealer_filter)

        from_lbl = QLabel("From:")
        from_lbl.setStyleSheet("color:#374151; font-size:12px;")
        filter_row.addWidget(from_lbl)
        self.from_date = QDateEdit()
        self.from_date.setFixedHeight(34)
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-3))
        self.from_date.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 8px; color:#1a1a1a; background:white;"
        )
        filter_row.addWidget(self.from_date)

        to_lbl = QLabel("To:")
        to_lbl.setStyleSheet("color:#374151; font-size:12px;")
        filter_row.addWidget(to_lbl)
        self.to_date = QDateEdit()
        self.to_date.setFixedHeight(34)
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        self.to_date.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 8px; color:#1a1a1a; background:white;"
        )
        filter_row.addWidget(self.to_date)

        search_btn = QPushButton("🔍 Search")
        search_btn.setFixedHeight(34)
        search_btn.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 12px; color:#374151; background:white;"
        )
        search_btn.clicked.connect(self._apply_filters)
        filter_row.addWidget(search_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(34)
        clear_btn.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 10px; color:#666; background:white;"
        )
        clear_btn.clicked.connect(self._clear_filters)
        filter_row.addWidget(clear_btn)

        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border:1px solid #e5e7eb; border-radius:8px; background:white; padding:12px;
            }
            QTabBar::tab {
                padding:8px 20px; font-size:13px; color:#6b7280;
                border:none; border-bottom:2px solid transparent; margin-right:4px;
            }
            QTabBar::tab:selected { color:#2563eb; border-bottom:2px solid #2563eb; font-weight:600; }
            QTabBar::tab:hover { color:#374151; }
        """)

        self.log_tab = self._build_log_tab()
        self.tabs.addTab(self.log_tab, "📋  Dispatch Log")
        layout.addWidget(self.tabs, 1)

    def _build_log_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Date", "Dealer", "Scooters", "Parts", "Notes", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 60)
        self.table.setColumnWidth(4, 180)
        self.table.setColumnWidth(5, 140)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { border:1px solid #e5e7eb; border-radius:8px; gridline-color:#f3f4f6; }
            QHeaderView::section {
                background:#f8fafc; padding:8px; border:none;
                border-bottom:1px solid #e5e7eb; font-weight:600; color:#374151;
            }
            QTableWidget::item { padding:4px 8px; color:#1a1a1a; }
            QTableWidget::item:alternate { background:#f9fafb; }
            QTableWidget::item:selected { background:#eff6ff; color:#1a1a1a; }
        """)
        layout.addWidget(self.table, 1)

        self.status_lbl = QLabel("Loading...")
        self.status_lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
        layout.addWidget(self.status_lbl)

        return widget

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

    def _load_summary(self):
        worker = LoadSummaryWorker()
        worker.done.connect(self._on_summary)
        worker.error.connect(lambda e: None)   # silently ignore; cards keep last value
        self.workers.append(worker)
        worker.start()

    def _on_summary(self, data):
        self._update_card(self.card_total,    data.get("total_dispatches", 0))
        self._update_card(self.card_scooters, data.get("total_scooters",   0))
        self._update_card(self.card_parts,    data.get("total_parts",      0))

    def _load_dealers(self):
        worker = LoadDealersWorker()
        worker.done.connect(self._on_dealers_loaded)
        worker.error.connect(lambda e: None)
        self.workers.append(worker)
        worker.start()

    def _on_dealers_loaded(self, dealers):
        self._dealers = dealers
        self.dealer_filter.clear()
        self.dealer_filter.addItem("All Dealers", "")
        for d in dealers:
            self.dealer_filter.addItem(d["dealer_name"], d["id"])

    def _load_notes(self, dealer_id="", from_date="", to_date=""):
        self.status_lbl.setText("Loading...")
        self.table.setRowCount(0)
        worker = LoadShipmentsWorker(dealer_id, from_date, to_date)
        worker.done.connect(self._populate_table)
        worker.error.connect(lambda e: self.status_lbl.setText(f"Error: {e}"))
        self.workers.append(worker)
        worker.start()

    def _apply_filters(self):
        dealer_id = self.dealer_filter.currentData() or ""
        from_date = self.from_date.date().toString("yyyy-MM-dd")
        to_date   = self.to_date.date().toString("yyyy-MM-dd")
        self._load_notes(dealer_id, from_date, to_date)

    def _clear_filters(self):
        self.dealer_filter.setCurrentIndex(0)
        self.from_date.setDate(QDate.currentDate().addMonths(-3))
        self.to_date.setDate(QDate.currentDate())
        self._load_notes()

    def _populate_table(self, notes):
        self.notes = notes
        self.table.setRowCount(len(notes))

        def cell(text, align=Qt.AlignmentFlag.AlignLeft):
            c = QTableWidgetItem(str(text) if text else "—")
            c.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            return c

        for row, note in enumerate(notes):
            self.table.setItem(row, 0, cell(note.get("dispatch_date", ""), Qt.AlignmentFlag.AlignCenter))
            self.table.setItem(row, 1, cell(note.get("dealer_name", "")))

            sc = note.get("scooter_count", 0)
            sc_cell = QTableWidgetItem(str(sc))
            sc_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            sc_cell.setForeground(QColor("#16a34a") if sc else QColor("#94a3b8"))
            self.table.setItem(row, 2, sc_cell)

            pt = note.get("part_count", 0)
            pt_cell = QTableWidgetItem(str(pt))
            pt_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            pt_cell.setForeground(QColor("#7c3aed") if pt else QColor("#94a3b8"))
            self.table.setItem(row, 3, pt_cell)

            self.table.setItem(row, 4, cell(note.get("notes", "")))

            view_btn = QPushButton("▶ View")
            view_btn.setFixedHeight(28)
            view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            view_btn.setStyleSheet("""
                QPushButton {
                    background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe;
                    border-radius:4px; font-size:11px; padding:0 10px; font-weight:500;
                }
                QPushButton:hover { background:#dbeafe; }
            """)
            view_btn.clicked.connect(lambda _, n=note: self._open_detail_tab(n))

            del_btn = QPushButton("🗑")
            del_btn.setFixedHeight(28)
            del_btn.setFixedWidth(30)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet("""
                QPushButton {
                    background:#fee2e2; color:#dc2626; border:1px solid #fecaca;
                    border-radius:4px; font-size:12px;
                }
                QPushButton:hover { background:#fecaca; }
            """)
            del_btn.clicked.connect(lambda _, n=note: self._delete_note(n))

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(4)
            btn_layout.addWidget(view_btn)
            btn_layout.addWidget(del_btn)
            self.table.setCellWidget(row, 5, btn_widget)

        self.status_lbl.setText(f"{len(notes)} dispatch{'es' if len(notes) != 1 else ''}")

    # ── Detail tab ────────────────────────────────────────────

    def _open_detail_tab(self, note):
        label = f"📦  {note['dealer_name']}  {note['dispatch_date']}"
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).strip() == label.strip():
                self.tabs.setCurrentIndex(i)
                return
        tab = DispatchDetailTab(note["id"], note["dealer_name"])
        idx = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(idx)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#6b7280; border:none; font-size:10px; }"
            "QPushButton:hover { color:#dc2626; }"
        )
        close_btn.clicked.connect(lambda _, i=idx: self._close_tab(i))
        self.tabs.tabBar().setTabButton(idx, self.tabs.tabBar().ButtonPosition.RightSide, close_btn)

    def _close_tab(self, index):
        if index > 0:
            self.tabs.removeTab(index)

    # ── Delete dispatch note ──────────────────────────────────

    def _delete_note(self, note):
        dealer = note.get("dealer_name", "")
        date   = note.get("dispatch_date", "")
        sc     = note.get("scooter_count", 0)
        pt     = note.get("part_count", 0)
        reply  = QMessageBox.question(
            self, "Delete Dispatch",
            f"Delete dispatch to {dealer} on {date}?\n\n"
            f"This will reverse {sc} scooter(s) back to PDI Done and restore {pt} part line(s) to inventory.\n\n"
            "⚠️ This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.delete(f"/shipments/{note['id']}")
                self._load_notes()
                self._load_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    # ── New dispatch ──────────────────────────────────────────

    def _new_dispatch(self):
        if not self._dealers:
            QMessageBox.warning(self, "No Dealers", "No active dealers found. Add a dealer first.")
            return
        dlg = CreateDispatchDialog(self, self._dealers)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                result = APIClient.post("/shipments/", dlg.result_data)
                sc = len(result.get("scooters", []))
                pt = len(result.get("parts", []))
                QMessageBox.information(
                    self, "Dispatch Created",
                    f"Dispatch recorded for {result.get('dealer_name', '')}.\n"
                    f"Scooters: {sc}  •  Part lines: {pt}"
                )
                self._load_notes()
                self._load_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)
