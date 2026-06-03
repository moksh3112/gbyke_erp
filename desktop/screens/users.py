from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QDialog, QFormLayout, QLineEdit, QComboBox,
    QMessageBox, QHeaderView, QAbstractItemView,
    QCheckBox, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from desktop.utils.api_client import APIClient, APIError
from desktop.utils.session import Session


# ── WORKER ────────────────────────────────────────────────────

class LoadUsersWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.done.emit(APIClient.get("/users"))
        except APIError as e:
            self.error.emit(e.message)


# ── ADD / EDIT USER DIALOG ────────────────────────────────────

class UserDialog(QDialog):
    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.user        = user
        self.result_data = {}
        self.setWindowTitle("Edit User" if user else "Add User")
        self.setFixedWidth(440)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setHorizontalSpacing(16)

        lbl = "font-size:13px; font-weight:500; color:#374151;"
        inp = ("border:1px solid #ddd; border-radius:6px;"
               "padding:0 10px; color:#1a1a1a; background:white;")

        # Full name
        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(38)
        self.name_input.setStyleSheet(inp)
        self.name_input.setPlaceholderText("e.g. Rahul Sharma")
        nl = QLabel("Full Name *"); nl.setStyleSheet(lbl)
        form.addRow(nl, self.name_input)

        # Username
        self.username_input = QLineEdit()
        self.username_input.setFixedHeight(38)
        self.username_input.setStyleSheet(inp)
        self.username_input.setPlaceholderText("e.g. rahul123")
        ul = QLabel("Username *"); ul.setStyleSheet(lbl)
        form.addRow(ul, self.username_input)

        # Password
        self.password_input = QLineEdit()
        self.password_input.setFixedHeight(38)
        self.password_input.setStyleSheet(inp)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        if self.user:
            self.password_input.setPlaceholderText(
                "Leave blank to keep current password"
            )
        else:
            self.password_input.setPlaceholderText("Enter password")
        pl = QLabel(
            "Password *" if not self.user else "New Password"
        )
        pl.setStyleSheet(lbl)
        form.addRow(pl, self.password_input)

        # Role
        self.role_combo = QComboBox()
        self.role_combo.setFixedHeight(38)
        self.role_combo.setStyleSheet(inp)
        self.role_combo.addItem("👔  Manager", "manager")
        self.role_combo.addItem("👷  Staff",   "staff")
        rl = QLabel("Role *"); rl.setStyleSheet(lbl)
        form.addRow(rl, self.role_combo)

        layout.addLayout(form)

        # Pre-fill if editing
        if self.user:
            self.name_input.setText(self.user.get("full_name", ""))
            self.username_input.setText(self.user.get("username", ""))
            role = self.user.get("role", "staff")
            for i in range(self.role_combo.count()):
                if self.role_combo.itemData(i) == role:
                    self.role_combo.setCurrentIndex(i)
                    break

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(40)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            "border:1px solid #ddd; border-radius:6px;"
            "color:#666; font-size:13px;"
        )

        save_btn = QPushButton(
            "Save Changes" if self.user else "Add User"
        )
        save_btn.setFixedHeight(40)
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
        name     = self.name_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        role     = self.role_combo.currentData()

        if not name:
            QMessageBox.warning(self, "Missing", "Full name is required.")
            return
        if not username:
            QMessageBox.warning(self, "Missing", "Username is required.")
            return
        if not self.user and not password:
            QMessageBox.warning(self, "Missing", "Password is required.")
            return

        self.result_data = {
            "full_name": name,
            "username":  username,
            "role":      role,
        }
        if password:
            self.result_data["password"] = password

        self.accept()


# ── USERS SCREEN ──────────────────────────────────────────────

class UsersScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.users   = []
        self.workers = []
        self._build_ui()
        self._load_users()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("👥  User Management")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#1e293b;")
        header_row.addWidget(title)
        header_row.addStretch()

        add_btn = QPushButton("+ Add User")
        add_btn.setFixedHeight(36)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background:#2563eb; color:white; border:none;
                border-radius:6px; padding:0 16px; font-weight:600;
            }
            QPushButton:hover { background:#1d4ed8; }
        """)
        add_btn.clicked.connect(self._add_user)
        header_row.addWidget(add_btn)
        layout.addLayout(header_row)

        sub = QLabel(
            "Manage manager and staff accounts. "
            "Only you can see this screen."
        )
        sub.setStyleSheet("color:#64748b; font-size:13px;")
        layout.addWidget(sub)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Full Name", "Username", "Role", "Status", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 200)
        self.table.verticalHeader().setDefaultSectionSize(46)
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
        self.status_label.setStyleSheet(
            "color:#94a3b8; font-size:12px;"
        )
        layout.addWidget(self.status_label)

    # ── LOADING ───────────────────────────────────────────────

    def _load_users(self):
        self.status_label.setText("Loading...")
        worker = LoadUsersWorker()
        worker.done.connect(self._populate_table)
        worker.error.connect(
            lambda e: self.status_label.setText(f"Error: {e}")
        )
        self.workers.append(worker)
        worker.start()

    def _populate_table(self, users):
        self.users = users
        self.table.setRowCount(len(users))

        role_icons = {
            "manager": "👔 Manager",
            "staff":   "👷 Staff"
        }

        for row, user in enumerate(users):
            def cell(text, align=Qt.AlignmentFlag.AlignLeft):
                c = QTableWidgetItem(str(text) if text else "—")
                c.setTextAlignment(
                    align | Qt.AlignmentFlag.AlignVCenter
                )
                return c

            self.table.setItem(row, 0, cell(user["full_name"]))
            self.table.setItem(row, 1, cell(user["username"]))
            self.table.setItem(
                row, 2,
                cell(
                    role_icons.get(user["role"], user["role"]),
                    Qt.AlignmentFlag.AlignCenter
                )
            )

            # Status
            is_active  = user.get("is_active", True)
            status_cell = QTableWidgetItem(
                "Active" if is_active else "Inactive"
            )
            status_cell.setForeground(
                QColor("#16a34a") if is_active else QColor("#dc2626")
            )
            status_cell.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter |
                Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 3, status_cell)

            # Action buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 4, 4, 4)
            btn_layout.setSpacing(6)

            edit_btn = QPushButton("✏️  Edit")
            edit_btn.setFixedHeight(32)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setStyleSheet("""
                QPushButton {
                    background:#2563eb; color:white; border:none;
                    border-radius:4px; font-size:12px; padding:0 12px;
                }
                QPushButton:hover { background:#1d4ed8; }
            """)
            edit_btn.clicked.connect(
                lambda checked, u=user: self._edit_user(u)
            )

            # Toggle active/inactive button
            if is_active:
                toggle_btn = QPushButton("🚫  Deactivate")
                toggle_btn.setStyleSheet("""
                    QPushButton {
                        background:#f59e0b; color:white; border:none;
                        border-radius:4px; font-size:12px; padding:0 12px;
                    }
                    QPushButton:hover { background:#d97706; }
                """)
            else:
                toggle_btn = QPushButton("✅  Activate")
                toggle_btn.setStyleSheet("""
                    QPushButton {
                        background:#16a34a; color:white; border:none;
                        border-radius:4px; font-size:12px; padding:0 12px;
                    }
                    QPushButton:hover { background:#15803d; }
                """)
            toggle_btn.setFixedHeight(32)
            toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle_btn.clicked.connect(
                lambda checked, u=user: self._toggle_user(u)
            )

            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(toggle_btn)
            self.table.setCellWidget(row, 4, btn_widget)

        self.status_label.setText(f"{len(users)} users loaded")

    # ── ACTIONS ───────────────────────────────────────────────

    def _add_user(self):
        dlg = UserDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.post("/users", dlg.result_data)
                QMessageBox.information(
                    self, "Success",
                    f"User '{dlg.result_data['username']}' created."
                )
                self._load_users()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _edit_user(self, user):
        dlg = UserDialog(self, user=user)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                APIClient.patch(
                    f"/users/{user['id']}",
                    dlg.result_data
                )
                QMessageBox.information(
                    self, "Success", "User updated successfully."
                )
                self._load_users()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)

    def _toggle_user(self, user):
        is_active = user.get("is_active", True)
        action    = "Deactivate" if is_active else "Activate"

        reply = QMessageBox.question(
            self, f"Confirm {action}",
            f"{action} user '{user['username']}'?",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                APIClient.patch(
                    f"/users/{user['id']}",
                    {"is_active": not is_active}
                )
                QMessageBox.information(
                    self, "Done",
                    f"User '{user['username']}' "
                    f"{'deactivated' if is_active else 'activated'}."
                )
                self._load_users()
            except APIError as e:
                QMessageBox.critical(self, "Error", e.message)