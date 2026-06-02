from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QDialog, QFormLayout, QComboBox,
    QMessageBox, QHeaderView, QFrame, QTextEdit,
    QAbstractItemView, QTabWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
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


class LoadLocationsWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.done.emit(APIClient.get("/master/locations"))
        except APIError as e:
            self.error.emit(e.message)


# ── ADD MODEL DIALOG ──────────────────────────────────────────

class AddModelDialog(QDialog):
    def __init__(self, parent=None, model=None):
        super().__init__(parent)
        self.model       = model
        self.result_data = {}
        self.setWindowTitle("Edit Model" if model else "Add Scooter Model")
        self.setFixedWidth(460)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

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

        # Model name
        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(36)
        self.name_input.setStyleSheet(inp)
        self.name_input.setPlaceholderText("e.g. G-Byke Hawk Pro")
        self.name_input.textChanged.connect(self._auto_generate_code)
        name_lbl = QLabel("Model Name *")
        name_lbl.setStyleSheet(lbl)
        form.addRow(name_lbl, self.name_input)

        # Model code — auto generated
        self.code_input = QLineEdit()
        self.code_input.setFixedHeight(36)
        self.code_input.setStyleSheet(inp)
        self.code_input.setPlaceholderText(
            "Auto-generated from model name"
        )

        code_hint = QLabel(
            "Auto-generated — you can edit it if needed"
        )
        code_hint.setStyleSheet(
            "color:#6b7280; font-size:11px; font-style:italic;"
        )

        code_col = QVBoxLayout()
        code_col.setSpacing(2)
        code_col.addWidget(self.code_input)
        code_col.addWidget(code_hint)

        code_lbl = QLabel("Model Code *")
        code_lbl.setStyleSheet(lbl)
        form.addRow(code_lbl, code_col)

        # Description
        self.desc_input = QTextEdit()
        self.desc_input.setFixedHeight(70)
        self.desc_input.setPlaceholderText("Optional description...")
        self.desc_input.setStyleSheet("color:#1a1a1a;")
        desc_lbl = QLabel("Description")
        desc_lbl.setStyleSheet(lbl)
        form.addRow(desc_lbl, self.desc_input)

        layout.addLayout(form)

        # Pre-fill if editing
        if self.model:
            self.name_input.setText(self.model.get("model_name", ""))
            self.code_input.setText(self.model.get("model_code", ""))
            self.code_input.setReadOnly(True)
            self.desc_input.setText(
                self.model.get("description") or ""
            )

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

        save_btn = QPushButton(
            "Save Changes" if self.model else "Add Model"
        )
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

    def _auto_generate_code(self, text: str):
        if self.model:
            return
        clean = re.sub(r'[^a-zA-Z0-9]', '', text).upper()[:8]
        self.code_input.setText(clean)

    def _save(self):
        name = self.name_input.text().strip()
        code = self.code_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Missing", "Model name is required.")
            return
        if not code:
            QMessageBox.warning(self, "Missing", "Model code is required.")
            return

        self.result_data = {
            "model_name":  name,
            "model_code":  code.upper(),
            "description": self.desc_input.toPlainText().strip() or None
        }
        self.accept()


# ── ADD LOCATION DIALOG ───────────────────────────────────────

