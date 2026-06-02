from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QDialog, QFormLayout,
    QSpinBox, QMessageBox, QHeaderView, QFrame,
    QTextEdit, QAbstractItemView, QCompleter,
    QStackedWidget, QDateEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QStringListModel, QDate
from PyQt6.QtGui import QFont, QColor
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session


# ── WORKERS ───────────────────────────────────────────────────

class LoadInventoryWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, search="", low_stock=False):
        super().__init__()
        self.search    = search
        self.low_stock = low_stock

    def run(self):
        try:
            params = []
            if self.search:
                params.append(f"search={self.search}")
            if self.low_stock:
                params.append("low_stock_only=true")
            qs     = "?" + "&".join(params) if params else ""
            result = APIClient.get(f"/inventory/items{qs}")
            self.done.emit(result)
        except APIError as e:
            self.error.emit(e.message)


class LoadSummaryWorker(QThread):
    done = pyqtSignal(dict)

    def run(self):
        try:
            self.done.emit(APIClient.get("/inventory/summary"))
        except APIError:
            self.done.emit({})


class LoadLocationStockWorker(QThread):
    done = pyqtSignal(str, list)

    def __init__(self, item_id: str):
        super().__init__()
        self.item_id = item_id

    def run(self):
        try:
            result = APIClient.get(
                f"/inventory/items/{self.item_id}/locations"
            )
            self.done.emit(self.item_id, result)
        except APIError:
            self.done.emit(self.item_id, [])


# ── SKU GENERATOR ─────────────────────────────────────────────

def generate_sku(model_name: str, part_name: str,
                 colour: str = "") -> str:
    def clean(text):
        return text.upper().replace(" ", "").replace("-", "")[:8]
    sku = f"{clean(model_name)}-{clean(part_name)}"
    if colour.strip():
        sku += f"-{clean(colour)}"
    return sku


# ── SEARCHABLE INPUT ──────────────────────────────────────────

class SearchableInput(QWidget):
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setFixedHeight(36)
        self.input.setStyleSheet(
            "border:1px solid #ddd; border-radius:4px;"
            "padding:0 8px; color:#1a1a1a; background:white;"
        )
        self._completer = QCompleter([])
        self._completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.input.setCompleter(self._completer)
        layout.addWidget(self.input)

    def set_items(self, items: list):
        self._completer.setModel(QStringListModel(items))

    def text(self) -> str:
        return self.input.text().strip()

    def setText(self, text: str):
        self.input.setText(text)


# ── IMPORT FORM ───────────────────────────────────────────────

