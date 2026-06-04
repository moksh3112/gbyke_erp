from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, 
    QPushButton, QDialog, QFormLayout, QLineEdit, QMessageBox,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from desktop.utils.api_client import APIClient, APIError

# ── DASHBOARD HELPER ──────────────────────────────────────────

def _stat_card(title, value, color):
    card = QFrame()
    card.setFixedHeight(100)
    card.setStyleSheet(f"""
        QFrame {{
            background:white; border-radius:10px;
            border-left:4px solid {color};
            border-top:1px solid #e5e7eb; border-right:1px solid #e5e7eb; border-bottom:1px solid #e5e7eb;
        }}
    """)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 12, 16, 12)
    val = QLabel(value)
    val.setFont(QFont("Arial", 24, QFont.Weight.Bold))
    val.setStyleSheet(f"color:{color}; border:none;")
    val.setObjectName("val")
    ttl = QLabel(title)
    ttl.setStyleSheet("color:#6b7280; font-size:12px; border:none;")
    lay.addWidget(val)
    lay.addWidget(ttl)
    return card

# ── WORKER ──────────────────────────────────────────────────

class PDIWorker(QThread):
    finished = pyqtSignal(list)
    def run(self):
        try:
            data = APIClient.get("/pdi/pending")
            self.finished.emit(data if data else [])
        except APIError:
            self.finished.emit([])

# ── DIALOG ──────────────────────────────────────────────────

class PDICompleteDialog(QDialog):
    def __init__(self, parent, unit):
        super().__init__(parent)
        self.unit = unit
        self.result = None
        self.setWindowTitle("Finalize Inspection")
        self.setFixedWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl = QLabel(f"Finalizing Inspection for {self.unit.get('model_name')}")
        lbl.setStyleSheet("font-weight:bold; font-size:14px; margin-bottom:10px;")
        layout.addWidget(lbl)
        
        form = QFormLayout()
        inp = "border:1px solid #d1d5db; border-radius:6px; padding:8px; background:white;"
        self.pdi = QLineEdit(); self.pdi.setStyleSheet(inp)
        self.motor = QLineEdit(); self.motor.setStyleSheet(inp)
        self.chassis = QLineEdit(); self.chassis.setStyleSheet(inp)
        form.addRow("PDI Doc #:", self.pdi)
        form.addRow("Motor #:", self.motor)
        form.addRow("Chassis #:", self.chassis)
        layout.addLayout(form)
        
        btn = QPushButton("Complete & Move to Warehouse")
        btn.setStyleSheet("background:#16a34a; color:white; font-weight:bold; padding:10px; border-radius:6px;")
        btn.clicked.connect(self._save)
        layout.addWidget(btn)

    def _save(self):
        if not all([self.pdi.text(), self.motor.text(), self.chassis.text()]):
            QMessageBox.warning(self, "Error", "All fields are required.")
            return
        self.result = {"pdi_number": self.pdi.text(), "serial_number": self.motor.text(), "chassis_number": self.chassis.text()}
        self.accept()

# ── MAIN SCREEN ────────────────────────────────────────────

class PDIScreen(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Header
        header = QLabel("Pre-Delivery Inspection (PDI)")
        header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(header)

        # Stats Grid
        self.grid = QGridLayout()
        layout.addLayout(self.grid)
        self.stat_card = _stat_card("Awaiting PDI", "0", "#f59e0b")
        self.grid.addWidget(self.stat_card, 0, 0)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Model Name", "Configuration", "Status", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("""
            QTableWidget { border: 1px solid #e5e7eb; background: white; border-radius: 8px; }
            QHeaderView::section { background: #f8fafc; padding: 10px; font-weight: 600; color: #374151; border: none; border-bottom: 1px solid #e5e7eb; }
        """)
        layout.addWidget(self.table)

    def _load_data(self):
        self.worker = PDIWorker()
        self.worker.finished.connect(self._populate_table)
        self.worker.start()

    def _populate_table(self, units):
        # Update Stats Card
        val_lbl = self.stat_card.findChild(QLabel, "val")
        if val_lbl: val_lbl.setText(str(len(units)))

        self.table.setRowCount(0)
        for row, u in enumerate(units):
            self.table.insertRow(row)
            
            # Create Items with explicit foreground color to ensure visibility
            name = QTableWidgetItem(u.get("model_name", "N/A"))
            config = QTableWidgetItem(f"{u.get('color', '-')} | {u.get('power_spec', '-')}")
            status = QTableWidgetItem("Awaiting PDI")
            
            for item in [name, config, status]:
                item.setForeground(QColor("#1a1a1a"))
            
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, config)
            self.table.setItem(row, 2, status)
            
            # Action Buttons
            btns = QWidget()
            hlay = QHBoxLayout(btns)
            hlay.setContentsMargins(0, 0, 0, 0)
            
            btn_comp = QPushButton("Complete")
            btn_comp.setFixedSize(90, 32)
            btn_comp.setStyleSheet("background:#2563eb; color:white; border-radius:4px; font-weight:bold;")
            btn_comp.clicked.connect(lambda _, unit=u: self._process_pdi(unit))
            
            btn_del = QPushButton("Delete")
            btn_del.setFixedSize(70, 32)
            btn_del.setStyleSheet("background:#ef4444; color:white; border-radius:4px;")
            btn_del.clicked.connect(lambda _, unit=u: self._delete_unit(unit))
            
            hlay.addWidget(btn_comp); hlay.addWidget(btn_del)
            self.table.setCellWidget(row, 3, btns)

    def _process_pdi(self, unit):
        dlg = PDICompleteDialog(self, unit)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            APIClient.post(f"/pdi/{unit['id']}/complete", dlg.result)
            self._load_data()

    def _delete_unit(self, unit):
        if QMessageBox.question(self, "Confirm", "Delete this record?") == QMessageBox.StandardButton.Yes:
            APIClient.delete(f"/pdi/{unit['id']}")
            self._load_data()