class AddLocationDialog(QDialog):
    def __init__(self, parent=None, location=None):
        super().__init__(parent)
        self.location    = location
        self.result_data = {}
        self.setWindowTitle(
            "Edit Location" if location else "Add Location"
        )
        self.setFixedWidth(460)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

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

        # Name
        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(36)
        self.name_input.setStyleSheet(inp)
        self.name_input.setPlaceholderText(
            "e.g. Main Factory, Delhi Godown"
        )
        name_lbl = QLabel("Location Name *")
        name_lbl.setStyleSheet(lbl)
        form.addRow(name_lbl, self.name_input)

        # Type
        self.type_combo = QComboBox()
        self.type_combo.setFixedHeight(36)
        self.type_combo.setStyleSheet(inp)
        self.type_combo.addItem("🏭  Factory",   "factory")
        self.type_combo.addItem("🏢  Warehouse", "warehouse")
        self.type_combo.addItem("📦  Godown",    "godown")
        type_lbl = QLabel("Type *")
        type_lbl.setStyleSheet(lbl)
        form.addRow(type_lbl, self.type_combo)

        # City
        self.city_input = QLineEdit()
        self.city_input.setFixedHeight(36)
        self.city_input.setStyleSheet(inp)
        self.city_input.setPlaceholderText("e.g. Delhi")
        city_lbl = QLabel("City")
        city_lbl.setStyleSheet(lbl)
        form.addRow(city_lbl, self.city_input)

        # State
        self.state_input = QLineEdit()
        self.state_input.setFixedHeight(36)
        self.state_input.setStyleSheet(inp)
        self.state_input.setPlaceholderText("e.g. Delhi")
        state_lbl = QLabel("State")
        state_lbl.setStyleSheet(lbl)
        form.addRow(state_lbl, self.state_input)

        # Address
        self.address_input = QTextEdit()
        self.address_input.setFixedHeight(60)
        self.address_input.setPlaceholderText(
            "Full address (optional)..."
        )
        self.address_input.setStyleSheet("color:#1a1a1a;")
        addr_lbl = QLabel("Address")
        addr_lbl.setStyleSheet(lbl)
        form.addRow(addr_lbl, self.address_input)

        layout.addLayout(form)

        # Pre-fill if editing
        if self.location:
            self.name_input.setText(self.location.get("name", ""))
            self.city_input.setText(self.location.get("city")    or "")
            self.state_input.setText(self.location.get("state")  or "")
            self.address_input.setText(
                self.location.get("address") or ""
            )
            for i in range(self.type_combo.count()):
                if self.type_combo.itemData(i) == self.location.get(
                    "location_type"
                ):
                    self.type_combo.setCurrentIndex(i)
                    break

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

        save_btn = QPushButton(
            "Save Changes" if self.location else "Add Location"
        )
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
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Missing", "Location name is required."
            )
            return

        self.result_data = {
            "name":          name,
            "location_type": self.type_combo.currentData(),
            "city":          self.city_input.text().strip()  or None,
            "state":         self.state_input.text().strip() or None,
            "address":       self.address_input.toPlainText().strip() or None
        }
        self.accept()


# ── MODELS TAB ────────────────────────────────────────────────

class ModelsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.models  = []
        self.workers = []
        self._build_ui()
        self._load_models()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.addStretch()

        if Session.role in ["superadmin", "manager"]:
            add_btn = QPushButton("+ Add Model")
            add_btn.setFixedHeight(36)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setStyleSheet("""
                QPushButton {
                    background:#2563eb; color:white; border:none;
                    border-radius:6px; padding:0 16px; font-weight:600;
                }
                QPushButton:hover { background:#1d4ed8; }
            """)
            add_btn.clicked.connect(self._add_model)
            header_row.addWidget(add_btn)

        layout.addLayout(header_row)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Model Name", "Model Code", "Description",
            "Status", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 160)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget {
                border:1px solid #e5e7eb; border-radius:8px;
                gridline-color:#f3f4f6;
            }
            QHeaderView::section {
                background:#f8fafc; padding:8px; border:none;
                border-bottom:1px solid #e5e7eb;
                font-weight:600; color:#374151;
            }
            QTableWidget::item { padding:6px 8px; color:#1a1a1a; }
            QTableWidget::item:alternate { background:#f9fafb; }
        """)
        layout.addWidget(self.table)

        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet("color:#94a3b8; font-size:12px;")
        layout.addWidget(self.status_label)

    def _load_models(self):
        worker = LoadModelsWorker()
        worker.done.connect(self._populate_table)
        worker.error.connect(
            lambda e: self.status_label.setText(f"Error: {e}")
        )
        self.workers.append(worker)
        worker.start()

    def _populate_table(self, models):
        self.models = models
        self.table.setRowCount(len(models))

        for row, model in enumerate(models):
            def cell(text):
                c = QTableWidgetItem(str(text) if text else "—")
                c.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft |
                    Qt.AlignmentFlag.AlignVCenter
                )
                return c

            self.table.setItem(row, 0, cell(model["model_name"]))
            self.table.setItem(row, 1, cell(model["model_code"]))
            self.table.setItem(row, 2, cell(model.get("description")))

            status = QTableWidgetItem(
                "Active" if model["is_active"] else "Inactive"
            )
            status.setForeground(
                QColor("#16a34a") if model["is_active"]
                else QColor("#dc2626")
            )
            status.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter |
                Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 3, status)

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(4)

            if Session.role in ["superadmin", "manager"]:
                edit_btn = QPushButton("Edit")
                edit_btn.setFixedHeight(30)
                edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                edit_btn.setStyleSheet("""
                    QPushButton {
                        background:#2563eb; color:white; border:none;
                        border-radius:4px; font-size:11px; padding:0 10px;
                    }
                    QPushButton:hover { background:#1d4ed8; }
                """)
                edit_btn.clicked.connect(
                    lambda _, m=model: self._edit_model(m)
                )
                btn_layout.addWidget(edit_btn)

                del_btn = QPushButton("Delete")
                del_btn.setFixedHeight(30)
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.setStyleSheet("""
                    QPushButton {
                        background:#dc2626; color:white; border:none;
                        border-radius:4px; font-size:11px; padding:0 10px;
                    }
                    QPushButton:hover { background:#b91c1c; }
                """)
                del_btn.clicked.connect(
                    lambda _, m=model: self._delete_model(m)
                )
                btn_layout.addWidget(del_btn)

            self.table.setCellWidget(row, 4, btn_widget)

        self.status_label.setText(f"{len(models)} models loaded")

    def _add_model(self):
        dlg = AddModelDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.post("/master/models", dlg.result_data)
                QMessageBox.information(
                    self, "Success", "Model added successfully."
                )
                self._load_models()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _edit_model(self, model):
        dlg = AddModelDialog(self, model=model)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.patch(
                    f"/master/models/{model['id']}",
                    dlg.result_data
                )
                QMessageBox.information(
                    self, "Success", "Model updated successfully."
                )
                self._load_models()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _delete_model(self, model):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete model '{model['model_name']}'?\n\n"
            f"Existing inventory parts will not be affected.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.delete(f"/master/models/{model['id']}")
                QMessageBox.information(
                    self, "Deleted", "Model deactivated."
                )
                self._load_models()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)


# ── LOCATIONS TAB ─────────────────────────────────────────────

class LocationsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.locations = []
        self.workers   = []
        self._build_ui()
        self._load_locations()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.addStretch()

        if Session.role in ["superadmin", "manager"]:
            add_btn = QPushButton("+ Add Location")
            add_btn.setFixedHeight(36)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setStyleSheet("""
                QPushButton {
                    background:#2563eb; color:white; border:none;
                    border-radius:6px; padding:0 16px; font-weight:600;
                }
                QPushButton:hover { background:#1d4ed8; }
            """)
            add_btn.clicked.connect(self._add_location)
            header_row.addWidget(add_btn)

        layout.addLayout(header_row)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Name", "Type", "City", "State", "Status", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 160)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget {
                border:1px solid #e5e7eb; border-radius:8px;
                gridline-color:#f3f4f6;
            }
            QHeaderView::section {
                background:#f8fafc; padding:8px; border:none;
                border-bottom:1px solid #e5e7eb;
                font-weight:600; color:#374151;
            }
            QTableWidget::item { padding:6px 8px; color:#1a1a1a; }
            QTableWidget::item:alternate { background:#f9fafb; }
        """)
        layout.addWidget(self.table)

        self.status_label = QLabel("Loading...")
        self.status_label.setStyleSheet("color:#94a3b8; font-size:12px;")
        layout.addWidget(self.status_label)

    def _load_locations(self):
        worker = LoadLocationsWorker()
        worker.done.connect(self._populate_table)
        worker.error.connect(
            lambda e: self.status_label.setText(f"Error: {e}")
        )
        self.workers.append(worker)
        worker.start()

    def _populate_table(self, locations):
        self.locations = locations
        self.table.setRowCount(len(locations))

        type_icons = {
            "factory":   "🏭 Factory",
            "warehouse": "🏢 Warehouse",
            "godown":    "📦 Godown"
        }

        for row, loc in enumerate(locations):
            def cell(text):
                c = QTableWidgetItem(str(text) if text else "—")
                c.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft |
                    Qt.AlignmentFlag.AlignVCenter
                )
                return c

            self.table.setItem(row, 0, cell(loc["name"]))
            self.table.setItem(
                row, 1,
                cell(type_icons.get(
                    loc["location_type"], loc["location_type"]
                ))
            )
            self.table.setItem(row, 2, cell(loc.get("city")))
            self.table.setItem(row, 3, cell(loc.get("state")))

            status = QTableWidgetItem(
                "Active" if loc["is_active"] else "Inactive"
            )
            status.setForeground(
                QColor("#16a34a") if loc["is_active"]
                else QColor("#dc2626")
            )
            status.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter |
                Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 4, status)

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(4)

            if Session.role in ["superadmin", "manager"]:
                edit_btn = QPushButton("Edit")
                edit_btn.setFixedHeight(30)
                edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                edit_btn.setStyleSheet("""
                    QPushButton {
                        background:#2563eb; color:white; border:none;
                        border-radius:4px; font-size:11px; padding:0 10px;
                    }
                    QPushButton:hover { background:#1d4ed8; }
                """)
                edit_btn.clicked.connect(
                    lambda _, l=loc: self._edit_location(l)
                )
                btn_layout.addWidget(edit_btn)

                del_btn = QPushButton("Delete")
                del_btn.setFixedHeight(30)
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.setStyleSheet("""
                    QPushButton {
                        background:#dc2626; color:white; border:none;
                        border-radius:4px; font-size:11px; padding:0 10px;
                    }
                    QPushButton:hover { background:#b91c1c; }
                """)
                del_btn.clicked.connect(
                    lambda _, l=loc: self._delete_location(l)
                )
                btn_layout.addWidget(del_btn)

            self.table.setCellWidget(row, 5, btn_widget)

        self.status_label.setText(f"{len(locations)} locations loaded")

    def _add_location(self):
        dlg = AddLocationDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.post("/master/locations", dlg.result_data)
                QMessageBox.information(
                    self, "Success", "Location added successfully."
                )
                self._load_locations()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _edit_location(self, location):
        dlg = AddLocationDialog(self, location=location)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.patch(
                    f"/master/locations/{location['id']}",
                    dlg.result_data
                )
                QMessageBox.information(
                    self, "Success", "Location updated successfully."
                )
                self._load_locations()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _delete_location(self, location):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete location '{location['name']}'?",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.delete(
                    f"/master/locations/{location['id']}"
                )
                QMessageBox.information(
                    self, "Deleted", "Location deactivated."
                )
                self._load_locations()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)


# ── MASTER DATA SCREEN ────────────────────────────────────────

class MasterDataScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("⚙️  Master Data")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        layout.addWidget(title)

        sub = QLabel(
            "Manage scooter models and warehouse locations."
        )
        sub.setStyleSheet("color:#64748b; font-size:13px;")
        layout.addWidget(sub)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border:1px solid #e5e7eb;
                border-radius:8px;
                background:white;
                padding:16px;
            }
            QTabBar::tab {
                padding:8px 20px;
                font-size:13px;
                color:#64748b;
                border:none;
                margin-right:4px;
            }
            QTabBar::tab:selected {
                color:#2563eb;
                font-weight:600;
                border-bottom:2px solid #2563eb;
            }
        """)

        tabs.addTab(ModelsTab(),    "🛵  Scooter Models")
        tabs.addTab(LocationsTab(), "🏢  Locations")

        layout.addWidget(tabs)