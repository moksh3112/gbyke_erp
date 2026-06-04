from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QDialog, QFormLayout,
    QSpinBox, QMessageBox, QHeaderView, QFrame,
    QTextEdit, QAbstractItemView, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QSizePolicy, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QAction
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session
import re
# ── WORKERS ───────────────────────────────────────────────────

class LoadModelsWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.done.emit(APIClient.get("/master/models"))
        except APIError as e:
            self.error.emit(e.message)


class LoadBOMWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, model_id):
        super().__init__()
        self.model_id = model_id

    def run(self):
        try:
            self.done.emit(APIClient.get(f"/manufacturing/bom/{self.model_id}"))
        except APIError as e:
            self.error.emit(e.message)


class LoadJobsWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, status_filter=""):
        super().__init__()
        self.status_filter = status_filter

    def run(self):
        try:
            qs = f"?status={self.status_filter}" if self.status_filter else ""
            self.done.emit(APIClient.get(f"/manufacturing/jobs{qs}"))
        except APIError as e:
            self.error.emit(e.message)


class LoadSummaryWorker(QThread):
    done = pyqtSignal(dict)

    def run(self):
        try:
            self.done.emit(APIClient.get("/manufacturing/summary"))
        except APIError:
            self.done.emit({})


# ── ADD BOM ITEM DIALOG — FREE TEXT + SKU PREVIEW ─────────────

