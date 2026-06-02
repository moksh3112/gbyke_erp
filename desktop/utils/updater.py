from desktop.utils.api_client import APIClient
from version import VERSION


def check_for_updates() -> dict:
    """
    Checks the server for the latest version.
    Returns a dict with:
      - update_available (bool)
      - force_update (bool)
      - message (str)
      - server_version (str)
      - current_version (str)
    """
    result = {
        "update_available": False,
        "force_update": False,
        "message": "",
        "server_version": VERSION,
        "current_version": VERSION,
    }

    try:
        data = APIClient.get_server_version()
        if not data:
            return result

        server_version = data.get("version", VERSION)
        result["server_version"] = server_version
        result["force_update"] = data.get("force_update", False)
        result["message"] = data.get("update_message", "")

        if server_version != VERSION:
            result["update_available"] = True

    except Exception:
        pass

    return result