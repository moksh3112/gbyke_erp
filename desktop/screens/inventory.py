from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QDialog, QFormLayout,
    QSpinBox, QMessageBox, QHeaderView, QFrame,
    QTextEdit, QAbstractItemView, QCompleter,
    QStackedWidget, QDateEdit, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QStringListModel, QDate, QPoint
from PyQt6.QtGui import QFont, QColor, QAction
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


class LoadItemHistoryWorker(QThread):
    done = pyqtSignal(str, dict, list)

    def __init__(self, item_id: str):
        super().__init__()
        self.item_id = item_id

    def run(self):
        try:
            movements = APIClient.get(
                f"/inventory/movements/{self.item_id}"
            )
            locations = APIClient.get(
                f"/inventory/items/{self.item_id}/locations"
            )
            self.done.emit(self.item_id, movements, locations)
        except APIError:
            self.done.emit(self.item_id, {}, [])


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
        self._completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self.input.setCompleter(self._completer)
        layout.addWidget(self.input)

    def set_items(self, items: list):
        self._completer.setModel(QStringListModel(items))

    def text(self) -> str:
        return self.input.text().strip()

    def setText(self, text: str):
        self.input.setText(text)


# ── HELPER: model combo setup ─────────────────────────────────

def _setup_model_combo(combo: QComboBox, model_names: list):
    """Simple non-editable dropdown."""
    inp = ("border:1px solid #ddd; border-radius:4px;"
           "padding:0 8px; color:#1a1a1a; background:white;")
    combo.setStyleSheet(inp)
    combo.setEditable(False)
    combo.addItem("-- Select Model --", "")
    for name in model_names:
        combo.addItem(name, name)
    combo.setCurrentIndex(0)


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

        # Model — simple dropdown
        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(36)
        _setup_model_combo(self.model_combo, self._model_names)
        self.model_combo.currentIndexChanged.connect(self._update_sku)
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
        model  = self.model_combo.currentData() or ""
        part   = self.part_input.text()
        colour = self.colour_input.text().strip()
        if model and part:
            self.sku_label.setText(
                f"Auto SKU: {generate_sku(model, part, colour)}"
            )
        else:
            self.sku_label.setText("Auto SKU: —")

    def validate(self) -> str:
        if not self.model_combo.currentData():
            return "Please select the scooter model name."
        if not self.part_input.text():
            return "Please enter the part name."
        return ""

    def get_data(self) -> dict:
        model  = self.model_combo.currentData() or ""
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

        # Model — simple dropdown
        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(36)
        _setup_model_combo(self.model_combo, self._model_names)
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

        # Damage stage
        self.stage_combo = QComboBox()
        self.stage_combo.setFixedHeight(36)
        self.stage_combo.setStyleSheet(inp)
        self.stage_combo.addItem("📥  During Purchase",      "during_import")
        self.stage_combo.addItem("🏭  During Manufacturing", "during_manufacturing")
        self.stage_combo.addItem("🏢  During Storage",       "during_storage")
        sl = QLabel("Damage Stage *"); sl.setStyleSheet(lbl)
        layout.addRow(sl, self.stage_combo)

        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(50)
        self.notes_input.setPlaceholderText("Optional: any additional details...")
        self.notes_input.setStyleSheet("color:#1a1a1a;")
        n = QLabel("Notes"); n.setStyleSheet(lbl)
        layout.addRow(n, self.notes_input)

    def validate(self) -> str:
        if not self.model_combo.currentData():
            return "Please select the scooter model name."
        if not self.part_input.text():
            return "Please enter the part name."
        return ""

    def get_data(self) -> dict:
        return {
            "model":        self.model_combo.currentData() or "",
            "part":         self.part_input.text(),
            "quantity":     self.qty_spin.value(),
            "type":         self.type_combo.currentData(),
            "damage_stage": self.stage_combo.currentData(),
            "notes":        self.notes_input.toPlainText().strip(),
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
        self.type_combo.addItem("📥  Purchase  (new stock arrived)", "purchase")
        self.type_combo.addItem("⚠️   Defective / Damaged",          "defective")
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

        self.save_btn = QPushButton("Save Purchase")
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
            self.save_btn.setText("Save Purchase")
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
        if entry_type == "purchase":
            error = self.import_form.validate()
            if error:
                QMessageBox.warning(self, "Missing Fields", error)
                return
            self.result_data = {
                "entry_type": "purchase",
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


# ── UPDATE STOCK DIALOG ───────────────────────────────────────

class UpdateStockDialog(QDialog):
    def __init__(self, parent, item, locations=None):
        super().__init__(parent)
        self.item      = item
        self.locations = locations or []
        self.setWindowTitle(f"Update Stock — {item['item_name']}")
        self.setFixedWidth(440)
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

        # Action type
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
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        al = QLabel("Action"); al.setStyleSheet(lbl)
        form.addRow(al, self.type_combo)

        # Quantity
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

        # Location
        self.location_combo = QComboBox()
        self.location_combo.setFixedHeight(36)
        self.location_combo.setStyleSheet(inp)
        self.location_combo.addItem("-- Select Location --", "")
        for loc in self.locations:
            icon = {"factory": "🏭", "warehouse": "🏢",
                    "godown": "📦"}.get(loc.get("location_type", ""), "📍")
            self.location_combo.addItem(
                f"{icon}  {loc['location_name']}  ({loc['quantity']} pcs)",
                loc["location_id"]
            )
        self.location_lbl = QLabel("From Location")
        self.location_lbl.setStyleSheet(lbl)
        form.addRow(self.location_lbl, self.location_combo)

        # Damage stage
        self.stage_combo = QComboBox()
        self.stage_combo.setFixedHeight(36)
        self.stage_combo.setStyleSheet(inp)
        self.stage_combo.addItem("-- Select Stage --",           "")
        self.stage_combo.addItem("📥  During Purchase",          "during_import")
        self.stage_combo.addItem("🏭  During Manufacturing",     "during_manufacturing")
        self.stage_combo.addItem("🏢  During Storage",           "during_storage")
        self.stage_lbl = QLabel("Damage Stage")
        self.stage_lbl.setStyleSheet(lbl)
        form.addRow(self.stage_lbl, self.stage_combo)

        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)
        self.notes_input.setPlaceholderText("Optional notes...")
        self.notes_input.setStyleSheet("color:#1a1a1a;")
        nl = QLabel("Notes"); nl.setStyleSheet(lbl)
        form.addRow(nl, self.notes_input)

        layout.addLayout(form)
        self._on_type_changed(0)

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

    def _on_type_changed(self, index):
        movement_type = self.type_combo.currentData()
        is_damage     = movement_type in ["defective", "damaged"]
        is_add        = movement_type == "adjusted"

        self.stage_combo.setVisible(is_damage)
        self.stage_lbl.setVisible(is_damage)

        # Update location label based on action
        if is_add:
            self.location_lbl.setText("To Location")
        else:
            self.location_lbl.setText("From Location")
# ── EDIT DETAILS DIALOG ───────────────────────────────────────

class EditDetailsDialog(QDialog):
    def __init__(self, parent, item, model_names):
        super().__init__(parent)
        self.item        = item
        self.model_names = model_names
        self.result_data = {}
        self.setWindowTitle(f"Edit Details — {item['item_name']}")
        self.setFixedWidth(460)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            "Edit part details. Stock quantities are not affected."
        )
        info.setStyleSheet(
            "background:#fef9c3; color:#854d0e;"
            "padding:8px 12px; border-radius:6px; font-size:12px;"
        )
        info.setWordWrap(True)
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

        # Part name
        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(36)
        self.name_input.setStyleSheet(inp)
        self.name_input.setText(self.item.get("item_name", ""))
        nl = QLabel("Part Name *"); nl.setStyleSheet(lbl)
        form.addRow(nl, self.name_input)

        # Model — simple dropdown
        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(36)
        self.model_combo.setStyleSheet(inp)
        self.model_combo.addItem("-- Select Model --", "")
        for name in self.model_names:
            self.model_combo.addItem(name, name)
        # Pre-select current model
        current_model = self.item.get("model_name", "")
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == current_model:
                self.model_combo.setCurrentIndex(i)
                break
        ml = QLabel("Scooter Model *"); ml.setStyleSheet(lbl)
        form.addRow(ml, self.model_combo)

        # Colour
        self.colour_input = QLineEdit()
        self.colour_input.setFixedHeight(36)
        self.colour_input.setStyleSheet(inp)
        self.colour_input.setText(self.item.get("colour") or "")
        self.colour_input.setPlaceholderText("Leave blank if no colour")
        cl = QLabel("Colour"); cl.setStyleSheet(lbl)
        form.addRow(cl, self.colour_input)

        # Low stock threshold
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setFixedHeight(36)
        self.threshold_spin.setMinimum(1)
        self.threshold_spin.setMaximum(999999)
        self.threshold_spin.setValue(
            self.item.get("low_stock_threshold", 10)
        )
        self.threshold_spin.setStyleSheet(
            "color:#1a1a1a; background:white; border:1px solid #ddd;"
            "border-radius:4px; padding:0 8px;"
        )
        tl = QLabel("Low Stock Alert At"); tl.setStyleSheet(lbl)
        form.addRow(tl, self.threshold_spin)

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

        save_btn = QPushButton("Save Changes")
        save_btn.setFixedHeight(38)
        save_btn.setDefault(True)
        save_btn.setStyleSheet(
            "background:#2563eb; color:white; border:none;"
            "border-radius:6px; font-weight:600; font-size:13px;"
        )
        save_btn.clicked.connect(self._save)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _save(self):
        name  = self.name_input.text().strip()
        model = self.model_combo.currentData() or ""
        if not name:
            QMessageBox.warning(self, "Missing", "Part name is required.")
            return
        if not model:
            QMessageBox.warning(self, "Missing", "Please select a model.")
            return
        self.result_data = {
            "item_name":           name,
            "model_name":          model,
            "colour":              self.colour_input.text().strip() or None,
            "low_stock_threshold": self.threshold_spin.value(),
        }
        self.accept()