class ImportForm(QWidget):
    def __init__(self, model_names, part_names, locations, parent=None):
        super().__init__(parent)
        self._model_names = model_names
        self._part_names  = part_names
        self._locations   = locations
        self._build_ui()

    def _build_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        layout.setHorizontalSpacing(16)

        lbl  = "font-size:13px; font-weight:500; color:#374151;"
        inp  = ("border:1px solid #ddd; border-radius:4px;"
                "padding:0 8px; color:#1a1a1a; background:white;")
        spin = ("color:#1a1a1a; background:white; border:1px solid #ddd;"
                "border-radius:4px; padding:0 8px;")

        # Date
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setFixedHeight(36)
        self.date_input.setStyleSheet(inp)
        d = QLabel("Date *"); d.setStyleSheet(lbl)
        layout.addRow(d, self.date_input)

        # Model — dropdown with blank first item
        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(36)
        self.model_combo.setStyleSheet(inp)
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model_combo.lineEdit().setPlaceholderText(
            "Select or type model name..."
        )
        self.model_combo.lineEdit().setStyleSheet("color:#1a1a1a;")
        self.model_combo.addItem("-- Select Model --", "")
        self.model_combo.addItems(self._model_names)
        self.model_combo.setCurrentIndex(0)
        self.model_combo.lineEdit().clear()  # ← add this line
        self.model_combo.currentTextChanged.connect(self._update_sku)
        m = QLabel("Scooter Model *"); m.setStyleSheet(lbl)
        layout.addRow(m, self.model_combo)

        # Part
        self.part_input = SearchableInput("Type or select part name...")
        self.part_input.set_items(self._part_names)
        self.part_input.input.textChanged.connect(self._update_sku)
        p = QLabel("Part Name *"); p.setStyleSheet(lbl)
        layout.addRow(p, self.part_input)

        # Colour
        self.colour_input = QLineEdit()
        self.colour_input.setPlaceholderText(
            "e.g. Red, Blue  —  leave blank if no colour"
        )
        self.colour_input.setFixedHeight(36)
        self.colour_input.setStyleSheet(inp)
        self.colour_input.textChanged.connect(self._update_sku)
        c = QLabel("Colour"); c.setStyleSheet(lbl)
        layout.addRow(c, self.colour_input)

        # Location
        self.location_combo = QComboBox()
        self.location_combo.setFixedHeight(36)
        self.location_combo.setStyleSheet(inp)
        self.location_combo.addItem("-- Select Location --", "")
        for loc in self._locations:
            icon = {"factory": "🏭", "warehouse": "🏢",
                    "godown": "📦"}.get(loc.get("location_type", ""), "📍")
            self.location_combo.addItem(
                f"{icon}  {loc['name']}", loc["id"]
            )
        l = QLabel("Location"); l.setStyleSheet(lbl)
        layout.addRow(l, self.location_combo)

        # Quantity
        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(999999)
        self.qty_spin.setValue(1)
        self.qty_spin.setStyleSheet(spin)
        q = QLabel("Quantity *"); q.setStyleSheet(lbl)
        layout.addRow(q, self.qty_spin)

        # SKU preview
        self.sku_label = QLabel("Auto SKU: —")
        self.sku_label.setStyleSheet(
            "color:#6b7280; font-size:11px; font-style:italic;"
        )
        layout.addRow("", self.sku_label)

    def _update_sku(self):
        model  = self.model_combo.currentText().strip()
        part   = self.part_input.text()
        colour = self.colour_input.text().strip()
        if model and model != "-- Select Model --" and part:
            self.sku_label.setText(
                f"Auto SKU: {generate_sku(model, part, colour)}"
            )
        else:
            self.sku_label.setText("Auto SKU: —")

    def validate(self) -> str:
        model = self.model_combo.currentText().strip()
        if not model or model == "-- Select Model --":
            return "Please select or enter the scooter model name."
        if not self.part_input.text():
            return "Please enter the part name."
        return ""

    def get_data(self) -> dict:
        model  = self.model_combo.currentText().strip()
        if model == "-- Select Model --":
            model = ""
        part   = self.part_input.text()
        colour = self.colour_input.text().strip()
        return {
            "date":        self.date_input.date().toString("yyyy-MM-dd"),
            "model":       model,
            "part":        part,
            "colour":      colour,
            "quantity":    self.qty_spin.value(),
            "sku":         generate_sku(model, part, colour),
            "location_id": self.location_combo.currentData() or None,
        }


# ── DEFECTIVE FORM ────────────────────────────────────────────

class DefectiveForm(QWidget):
    def __init__(self, model_names, part_names, parent=None):
        super().__init__(parent)
        self._model_names = model_names
        self._part_names  = part_names
        self._build_ui()

    def _build_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        layout.setHorizontalSpacing(16)

        lbl  = "font-size:13px; font-weight:500; color:#374151;"
        inp  = ("border:1px solid #ddd; border-radius:4px;"
                "padding:0 8px; color:#1a1a1a; background:white;")
        spin = ("color:#1a1a1a; background:white; border:1px solid #ddd;"
                "border-radius:4px; padding:0 8px;")

        # Model — blank first item
        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(36)
        self.model_combo.setStyleSheet(inp)
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model_combo.lineEdit().setPlaceholderText(
            "Select or type model name..."
        )
        self.model_combo.lineEdit().setStyleSheet("color:#1a1a1a;")
        self.model_combo.addItem("-- Select Model --", "")
        self.model_combo.addItems(self._model_names)
        self.model_combo.setCurrentIndex(0)
        self.model_combo.lineEdit().clear()  # ← add this line
        m = QLabel("Scooter Model *"); m.setStyleSheet(lbl)
        layout.addRow(m, self.model_combo)

        # Part
        self.part_input = SearchableInput("Type or select part name...")
        self.part_input.set_items(self._part_names)
        p = QLabel("Part Name *"); p.setStyleSheet(lbl)
        layout.addRow(p, self.part_input)

        # Quantity
        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(999999)
        self.qty_spin.setValue(1)
        self.qty_spin.setStyleSheet(spin)
        q = QLabel("Quantity *"); q.setStyleSheet(lbl)
        layout.addRow(q, self.qty_spin)

        # Type
        self.type_combo = QComboBox()
        self.type_combo.setFixedHeight(36)
        self.type_combo.setStyleSheet(inp)
        self.type_combo.addItem("Defective (faulty / not working)", "defective")
        self.type_combo.addItem("Damaged (physically damaged)",     "damaged")
        t = QLabel("Type *"); t.setStyleSheet(lbl)
        layout.addRow(t, self.type_combo)

        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)
        self.notes_input.setPlaceholderText("Optional: describe the issue...")
        self.notes_input.setStyleSheet("color:#1a1a1a;")
        n = QLabel("Notes"); n.setStyleSheet(lbl)
        layout.addRow(n, self.notes_input)

    def validate(self) -> str:
        model = self.model_combo.currentText().strip()
        if not model or model == "-- Select Model --":
            return "Please select or enter the scooter model name."
        if not self.part_input.text():
            return "Please enter the part name."
        return ""

    def get_data(self) -> dict:
        model = self.model_combo.currentText().strip()
        if model == "-- Select Model --":
            model = ""
        return {
            "model":    model,
            "part":     self.part_input.text(),
            "quantity": self.qty_spin.value(),
            "type":     self.type_combo.currentData(),
            "notes":    self.notes_input.toPlainText().strip(),
        }


