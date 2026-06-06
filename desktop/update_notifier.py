from PyQt6.QtCore import QThread, pyqtSignal


class UpdatePoller(QThread):
    """
    Background thread started after login.
    Polls /version every 5 minutes. Emits update_available once when a newer
    version is detected, then stops — no repeated notifications.
    """
    update_available = pyqtSignal(str)   # new version string

    def run(self):
        from version import VERSION
        from desktop.utils.api_client import APIClient

        while True:
            self.sleep(300)   # 5 minutes
            try:
                info = APIClient.get_server_version()
                if info and info.get("version") and info["version"] != VERSION:
                    self.update_available.emit(info["version"])
                    break
            except Exception:
                pass