# ── CORRECT QUANTITY DIALOG ───────────────────────────────────
class CorrectQuantityDialog(QDialog):
    def __init__(self, parent, item, locations=None):
        super().__init__(parent)
        self.item      = item
        self.locations = locations or []
        self.setWindowTitle(f"Correct Quantity — {item['item_name']}")
        self.setFixedWidth(440)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            f"Current stock: {self.item['remaining_quantity']} pcs\n"
            f"Use this to fix a wrong quantity entry.\n"
            f"A correction record will be added to history."
        )
        info.setStyleSheet(
            "background:#fef9c3; color:#854d0e;"
            "padding:8px 12px; border-radius:6px; font-size:12px;"
        )
        info.setWordWrap(True)
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

        # Correction type
        self.direction_combo = QComboBox()
        self.direction_combo.setFixedHeight(36)
        self.direction_combo.setStyleSheet(inp)
        self.direction_combo.addItem(
            "➕  Add quantity  (entered too little)", "add"
        )
        self.direction_combo.addItem(
            "➖  Remove quantity  (entered too much)", "remove"
        )
        self.direction_combo.currentIndexChanged.connect(
            self._on_direction_changed
        )
        dl = QLabel("Correction Type *"); dl.setStyleSheet(lbl)
        form.addRow(dl, self.direction_combo)

        # Quantity
        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(999999)
        self.qty_spin.setStyleSheet(
            "color:#1a1a1a; background:white; border:1px solid #ddd;"
            "border-radius:4px; padding:0 8px;"
        )
        ql = QLabel("Correction Amount *"); ql.setStyleSheet(lbl)
        form.addRow(ql, self.qty_spin)

        # Location
        self.location_combo = QComboBox()
        self.location_combo.setFixedHeight(36)
        self.location_combo.setStyleSheet(inp)
        self.location_combo.addItem("-- Select Location --", "")
        for loc in self.locations:
            icon = {"factory": "🏭", "warehouse": "🏢",
                    "godown": "📦"}.get(loc.get("location_type", ""), "📍")
            self.location_combo.addItem(
                f"{icon}  {loc['location_name']}  ({loc['quantity']} pcs)",
                loc["location_id"]
            )
        self.location_lbl = QLabel("Location *")
        self.location_lbl.setStyleSheet(lbl)
        form.addRow(self.location_lbl, self.location_combo)

        # Reason
        self.reason_input = QTextEdit()
        self.reason_input.setFixedHeight(60)
        self.reason_input.setPlaceholderText(
            "e.g. Typed 1 instead of 100 during purchase"
        )
        self.reason_input.setStyleSheet("color:#1a1a1a;")
        rl = QLabel("Reason *"); rl.setStyleSheet(lbl)
        form.addRow(rl, self.reason_input)

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

        save_btn = QPushButton("Apply Correction")
        save_btn.setFixedHeight(38)
        save_btn.setDefault(True)
        save_btn.setStyleSheet(
            "background:#f59e0b; color:white; border:none;"
            "border-radius:6px; font-weight:600; font-size:13px;"
        )
        save_btn.clicked.connect(self._save)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_direction_changed(self, index):
        direction = self.direction_combo.currentData()
        if direction == "add":
            self.location_lbl.setText("Add To Location *")
        else:
            self.location_lbl.setText("Remove From Location *")

    def _save(self):
        if not self.reason_input.toPlainText().strip():
            QMessageBox.warning(
                self, "Missing",
                "Please enter a reason for the correction."
            )
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "direction":   self.direction_combo.currentData(),
            "quantity":    self.qty_spin.value(),
            "reason":      self.reason_input.toPlainText().strip(),
            "location_id": self.location_combo.currentData() or None,
        }

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

        self.avail_label = QLabel("")
        self.avail_label.setStyleSheet(
            "color:#6b7280; font-size:11px; font-style:italic;"
        )
        self._update_max(0)
        form.addRow("", self.avail_label)

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