# ── ADD STOCK DIALOG ──────────────────────────────────────────

class AddItemDialog(QDialog):
    def __init__(self, parent=None, existing_items=None,
                 model_names=None, locations=None):
        super().__init__(parent)
        self.existing_items = existing_items or []
        self.result_data    = {}
        self.model_names    = model_names or []
        self.locations      = locations   or []
        self.part_names     = sorted(set(
            i.get("item_name", "") for i in self.existing_items
            if i.get("item_name")
        ))
        self.setWindowTitle("Add Stock Entry")
        self.setFixedWidth(560)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        type_row = QHBoxLayout()
        tl = QLabel("Entry Type:")
        tl.setStyleSheet("font-size:13px; font-weight:500; color:#374151;")
        type_row.addWidget(tl)

        self.type_combo = QComboBox()
        self.type_combo.setFixedHeight(36)
        self.type_combo.addItem("📥  Import  (new stock arrived)", "import")
        self.type_combo.addItem("⚠️   Defective / Damaged",        "defective")
        self.type_combo.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px;"
            "padding:0 8px; color:#1a1a1a; font-size:13px;"
        )
        self.type_combo.currentIndexChanged.connect(self._on_type_change)
        type_row.addWidget(self.type_combo, 1)
        layout.addLayout(type_row)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color:#e5e7eb;")
        layout.addWidget(div)

        self.stack = QStackedWidget()
        self.import_form    = ImportForm(
            self.model_names, self.part_names, self.locations
        )
        self.defective_form = DefectiveForm(
            self.model_names, self.part_names
        )
        self.stack.addWidget(self.import_form)
        self.stack.addWidget(self.defective_form)
        layout.addWidget(self.stack)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px;"
            "color:#666; font-size:13px;"
        )

        self.save_btn = QPushButton("Save Import")
        self.save_btn.setFixedHeight(38)
        self.save_btn.setDefault(True)
        self.save_btn.setAutoDefault(True)
        self.save_btn.setStyleSheet(
            "background:#2563eb; color:white; border:none;"
            "border-radius:6px; font-weight:600; font-size:13px;"
        )
        self.save_btn.clicked.connect(self._save)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

    def _on_type_change(self, index):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.save_btn.setText("Save Import")
            self.save_btn.setStyleSheet(
                "background:#2563eb; color:white; border:none;"
                "border-radius:6px; font-weight:600; font-size:13px;"
            )
        else:
            self.save_btn.setText("Record Defective / Damaged")
            self.save_btn.setStyleSheet(
                "background:#dc2626; color:white; border:none;"
                "border-radius:6px; font-weight:600; font-size:13px;"
            )

    def _save(self):
        entry_type = self.type_combo.currentData()
        if entry_type == "import":
            error = self.import_form.validate()
            if error:
                QMessageBox.warning(self, "Missing Fields", error)
                return
            self.result_data = {
                "entry_type": "import",
                **self.import_form.get_data()
            }
        else:
            error = self.defective_form.validate()
            if error:
                QMessageBox.warning(self, "Missing Fields", error)
                return
            self.result_data = {
                "entry_type": "defective",
                **self.defective_form.get_data()
            }
        self.accept()


# ── MOVE STOCK DIALOG ─────────────────────────────────────────

