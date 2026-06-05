from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QDialog, QFormLayout,
    QMessageBox, QHeaderView, QFrame,
    QAbstractItemView, QTabWidget, QMenu, QCompleter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QTimer
from PyQt6.QtGui import QFont, QColor, QAction
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session
from desktop.screens.spare_parts import DealerSparePartsDialog


# ── WORKERS ───────────────────────────────────────────────────

class LoadDealersWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.done.emit(APIClient.get("/dealers/?active_only=false"))
        except APIError as e:
            self.error.emit(e.message)


class LoadDealerUnitsWorker(QThread):
    done  = pyqtSignal(str, list)
    error = pyqtSignal(str)

    def __init__(self, dealer_id):
        super().__init__()
        self.dealer_id = dealer_id

    def run(self):
        try:
            units = APIClient.get(f"/dealers/{self.dealer_id}/units")
            self.done.emit(self.dealer_id, units)
        except APIError as e:
            self.error.emit(e.message)


# ── ADD / EDIT DEALER DIALOG ──────────────────────────────────

class DealerDialog(QDialog):
    def __init__(self, parent, existing=None):
        super().__init__(parent)
        self.existing    = existing
        self.result_data = {}
        self.setWindowTitle("Edit Dealer" if existing else "Add Dealer")
        self.setFixedWidth(480)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)

        lbl = "font-size:13px; font-weight:500; color:#374151;"
        inp = "border:1px solid #ddd; border-radius:4px; padding:0 8px; color:#1a1a1a; background:white;"

        def field(placeholder=""):
            f = QLineEdit()
            f.setFixedHeight(36)
            f.setStyleSheet(inp)
            f.setPlaceholderText(placeholder)
            return f

        self.name_input  = field("e.g. Sharma Motors")
        self.city_input  = field("e.g. Jaipur")
        self.state_input = field("e.g. Rajasthan")
        self.phone_input = field("e.g. 9876543210")
        self.email_input = field("e.g. contact@dealer.com")
        self.cname_input = field("Contact person name")

        if self.existing:
            self.name_input.setText(self.existing.get("dealer_name", ""))
            self.city_input.setText(self.existing.get("city", "") or "")
            self.state_input.setText(self.existing.get("state", "") or "")
            self.phone_input.setText(self.existing.get("contact_phone", "") or "")
            self.email_input.setText(self.existing.get("contact_email", "") or "")
            self.cname_input.setText(self.existing.get("contact_name", "") or "")

        # Code preview (auto-generated, read-only)
        self.code_preview = QLabel("Auto-generated on save")
        self.code_preview.setStyleSheet("color:#6b7280; font-size:12px; font-style:italic;")
        if self.existing:
            self.code_preview.setText(self.existing.get("dealer_code", ""))
            self.code_preview.setStyleSheet("color:#1a1a1a; font-size:12px; font-weight:600;")

        for label_text, widget in [
            ("Dealer Name *",  self.name_input),
            ("Dealer Code",    self.code_preview),
            ("City",           self.city_input),
            ("State",          self.state_input),
            ("Phone",          self.phone_input),
            ("Email",          self.email_input),
            ("Contact Person", self.cname_input),
        ]:
            lbl_widget = QLabel(label_text)
            lbl_widget.setStyleSheet(lbl)
            form.addRow(lbl_widget, widget)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("border:1px solid #ddd; border-radius:6px; color:#666;")
        save_btn = QPushButton("Save Dealer")
        save_btn.setFixedHeight(38)
        save_btn.setDefault(True)
        save_btn.setStyleSheet(
            "background:#2563eb; color:white; border:none; border-radius:6px; font-weight:600;"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing", "Dealer name is required.")
            return
        self.result_data = {
            "dealer_name":   name,
            "city":          self.city_input.text().strip() or None,
            "state":         self.state_input.text().strip() or None,
            "contact_phone": self.phone_input.text().strip() or None,
            "contact_email": self.email_input.text().strip() or None,
            "contact_name":  self.cname_input.text().strip() or None,
        }
        self.accept()


# ── LOG DAMAGE DIALOG ────────────────────────────────────────

class LogDamageDialog(QDialog):
    def __init__(self, parent, unit):
        super().__init__(parent)
        self.unit        = unit
        self.result_data = {}
        self._bom_parts  = []
        self.setWindowTitle("Log Damage")
        self.setFixedWidth(440)
        self.setModal(True)
        self._load_bom()
        self._build_ui()

    def _load_bom(self):
        names = []
        seen  = set()

        def _add(name):
            n = (name or "").strip()
            key = n.lower()
            if n and key not in seen:
                seen.add(key)
                names.append(n)

        # Only this model's BOM parts — general-part damage is logged separately
        # via "Log Spare Part Damage".
        model_id = self.unit.get("model_id")
        if model_id:
            try:
                for b in APIClient.get(f"/manufacturing/bom/{model_id}"):
                    _add(b.get("part_name") or b.get("item_name"))
            except Exception:
                pass
        self._part_names = names

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("⚠️  Log Damage")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        layout.addWidget(title)

        sub = QLabel(
            f"Serial: {self.unit.get('serial_number', '—')}  ·  "
            f"Model: {self.unit.get('model_name', '—')}"
        )
        sub.setStyleSheet("color:#6b7280; font-size:12px;")
        layout.addWidget(sub)

        inp = "border:1px solid #ddd; border-radius:4px; padding:0 8px; color:#1a1a1a; background:white;"
        form = QFormLayout()
        form.setSpacing(10)
        form.setHorizontalSpacing(16)

        self.part_combo = QComboBox()
        self.part_combo.setFixedHeight(34)
        self.part_combo.setStyleSheet(inp)
        self.part_combo.setEditable(True)
        self.part_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.part_combo.lineEdit().setPlaceholderText("Type to search BOM parts…")
        self.part_combo.addItem("", "")
        for name in self._part_names:
            self.part_combo.addItem(name, name)
        # Type-ahead autocomplete over the BOM part list
        completer = self.part_combo.completer()
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.part_combo.setCurrentIndex(0)
        form.addRow(QLabel("Part *"), self.part_combo)

        self.stage_combo = QComboBox()
        self.stage_combo.setFixedHeight(34)
        self.stage_combo.setStyleSheet(inp)
        self.stage_combo.addItem("During Transportation to Dealer", "transit")
        self.stage_combo.addItem("After Sale (Customer Use)",        "dealer")
        form.addRow(QLabel("Damage Stage *"), self.stage_combo)

        self.notes_input = QLineEdit()
        self.notes_input.setFixedHeight(34)
        self.notes_input.setPlaceholderText("Optional notes…")
        self.notes_input.setStyleSheet(inp)
        form.addRow(QLabel("Notes"), self.notes_input)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("border:1px solid #ddd; border-radius:6px; color:#666;")
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton("⚠️  Log Damage")
        confirm_btn.setFixedHeight(36)
        confirm_btn.setDefault(True)
        confirm_btn.setStyleSheet(
            "background:#dc2626; color:white; border:none; border-radius:6px; font-weight:600;"
        )
        confirm_btn.clicked.connect(self._confirm)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def _confirm(self):
        # Editable combo — accept either a picked BOM part or free-typed text
        part = self.part_combo.currentText().strip()
        if not part:
            QMessageBox.warning(self, "Missing", "Please select or type a part.")
            return
        self.result_data = {
            "scooter_unit_id": self.unit["id"],
            "stage":           self.stage_combo.currentData(),
            "part_name":       part,
            "notes":           self.notes_input.text().strip() or None,
        }
        self.accept()


# ── LOG SPARE PART DAMAGE DIALOG ─────────────────────────────

class LogSparePartDamageDialog(QDialog):
    def __init__(self, parent, dealer):
        super().__init__(parent)
        self.dealer      = dealer
        self.result_data = {}
        self._parts      = []
        self.setWindowTitle("Log Spare Part Damage")
        self.setFixedWidth(440)
        self.setModal(True)
        self._load_parts()
        self._build_ui()

    def _load_parts(self):
        try:
            rows = APIClient.get(f"/spare-parts/dispatches?dealer_id={self.dealer['id']}")
            seen = {}
            for r in rows:
                name = r.get("part_name", "")
                if name and name not in seen:
                    seen[name] = True
                    self._parts.append(name)
        except Exception:
            pass

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("⚠️  Log Spare Part Damage")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        layout.addWidget(title)

        sub = QLabel(f"Dealer: {self.dealer.get('dealer_name', '—')}")
        sub.setStyleSheet("color:#6b7280; font-size:12px;")
        layout.addWidget(sub)

        inp = "border:1px solid #ddd; border-radius:4px; padding:0 8px; color:#1a1a1a; background:white;"
        form = QFormLayout()
        form.setSpacing(10)
        form.setHorizontalSpacing(16)

        self.part_combo = QComboBox()
        self.part_combo.setFixedHeight(34)
        self.part_combo.setStyleSheet(inp)
        self.part_combo.addItem("-- Select Part --", "")
        for p in self._parts:
            self.part_combo.addItem(p, p)
        self.part_combo.addItem("Other (describe below)", "__other__")
        self.part_combo.currentIndexChanged.connect(self._on_part_changed)
        form.addRow(QLabel("Part *"), self.part_combo)

        self.other_input = QLineEdit()
        self.other_input.setFixedHeight(34)
        self.other_input.setPlaceholderText("Describe the part…")
        self.other_input.setStyleSheet(inp)
        self.other_input.setVisible(False)
        form.addRow(QLabel("Description *"), self.other_input)

        self.notes_input = QLineEdit()
        self.notes_input.setFixedHeight(34)
        self.notes_input.setPlaceholderText("Describe the damage…")
        self.notes_input.setStyleSheet(inp)
        form.addRow(QLabel("Damage Notes *"), self.notes_input)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet("border:1px solid #ddd; border-radius:6px; color:#666;")
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton("⚠️  Log Damage")
        confirm_btn.setFixedHeight(36)
        confirm_btn.setDefault(True)
        confirm_btn.setStyleSheet(
            "background:#dc2626; color:white; border:none; border-radius:6px; font-weight:600;"
        )
        confirm_btn.clicked.connect(self._confirm)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def _on_part_changed(self, _):
        self.other_input.setVisible(self.part_combo.currentData() == "__other__")

    def _confirm(self):
        selected = self.part_combo.currentData()
        if not selected:
            QMessageBox.warning(self, "Missing", "Please select a part.")
            return
        if selected == "__other__":
            part = self.other_input.text().strip()
            if not part:
                QMessageBox.warning(self, "Missing", "Please describe the part.")
                return
        else:
            part = selected
        notes = self.notes_input.text().strip()
        if not notes:
            QMessageBox.warning(self, "Missing", "Please describe the damage.")
            return
        self.result_data = {
            "part_name": part,
            "notes":     notes,
            "stage":     "dealer",
        }
        self.accept()


# ── DEALER UNITS TAB ─────────────────────────────────────────

class DealerUnitsTab(QWidget):
    def __init__(self, dealer, parent=None):
        super().__init__(parent)
        self.dealer  = dealer
        self.units   = []
        self.workers = []
        self._build_ui()
        self._load_units()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        title = QLabel(f"🚚  {self.dealer['dealer_name']}  —  Units")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search serial, model, chassis or PDI no...")
        self.search_input.setFixedHeight(34)
        self.search_input.setFixedWidth(280)
        self.search_input.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 10px; color:#1a1a1a; background:white;"
        )
        self.search_input.textChanged.connect(self._filter)
        hdr.addWidget(self.search_input)

        layout.addLayout(hdr)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Serial No.", "Model", "Colour", "Chassis No.", "PDI No.", "Delivered Date", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 110)
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
        layout.addWidget(self.table)

        self.status_lbl = QLabel("Loading...")
        self.status_lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
        layout.addWidget(self.status_lbl)

    def _load_units(self):
        worker = LoadDealerUnitsWorker(self.dealer["id"])
        worker.done.connect(self._populate)
        worker.error.connect(lambda e: self.status_lbl.setText(f"Error: {e}"))
        self.workers.append(worker)
        worker.start()

    def _populate(self, dealer_id, units):
        self.units = units
        self._render(units)

    def _filter(self, text):
        q = text.strip().lower()
        filtered = [
            u for u in self.units
            if not q
            or q in u.get("serial_number", "").lower()
            or q in (u.get("model_name") or "").lower()
            or q in (u.get("chassis_number") or "").lower()
            or q in (u.get("pdi_number") or "").lower()
            or q in (u.get("color") or "").lower()
        ]
        self._render(filtered)

    def _render(self, units):
        self.table.setRowCount(len(units))

        def cell(text, align=Qt.AlignmentFlag.AlignLeft):
            c = QTableWidgetItem(str(text) if text else "—")
            c.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            return c

        for row, unit in enumerate(units):
            self.table.setItem(row, 0, cell(unit.get("serial_number", "")))
            self.table.setItem(row, 1, cell(unit.get("model_name", "")))
            self.table.setItem(row, 2, cell(unit.get("color", "")))
            self.table.setItem(row, 3, cell(unit.get("chassis_number", "")))
            self.table.setItem(row, 4, cell(unit.get("pdi_number", ""), Qt.AlignmentFlag.AlignCenter))
            self.table.setItem(row, 5, cell(unit.get("delivered_date", ""), Qt.AlignmentFlag.AlignCenter))

            dmg_btn = QPushButton("⚠ Damage")
            dmg_btn.setFixedHeight(26)
            dmg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            dmg_btn.setStyleSheet("""
                QPushButton {
                    background:#fef2f2; color:#dc2626;
                    border:1px solid #fca5a5; border-radius:4px;
                    font-size:11px; font-weight:600; padding:0 8px;
                }
                QPushButton:hover { background:#fee2e2; }
            """)
            dmg_btn.clicked.connect(lambda _, u=unit: self._log_damage(u))
            self.table.setCellWidget(row, 6, dmg_btn)

        total = len(self.units)
        shown = len(units)
        if shown == total:
            self.status_lbl.setText(f"{total} unit{'s' if total != 1 else ''} at this dealer")
        else:
            self.status_lbl.setText(f"{shown} of {total} units")

    def _log_damage(self, unit):
        dlg = LogDamageDialog(self, unit)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.post("/damage-log/", dlg.result_data)
                QMessageBox.information(
                    self, "Logged",
                    f"Damage recorded for {unit.get('serial_number', '')}."
                )
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)