class AddBOMItemDialog(QDialog):
    def __init__(self, parent, model_id, model_name, model_code=""):
        super().__init__(parent)
        self.model_id   = model_id
        self.model_name = model_name
        self.model_code = model_code   # ← used for SKU preview
        self.result_data = {}
        self.setWindowTitle(f"Add BOM Part — {model_name}")
        self.setFixedWidth(500)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            "Define a part required to build this scooter model.\n"
            "You can add inventory stock for this part later."
        )
        info.setStyleSheet(
            "background:#eff6ff; color:#1d4ed8; padding:10px 12px;"
            "border-radius:6px; font-size:12px;"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)

        lbl  = "font-size:13px; font-weight:500; color:#374151;"
        inp  = "border:1px solid #ddd; border-radius:4px; padding:0 8px; color:#1a1a1a; background:white;"
        spin = "color:#1a1a1a; background:white; border:1px solid #ddd; border-radius:4px; padding:0 8px;"

        # Part name — free text
        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(36)
        self.name_input.setStyleSheet(inp)
        self.name_input.setPlaceholderText("e.g. Front Tyre, Motor, Side Panel")
        self.name_input.textChanged.connect(self._update_sku)
        nl = QLabel("Part Name *"); nl.setStyleSheet(lbl)
        form.addRow(nl, self.name_input)

        # Quantity per unit
        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(9999)
        self.qty_spin.setValue(1)
        self.qty_spin.setStyleSheet(spin)
        ql = QLabel("Qty per Unit *"); ql.setStyleSheet(lbl)
        form.addRow(ql, self.qty_spin)

        # Colour filter — optional
        self.colour_input = QLineEdit()
        self.colour_input.setFixedHeight(36)
        self.colour_input.setStyleSheet(inp)
        self.colour_input.setPlaceholderText("e.g. Red — only for Red scooters. Blank = all colours.")
        self.colour_input.textChanged.connect(self._update_sku)
        cl = QLabel("Colour Filter"); cl.setStyleSheet(lbl)
        form.addRow(cl, self.colour_input)

        # Power spec filter — optional
        self.power_input = QLineEdit()
        self.power_input.setFixedHeight(36)
        self.power_input.setStyleSheet(inp)
        self.power_input.setPlaceholderText("e.g. 72V — only for 72V variant. Blank = all.")
        pwl = QLabel("Power Spec Filter"); pwl.setStyleSheet(lbl)
        form.addRow(pwl, self.power_input)

        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(50)
        self.notes_input.setPlaceholderText("Optional notes...")
        self.notes_input.setStyleSheet("color:#1a1a1a;")
        notl = QLabel("Notes"); notl.setStyleSheet(lbl)
        form.addRow(notl, self.notes_input)

        # SKU preview — generated from model_code + part_name + colour
        self.sku_preview = QLabel("SKU Preview: —")
        self.sku_preview.setStyleSheet(
            "color:#6b7280; font-size:11px; font-style:italic;"
        )
        form.addRow("", self.sku_preview)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("border:1px solid #ddd; border-radius:6px; color:#666;")
        save_btn = QPushButton("Add Part to BOM")
        save_btn.setFixedHeight(38)
        save_btn.setDefault(True)
        save_btn.setStyleSheet(
            "background:#2563eb; color:white; border:none; border-radius:6px; font-weight:600;"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _update_sku(self):
        """Generate SKU preview: model_code + part_name + colour"""
        def clean(text):
            return re.sub(r'[^a-zA-Z0-9]', '', str(text)).upper()[:8]

        part   = self.name_input.text().strip()
        colour = self.colour_input.text().strip()

        if self.model_code and part:
            sku = f"{clean(self.model_code)}-{clean(part)}"
            if colour:
                sku += f"-{clean(colour)}"
            self.sku_preview.setText(f"SKU Preview: {sku}")
        else:
            self.sku_preview.setText("SKU Preview: —")

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing", "Part name is required.")
            return

        # Generate the actual SKU to store
        def clean(text):
            return re.sub(r'[^a-zA-Z0-9]', '', str(text)).upper()[:8]
        colour = self.colour_input.text().strip()
        sku = None
        if self.model_code and name:
            sku = f"{clean(self.model_code)}-{clean(name)}"
            if colour:
                sku += f"-{clean(colour)}"

        self.result_data = {
            "model_id":          self.model_id,
            "part_name":         name,
            "sku":               sku,
            "quantity_required": self.qty_spin.value(),
            "colour":            colour or None,
            "power_spec":        self.power_input.text().strip() or None,
            "notes":             self.notes_input.toPlainText().strip() or None,
        }
        self.accept()


# ── CREATE JOB DIALOG ─────────────────────────────────────────

class CreateJobDialog(QDialog):
    def __init__(self, parent, variants, locations):
        super().__init__(parent)
        self.variants    = variants
        self.locations   = locations
        self.result_data = {}
        self.setWindowTitle("Create Assembly Job")
        self.setFixedWidth(500)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            "⚠️  Parts will be deducted from inventory immediately.\n"
            "Job will be blocked if any matched part has insufficient stock."
        )
        info.setStyleSheet(
            "background:#fef9c3; color:#854d0e; padding:10px 12px; border-radius:6px; font-size:12px;"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)

        lbl  = "font-size:13px; font-weight:500; color:#374151;"
        inp  = "border:1px solid #ddd; border-radius:4px; padding:0 8px; color:#1a1a1a; background:white;"
        spin = "color:#1a1a1a; background:white; border:1px solid #ddd; border-radius:4px; padding:0 8px;"

        self.variant_combo = QComboBox()
        self.variant_combo.setFixedHeight(36)
        self.variant_combo.setStyleSheet(inp)
        for v in self.variants:
            display = (
                f"{v.get('model_name','?')}  |  "
                f"{v.get('color','?')}  |  "
                f"{v.get('battery_type','?')}  "
                f"{v.get('power_spec','') or ''}"
            ).strip()
            self.variant_combo.addItem(display, v["id"])
        form.addRow(QLabel("Model / Variant *", styleSheet=lbl), self.variant_combo)

        self.qty_spin = QSpinBox()
        self.qty_spin.setFixedHeight(36)
        self.qty_spin.setMinimum(1)
        self.qty_spin.setMaximum(9999)
        self.qty_spin.setValue(1)
        self.qty_spin.setStyleSheet(spin)
        form.addRow(QLabel("Units to Produce *", styleSheet=lbl), self.qty_spin)

        self.location_combo = QComboBox()
        self.location_combo.setFixedHeight(36)
        self.location_combo.setStyleSheet(inp)
        self.location_combo.addItem("-- Select Location --", "")
        for loc in self.locations:
            icon = {"factory": "🏭", "warehouse": "🏢", "godown": "📦"}.get(loc.get("location_type", ""), "📍")
            self.location_combo.addItem(f"{icon}  {loc['name']}", loc["id"])
        form.addRow(QLabel("Production Location", styleSheet=lbl), self.location_combo)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)
        self.notes_input.setPlaceholderText("Optional notes...")
        self.notes_input.setStyleSheet("color:#1a1a1a;")
        form.addRow(QLabel("Notes", styleSheet=lbl), self.notes_input)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("border:1px solid #ddd; border-radius:6px; color:#666;")
        self.create_btn = QPushButton("✅  Create Job & Deduct Stock")
        self.create_btn.setFixedHeight(38)
        self.create_btn.setDefault(True)
        self.create_btn.setStyleSheet(
            "background:#16a34a; color:white; border:none; border-radius:6px; font-weight:600;"
        )
        self.create_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.create_btn)
        layout.addLayout(btn_row)

    def _save(self):
        if not self.variant_combo.currentData():
            QMessageBox.warning(self, "Missing", "Please select a variant.")
            return
        self.result_data = {
            "variant_id":  self.variant_combo.currentData(),
            "quantity":    self.qty_spin.value(),
            "location_id": self.location_combo.currentData() or None,
            "notes":       self.notes_input.toPlainText().strip() or None,
        }
        self.accept()