class MoveStockDialog(QDialog):
    def __init__(self, parent, item, location_stocks, all_locations):
        super().__init__(parent)
        self.item            = item
        self.location_stocks = location_stocks
        self.all_locations   = all_locations
        self.setWindowTitle(f"Move Stock — {item['item_name']}")
        self.setFixedWidth(460)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            f"Total stock: {self.item['remaining_quantity']} pcs"
        )
        info.setStyleSheet(
            "background:#eff6ff; color:#1d4ed8;"
            "padding:8px 12px; border-radius:6px;"
        )
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setHorizontalSpacing(16)

        lbl  = "font-size:13px; font-weight:500; color:#374151;"
        inp  = ("border:1px solid #ddd; border-radius:4px;"
                "padding:0 8px; color:#1a1a1a; background:white;")
        spin = ("color:#1a1a1a; background:white; border:1px solid #ddd;"
                "border-radius:4px; padding:0 8px;")

        # From location
        self.from_combo = QComboBox()
        self.from_combo.setFixedHeight(36)
        self.from_combo.setStyleSheet(inp)
        for ls in self.location_stocks:
            icon = {"factory": "🏭", "warehouse": "🏢",
                    "godown": "📦"}.get(ls.get("location_type", ""), "📍")
            self.from_combo.addItem(
                f"{icon}  {ls['location_name']}  ({ls['quantity']} pcs)",
                ls["location_id"]
            )
        self.from_combo.currentIndexChanged.connect(self._update_max)
        fl = QLabel("From Location *"); fl.setStyleSheet(lbl)
        form.addRow(fl, self.from_combo)

        # To location
        self.to_combo = QComboBox()
        self.to_combo.setFixedHeight(36)
        self.to_combo.setStyleSheet(inp)
        for loc in self.all_locations:
            icon = {"factory": "🏭", "warehouse": "🏢",
                    "godown": "📦"}.get(loc.get("location_type", ""), "📍")
            self.to_combo.addItem(
                f"{icon}  {loc['name']}", loc["id"]
            )
        tl = QLabel("To Location *"); tl.setStyleSheet(lbl)
        form.addRow(tl, self.to_combo)

        # Quantity
        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(
            self.location_stocks[0]["quantity"]
            if self.location_stocks else 1
        )
        self.qty_spin.setStyleSheet(spin)
        ql = QLabel("Quantity *"); ql.setStyleSheet(lbl)
        form.addRow(ql, self.qty_spin)

        # Available hint
        self.avail_label = QLabel("")
        self.avail_label.setStyleSheet(
            "color:#6b7280; font-size:11px; font-style:italic;"
        )
        self._update_max(0)
        form.addRow("", self.avail_label)

        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)
        self.notes_input.setPlaceholderText("Optional notes...")
        self.notes_input.setStyleSheet("color:#1a1a1a;")
        nl = QLabel("Notes"); nl.setStyleSheet(lbl)
        form.addRow(nl, self.notes_input)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px;"
            "color:#666; font-size:13px;"
        )

        move_btn = QPushButton("Move Stock")
        move_btn.setFixedHeight(38)
        move_btn.setDefault(True)
        move_btn.setStyleSheet(
            "background:#7c3aed; color:white; border:none;"
            "border-radius:6px; font-weight:600; font-size:13px;"
        )
        move_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(move_btn)
        layout.addLayout(btn_row)

    def _update_max(self, index):
        if index < len(self.location_stocks):
            available = self.location_stocks[index]["quantity"]
            self.qty_spin.setMaximum(available)
            self.avail_label.setText(
                f"Available at this location: {available} pcs"
            )

    def get_data(self) -> dict:
        return {
            "from_location_id": self.from_combo.currentData(),
            "to_location_id":   self.to_combo.currentData(),
            "quantity":         self.qty_spin.value(),
            "notes":            self.notes_input.toPlainText().strip() or None
        }


# ── ADJUST STOCK DIALOG ───────────────────────────────────────