# ── ITEM HISTORY WIDGET ───────────────────────────────────────

class ItemHistoryWidget(QWidget):
    def __init__(self, movements: dict, location_stocks: list,
                 parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#f8fafc;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 8, 16, 8)
        layout.setSpacing(8)

        # Locations
        if location_stocks:
            loc_row = QHBoxLayout()
            loc_row.setSpacing(6)
            loc_title = QLabel("📍 Stock Locations:")
            loc_title.setStyleSheet(
                "color:#374151; font-size:12px; font-weight:600;"
            )
            loc_row.addWidget(loc_title)
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
                    border-radius:4px; padding:2px 8px;
                    font-size:12px; font-weight:500;
                """)
                loc_row.addWidget(badge)
            loc_row.addStretch()
            layout.addLayout(loc_row)

            div = QFrame()
            div.setFrameShape(QFrame.Shape.HLine)
            div.setStyleSheet("color:#e5e7eb;")
            layout.addWidget(div)

        # History sections
        history_row = QHBoxLayout()
        history_row.setSpacing(12)
        history_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        purchases  = movements.get("imports",    [])
        defectives = movements.get("defectives", [])
        consumed   = movements.get("consumed",   [])
        transfers  = movements.get("transfers",  [])
        corrections = movements.get("corrections", [])

        if purchases:
            history_row.addWidget(self._section(
                "📥 Purchase History", purchases, "#1d4ed8", "#eff6ff",
                lambda e: (
                    f"📅 {e['created_at']}\n"
                    f"   {e['quantity']} pcs  |  {e['performed_by']}"
                    + (f"\n   {e['notes'][:50]}" if e['notes'] else "")
                )
            ))

        if defectives:
            history_row.addWidget(self._section(
                "⚠️ Defective / Damaged", defectives, "#dc2626", "#fef2f2",
                lambda e: (
                    f"📅 {e['created_at']}\n"
                    f"   {e['quantity']} pcs {e['type']}  |  {e['performed_by']}"
                    + (f"\n   📍 {e['notes']}" if e['notes'] else "")
                )
            ))

        if consumed:
            history_row.addWidget(self._section(
                "🏭 Manufacturing / Consumed", consumed, "#7c3aed", "#f5f3ff",
                lambda e: (
                    f"📅 {e['created_at']}\n"
                    f"   {e['quantity']} pcs  |  {e['performed_by']}"
                    + (f"\n   {e['notes'][:50]}" if e['notes'] else "")
                )
            ))

        if transfers:
            history_row.addWidget(self._section(
                "🔄 Stock Movements", transfers, "#0891b2", "#ecfeff",
                lambda e: (
                    f"📅 {e['created_at']}\n"
                    f"   {e['quantity']} pcs"
                    + (f"\n   {e['notes'][:50]}" if e['notes'] else "")
                )
            ))
        if corrections:
            history_row.addWidget(self._section(
                "⚙️ Quantity Corrections", corrections, "#f59e0b", "#fffbeb",
                lambda e: (
                    f"📅 {e['created_at']}\n"
                    f"   {e['quantity']} pcs  |  {e['performed_by']}"
                    + (f"\n   {e['notes'][2:50]}" if e['notes'] else "")
                )
            ))

        if not any([purchases, defectives, consumed, transfers]):
            no_hist = QLabel("No history recorded yet.")
            no_hist.setStyleSheet("color:#94a3b8; font-size:12px;")
            history_row.addWidget(no_hist)

        layout.addLayout(history_row)

    def _section(self, title, entries, color, bg, fmt):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background:{bg};
                border:1px solid {color}30;
                border-radius:6px;
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color:{color}; font-size:12px; font-weight:600; border:none;"
        )
        lay.addWidget(title_lbl)

        for entry in entries[:5]:
            row_lbl = QLabel(fmt(entry))
            row_lbl.setStyleSheet(
                "color:#374151; font-size:11px; border:none;"
            )
            row_lbl.setWordWrap(True)
            row_lbl.setMinimumWidth(280)
            lay.addWidget(row_lbl)

        if len(entries) > 5:
            more = QLabel(f"+ {len(entries) - 5} more entries")
            more.setStyleSheet(
                f"color:{color}; font-size:11px; font-style:italic; border:none;"
            )
            lay.addWidget(more)

        return frame


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
        self.total_card     = self._stat_card("Total Items",       "—", "#2563eb")
        self.low_card       = self._stat_card("Low Stock",         "—", "#dc2626")
        self.consumed_card  = self._stat_card("Total Consumed",    "—", "#f59e0b")
        self.defective_card = self._stat_card("Total Def/Damaged", "—", "#7c3aed")
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
            "SKU", "Total Stock", "Consumed", "Defective/Damaged", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(0, 44)
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
        self.table.setColumnWidth(7, 130)
        self.table.setColumnWidth(8, 120)
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
            QTableWidget::item { padding:6px 8px; color:#1a1a1a; }
            QTableWidget::item:alternate { background:#f9fafb; }
            QTableWidget::item:selected {
                background:#eff6ff; color:#1a1a1a;
            }
            QTableWidget::item:hover { background:transparent; }
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
        self._update_card(self.total_card,     data.get("total_items",     "—"))
        self._update_card(self.low_card,       data.get("low_stock_count", "—"))
        self._update_card(self.consumed_card,  data.get("total_consumed",  "—"))
        self._update_card(self.defective_card, data.get("total_defective", "—"))

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
            expand_btn.setFixedSize(28, 28)
            expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            expand_btn.setStyleSheet("""
                QPushButton {
                    background:#f1f5f9; color:#475569;
                    border:1px solid #e2e8f0;
                    border-radius:4px; font-size:10px; font-weight:bold;
                }
                QPushButton:hover { background:#e2e8f0; }
            """)
            expand_btn.clicked.connect(
                lambda _, i=item, r=row, b=expand_btn:
                self._toggle_expand(i, r, b)
            )
            ew = QWidget()
            el = QHBoxLayout(ew)
            el.setContentsMargins(6, 6, 6, 6)
            el.setAlignment(Qt.AlignmentFlag.AlignCenter)
            el.addWidget(expand_btn)
            self.table.setCellWidget(row, 0, ew)

            self.table.setItem(row, 1, cell(item.get("item_name",  "")))
            self.table.setItem(row, 2, cell(item.get("model_name", "")))
            self.table.setItem(row, 3, cell(item.get("colour",     "")))
            self.table.setItem(row, 4, cell(item.get("sku",        "")))

            rem_cell = QTableWidgetItem(str(remaining))
            rem_cell.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            if is_low:
                rem_cell.setForeground(QColor("#ffffff"))
                rem_cell.setBackground(QColor("#dc2626"))
            self.table.setItem(row, 5, rem_cell)

            self.table.setItem(
                row, 6,
                cell(item["consumed_quantity"], Qt.AlignmentFlag.AlignCenter)
            )

            combined = (
                item["defective_quantity"] + item["damaged_quantity"]
            )
            combined_cell = QTableWidgetItem(str(combined))
            combined_cell.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            if combined > 0:
                combined_cell.setForeground(QColor("#dc2626"))
            self.table.setItem(row, 7, combined_cell)

            # Actions button
            actions_btn = QPushButton("⚡ Actions ▾")
            actions_btn.setFixedHeight(30)
            actions_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            actions_btn.setStyleSheet("""
                QPushButton {
                    background:#1e293b; color:white; border:none;
                    border-radius:4px; font-size:11px; padding:0 10px;
                    font-weight:500;
                }
                QPushButton:hover { background:#334155; }
            """)
            actions_btn.clicked.connect(
                lambda _, i=item, b=actions_btn:
                self._show_actions_menu(i, b)
            )

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.addWidget(actions_btn)
            self.table.setCellWidget(row, 8, btn_widget)

        low_count = sum(
            1 for i in items
            if i["remaining_quantity"] <= i["low_stock_threshold"]
        )
        self.status_label.setText(
            f"{len(items)} items loaded"
            + (f"  •  ⚠ {low_count} low stock" if low_count else "")
        )

    # ── ACTIONS MENU ──────────────────────────────────────────

    def _show_actions_menu(self, item, btn):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background:white;
                border:1px solid #e5e7eb;
                border-radius:8px;
                padding:4px;
            }
            QMenu::item {
                padding:8px 16px;
                font-size:13px;
                color:#1a1a1a;
                border-radius:4px;
            }
            QMenu::item:selected {
                background:#eff6ff;
                color:#2563eb;
            }
            QMenu::separator {
                height:1px;
                background:#e5e7eb;
                margin:4px 8px;
            }
        """)

        update_action  = QAction("📦  Update Stock",     self)
        edit_action    = QAction("✏️   Edit Details",     self)
        correct_action = QAction("🔢  Correct Quantity", self)

        menu.addAction(update_action)
        menu.addAction(edit_action)
        menu.addAction(correct_action)

        update_action.triggered.connect(
            lambda checked, i=item: self._update_stock(i)
        )
        edit_action.triggered.connect(
            lambda checked, i=item: self._edit_details(i)
        )
        correct_action.triggered.connect(
            lambda checked, i=item: self._correct_quantity(i)
        )

        if Session.role in ["superadmin", "manager"]:
            move_action = QAction("🔄  Move Stock", self)
            move_action.triggered.connect(
                lambda checked, i=item: self._move_stock(i)
            )
            menu.addAction(move_action)
            menu.addSeparator()
            delete_action = QAction("🗑️   Delete", self)
            delete_action.triggered.connect(
                lambda checked, i=item: self._delete_item(i)
            )
            menu.addAction(delete_action)

        pos = btn.mapToGlobal(QPoint(0, btn.height()))
        menu.exec(pos)

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
        self.table.setRowHeight(exp_row, 220)
        self.table.setSpan(exp_row, 1, 1, 8)
        self.expanded_rows[item_id] = exp_row

        loading_widget = QWidget()
        loading_widget.setStyleSheet("background:#f8fafc;")
        ll = QHBoxLayout(loading_widget)
        ll.setContentsMargins(16, 0, 0, 0)
        lbl = QLabel("Loading history...")
        lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
        ll.addWidget(lbl)
        self.table.setCellWidget(exp_row, 1, loading_widget)

        if item_id in self.location_cache:
            cached = self.location_cache[item_id]
            self._show_history(
                item_id,
                cached["movements"],
                cached["locations"]
            )
        else:
            worker = LoadItemHistoryWorker(item_id)
            worker.done.connect(self._on_history_loaded)
            self.workers.append(worker)
            worker.start()

    def _on_history_loaded(self, item_id, movements, locations):
        self.location_cache[item_id] = {
            "movements": movements,
            "locations": locations
        }
        self._show_history(item_id, movements, locations)

    def _show_history(self, item_id, movements, locations):
        if item_id not in self.expanded_rows:
            return
        exp_row = self.expanded_rows[item_id]
        widget  = ItemHistoryWidget(movements, locations)
        self.table.setCellWidget(exp_row, 1, widget)
        self.table.setRowHeight(
            exp_row, max(widget.sizeHint().height(), 220)
        )

    # ── ACTION HANDLERS ───────────────────────────────────────

    def _update_stock(self, item):
        # Load location stocks so dialog can show them
        try:
            location_stocks = APIClient.get(
                f"/inventory/items/{item['id']}/locations"
            )
        except APIError:
            location_stocks = []

        dlg = UpdateStockDialog(self, item, location_stocks)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            movement_type = dlg.type_combo.currentData()
            stage_labels  = {
                "during_import":        "During Purchase",
                "during_manufacturing": "During Manufacturing",
                "during_storage":       "During Storage",
            }
            note_parts = []
            if movement_type in ["defective", "damaged"]:
                stage = dlg.stage_combo.currentData()
                if stage:
                    note_parts.append(
                        f"Stage: {stage_labels.get(stage, stage)}"
                    )
            if dlg.notes_input.toPlainText().strip():
                note_parts.append(dlg.notes_input.toPlainText().strip())
            final_note = "  |  ".join(note_parts) or None

            location_id = dlg.location_combo.currentData() or None

            try:
                APIClient.post("/inventory/adjust", {
                    "item_id":       item["id"],
                    "quantity":      dlg.qty_spin.value(),
                    "movement_type": movement_type,
                    "notes":         final_note,
                    "location_id":   location_id,
                })
                QMessageBox.information(
                    self, "Success", "Stock updated successfully."
                )
                self.location_cache = {}
                self._load_items()
                self._load_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _edit_details(self, item):
        try:
            models      = APIClient.get("/master/models")
            model_names = [m["model_name"] for m in models]
        except APIError:
            model_names = []

        dlg = EditDetailsDialog(self, item, model_names)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.patch(
                    f"/inventory/items/{item['id']}",
                    dlg.result_data
                )
                QMessageBox.information(
                    self, "Success", "Details updated successfully."
                )
                self.location_cache = {}
                self._load_items()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)
    def _correct_quantity(self, item):
        # Load location stocks first
        try:
            location_stocks = APIClient.get(
                f"/inventory/items/{item['id']}/locations"
            )
        except APIError:
            location_stocks = []

        dlg = CorrectQuantityDialog(self, item, location_stocks)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data      = dlg.get_data()
            direction = data["direction"]
            quantity  = data["quantity"]
            reason    = data["reason"]

            if direction == "remove":
                if quantity > item["remaining_quantity"]:
                    QMessageBox.warning(
                        self, "Invalid",
                        f"Cannot remove {quantity} pcs — "
                        f"only {item['remaining_quantity']} available."
                    )
                    return

            movement_type = "adjusted" if direction == "add" else "consumed"
            note = f"⚙️ Quantity Correction  |  {reason}"

            try:
                APIClient.post("/inventory/adjust", {
                    "item_id":       item["id"],
                    "quantity":      quantity,
                    "movement_type": movement_type,
                    "notes":         note,
                    "location_id":   data.get("location_id"),
                })
                new_qty = (
                    item["remaining_quantity"] + quantity
                    if direction == "add"
                    else item["remaining_quantity"] - quantity
                )
                QMessageBox.information(
                    self, "Corrected",
                    f"Quantity corrected by "
                    f"{'+'if direction=='add' else '-'}{quantity} pcs.\n"
                    f"New stock: {new_qty} pcs"
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
                "Add it via Purchase with a location selected first."
            )
            return

        try:
            all_locations = APIClient.get("/master/locations")
        except APIError:
            all_locations = []

        dlg = MoveStockDialog(self, item, location_stocks, all_locations)
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
                    f"Moved {move_data['quantity']} pcs.\n"
                    f"From : {result.get('from', '')}\n"
                    f"To   : {result.get('to', '')}"
                )
                self.location_cache = {}
                self._load_items()
                self._load_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _delete_item(self, item):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Permanently delete:\n\n"
            f"Part  : {item['item_name']}\n"
            f"Model : {item.get('model_name', '')}\n\n"
            f"This removes the item AND all its history.\n"
            f"This cannot be undone.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.delete(f"/inventory/items/{item['id']}")
                QMessageBox.information(
                    self, "Deleted",
                    f"'{item['item_name']}' permanently deleted."
                )
                self.location_cache = {}
                self._load_items()
                self._load_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

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
                if entry_type == "purchase":
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
                            "Please add it via Purchase first."
                        )
                        return

                    stage_labels = {
                        "during_import":        "During Purchase",
                        "during_manufacturing": "During Manufacturing",
                        "during_storage":       "During Storage",
                    }
                    stage_text = stage_labels.get(
                        data.get("damage_stage", ""), ""
                    )
                    note_parts = []
                    if stage_text:
                        note_parts.append(f"Stage: {stage_text}")
                    if data.get("notes"):
                        note_parts.append(data["notes"])
                    final_note = "  |  ".join(note_parts) or None

                    APIClient.post("/inventory/adjust", {
                        "item_id":       existing["id"],
                        "quantity":      data["quantity"],
                        "movement_type": data["type"],
                        "notes":         final_note,
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