# ── BOM TAB ───────────────────────────────────────────────────

class BOMTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers       = []
        self.models        = []
        self.current_model = None
        self._build_ui()
        self._load_models()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        left = QFrame()
        left.setFixedWidth(240)
        left.setStyleSheet("QFrame { background:#f8fafc; border-right:1px solid #e5e7eb; }")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 12, 8, 8)
        left_layout.setSpacing(6)

        ml = QLabel("Scooter Models")
        ml.setStyleSheet("font-size:13px; font-weight:700; color:#374151; padding:4px;")
        left_layout.addWidget(ml)

        self.model_list = QTreeWidget()
        self.model_list.setHeaderHidden(True)
        self.model_list.setStyleSheet("""
            QTreeWidget { border:none; background:transparent; }
            QTreeWidget::item { padding:6px 8px; border-radius:4px; color:#374151; }
            QTreeWidget::item:selected { background:#eff6ff; color:#2563eb; }
            QTreeWidget::item:hover { background:#f1f5f9; }
        """)
        self.model_list.itemClicked.connect(self._on_model_selected)
        left_layout.addWidget(self.model_list)
        layout.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 12, 16, 12)
        right_layout.setSpacing(12)

        hdr = QHBoxLayout()
        self.bom_title = QLabel("Select a model to view its BOM")
        self.bom_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.bom_title.setStyleSheet("color:#1e293b;")
        hdr.addWidget(self.bom_title)
        hdr.addStretch()

        if Session.role in ["superadmin", "manager"]:
            self.add_bom_btn = QPushButton("+ Add Part to BOM")
            self.add_bom_btn.setFixedHeight(34)
            self.add_bom_btn.setEnabled(False)
            self.add_bom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.add_bom_btn.setStyleSheet("""
                QPushButton {
                    background:#2563eb; color:white; border:none;
                    border-radius:6px; padding:0 14px; font-weight:600; font-size:12px;
                }
                QPushButton:hover { background:#1d4ed8; }
                QPushButton:disabled { background:#94a3b8; }
            """)
            self.add_bom_btn.clicked.connect(self._add_bom_item)
            hdr.addWidget(self.add_bom_btn)

        right_layout.addLayout(hdr)

        self.total_parts_lbl = QLabel("")
        self.total_parts_lbl.setStyleSheet(
            "background:#eff6ff; color:#1d4ed8; padding:4px 10px; border-radius:4px; font-size:12px;"
        )
        right_layout.addWidget(self.total_parts_lbl)

        self.bom_table = QTableWidget()
        self.bom_table.setColumnCount(7)
        self.bom_table.setHorizontalHeaderLabels([
            "Part Name", "SKU", "Qty/Unit", "Colour Filter", "Power Filter", "Notes", "Actions"
        ])
        self.bom_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.bom_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.bom_table.setColumnWidth(1, 160)
        self.bom_table.setColumnWidth(2, 70)
        self.bom_table.setColumnWidth(3, 90)
        self.bom_table.setColumnWidth(4, 90)
        self.bom_table.setColumnWidth(5, 120)
        self.bom_table.setColumnWidth(6, 80)
        self.bom_table.verticalHeader().setDefaultSectionSize(38)
        self.bom_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.bom_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bom_table.setAlternatingRowColors(True)
        self.bom_table.verticalHeader().setVisible(False)
        self.bom_table.setStyleSheet("""
            QTableWidget { border:1px solid #e5e7eb; border-radius:8px; gridline-color:#f3f4f6; }
            QHeaderView::section {
                background:#f8fafc; padding:8px; border:none;
                border-bottom:1px solid #e5e7eb; font-weight:600; color:#374151;
            }
            QTableWidget::item { padding:4px 8px; color:#1a1a1a; }
            QTableWidget::item:alternate { background:#f9fafb; }
            QTableWidget::item:selected { background:#eff6ff; color:#1a1a1a; }
        """)
        right_layout.addWidget(self.bom_table)

        self.bom_status = QLabel("")
        self.bom_status.setStyleSheet("color:#94a3b8; font-size:12px;")
        right_layout.addWidget(self.bom_status)

        layout.addWidget(right, 1)

    def _load_models(self):
        worker = LoadModelsWorker()
        worker.done.connect(self._on_models_loaded)
        worker.error.connect(lambda e: None)
        self.workers.append(worker)
        worker.start()

    def _on_models_loaded(self, models):
        self.models = models
        self.model_list.clear()
        for m in models:
            item = QTreeWidgetItem([f"🛵  {m['model_name']}"])
            item.setData(0, Qt.ItemDataRole.UserRole, m)
            self.model_list.addTopLevelItem(item)

    def _on_model_selected(self, item):
        model = item.data(0, Qt.ItemDataRole.UserRole)
        if not model:
            return
        self.current_model = model
        self.bom_title.setText(f"BOM — {model['model_name']}  ({model.get('model_code', '')})")
        if Session.role in ["superadmin", "manager"]:
            self.add_bom_btn.setEnabled(True)
        self.bom_status.setText("Loading BOM...")
        self.bom_table.setRowCount(0)

        worker = LoadBOMWorker(model["id"])
        worker.done.connect(self._populate_bom)
        worker.error.connect(lambda e: self.bom_status.setText(f"Error: {e}"))
        self.workers.append(worker)
        worker.start()

    def _populate_bom(self, items):
        self.bom_table.setRowCount(len(items))

        def cell(text, align=Qt.AlignmentFlag.AlignLeft):
            c = QTableWidgetItem(str(text) if text else "—")
            c.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            return c

        for row, item in enumerate(items):
            display_name = item.get("part_name") or item.get("item_name", "")
            self.bom_table.setItem(row, 0, cell(display_name))
            self.bom_table.setItem(row, 1, cell(item.get("sku", "") or "—"))
            self.bom_table.setItem(row, 2, cell(item.get("quantity_required", ""), Qt.AlignmentFlag.AlignCenter))

            colour = item.get("colour") or ""
            colour_cell = QTableWidgetItem(colour if colour else "All colours")
            colour_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            colour_cell.setForeground(QColor("#7c3aed") if colour else QColor("#94a3b8"))
            self.bom_table.setItem(row, 3, colour_cell)

            power = item.get("power_spec") or ""
            power_cell = QTableWidgetItem(power if power else "All variants")
            power_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            power_cell.setForeground(QColor("#0891b2") if power else QColor("#94a3b8"))
            self.bom_table.setItem(row, 4, power_cell)

            self.bom_table.setItem(row, 5, cell(item.get("notes", "")))

            if Session.role in ["superadmin", "manager"]:
                del_btn = QPushButton("🗑️")
                del_btn.setFixedSize(32, 28)
                del_btn.setStyleSheet(
                    "QPushButton { background:#fee2e2; color:#dc2626; border:none;"
                    "border-radius:4px; font-size:13px; }"
                    "QPushButton:hover { background:#fecaca; }"
                )
                del_btn.clicked.connect(lambda _, i=item: self._delete_bom_item(i))
                w = QWidget()
                wl = QHBoxLayout(w)
                wl.setContentsMargins(4, 3, 4, 3)
                wl.addWidget(del_btn)
                self.bom_table.setCellWidget(row, 6, w)

        self.total_parts_lbl.setText(f"📋 {len(items)} parts in BOM")
        self.bom_status.setText(f"{len(items)} BOM items for {self.current_model['model_name']}")

    def _add_bom_item(self):
        if not self.current_model:
            return
        # ── FIX: pass model_code so dialog can generate SKU preview ──
        dlg = AddBOMItemDialog(
            self,
            self.current_model["id"],
            self.current_model["model_name"],
            self.current_model.get("model_code", ""),  # ← model_code
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.post("/manufacturing/bom", dlg.result_data)
                QMessageBox.information(self, "Added", "Part added to BOM successfully.")
                self._on_model_selected(self.model_list.currentItem())
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _delete_bom_item(self, item):
        reply = QMessageBox.question(
            self, "Delete BOM Item",
            f"Remove '{item.get('part_name') or item.get('item_name')}' from BOM?\n"
            "This will not affect existing assembly jobs.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.delete(f"/manufacturing/bom/{item['id']}")
                self._on_model_selected(self.model_list.currentItem())
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)


# ── JOBS TAB ──────────────────────────────────────────────────


# ── JOBS TAB ──────────────────────────────────────────────────

class JobsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers   = []
        self.jobs      = []
        self.variants  = []
        self.locations = []
        self._build_ui()
        self._load_jobs()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        hdr = QHBoxLayout()

        self.filter_combo = QComboBox()
        self.filter_combo.setFixedHeight(34)
        self.filter_combo.addItem("All Jobs",        "")
        self.filter_combo.addItem("🔄  In Progress", "in_progress")
        self.filter_combo.addItem("✅  Completed",   "completed")
        self.filter_combo.addItem("❌  Cancelled",   "cancelled")
        self.filter_combo.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 8px; color:#1a1a1a; background:white;"
        )
        self.filter_combo.currentIndexChanged.connect(self._load_jobs)
        hdr.addWidget(self.filter_combo)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px; padding:0 12px; color:#666;"
        )
        refresh_btn.clicked.connect(self._refresh_all)
        hdr.addWidget(refresh_btn)
        hdr.addStretch()

        if Session.role in ["superadmin", "manager"]:
            create_btn = QPushButton("+ New Assembly Job")
            create_btn.setFixedHeight(34)
            create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            create_btn.setStyleSheet("""
                QPushButton {
                    background:#16a34a; color:white; border:none;
                    border-radius:6px; padding:0 16px; font-weight:600; font-size:12px;
                }
                QPushButton:hover { background:#15803d; }
            """)
            create_btn.clicked.connect(self._create_job)
            hdr.addWidget(create_btn)

        layout.addLayout(hdr)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Model", "Colour", "Power Spec", "Qty",
            "Location", "Status", "Created", "Units Done", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 50)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 100)
        self.table.setColumnWidth(6, 110)
        self.table.setColumnWidth(7, 80)
        self.table.setColumnWidth(8, 110)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
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

        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet("color:#94a3b8; font-size:12px;")
        layout.addWidget(self.status_label)

    def _refresh_all(self):
        self._load_jobs()
        self._refresh_summary()

    def _refresh_summary(self):
        parent = self.parent()
        while parent:
            if hasattr(parent, '_load_summary'):
                parent._load_summary()
                break
            parent = parent.parent()

    def _load_jobs(self):
        self.status_label.setText("Loading...")
        self.table.setRowCount(0)
        worker = LoadJobsWorker(self.filter_combo.currentData())
        worker.done.connect(self._populate_table)
        worker.error.connect(lambda e: self.status_label.setText(f"Error: {e}"))
        self.workers.append(worker)
        worker.start()

    def _populate_table(self, jobs):
        self.jobs = jobs
        self.table.setRowCount(len(jobs))

        STATUS_STYLE = {
            "in_progress": ("🔄 In Progress", "#0891b2"),
            "completed":   ("✅ Completed",   "#16a34a"),
            "cancelled":   ("❌ Cancelled",   "#dc2626"),
            "pending":     ("⏳ Pending",     "#f59e0b"),
        }

        def cell(text, align=Qt.AlignmentFlag.AlignLeft):
            c = QTableWidgetItem(str(text) if text else "—")
            c.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            return c

        for row, job in enumerate(jobs):
            self.table.setItem(row, 0, cell(job.get("model_name", "")))
            self.table.setItem(row, 1, cell(job.get("color", "")))
            self.table.setItem(row, 2, cell(job.get("power_spec", "") or "—"))
            self.table.setItem(row, 3, cell(job.get("quantity", ""), Qt.AlignmentFlag.AlignCenter))
            self.table.setItem(row, 4, cell(job.get("location_name", "") or "—"))

            status = job.get("status", "pending")
            label, color = STATUS_STYLE.get(status, (status, "#374151"))
            status_cell = QTableWidgetItem(label)
            status_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            status_cell.setForeground(QColor(color))
            self.table.setItem(row, 5, status_cell)

            self.table.setItem(row, 6, cell(job.get("created_at", "") or "—"))
            self.table.setItem(
                row, 7,
                cell(
                    f"{job.get('units_created', 0)} / {job.get('quantity', 0)}",
                    Qt.AlignmentFlag.AlignCenter
                )
            )

            # ── Actions dropdown ───────────────────────────────
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
                lambda _, j=job, b=actions_btn: self._show_actions_menu(j, b)
            )
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.addWidget(actions_btn)
            self.table.setCellWidget(row, 8, btn_widget)

        self.status_label.setText(f"{len(jobs)} jobs loaded")

    def _show_actions_menu(self, job, btn):
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

        status = job.get("status", "")

        if status == "in_progress":
            complete_action = QAction("✅  Mark Complete", self)
            complete_action.triggered.connect(lambda checked, j=job: self._complete_job(j))
            menu.addAction(complete_action)

            if Session.role in ["superadmin", "manager"]:
                cancel_action = QAction("❌  Cancel Job", self)
                cancel_action.triggered.connect(lambda checked, j=job: self._cancel_job(j))
                menu.addAction(cancel_action)

        elif status == "completed":
            info_action = QAction("✅  Job Completed", self)
            info_action.setEnabled(False)
            menu.addAction(info_action)

        elif status == "cancelled":
            info_action = QAction("❌  Job Cancelled", self)
            info_action.setEnabled(False)
            menu.addAction(info_action)

        if Session.role == "superadmin":
            menu.addSeparator()
            delete_action = QAction("🗑️  Delete Job", self)
            delete_action.triggered.connect(lambda checked, j=job: self._delete_job(j))
            menu.addAction(delete_action)

        from PyQt6.QtCore import QPoint
        pos = btn.mapToGlobal(QPoint(0, btn.height()))
        menu.exec(pos)
        QTimer.singleShot(0, lambda: None)

    def _create_job(self):
        try:
            self.variants  = APIClient.get("/master/variants")
            self.locations = APIClient.get("/master/locations")
        except APIError as e:
            QMessageBox.critical(self, "Error", str(e.message))
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        if not self.variants:
            QMessageBox.warning(
                self, "No Variants",
                "No scooter variants found.\nPlease add variants in Master Data → Variants first."
            )
            return

        dlg = CreateJobDialog(self, self.variants, self.locations)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.post("/manufacturing/jobs", dlg.result_data)
                QMessageBox.information(
                    self, "Job Created",
                    f"Assembly job created.\n"
                    f"Parts deducted from inventory.\n"
                    f"Producing {dlg.result_data['quantity']} units."
                )
                self._load_jobs()
                self._refresh_summary()
            except APIError as e:
                QMessageBox.critical(self, "Cannot Create Job", str(e.message))

    def _complete_job(self, job):
        reply = QMessageBox.question(
            self, "Complete Job",
            f"Mark this job as completed?\n\n"
            f"Model    : {job.get('model_name', '')}\n"
            f"Colour   : {job.get('color', '')}\n"
            f"Quantity : {job.get('quantity', '')} units\n\n"
            f"{job.get('quantity', '')} scooter units will be created "
            f"with status 'Manufacturing Done'.\n"
            f"Motor and Chassis numbers assigned later in PDI.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.post(f"/manufacturing/jobs/{job['id']}/complete", {})
                QMessageBox.information(
                    self, "Completed",
                    f"{job.get('quantity', '')} scooter units created and ready for PDI."
                )
                self._load_jobs()
                self._refresh_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _cancel_job(self, job):
        reply = QMessageBox.question(
            self, "Cancel Job",
            f"Cancel this assembly job?\n\n"
            f"Model    : {job.get('model_name', '')}\n"
            f"Quantity : {job.get('quantity', '')} units\n\n"
            f"⚠️  All deducted parts will be RETURNED to inventory.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.post(f"/manufacturing/jobs/{job['id']}/cancel", {})
                QMessageBox.information(self, "Cancelled", "Job cancelled and parts returned to inventory.")
                self._load_jobs()
                self._refresh_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _delete_job(self, job):
        reply = QMessageBox.question(
            self, "Delete Job",
            f"Permanently delete this assembly job?\n\n"
            f"Model    : {job.get('model_name', '')}\n"
            f"Quantity : {job.get('quantity', '')} units\n"
            f"Status   : {job.get('status', '')}\n\n"
            f"⚠️  This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.delete(f"/manufacturing/jobs/{job['id']}")
                self._load_jobs()
                self._refresh_summary()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

class ManufacturingScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers = []
        self._build_ui()
        self._load_summary()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("🏭 Manufacturing")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)
        self.card_inprogress = self._stat_card("In Progress",    "—", "#0891b2")
        self.card_completed  = self._stat_card("Completed Jobs", "—", "#16a34a")
        self.card_awaiting   = self._stat_card("Awaiting PDI",   "—", "#f59e0b")
        self.card_total      = self._stat_card("Total Jobs",     "—", "#7c3aed")
        for c in [self.card_inprogress, self.card_completed, self.card_awaiting, self.card_total]:
            summary_row.addWidget(c)
        layout.addLayout(summary_row)

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

        self.jobs_tab = JobsTab()
        self.bom_tab  = BOMTab()
        self.tabs.addTab(self.jobs_tab, "🔧  Assembly Jobs")
        self.tabs.addTab(self.bom_tab,  "📋  Bill of Materials")
        layout.addWidget(self.tabs)

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
        worker = LoadSummaryWorker()
        worker.done.connect(self._on_summary)
        self.workers.append(worker)
        worker.start()

    def _on_summary(self, data):
        self._update_card(self.card_inprogress, data.get("in_progress_jobs",   "—"))
        self._update_card(self.card_completed,  data.get("completed_jobs",     "—"))
        self._update_card(self.card_awaiting,   data.get("units_awaiting_pdi", "—"))
        self._update_card(self.card_total,      data.get("total_jobs",         "—"))