class AdjustDialog(QDialog):
    def __init__(self, parent, item):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle(f"Update Stock — {item['item_name']}")
        self.setFixedWidth(420)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            f"Current stock: {self.item['remaining_quantity']} pcs"
        )
        info.setStyleSheet(
            "background:#eff6ff; color:#1d4ed8;"
            "padding:8px 12px; border-radius:6px;"
        )
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setHorizontalSpacing(16)

        lbl = "font-size:13px; font-weight:500; color:#374151;"
        inp = ("border:1px solid #ddd; border-radius:4px;"
               "padding:0 8px; color:#1a1a1a; background:white;")

        self.type_combo = QComboBox()
        self.type_combo.setFixedHeight(36)
        self.type_combo.setStyleSheet(inp)
        self.type_combo.addItem("Consumed (used in production)", "consumed")
        self.type_combo.addItem("Defective (faulty item)",       "defective")
        self.type_combo.addItem("Damaged (physically damaged)",  "damaged")
        if Session.role in ["superadmin", "manager"]:
            self.type_combo.addItem(
                "Manual Adjustment (add stock)", "adjusted"
            )
        al = QLabel("Action"); al.setStyleSheet(lbl)
        form.addRow(al, self.type_combo)

        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(999999)
        self.qty_spin.setStyleSheet(
            "color:#1a1a1a; background:white; border:1px solid #ddd;"
            "border-radius:4px; padding:0 8px;"
        )
        ql = QLabel("Quantity"); ql.setStyleSheet(lbl)
        form.addRow(ql, self.qty_spin)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(70)
        self.notes_input.setPlaceholderText("Optional notes...")
        self.notes_input.setStyleSheet("color:#1a1a1a;")
        nl = QLabel("Notes"); nl.setStyleSheet(lbl)
        form.addRow(nl, self.notes_input)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px;"
            "color:#666; font-size:13px;"
        )

        save_btn = QPushButton("Update Stock")
        save_btn.setFixedHeight(38)
        save_btn.setDefault(True)
        save_btn.setAutoDefault(True)
        save_btn.setStyleSheet(
            "background:#16a34a; color:white; border:none;"
            "border-radius:6px; font-weight:600; font-size:13px;"
        )
        save_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)


# ── LOCATION BREAKDOWN WIDGET ─────────────────────────────────

