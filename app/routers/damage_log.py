from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.core.dependencies import require_any_role
from app.models import (
    StockMovement, InventoryItem,
    ScooterUnit, VehicleStatus, User,
    AssemblyJob, AssemblyStatus,
    DamageRecord, DamageStage,
)

router = APIRouter(prefix="/damage-log", tags=["Damage Log"])


class DamageRecordCreate(BaseModel):
    scooter_unit_id: str
    stage:           str        # "transit" or "dealer"
    part_name:       str
    notes:           Optional[str] = None


class SparePartDamageCreate(BaseModel):
    dealer_id:  str
    part_name:  str
    notes:      str
    stage:      str = "dealer"


@router.post("/")
def create_damage_record(
    data:         DamageRecordCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    unit = db.query(ScooterUnit).filter(ScooterUnit.id == data.scooter_unit_id).first()
    if not unit:
        raise HTTPException(404, "Scooter unit not found.")

    try:
        stage = DamageStage(data.stage)
    except ValueError:
        raise HTTPException(400, f"Invalid stage '{data.stage}'. Use 'transit' or 'dealer'.")

    record = DamageRecord(
        scooter_unit_id = data.scooter_unit_id,
        stage           = stage,
        root_cause      = data.part_name,
        corrective_action = data.notes,
        reported_by     = current_user.id,
    )
    db.add(record)
    db.commit()
    return {"message": "Damage record created.", "id": record.id}


@router.post("/spare-part-damage")
def create_spare_part_damage(
    data:         SparePartDamageCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    from app.models import Dealer
    dealer = db.query(Dealer).filter(Dealer.id == data.dealer_id).first()
    if not dealer:
        raise HTTPException(404, "Dealer not found.")
    try:
        stage = DamageStage(data.stage)
    except ValueError:
        raise HTTPException(400, f"Invalid stage '{data.stage}'.")

    record = DamageRecord(
        dealer_id         = data.dealer_id,
        stage             = stage,
        part_name_free    = data.part_name,
        root_cause        = data.part_name,
        corrective_action = data.notes,
        reported_by       = current_user.id,
    )
    db.add(record)
    db.commit()
    return {"message": "Spare part damage recorded.", "id": record.id}


@router.get("/dealer-damages")
def list_dealer_damages(
    scooter_unit_id: Optional[str] = None,
    search:          Optional[str] = None,
    db:              Session = Depends(get_db),
    current_user:    User    = Depends(require_any_role),
):
    from app.models import ScooterModel, Dealer
    q = db.query(DamageRecord, User, ScooterUnit, Dealer).outerjoin(
        User, DamageRecord.reported_by == User.id
    ).outerjoin(
        ScooterUnit, DamageRecord.scooter_unit_id == ScooterUnit.id
    ).outerjoin(
        Dealer, DamageRecord.dealer_id == Dealer.id
    ).filter(
        DamageRecord.stage.in_([DamageStage.transit, DamageStage.dealer])
    )
    if scooter_unit_id:
        q = q.filter(DamageRecord.scooter_unit_id == scooter_unit_id)
    if search:
        q = q.outerjoin(ScooterModel, ScooterUnit.model_id == ScooterModel.id).filter(
            DamageRecord.root_cause.ilike(f"%{search}%") |
            DamageRecord.part_name_free.ilike(f"%{search}%") |
            ScooterUnit.serial_number.ilike(f"%{search}%") |
            ScooterModel.model_name.ilike(f"%{search}%") |
            ScooterUnit.color.ilike(f"%{search}%")
        )

    rows = q.order_by(DamageRecord.created_at.desc()).all()

    result = []
    for rec, reporter, unit, dealer in rows:
        is_spare = rec.scooter_unit_id is None
        result.append({
            "id":            rec.id,
            "serial_number": unit.serial_number if unit else ("—" if not is_spare else "Spare Part"),
            "model_name":    (unit.model.model_name if unit and unit.model else None) or (dealer.dealer_name if dealer else "—"),
            "color":         unit.color if unit else "—",
            "stage":         rec.stage.value,
            "part_name":     rec.root_cause or "—",
            "notes":         rec.corrective_action or "",
            "reported_by":   reporter.full_name if reporter else "—",
            "created_at":    rec.created_at.strftime("%d-%b-%Y  %H:%M") if rec.created_at else "—",
            "is_spare_part": is_spare,
        })
    return result


@router.get("/summary")
def get_summary(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    damaged_parts = db.query(func.sum(StockMovement.quantity)).filter(
        StockMovement.movement_type.in_(["defective", "damaged"])
    ).scalar() or 0

    after_sale_events = db.query(func.count(DamageRecord.id)).filter(
        DamageRecord.stage.in_([DamageStage.transit, DamageStage.dealer])
    ).scalar() or 0

    return {
        "damaged_parts_qty":  int(damaged_parts),
        "after_sale_events":  int(after_sale_events),
    }


@router.get("/parts")
def list_damaged_parts(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    search:    Optional[str] = None,
    db:        Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    q = db.query(StockMovement, InventoryItem, User).outerjoin(
        InventoryItem, StockMovement.item_id == InventoryItem.id
    ).outerjoin(
        User, StockMovement.performed_by == User.id
    ).filter(
        StockMovement.movement_type.in_(["defective", "damaged"])
    )
    if from_date:
        q = q.filter(StockMovement.created_at >= from_date)
    if to_date:
        q = q.filter(StockMovement.created_at <= to_date + " 23:59:59")
    if search:
        q = q.filter(
            InventoryItem.item_name.ilike(f"%{search}%") |
            InventoryItem.sku.ilike(f"%{search}%") |
            InventoryItem.model_name.ilike(f"%{search}%")
        )

    rows = q.order_by(StockMovement.created_at.desc()).all()

    return [
        {
            "id":          m.id,
            "date":        m.created_at.strftime("%d-%b-%Y  %H:%M") if m.created_at else "—",
            "item_name":   (inv.item_name if inv else None) or "—",
            "sku":         (inv.sku       if inv else None) or "—",
            "type":        m.movement_type,
            "quantity":    m.quantity,
            "notes":       m.notes or "",
            "reported_by": u.full_name if u else "—",
        }
        for m, inv, u in rows
    ]


@router.get("/units")
def list_damaged_units(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    search:    Optional[str] = None,
    db:        Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    q = db.query(ScooterUnit).filter(
        ScooterUnit.status.in_([VehicleStatus.defective, VehicleStatus.damaged])
    )
    if search:
        q = q.filter(
            ScooterUnit.serial_number.ilike(f"%{search}%") |
            ScooterUnit.chassis_number.ilike(f"%{search}%") |
            ScooterUnit.pdi_number.ilike(f"%{search}%")
        )

    units = q.order_by(ScooterUnit.updated_at.desc()).all()

    return [
        {
            "id":             u.id,
            "serial_number":  u.serial_number,
            "chassis_number": u.chassis_number or "—",
            "pdi_number":     u.pdi_number or "—",
            "model_name":     u.model.model_name if u.model else "—",
            "color":          u.color or "—",
            "status":         u.status.value,
            "updated_at":     u.updated_at.strftime("%d-%b-%Y") if u.updated_at else "—",
        }
        for u in units
    ]


@router.get("/manufacturing")
def list_cancelled_jobs(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    db:        Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    q = db.query(AssemblyJob).filter(
        AssemblyJob.status == AssemblyStatus.cancelled
    )
    if from_date:
        q = q.filter(AssemblyJob.created_at >= from_date)
    if to_date:
        q = q.filter(AssemblyJob.created_at <= to_date + " 23:59:59")

    jobs = q.order_by(AssemblyJob.created_at.desc()).all()

    result = []
    for j in jobs:
        created_by = db.query(User).filter(User.id == j.created_by).first() if j.created_by else None
        result.append({
            "id":           j.id,
            "job_number":   j.job_number,
            "model_name":   j.model.model_name if j.model else "—",
            "quantity":     j.quantity,
            "damaged_qty":  j.damaged_quantity,
            "notes":        j.notes or "",
            "created_by":   created_by.full_name if created_by else "—",
            "created_at":   j.created_at.strftime("%d-%b-%Y") if j.created_at else "—",
        })
    return result
