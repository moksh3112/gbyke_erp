# app/routers/pdi.py
# FIX 2: Added authentication to all endpoints (were completely open before)
# FIX 3: API calls now in background workers on desktop side (see pdi.py)
# FIX 11: Broaden filter to include pdi_pending + pdi_in_progress units too
# FIX 12: Added PATCH /pdi/{unit_id}/start endpoint for pdi_in_progress transition

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.database import get_db
from app.core.dependencies import require_any_role, require_manager_or_above
from app.models import ScooterUnit, User, VehicleStatus, ScooterModel
from app.schemas.pdi import ScooterUnitResponse, PDICompleteRequest

router = APIRouter(prefix="/pdi", tags=["PDI"])


def _unit_to_response(unit: ScooterUnit) -> dict:
    """Build response dict — resolves model_name via the ORM relationship."""
    return {
        "id":             unit.id,
        "serial_number":  unit.serial_number,
        "chassis_number": unit.chassis_number,
        "model_name":     unit.model.model_name if unit.model else None,
        "color":          unit.color,
        "battery_type":   unit.battery_type,
        "power_spec":     unit.power_spec,
        "status":         unit.status.value if unit.status else None,
    }


@router.get("/pending")
def get_pending_pdi(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),   # FIX 2
):
    """Returns all units that need PDI (manufacturing_done, pdi_pending, pdi_in_progress)."""
    units = (
        db.query(ScooterUnit)
        .options(joinedload(ScooterUnit.model))          # eager-load so model_name works
        .filter(
            ScooterUnit.status.in_([                     # FIX 11
                VehicleStatus.manufacturing_done,
                VehicleStatus.pdi_pending,
                VehicleStatus.pdi_in_progress,
            ])
        )
        .order_by(ScooterUnit.created_at.asc())
        .all()
    )
    return [_unit_to_response(u) for u in units]


@router.patch("/{unit_id}/start")
def start_pdi(
    unit_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),   # FIX 12: new endpoint
):
    """Mark a unit as PDI In Progress."""
    unit = db.query(ScooterUnit).filter(ScooterUnit.id == unit_id).first()
    if not unit:
        raise HTTPException(404, "Scooter unit not found.")
    if unit.status not in [VehicleStatus.manufacturing_done, VehicleStatus.pdi_pending]:
        raise HTTPException(400, f"Cannot start PDI for a unit with status '{unit.status.value}'.")
    unit.status = VehicleStatus.pdi_in_progress
    db.commit()
    return {"message": "PDI started.", "status": "pdi_in_progress"}


@router.post("/{unit_id}/complete")
def complete_pdi(
    unit_id:      str,
    data:         PDICompleteRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),   # FIX 2
):
    unit = db.query(ScooterUnit).filter(ScooterUnit.id == unit_id).first()
    if not unit:
        raise HTTPException(404, "Scooter unit not found.")

    unit.serial_number  = data.serial_number
    unit.chassis_number = data.chassis_number
    unit.pdi_number     = data.pdi_number
    unit.status         = VehicleStatus.pdi_done
    db.commit()
    return {"message": "PDI completed successfully."}


@router.delete("/{unit_id}")
def delete_unit(
    unit_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above),  # FIX 2: managers only
):
    unit = db.query(ScooterUnit).filter(ScooterUnit.id == unit_id).first()
    if not unit:
        raise HTTPException(404, "Scooter unit not found.")
    db.delete(unit)
    db.commit()
    return {"message": "Unit deleted."}