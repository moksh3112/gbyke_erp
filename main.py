import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from desktop.app import MainWindow


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

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()