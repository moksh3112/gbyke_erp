# app/routers/warehouses.py
# New router — Warehouse & Godown management
# Handles:
#   GET  /warehouses/                    — list all warehouses/godowns with scooter counts
#   GET  /warehouses/{location_id}/units — scooter units at a specific location
#   POST /warehouses/transfer            — transfer a scooter unit to another location

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.core.dependencies import require_any_role, require_manager_or_above
from app.models import (
    ScooterUnit, Location, User, VehicleStatus
)

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


# ── SCHEMAS ───────────────────────────────────────────────────────────────────

class WarehouseSummary(BaseModel):
    id:            str
    name:          str
    location_type: str
    city:          Optional[str] = None
    state:         Optional[str] = None
    is_active:     bool
    total_units:   int
    pdi_done:      int
    delivered:     int


class UnitAtLocation(BaseModel):
    id:             str
    serial_number:  str
    chassis_number: Optional[str] = None
    model_name:     Optional[str] = None
    color:          Optional[str] = None
    battery_type:   Optional[str] = None
    power_spec:     Optional[str] = None
    status:         str
    pdi_number:     Optional[str] = None


class TransferRequest(BaseModel):
    unit_id:         str
    to_location_id:  str
    notes:           Optional[str] = None


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[WarehouseSummary])
def get_warehouses(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    """Return all active warehouse/godown/factory locations with scooter counts."""
    locations = (
        db.query(Location)
        .filter(Location.is_active == True)
        .order_by(Location.location_type, Location.name)
        .all()
    )

    # One grouped query for all (location, status) counts — avoids N+1.
    from sqlalchemy import func
    rows = (
        db.query(
            ScooterUnit.current_location_id,
            ScooterUnit.status,
            func.count(ScooterUnit.id),
        )
        .filter(ScooterUnit.current_location_id.isnot(None))
        .group_by(ScooterUnit.current_location_id, ScooterUnit.status)
        .all()
    )
    totals:    dict = {}
    pdi_map:   dict = {}
    deliv_map: dict = {}
    for loc_id, status, cnt in rows:
        totals[loc_id] = totals.get(loc_id, 0) + cnt
        if status == VehicleStatus.pdi_done:
            pdi_map[loc_id] = pdi_map.get(loc_id, 0) + cnt
        elif status == VehicleStatus.delivered:
            deliv_map[loc_id] = deliv_map.get(loc_id, 0) + cnt

    return [
        WarehouseSummary(
            id            = loc.id,
            name          = loc.name,
            location_type = loc.location_type,
            city          = loc.city,
            state         = loc.state,
            is_active     = loc.is_active,
            total_units   = totals.get(loc.id, 0),
            pdi_done      = pdi_map.get(loc.id, 0),
            delivered     = deliv_map.get(loc.id, 0),
        )
        for loc in locations
    ]


@router.get("/{location_id}/units", response_model=List[UnitAtLocation])
def get_units_at_location(
    location_id:  str,
    status:       Optional[str] = None,
    db:           Session       = Depends(get_db),
    current_user: User          = Depends(require_any_role),
):
    """Return all scooter units stored at a specific location."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(404, "Location not found.")

    query = (
        db.query(ScooterUnit)
        .options(joinedload(ScooterUnit.model))
        .filter(ScooterUnit.current_location_id == location_id)
    )

    if status:
        try:
            status_enum = VehicleStatus(status)
            query = query.filter(ScooterUnit.status == status_enum)
        except ValueError:
            raise HTTPException(400, f"Invalid status '{status}'.")

    units = query.order_by(ScooterUnit.created_at.desc()).all()

    return [
        UnitAtLocation(
            id             = u.id,
            serial_number  = u.serial_number,
            chassis_number = u.chassis_number,
            model_name     = u.model.model_name if u.model else None,
            color          = u.color,
            battery_type   = u.battery_type,
            power_spec     = u.power_spec,
            status         = u.status.value if u.status else "unknown",
            pdi_number     = u.pdi_number,
        )
        for u in units
    ]


@router.post("/transfer")
def transfer_unit(
    data:         TransferRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above),
):
    """Transfer a scooter unit from its current location to another location."""
    unit = (
        db.query(ScooterUnit)
        .options(joinedload(ScooterUnit.model))
        .filter(ScooterUnit.id == data.unit_id)
        .first()
    )
    if not unit:
        raise HTTPException(404, "Scooter unit not found.")

    to_location = db.query(Location).filter(
        Location.id == data.to_location_id,
        Location.is_active == True
    ).first()
    if not to_location:
        raise HTTPException(404, "Destination location not found or inactive.")

    if unit.current_location_id == data.to_location_id:
        raise HTTPException(400, "Unit is already at that location.")

    from_name = "Unknown"
    if unit.current_location_id:
        from_loc = db.query(Location).filter(
            Location.id == unit.current_location_id
        ).first()
        if from_loc:
            from_name = from_loc.name

    unit.current_location_id = data.to_location_id
    db.commit()

    model_name = unit.model.model_name if unit.model else "Unknown"
    return {
        "message":    "Unit transferred successfully.",
        "unit_id":    unit.id,
        "serial":     unit.serial_number,
        "model":      model_name,
        "from":       from_name,
        "to":         to_location.name,
    }