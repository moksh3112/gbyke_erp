# app/main.py
# FIX 20: VERSION now imported from version.py — never hardcoded here again.
# To release a new version: change the number ONLY in version.py.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.database import Base, engine, test_connection
from app.routers import auth, inventory, models, users, manufacturing, pdi, warehouses, dealers, shipments, spare_parts, damage_log, reports, updates
import app.models

# ── Single source of truth ────────────────────────────────────────────────────
try:
    from version import VERSION  # FIX 20
except ImportError:
    VERSION = "unknown"


def _run_migrations():
    """Safe column additions — each is idempotent (IF NOT EXISTS)."""
    migrations = [
        """
        ALTER TABLE dispatch_note_parts
        ADD COLUMN IF NOT EXISTS inventory_item_id VARCHAR
        REFERENCES inventory_items(id);
        """,
        """
        ALTER TABLE dispatch_note_parts
        ADD COLUMN IF NOT EXISTS location_id VARCHAR
        REFERENCES locations(id);
        """,
        """
        ALTER TABLE damage_records
        ADD COLUMN IF NOT EXISTS dealer_id VARCHAR
        REFERENCES dealers(id);
        """,
        """
        ALTER TABLE damage_records
        ADD COLUMN IF NOT EXISTS part_name_free VARCHAR(300);
        """,
        """
        ALTER TABLE bom_items
        ADD COLUMN IF NOT EXISTS is_colour_specific BOOLEAN DEFAULT FALSE;
        """,
    ]
    with engine.begin() as conn:
        for sql in migrations:
            conn.execute(text(sql))
        # Ensure the special "General Parts" model exists
        conn.execute(text("""
            INSERT INTO scooter_models (id, model_name, model_code, is_active)
            SELECT gen_random_uuid()::text, 'General Parts', 'GEN', true
            WHERE NOT EXISTS (
                SELECT 1 FROM scooter_models WHERE model_code = 'GEN'
            );
        """))
    print("✓ Migrations applied.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    test_connection()
    Base.metadata.create_all(bind=engine)
    _run_migrations()
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
app.include_router(dealers.router)
app.include_router(shipments.router)
app.include_router(spare_parts.router)
app.include_router(damage_log.router)
app.include_router(reports.router)
app.include_router(updates.router)


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