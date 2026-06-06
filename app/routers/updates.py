import os
import zipfile
import tempfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/download", tags=["updates"])

_DIST_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "dist", "GByke ERP")
)


def _make_zip() -> str:
    """Zip dist/GByke ERP/ folder into a temp file and return its path."""
    tmp = tempfile.mktemp(suffix=".zip")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(_DIST_DIR):
            for fname in files:
                full = os.path.join(root, fname)
                arcname = os.path.relpath(full, _DIST_DIR)
                zf.write(full, arcname)
    return tmp


@router.get("/client")
def download_client():
    if not os.path.isdir(_DIST_DIR):
        raise HTTPException(status_code=404, detail="Client build not found. Run pyinstaller first.")
    zip_path = _make_zip()
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="GByke ERP.zip",
        background=None,
    )