class LocationBreakdownWidget(QWidget):
    def __init__(self, location_stocks: list, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#f8fafc;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 4, 8, 4)
        layout.setSpacing(8)

        if not location_stocks:
            lbl = QLabel("No location data recorded")
            lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
            layout.addWidget(lbl)
            return

        type_icons = {
            "factory":   "🏭",
            "warehouse": "🏢",
            "godown":    "📦"
        }

        for ls in location_stocks:
            icon  = type_icons.get(ls.get("location_type", ""), "📍")
            badge = QLabel(
                f"{icon} {ls['location_name']}: {ls['quantity']} pcs"
            )
            badge.setStyleSheet("""
                background:#f0fdf4; color:#166534;
                border:1px solid #bbf7d0;
                border-radius:4px;
                padding:3px 10px;
                font-size:12px;
                font-weight:500;
            """)
            layout.addWidget(badge)

        layout.addStretch()


# ── MAIN INVENTORY SCREEN ─────────────────────────────────────

class InventoryScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items          = []
        self.workers        = []
        self.expanded_rows  = {}
        self.location_cache = {}
        self._build_ui()
        self._load_summary()
        self._load_items()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("📦 Inventory")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        header_row.addWidget(title)
        header_row.addStretch()

        if Session.role in ["superadmin", "manager"]:
            add_btn = QPushButton("+ Add Stock Entry")
            add_btn.setFixedHeight(36)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setStyleSheet("""
                QPushButton {
                    background:#2563eb; color:white; border:none;
                    border-radius:6px; padding:0 16px; font-weight:600;
                }
                QPushButton:hover { background:#1d4ed8; }
            """)
            add_btn.clicked.connect(self._add_stock_entry)
            header_row.addWidget(add_btn)

        layout.addLayout(header_row)

        # Summary cards
        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)
        self.total_card     = self._stat_card("Total Items",     "—", "#2563eb")
        self.low_card       = self._stat_card("Low Stock",       "—", "#dc2626")
        self.consumed_card  = self._stat_card("Total Consumed",  "—", "#f59e0b")
        self.defective_card = self._stat_card("Total Defective", "—", "#7c3aed")
        for c in [self.total_card, self.low_card,
                  self.consumed_card, self.defective_card]:
            summary_row.addWidget(c)
        layout.addLayout(summary_row)

        # Filters
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "🔍  Search by part name, model or SKU..."
        )
        self.search_input.setFixedHeight(36)
        self.search_input.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px;"
            "padding:0 10px; color:#1a1a1a;"
        )
        self.search_input.textChanged.connect(self._load_items)

        self.low_stock_btn = QPushButton("⚠ Low Stock Only")
        self.low_stock_btn.setFixedHeight(36)
        self.low_stock_btn.setCheckable(True)
        self.low_stock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.low_stock_btn.setStyleSheet("""
            QPushButton {
                border:1px solid #ddd; border-radius:6px;
                padding:0 12px; color:#666;
            }
            QPushButton:checked {
                background:#fef3c7; border-color:#f59e0b; color:#92400e;
            }
        """)
        self.low_stock_btn.clicked.connect(self._load_items)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setFixedHeight(36)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px;"
            "padding:0 12px; color:#666;"
        )
        refresh_btn.clicked.connect(self._refresh)

        filter_row.addWidget(self.search_input, 1)
        filter_row.addWidget(self.low_stock_btn)
        filter_row.addWidget(refresh_btn)
        layout.addLayout(filter_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "", "Part Name", "Model", "Colour",
            "SKU", "Total Stock", "Consumed", "Defective", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(0, 50)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            8, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 140)
        self.table.setColumnWidth(5, 90)
        self.table.setColumnWidth(6, 90)
        self.table.setColumnWidth(7, 90)
        self.table.setColumnWidth(8, 240)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget {
                border:1px solid #e5e7eb;
                border-radius:8px;
                gridline-color:#f3f4f6;
            }
            QHeaderView::section {
                background:#f8fafc; padding:8px;
                border:none; border-bottom:1px solid #e5e7eb;
                font-weight:600; color:#374151;
            }
            QTableWidget::item {
                padding:6px 8px; color:#1a1a1a;
            }
            QTableWidget::item:alternate { background:#f9fafb; }
            QTableWidget::item:selected {
                background:#eff6ff; color:#1a1a1a;
            }
            QTableWidget::item:hover {
                background:transparent;
            }
        """)
        layout.addWidget(self.table)

        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet("color:#94a3b8; font-size:12px;")
        layout.addWidget(self.status_label)

    def _stat_card(self, title, value, color):
        card = QFrame()
        card.setFixedHeight(80)
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
        val.setFont(QFont("Arial", 20, QFont.Weight.Bold))
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

    # ── LOADING ───────────────────────────────────────────────

    def _load_summary(self):
        worker = LoadSummaryWorker()
        worker.done.connect(self._on_summary)
        self.workers.append(worker)
        worker.start()

    def _on_summary(self, data):
        self._update_card(self.total_card,
                          data.get("total_items",     "—"))
        self._update_card(self.low_card,
                          data.get("low_stock_count", "—"))
        self._update_card(self.consumed_card,
                          data.get("total_consumed",  "—"))
        self._update_card(self.defective_card,
                          data.get("total_defective", "—"))

    def _load_items(self):
        self.status_label.setText("Loading...")
        self.table.setRowCount(0)
        self.expanded_rows = {}
        worker = LoadInventoryWorker(
            search=self.search_input.text().strip(),
            low_stock=self.low_stock_btn.isChecked()
        )
        worker.done.connect(self._populate_table)
        worker.error.connect(
            lambda e: self.status_label.setText(f"Error: {e}")
        )
        self.workers.append(worker)
        worker.start()

    def _refresh(self):
        self.location_cache = {}
        self._load_summary()
        self._load_items()

    def _populate_table(self, items):
        self.items = items
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            remaining = item["remaining_quantity"]
            threshold = item["low_stock_threshold"]
            is_low    = remaining <= threshold

            def cell(text, align=Qt.AlignmentFlag.AlignLeft):
                c = QTableWidgetItem(str(text) if text else "—")
                c.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                if is_low:
                    c.setBackground(QColor("#fee2e2"))
                    c.setForeground(QColor("#991b1b"))
                return c

            # Expand button
            expand_btn = QPushButton("▶")
            expand_btn.setFixedSize(30, 30)
            expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            expand_btn.setStyleSheet("""
                QPushButton {
                    background:#f1f5f9; color:#475569;
                    border:1px solid #e2e8f0;
                    border-radius:4px; font-size:11px;
                    font-weight:bold;
                }
                QPushButton:hover { background:#e2e8f0; }
            """)
            expand_btn.clicked.connect(
                lambda _, i=item, r=row, b=expand_btn:
                self._toggle_expand(i, r, b)
            )
            expand_widget = QWidget()
            expand_layout = QHBoxLayout(expand_widget)
            expand_layout.setContentsMargins(3, 0, 0, 0)
            expand_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            expand_layout.addWidget(expand_btn)
            self.table.setCellWidget(row, 0, expand_widget)

            self.table.setItem(row, 1, cell(item.get("item_name",  "")))
            self.table.setItem(row, 2, cell(item.get("model_name", "")))
            self.table.setItem(row, 3, cell(item.get("colour",     "")))
            self.table.setItem(row, 4, cell(item.get("sku",        "")))

            rem_cell = QTableWidgetItem(str(remaining))
            rem_cell.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter |
                Qt.AlignmentFlag.AlignVCenter
            )
            if is_low:
                rem_cell.setForeground(QColor("#ffffff"))
                rem_cell.setBackground(QColor("#dc2626"))
            self.table.setItem(row, 5, rem_cell)

            self.table.setItem(
                row, 6,
                cell(item["consumed_quantity"],
                     Qt.AlignmentFlag.AlignCenter)
            )
            self.table.setItem(
                row, 7,
                cell(item["defective_quantity"],
                     Qt.AlignmentFlag.AlignCenter)
            )

            # Action buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(4)

            update_btn = QPushButton("Update")
            update_btn.setFixedHeight(30)
            update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            update_btn.setStyleSheet("""
                QPushButton {
                    background:#16a34a; color:white; border:none;
                    border-radius:4px; font-size:11px; padding:0 8px;
                }
                QPushButton:hover { background:#15803d; }
            """)
            update_btn.clicked.connect(
                lambda _, i=item: self._adjust_stock(i)
            )
            btn_layout.addWidget(update_btn)

            if Session.role in ["superadmin", "manager"]:
                move_btn = QPushButton("Move")
                move_btn.setFixedHeight(30)
                move_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                move_btn.setStyleSheet("""
                    QPushButton {
                        background:#7c3aed; color:white; border:none;
                        border-radius:4px; font-size:11px; padding:0 8px;
                    }
                    QPushButton:hover { background:#6d28d9; }
                """)
                move_btn.clicked.connect(
                    lambda _, i=item: self._move_stock(i)
                )
                btn_layout.addWidget(move_btn)

                delete_btn = QPushButton("Delete")
                delete_btn.setFixedHeight(30)
                delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                delete_btn.setStyleSheet("""
                    QPushButton {
                        background:#dc2626; color:white; border:none;
                        border-radius:4px; font-size:11px; padding:0 8px;
                    }
                    QPushButton:hover { background:#b91c1c; }
                """)
                delete_btn.clicked.connect(
                    lambda _, i=item: self._delete_item(i)
                )
                btn_layout.addWidget(delete_btn)

            self.table.setCellWidget(row, 8, btn_widget)

        low_count = sum(
            1 for i in items
            if i["remaining_quantity"] <= i["low_stock_threshold"]
        )
        self.status_label.setText(
            f"{len(items)} items loaded"
            + (f"  •  ⚠ {low_count} low stock" if low_count else "")
        )

    # ── EXPAND / COLLAPSE ─────────────────────────────────────

    def _toggle_expand(self, item, row, btn):
        item_id = item["id"]

        if item_id in self.expanded_rows:
            exp_row = self.expanded_rows.pop(item_id)
            self.table.removeRow(exp_row)
            for k in list(self.expanded_rows.keys()):
                if self.expanded_rows[k] > exp_row:
                    self.expanded_rows[k] -= 1
            btn.setText("▶")
            return

        btn.setText("▼")

        offset  = sum(1 for v in self.expanded_rows.values() if v <= row)
        exp_row = row + 1 + offset

        self.table.insertRow(exp_row)
        self.table.setRowHeight(exp_row, 44)
        self.table.setSpan(exp_row, 1, 1, 8)
        self.expanded_rows[item_id] = exp_row

        # Loading widget
        loading_widget = QWidget()
        loading_widget.setStyleSheet("background:#f8fafc;")
        loading_layout = QHBoxLayout(loading_widget)
        loading_layout.setContentsMargins(16, 0, 0, 0)
        loading_lbl = QLabel("Loading location breakdown...")
        loading_lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
        loading_layout.addWidget(loading_lbl)
        self.table.setCellWidget(exp_row, 1, loading_widget)

        if item_id in self.location_cache:
            self._show_location_breakdown(
                item_id, self.location_cache[item_id]
            )
        else:
            worker = LoadLocationStockWorker(item_id)
            worker.done.connect(self._on_location_loaded)
            self.workers.append(worker)
            worker.start()

    def _on_location_loaded(self, item_id: str, stocks: list):
        self.location_cache[item_id] = stocks
        self._show_location_breakdown(item_id, stocks)

    def _show_location_breakdown(self, item_id: str, stocks: list):
        if item_id not in self.expanded_rows:
            return
        exp_row = self.expanded_rows[item_id]
        breakdown = LocationBreakdownWidget(stocks)
        self.table.setCellWidget(exp_row, 1, breakdown)

    # ── ACTIONS ───────────────────────────────────────────────

    def _add_stock_entry(self):
        try:
            models      = APIClient.get("/master/models")
            model_names = [m["model_name"] for m in models]
        except APIError:
            model_names = []

        try:
            locations = APIClient.get("/master/locations")
        except APIError:
            locations = []

        dlg = AddItemDialog(
            self,
            existing_items=self.items,
            model_names=model_names,
            locations=locations
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data       = dlg.result_data
            entry_type = data["entry_type"]

            try:
                if entry_type == "import":
                    APIClient.post("/inventory/items", {
                        "item_name":           data["part"],
                        "sku":                 data["sku"],
                        "unit":                "pcs",
                        "total_quantity":      data["quantity"],
                        "low_stock_threshold": 10,
                        "is_spare_part":       False,
                        "model_name":          data["model"],
                        "colour":              data["colour"] or None,
                        "import_date":         data["date"],
                        "location_id":         data.get("location_id"),
                    })
                    QMessageBox.information(
                        self, "Stock Added",
                        f"Stock added successfully.\n"
                        f"Part     : {data['part']}\n"
                        f"Model    : {data['model']}\n"
                        f"Quantity : {data['quantity']} pcs"
                    )
                else:
                    existing = next(
                        (i for i in self.items
                         if data["part"].lower() in
                         i["item_name"].lower()
                         and data["model"].lower() in
                         (i.get("model_name") or "").lower()),
                        None
                    )
                    if not existing:
                        QMessageBox.warning(
                            self, "Part Not Found",
                            f"No part named '{data['part']}' found "
                            f"for model '{data['model']}'.\n"
                            "Please add it via Import first."
                        )
                        return

                    APIClient.post("/inventory/adjust", {
                        "item_id":       existing["id"],
                        "quantity":      data["quantity"],
                        "movement_type": data["type"],
                        "notes":         data["notes"] or None,
                    })
                    QMessageBox.information(
                        self, "Recorded",
                        f"{data['quantity']} pcs marked as "
                        f"{data['type']}.\nPart : {data['part']}"
                    )

                self.location_cache = {}
                self._load_items()
                self._load_summary()

            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _move_stock(self, item):
        try:
            location_stocks = APIClient.get(
                f"/inventory/items/{item['id']}/locations"
            )
        except APIError as e:
            QMessageBox.critical(self, "Error", e.message)
            return

        if not location_stocks:
            QMessageBox.warning(
                self, "No Location Data",
                "This item has no location breakdown yet.\n"
                "Add it via Import with a location selected first."
            )
            return

        try:
            all_locations = APIClient.get("/master/locations")
        except APIError:
            all_locations = []

        dlg = MoveStockDialog(
            self, item, location_stocks, all_locations
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            move_data = dlg.get_data()
            if move_data["from_location_id"] == move_data["to_location_id"]:
                QMessageBox.warning(
                    self, "Invalid",
                    "From and To locations cannot be the same."
                )
                return
            try:
                result = APIClient.post("/inventory/move", {
                    "item_id":          item["id"],
                    "from_location_id": move_data["from_location_id"],
                    "to_location_id":   move_data["to_location_id"],
                    "quantity":         move_data["quantity"],
                    "notes":            move_data["notes"],
                })
                QMessageBox.information(
                    self, "Moved",
                    f"Successfully moved {move_data['quantity']} pcs.\n"
                    f"From : {result.get('from', '')}\n"
                    f"To   : {result.get('to', '')}"
                )
                self.location_cache = {}
                self._load_items()
                self._load_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _adjust_stock(self, item):
        dlg = AdjustDialog(self, item)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.post("/inventory/adjust", {
                    "item_id":       item["id"],
                    "quantity":      dlg.qty_spin.value(),
                    "movement_type": dlg.type_combo.currentData(),
                    "notes":         dlg.notes_input.toPlainText().strip()
                                     or None,
                })
                QMessageBox.information(
                    self, "Success", "Stock updated successfully."
                )
                self.location_cache = {}
                self._load_items()
                self._load_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _delete_item(self, item):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete:\n\n"
            f"Part  : {item['item_name']}\n"
            f"Model : {item.get('model_name', '')}\n\n"
            f"This will deactivate the item.\n"
            f"Stock history is kept.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.delete(f"/inventory/items/{item['id']}")
                QMessageBox.information(
                    self, "Deleted",
                    f"'{item['item_name']}' removed from inventory."
                )
                self.location_cache = {}
                self._load_items()
                self._load_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)