# ── DEALERS OVERVIEW TAB ─────────────────────────────────────

class DealersTab(QWidget):
    view_dealer_requested = pyqtSignal(dict)
    data_changed          = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dealers = []
        self.workers = []
        self._build_ui()
        self._load_dealers()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        hdr = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search by name, code, city or state...")
        self.search_input.setFixedHeight(34)
        self.search_input.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 10px; color:#1a1a1a; background:white;"
        )
        self.search_input.textChanged.connect(self._filter)
        hdr.addWidget(self.search_input, 1)

        if Session.role in ["superadmin", "manager"]:
            self.add_btn = QPushButton("+ Add Dealer")
            self.add_btn.setFixedHeight(34)
            self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.add_btn.setStyleSheet("""
                QPushButton {
                    background:#2563eb; color:white; border:none;
                    border-radius:6px; padding:0 16px; font-weight:600; font-size:12px;
                }
                QPushButton:hover { background:#1d4ed8; }
            """)
            self.add_btn.clicked.connect(self._add_dealer)
            hdr.addWidget(self.add_btn)

        layout.addLayout(hdr)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Dealer Name", "Code", "City", "State", "Phone", "Units", "Status", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 60)
        self.table.setColumnWidth(6, 90)
        self.table.setColumnWidth(7, 130)
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
        layout.addWidget(self.table)

        self.status_lbl = QLabel("Loading...")
        self.status_lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
        layout.addWidget(self.status_lbl)

    def _load_dealers(self):
        self.status_lbl.setText("Loading...")
        self.table.setRowCount(0)
        worker = LoadDealersWorker()
        worker.done.connect(self._populate)
        worker.error.connect(lambda e: self.status_lbl.setText(f"Error: {e}"))
        self.workers.append(worker)
        worker.start()

    def _filter(self, text):
        q = text.strip().lower()
        filtered = [
            d for d in self.dealers
            if not q
            or q in d.get("dealer_name", "").lower()
            or q in d.get("dealer_code", "").lower()
            or q in (d.get("city") or "").lower()
            or q in (d.get("state") or "").lower()
        ]
        self._render(filtered)

    def _populate(self, dealers):
        self.dealers = dealers
        self._render(dealers)

    def _render(self, dealers):
        self.table.setRowCount(len(dealers))

        def cell(text, align=Qt.AlignmentFlag.AlignLeft):
            c = QTableWidgetItem(str(text) if text else "—")
            c.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            return c

        for row, dealer in enumerate(dealers):
            is_active = dealer.get("is_active", True)

            name_cell = QTableWidgetItem(dealer.get("dealer_name", ""))
            name_cell.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if not is_active:
                name_cell.setForeground(QColor("#94a3b8"))
            self.table.setItem(row, 0, name_cell)

            self.table.setItem(row, 1, cell(dealer.get("dealer_code", "")))
            self.table.setItem(row, 2, cell(dealer.get("city", "")))
            self.table.setItem(row, 3, cell(dealer.get("state", "")))
            self.table.setItem(row, 4, cell(dealer.get("contact_phone", "")))

            units_cell = QTableWidgetItem(str(dealer.get("unit_count", 0)))
            units_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            units_cell.setForeground(QColor("#2563eb"))
            self.table.setItem(row, 5, units_cell)

            status_lbl = QLabel("● Active" if is_active else "● Inactive")
            status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_lbl.setStyleSheet(
                "color:#16a34a; font-size:12px; font-weight:600;"
                if is_active else
                "color:#dc2626; font-size:12px; font-weight:600;"
            )
            status_widget = QWidget()
            sl = QHBoxLayout(status_widget)
            sl.setContentsMargins(4, 0, 4, 0)
            sl.addWidget(status_lbl)
            self.table.setCellWidget(row, 6, status_widget)

            actions_btn = QPushButton("⚡ Actions ▾")
            actions_btn.setFixedHeight(30)
            actions_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            actions_btn.setStyleSheet("""
                QPushButton {
                    background:#1e293b; color:white; border:none;
                    border-radius:4px; font-size:11px; padding:0 10px; font-weight:500;
                }
                QPushButton:hover { background:#334155; }
            """)
            actions_btn.clicked.connect(
                lambda _, d=dealer, b=actions_btn: self._show_actions(d, b)
            )
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.addWidget(actions_btn)
            self.table.setCellWidget(row, 7, btn_widget)

        total = len(self.dealers)
        shown = len(dealers)
        if shown == total:
            self.status_lbl.setText(f"{total} dealer{'s' if total != 1 else ''}")
        else:
            self.status_lbl.setText(f"{shown} of {total} dealers")

    def _show_actions(self, dealer, btn):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background:white; border:1px solid #e5e7eb;
                border-radius:8px; padding:4px;
            }
            QMenu::item {
                padding:8px 16px; font-size:13px; color:#1a1a1a; border-radius:4px;
            }
            QMenu::item:selected { background:#eff6ff; color:#2563eb; }
            QMenu::item:disabled { color:#94a3b8; }
            QMenu::separator { height:1px; background:#e5e7eb; margin:4px 8px; }
        """)

        view_action = QAction("🔍  View Units", self)
        view_action.triggered.connect(lambda checked, d=dealer: self.view_dealer_requested.emit(d))
        menu.addAction(view_action)

        parts_action = QAction("📦  View Spare Parts", self)
        parts_action.triggered.connect(
            lambda checked, d=dealer: DealerSparePartsDialog(d["id"], d["dealer_name"], self).exec()
        )
        menu.addAction(parts_action)

        spare_dmg_action = QAction("⚠️  Log Spare Part Damage", self)
        spare_dmg_action.triggered.connect(lambda checked, d=dealer: self._log_spare_part_damage(d))
        menu.addAction(spare_dmg_action)

        if Session.role in ["superadmin", "manager"]:
            edit_action = QAction("✏️   Edit Dealer", self)
            edit_action.triggered.connect(lambda checked, d=dealer: self._edit_dealer(d))
            menu.addAction(edit_action)

        if Session.role == "superadmin":
            menu.addSeparator()
            if dealer.get("is_active"):
                deact_action = QAction("⛔  Deactivate", self)
                deact_action.triggered.connect(lambda checked, d=dealer: self._deactivate(d))
                menu.addAction(deact_action)
            else:
                react_action = QAction("✅  Reactivate", self)
                react_action.triggered.connect(lambda checked, d=dealer: self._reactivate(d))
                menu.addAction(react_action)
            delete_action = QAction("🗑️  Delete Permanently", self)
            delete_action.triggered.connect(lambda checked, d=dealer: self._delete_dealer(d))
            menu.addAction(delete_action)

        pos = btn.mapToGlobal(QPoint(0, btn.height()))
        menu.exec(pos)
        QTimer.singleShot(0, lambda: None)

    def _log_spare_part_damage(self, dealer):
        dlg = LogSparePartDamageDialog(self, dealer)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                payload = {**dlg.result_data, "dealer_id": dealer["id"]}
                APIClient.post("/damage-log/spare-part-damage", payload)
                QMessageBox.information(
                    self, "Logged",
                    f"Spare part damage recorded for {dealer['dealer_name']}."
                )
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _add_dealer(self):
        dlg = DealerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.post("/dealers/", dlg.result_data)
                QMessageBox.information(self, "Added", "Dealer added successfully.")
                self._load_dealers()
                self.data_changed.emit()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _edit_dealer(self, dealer):
        dlg = DealerDialog(self, existing=dealer)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.patch(f"/dealers/{dealer['id']}", dlg.result_data)
                QMessageBox.information(self, "Updated", "Dealer updated.")
                self._load_dealers()
                self.data_changed.emit()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _deactivate(self, dealer):
        reply = QMessageBox.question(
            self, "Deactivate Dealer",
            f"Deactivate '{dealer['dealer_name']}'?\nThey will be marked inactive but not deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.patch(f"/dealers/{dealer['id']}/deactivate", {})
                self._load_dealers()
                self.data_changed.emit()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _reactivate(self, dealer):
        try:
            APIClient.patch(f"/dealers/{dealer['id']}/reactivate", {})
            self._load_dealers()
            self.data_changed.emit()
        except APIError as e:
            QMessageBox.critical(self, "Error", e.message)

    def _delete_dealer(self, dealer):
        reply = QMessageBox.question(
            self, "Delete Dealer",
            f"Permanently delete '{dealer['dealer_name']}'?\n\n"
            "⚠️ This cannot be undone. Dealers with scooters assigned cannot be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.delete(f"/dealers/{dealer['id']}")
                self._load_dealers()
                self.data_changed.emit()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)


# ── MAIN DEALERS SCREEN ───────────────────────────────────────

class DealersScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("🚚 Dealers")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        hdr.addWidget(title)
        hdr.addStretch()

        layout.addLayout(hdr)

        # Stat cards
        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)
        self.card_total    = self._stat_card("Total Dealers",    "—", "#2563eb")
        self.card_active   = self._stat_card("Active Dealers",   "—", "#16a34a")
        self.card_dispatch = self._stat_card("Units Dispatched", "—", "#7c3aed")
        for c in [self.card_total, self.card_active, self.card_dispatch]:
            summary_row.addWidget(c)
        layout.addLayout(summary_row)

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

        self.dealers_tab = DealersTab()
        self.dealers_tab.view_dealer_requested.connect(self._open_dealer_tab)
        self.dealers_tab.data_changed.connect(self._load_summary)
        self.tabs.addTab(self.dealers_tab, "🏪  Dealers")
        layout.addWidget(self.tabs)

        self._load_summary()

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

    def _load_summary(self):
        worker = LoadDealersWorker()
        worker.done.connect(self._on_summary_dealers)
        worker.error.connect(lambda e: None)
        self.workers.append(worker)
        worker.start()

    def _on_summary_dealers(self, dealers):
        total      = len(dealers)
        active     = sum(1 for d in dealers if d.get("is_active"))
        dispatched = sum(d.get("unit_count", 0) for d in dealers)
        self._update_card(self.card_total,    total)
        self._update_card(self.card_active,   active)
        self._update_card(self.card_dispatch, dispatched)

    def _open_dealer_tab(self, dealer):
        # Check if tab already open
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).strip().startswith(dealer["dealer_name"][:12]):
                self.tabs.setCurrentIndex(i)
                return
        tab = DealerUnitsTab(dealer)
        idx = self.tabs.addTab(tab, f"🏪  {dealer['dealer_name']}")
        self.tabs.setCurrentIndex(idx)

        # Add close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#6b7280; border:none; font-size:10px; }"
            "QPushButton:hover { color:#dc2626; }"
        )
        close_btn.clicked.connect(lambda _, i=idx: self._close_dealer_tab(i))
        self.tabs.tabBar().setTabButton(idx, self.tabs.tabBar().ButtonPosition.RightSide, close_btn)

    def _close_dealer_tab(self, index):
        if index > 0:
            self.tabs.removeTab(index)
