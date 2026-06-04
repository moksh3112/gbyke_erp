from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.core.dependencies import require_any_role
from app.models import ScooterUnit, User, VehicleStatus, ScooterModel
from app.schemas.pdi import ScooterUnitResponse, PDICompleteRequest

router = APIRouter(prefix="/pdi", tags=["PDI"])

@router.get("/pending", response_model=List[ScooterUnitResponse])
def get_pending_pdi(db: Session = Depends(get_db)):
    # Fetch units that are done with manufacturing
    units = db.query(ScooterUnit).filter(
        ScooterUnit.status == VehicleStatus.manufacturing_done
    ).all()
    return units

@router.post("/{unit_id}/complete")
def complete_pdi(unit_id: str, data: PDICompleteRequest, db: Session = Depends(get_db)):
    unit = db.query(ScooterUnit).filter(ScooterUnit.id == unit_id).first()
    if not unit: raise HTTPException(404, "Scooter not found")

    unit.serial_number = data.serial_number
    unit.chassis_number = data.chassis_number
    unit.pdi_number = data.pdi_number
    unit.status = VehicleStatus.pdi_done
    db.commit()
    return {"message": "Success"}

@router.delete("/{unit_id}")
def delete_unit(unit_id: str, db: Session = Depends(get_db)):
    unit = db.query(ScooterUnit).filter(ScooterUnit.id == unit_id).first()
    if unit:
        db.delete(unit)
        db.commit()
    return {"message": "Deleted"}