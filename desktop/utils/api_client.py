import requests
from desktop.utils.session import Session

# ── CHANGE THIS TO YOUR CAMERA PC's LOCAL IP WHEN DEPLOYING ──
SERVER_IP = "127.0.0.1"
SERVER_PORT = 8000
BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}"

TIMEOUT = 10  # seconds


class APIError(Exception):
    """Raised when the API returns an error."""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class APIClient:

    @staticmethod
    def _headers() -> dict:
        headers = {"Content-Type": "application/json"}
        if Session.token:
            headers["Authorization"] = f"Bearer {Session.token}"
        return headers

    @staticmethod
    def _handle_response(response: requests.Response) -> dict:
        try:
            data = response.json()
        except Exception:
            data = {}

        if response.status_code == 200 or response.status_code == 201:
            return data

        # Extract error detail
        detail = data.get("detail", f"Server error {response.status_code}")
        raise APIError(detail, response.status_code)

    @classmethod
    def get(cls, endpoint: str) -> dict:
        try:
            response = requests.get(
                f"{BASE_URL}{endpoint}",
                headers=cls._headers(),
                timeout=TIMEOUT
            )
            return cls._handle_response(response)
        except requests.exceptions.ConnectionError:
            raise APIError("Cannot connect to server. Check that the server is running.")
        except requests.exceptions.Timeout:
            raise APIError("Server took too long to respond. Try again.")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Unexpected error: {str(e)}")

    @classmethod
    def post(cls, endpoint: str, data: dict) -> dict:
        try:
            response = requests.post(
                f"{BASE_URL}{endpoint}",
                json=data,
                headers=cls._headers(),
                timeout=TIMEOUT
            )
            return cls._handle_response(response)
        except requests.exceptions.ConnectionError:
            raise APIError("Cannot connect to server. Check that the server is running.")
        except requests.exceptions.Timeout:
            raise APIError("Server took too long to respond. Try again.")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Unexpected error: {str(e)}")

    @classmethod
    def patch(cls, endpoint: str, data: dict = None) -> dict:
        try:
            response = requests.patch(
                f"{BASE_URL}{endpoint}",
                json=data or {},
                headers=cls._headers(),
                timeout=TIMEOUT
            )
            return cls._handle_response(response)
        except requests.exceptions.ConnectionError:
            raise APIError("Cannot connect to server. Check that the server is running.")
        except requests.exceptions.Timeout:
            raise APIError("Server took too long to respond. Try again.")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Unexpected error: {str(e)}")

    # ── AUTH SHORTCUTS ─────────────────────────────────────────

    @classmethod
    def login(cls, username: str, password: str) -> dict:
        return cls.post("/auth/login", {
            "username": username,
            "password": password
        })

    @classmethod
    def get_me(cls) -> dict:
        return cls.get("/auth/me")

    @classmethod
    def check_server(cls) -> bool:
        try:
            cls.get("/health")
            return True
        except APIError:
            return False