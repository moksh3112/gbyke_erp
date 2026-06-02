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


# ── WORKER THREADS ────────────────────────────────────────────

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
            result = APIClient.get("/inventory/summary")
            self.done.emit(result)
        except APIError:
            self.done.emit({})


# ── SKU GENERATOR ─────────────────────────────────────────────

def generate_sku(model_name: str, part_name: str, colour: str = "") -> str:
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
    def __init__(self, model_names: list, part_names: list, parent=None):
        super().__init__(parent)
        self._build_ui(model_names, part_names)

    def _build_ui(self, model_names, part_names):
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        layout.setHorizontalSpacing(16)

        lbl = "font-size:13px; font-weight:500; color:#374151;"
        inp = (
            "border:1px solid #ddd; border-radius:4px;"
            "padding:0 8px; color:#1a1a1a; background:white;"
        )
        spin_style = (
            "color:#1a1a1a; background:white;"
            "border:1px solid #ddd; border-radius:4px; padding:0 8px;"
        )

        # Date
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setFixedHeight(36)
        self.date_input.setStyleSheet(inp)
        date_lbl = QLabel("Date *")
        date_lbl.setStyleSheet(lbl)
        layout.addRow(date_lbl, self.date_input)

        # Model
        self.model_input = SearchableInput("Type or select model name...")
        self.model_input.set_items(model_names)
        self.model_input.input.textChanged.connect(self._update_sku)
        model_lbl = QLabel("Scooter Model *")
        model_lbl.setStyleSheet(lbl)
        layout.addRow(model_lbl, self.model_input)

        # Part
        self.part_input = SearchableInput("Type or select part name...")
        self.part_input.set_items(part_names)
        self.part_input.input.textChanged.connect(self._update_sku)
        part_lbl = QLabel("Part Name *")
        part_lbl.setStyleSheet(lbl)
        layout.addRow(part_lbl, self.part_input)

        # Colour
        self.colour_input = QLineEdit()
        self.colour_input.setPlaceholderText(
            "e.g. Red, Blue  —  leave blank if no colour"
        )
        self.colour_input.setFixedHeight(36)
        self.colour_input.setStyleSheet(inp)
        self.colour_input.textChanged.connect(self._update_sku)
        colour_lbl = QLabel("Colour")
        colour_lbl.setStyleSheet(lbl)
        layout.addRow(colour_lbl, self.colour_input)

        # Quantity
        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(999999)
        self.qty_spin.setValue(1)
        self.qty_spin.setStyleSheet(spin_style)
        qty_lbl = QLabel("Quantity *")
        qty_lbl.setStyleSheet(lbl)
        layout.addRow(qty_lbl, self.qty_spin)

        # SKU preview
        self.sku_label = QLabel("Auto SKU: —")
        self.sku_label.setStyleSheet(
            "color:#6b7280; font-size:11px; font-style:italic;"
        )
        layout.addRow("", self.sku_label)

    def _update_sku(self):
        model  = self.model_input.text()
        part   = self.part_input.text()
        colour = self.colour_input.text().strip()
        if model and part:
            self.sku_label.setText(
                f"Auto SKU: {generate_sku(model, part, colour)}"
            )
        else:
            self.sku_label.setText("Auto SKU: —")

    def validate(self) -> str:
        if not self.model_input.text():
            return "Please enter the scooter model name."
        if not self.part_input.text():
            return "Please enter the part name."
        return ""

    def get_data(self) -> dict:
        model  = self.model_input.text()
        part   = self.part_input.text()
        colour = self.colour_input.text().strip()
        return {
            "date":     self.date_input.date().toString("yyyy-MM-dd"),
            "model":    model,
            "part":     part,
            "colour":   colour,
            "quantity": self.qty_spin.value(),
            "sku":      generate_sku(model, part, colour),
        }


# ── DEFECTIVE FORM ────────────────────────────────────────────

