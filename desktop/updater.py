import os
import sys
import subprocess
import tempfile
import zipfile

import requests as _requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QFrame,
)


def get_app_dir() -> str:
    """
    Returns the directory that contains the running exe.
    In frozen (onedir) mode: the folder with GByke ERP.exe and all DLLs.
    In dev mode: the project root.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_exe_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.join(get_app_dir(), "main.py")


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


class _DownloadThread(QThread):
    progress = pyqtSignal(int)
    done     = pyqtSignal(str)   # path to downloaded zip, or "" on error

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            r = _requests.get(self.url, stream=True, timeout=120)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            tmp = tempfile.mktemp(suffix=".zip")
            downloaded = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(int(downloaded * 100 / total))
            self.progress.emit(100)
            self.done.emit(tmp)
        except Exception:
            self.done.emit("")


class UpdateDialog(QDialog):
    """
    Blocking dialog shown at startup when the server has a newer version.
    Only shown when running as a compiled exe (not in dev mode).
    """

    def __init__(self, server_version: str, client_version: str, download_url: str):
        super().__init__()
        self.download_url = download_url

        self.setWindowTitle("Update Required")
        self.setFixedSize(400, 240)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet("background: white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        title = QLabel("Update Required")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #1e293b;")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(sep)

        info = QLabel(
            f"A new version of G-Byke ERP is available.\n\n"
            f"  Your version:     {client_version}\n"
            f"  Latest version:   {server_version}\n\n"
            f"Please update to continue."
        )
        info.setStyleSheet("color: #334155; font-size: 13px;")
        layout.addWidget(info)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar { border: 1px solid #e2e8f0; border-radius: 4px; height: 10px; }"
            "QProgressBar::chunk { background: #3b82f6; border-radius: 4px; }"
        )
        layout.addWidget(self.progress)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        self.status_lbl.setVisible(False)
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn = QPushButton("Update Now")
        self.btn.setFixedWidth(130)
        self.btn.setStyleSheet(
            "QPushButton { background: #3b82f6; color: white; border-radius: 6px;"
            " padding: 8px 0; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background: #2563eb; }"
            "QPushButton:disabled { background: #94a3b8; }"
        )
        self.btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.btn)
        layout.addLayout(btn_row)

    def _start_download(self):
        self.btn.setEnabled(False)
        self.btn.setText("Downloading…")
        self.progress.setVisible(True)
        self.status_lbl.setText("Downloading update…")
        self.status_lbl.setVisible(True)

        self._thread = _DownloadThread(self.download_url)
        self._thread.progress.connect(self.progress.setValue)
        self._thread.done.connect(self._on_done)
        self._thread.start()

    def _on_done(self, zip_path: str):
        if not zip_path:
            self.status_lbl.setText("Download failed. Check network and retry.")
            self.btn.setText("Retry")
            self.btn.setEnabled(True)
            return

        self.status_lbl.setText("Installing… app will restart automatically.")

        app_dir    = get_app_dir()
        exe_path   = get_exe_path()
        extract_to = tempfile.mkdtemp(prefix="_gbyke_update_")

        # Extract zip to temp folder
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_to)
        os.remove(zip_path)

        # Write a bat that:
        # 1. Kills EVERY instance of the app by image name (any extra instance from the
        #    same folder keeps the _internal DLLs locked, so killing one PID isn't enough)
        # 2. Copies new files over the app dir with robocopy
        # 3. Relaunches the exe
        exe_name = os.path.basename(exe_path)   # "GByke ERP.exe"
        log_path = os.path.join(tempfile.gettempdir(), "_gbyke_update_log.txt")
        bat_path = os.path.join(tempfile.gettempdir(), "_gbyke_updater.bat")
        with open(bat_path, "w") as f:
            f.write("@echo off\n")
            f.write(f'echo Update started %DATE% %TIME% > "{log_path}"\n')
            f.write("timeout /t 1 /nobreak >nul\n")
            # Kill ALL instances of the app so no DLL in _internal stays locked.
            f.write(f'taskkill /F /IM "{exe_name}" >nul 2>&1\n')
            f.write(f'echo Killed all instances of {exe_name} >> "{log_path}"\n')
            f.write("timeout /t 1 /nobreak >nul\n")
            # robocopy with retry (/R:5 /W:1) in case a lock lingers briefly. Exit <8 = success.
            f.write(f'robocopy "{extract_to}" "{app_dir}" /E /R:5 /W:1 >> "{log_path}" 2>&1\n')
            f.write(f'if errorlevel 8 (echo ROBOCOPY FAILED >> "{log_path}") else (echo Copy OK >> "{log_path}")\n')
            f.write(f'start "" "{exe_path}"\n')
            f.write(f'echo Relaunched >> "{log_path}"\n')
            f.write(f'rmdir /s /q "{extract_to}"\n')
            f.write('del "%~f0"\n')

        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        # Force-terminate immediately. sys.exit() is unreliable here because the Qt modal
        # event loop and the download QThread keep the process alive, so the updater bat
        # would wait forever for this PID. os._exit bypasses all cleanup and ends now.
        os._exit(0)
