import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from desktop.app import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("G-Byke ERP")
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()