class DefectiveForm(QWidget):
    def __init__(self, model_names: list, part_names: list, parent=None):
        super().__init__(parent)
        self._build_ui(model_names, part_names)

    def _build_ui(self, model_names, part_names):
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        layout.setHorizontalSpacing(16)

        lbl = "font-size:13px; font-weight:500; color:#374151;"
        inp = (
            "border:1px solid #ddd; border-radius:4px;"
            "padding:0 8px; color:#1a1a1a; background:white;"
        )
        spin_style = (
            "color:#1a1a1a; background:white;"
            "border:1px solid #ddd; border-radius:4px; padding:0 8px;"
        )

        # Model
        self.model_input = SearchableInput("Type or select model name...")
        self.model_input.set_items(model_names)
        model_lbl = QLabel("Scooter Model *")
        model_lbl.setStyleSheet(lbl)
        layout.addRow(model_lbl, self.model_input)

        # Part
        self.part_input = SearchableInput("Type or select part name...")
        self.part_input.set_items(part_names)
        part_lbl = QLabel("Part Name *")
        part_lbl.setStyleSheet(lbl)
        layout.addRow(part_lbl, self.part_input)

        # Quantity
        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(999999)
        self.qty_spin.setValue(1)
        self.qty_spin.setStyleSheet(spin_style)
        qty_lbl = QLabel("Quantity *")
        qty_lbl.setStyleSheet(lbl)
        layout.addRow(qty_lbl, self.qty_spin)

        # Type
        self.type_combo = QComboBox()
        self.type_combo.setFixedHeight(36)
        self.type_combo.setStyleSheet(inp)
        self.type_combo.addItem("Defective (faulty / not working)", "defective")
        self.type_combo.addItem("Damaged (physically damaged)",     "damaged")
        type_lbl = QLabel("Type *")
        type_lbl.setStyleSheet(lbl)
        layout.addRow(type_lbl, self.type_combo)

        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)
        self.notes_input.setPlaceholderText("Optional: describe the issue...")
        self.notes_input.setStyleSheet("color:#1a1a1a;")
        notes_lbl = QLabel("Notes")
        notes_lbl.setStyleSheet(lbl)
        layout.addRow(notes_lbl, self.notes_input)

    def validate(self) -> str:
        if not self.model_input.text():
            return "Please enter the scooter model name."
        if not self.part_input.text():
            return "Please enter the part name."
        return ""

    def get_data(self) -> dict:
        return {
            "model":    self.model_input.text(),
            "part":     self.part_input.text(),
            "quantity": self.qty_spin.value(),
            "type":     self.type_combo.currentData(),
            "notes":    self.notes_input.toPlainText().strip(),
        }


# ── ADD STOCK ENTRY DIALOG ────────────────────────────────────

