# app/main.py
# FIX 20: VERSION now imported from version.py — never hardcoded here again.
# To release a new version: change the number ONLY in version.py.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import Base, engine, test_connection
from app.routers import auth, inventory, models, users, manufacturing, pdi, warehouses 
import app.models

# ── Single source of truth ────────────────────────────────────────────────────
try:
    from version import VERSION  # FIX 20
except ImportError:
    VERSION = "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    test_connection()
    Base.metadata.create_all(bind=engine)
    print("✓ All tables ready.")
    yield


app = FastAPI(
    title   = "G-Byke ERP",
    version = VERSION,           # FIX 20
    lifespan = lifespan
)

app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(models.router)
app.include_router(users.router)
app.include_router(manufacturing.router)
app.include_router(pdi.router)
app.include_router(warehouses.router) 


@app.get("/")
def root():
    return {"status": "G-Byke ERP server is running", "version": VERSION}  # FIX 20

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/version")
def get_version():
    return {
        "version":        VERSION,   # FIX 20
        "force_update":   False,
        "update_message": ""
    }