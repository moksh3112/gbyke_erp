import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from desktop.app import MainWindow


def _check_for_update():
    """
    Called at startup before the main window appears.
    If the server has a newer version AND we are running as a compiled exe,
    show a blocking update dialog. Silently skipped if server is offline.
    """
    from desktop.updater import UpdateDialog, is_frozen
    if not is_frozen():
        return   # don't force-update in dev mode

    try:
        from desktop.utils.api_client import APIClient, BASE_URL
        from version import VERSION
        info = APIClient.get_server_version()
        if info and info.get("version") and info["version"] != VERSION:
            dlg = UpdateDialog(
                server_version=info["version"],
                client_version=VERSION,
                download_url=f"{BASE_URL}/download/client",
            )
            dlg.exec()   # blocks until update completes or app exits
    except Exception:
        pass   # server offline — skip update check, proceed to login


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("G-Byke ERP")
    app.setFont(QFont("Segoe UI", 10))

    # Fix white text on white background in all dialogs
    app.setStyleSheet("""
        QMessageBox {
            background-color: white;
        }
        QMessageBox QLabel {
            color: #1a1a1a;
            font-size: 13px;
        }
        QMessageBox QPushButton {
            color: #1a1a1a;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 4px 16px;
            min-width: 60px;
        }
        QMessageBox QPushButton:hover {
            background: #f0f0f0;
        }
        QInputDialog QLabel {
            color: #1a1a1a;
        }
        QInputDialog QLineEdit {
            color: #1a1a1a;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QToolTip {
            color: #1a1a1a;
            background: white;
            border: 1px solid #ddd;
        }
    """)

    _check_for_update()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()