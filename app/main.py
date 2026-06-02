from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import Base, engine, test_connection
from app.routers import auth
import app.models

@asynccontextmanager
async def lifespan(app: FastAPI):
    test_connection()
    Base.metadata.create_all(bind=engine)
    print("✓ All tables ready.")
    yield

app = FastAPI(
    title="G-Byke ERP",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(auth.router)

@app.get("/")
def root():
    return {"status": "G-Byke ERP server is running", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/version")
def get_version():
    """
    Desktop app calls this on startup to check if an update is available.
    When you push a new version, bump the number here and in version.py.
    """
    return {
        "version": "1.0.2",
        "force_update": False,      # set True to force all clients to update
        "update_message": ""        # shown to user when update is available
    }