class AddItemDialog(QDialog):
    def __init__(self, parent=None, existing_items=None, model_names=None):
        super().__init__(parent)
        self.existing_items = existing_items or []
        self.result_data    = {}
        self.model_names    = model_names or sorted(set(
            i.get("model_name", "") for i in self.existing_items
            if i.get("model_name")
        ))
        self.part_names = sorted(set(
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

        # Type selector
        type_row = QHBoxLayout()
        type_lbl = QLabel("Entry Type:")
        type_lbl.setStyleSheet(
            "font-size:13px; font-weight:500; color:#374151;"
        )
        type_row.addWidget(type_lbl)

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

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color:#e5e7eb;")
        layout.addWidget(div)

        # Stacked forms
        self.stack = QStackedWidget()
        self.import_form    = ImportForm(self.model_names, self.part_names)
        self.defective_form = DefectiveForm(self.model_names, self.part_names)
        self.stack.addWidget(self.import_form)
        self.stack.addWidget(self.defective_form)
        layout.addWidget(self.stack)

        # Buttons
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
        inp = (
            "border:1px solid #ddd; border-radius:4px;"
            "padding:0 8px; color:#1a1a1a; background:white;"
        )

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
        action_lbl = QLabel("Action")
        action_lbl.setStyleSheet(lbl)
        form.addRow(action_lbl, self.type_combo)

        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(999999)
        self.qty_spin.setStyleSheet(
            "color:#1a1a1a; background:white;"
            "border:1px solid #ddd; border-radius:4px; padding:0 8px;"
        )
        qty_lbl = QLabel("Quantity")
        qty_lbl.setStyleSheet(lbl)
        form.addRow(qty_lbl, self.qty_spin)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(70)
        self.notes_input.setPlaceholderText("Optional notes...")
        self.notes_input.setStyleSheet("color:#1a1a1a;")
        notes_lbl = QLabel("Notes")
        notes_lbl.setStyleSheet(lbl)
        form.addRow(notes_lbl, self.notes_input)

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


# ── MAIN INVENTORY SCREEN ─────────────────────────────────────

class InventoryScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items   = []
        self.workers = []
        self._build_ui()
        self._load_summary()
        self._load_items()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ── Header ────────────────────────────────────────────
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

        # ── Summary cards ─────────────────────────────────────
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

        # ── Filters ───────────────────────────────────────────
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

        # ── Table ─────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Part Name", "Model", "Colour", "SKU",
            "Remaining", "Consumed", "Defective", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 90)
        self.table.setColumnWidth(6, 90)
        self.table.setColumnWidth(7, 220)
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

    # ── DATA LOADING ──────────────────────────────────────────

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
                c.setTextAlignment(
                    align | Qt.AlignmentFlag.AlignVCenter
                )
                if is_low:
                    c.setBackground(QColor("#fff7ed"))
                return c

            self.table.setItem(row, 0, cell(item.get("item_name",  "")))
            self.table.setItem(row, 1, cell(item.get("model_name", "")))
            self.table.setItem(row, 2, cell(item.get("colour",     "")))
            self.table.setItem(row, 3, cell(item.get("sku",        "")))

            rem_cell = QTableWidgetItem(str(remaining))
            rem_cell.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            if is_low:
                rem_cell.setForeground(QColor("#dc2626"))
                rem_cell.setBackground(QColor("#fff7ed"))
            self.table.setItem(row, 4, rem_cell)

            self.table.setItem(
                row, 5,
                cell(item["consumed_quantity"],  Qt.AlignmentFlag.AlignCenter)
            )
            self.table.setItem(
                row, 6,
                cell(item["defective_quantity"], Qt.AlignmentFlag.AlignCenter)
            )

            # ── Action buttons ─────────────────────────────────
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(4)

            # Update Stock — all roles
            update_btn = QPushButton("Update Stock")
            update_btn.setFixedHeight(30)
            update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            update_btn.setStyleSheet("""
                QPushButton {
                    background:#16a34a; color:white; border:none;
                    border-radius:4px; font-size:11px; padding:0 10px;
                }
                QPushButton:hover { background:#15803d; }
            """)
            update_btn.clicked.connect(
                lambda _, i=item: self._adjust_stock(i)
            )
            btn_layout.addWidget(update_btn)

            # Delete — manager and above only
            if Session.role in ["superadmin", "manager"]:
                delete_btn = QPushButton("Delete")
                delete_btn.setFixedHeight(30)
                delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                delete_btn.setStyleSheet("""
                    QPushButton {
                        background:#dc2626; color:white; border:none;
                        border-radius:4px; font-size:11px; padding:0 10px;
                    }
                    QPushButton:hover { background:#b91c1c; }
                """)
                delete_btn.clicked.connect(
                    lambda _, i=item: self._delete_item(i)
                )
                btn_layout.addWidget(delete_btn)

            self.table.setCellWidget(row, 7, btn_widget)

        low_count = sum(
            1 for i in items
            if i["remaining_quantity"] <= i["low_stock_threshold"]
        )
        self.status_label.setText(
            f"{len(items)} items loaded"
            + (f"  •  ⚠ {low_count} low stock" if low_count else "")
        )

    # ── ACTIONS ───────────────────────────────────────────────

    def _add_stock_entry(self):
        try:
            model_names = APIClient.get("/inventory/models")
        except APIError:
            model_names = []

        dlg = AddItemDialog(
            self,
            existing_items=self.items,
            model_names=model_names
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data       = dlg.result_data
            entry_type = data["entry_type"]

            try:
                if entry_type == "import":
                    existing = next(
                        (i for i in self.items if i["sku"] == data["sku"]),
                        None
                    )
                    if existing:
                        APIClient.post("/inventory/adjust", {
                            "item_id":       existing["id"],
                            "quantity":      data["quantity"],
                            "movement_type": "received",
                            "notes":         f"Import on {data['date']}"
                        })
                        QMessageBox.information(
                            self, "Stock Updated",
                            f"Added {data['quantity']} pcs to existing item.\n"
                            f"Part  : {data['part']}\n"
                            f"Model : {data['model']}"
                        )
                    else:
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
                        })
                        QMessageBox.information(
                            self, "Item Added",
                            f"New part added to inventory.\n"
                            f"Part     : {data['part']}\n"
                            f"Model    : {data['model']}\n"
                            f"Quantity : {data['quantity']} pcs"
                        )

                else:  # defective / damaged
                    existing = next(
                        (i for i in self.items
                         if data["part"].lower() in i["item_name"].lower()
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
                        f"{data['quantity']} pcs marked as {data['type']}.\n"
                        f"Part : {data['part']}"
                    )

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
                    "notes":         dlg.notes_input.toPlainText().strip() or None,
                })
                QMessageBox.information(
                    self, "Success", "Stock updated successfully."
                )
                self._load_items()
                self._load_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _delete_item(self, item):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete:\n\n"
            f"Part  : {item['item_name']}\n"
            f"Model : {item.get('model_name', '')}\n\n"
            f"This will deactivate the item.\n"
            f"Stock history is kept.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.delete(f"/inventory/items/{item['id']}")
                QMessageBox.information(
                    self, "Deleted",
                    f"'{item['item_name']}' removed from inventory."
                )
                self._load_items()
                self._load_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)