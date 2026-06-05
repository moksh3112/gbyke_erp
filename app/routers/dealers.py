from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.core.dependencies import require_any_role, require_manager_or_above, require_superadmin
from app.models import Dealer, ScooterUnit, User, VehicleStatus
from app.schemas.dealers import (
    DealerCreate, DealerUpdate, DealerResponse, UnitAtDealer, DispatchRequest
)

router = APIRouter(prefix="/dealers", tags=["Dealers"])


def _generate_dealer_code(name: str, db: Session) -> str:
    """Generate a unique dealer code from initials of the dealer name, e.g. 'Sharma Motors' → 'SM001'."""
    import re
    words   = re.sub(r'[^a-zA-Z\s]', '', name).split()
    initials = "".join(w[0].upper() for w in words if w)[:4] or "DLR"
    seq = 1
    while True:
        code = f"{initials}{seq:03d}"
        if not db.query(Dealer).filter(Dealer.dealer_code == code).first():
            return code
        seq += 1


def _dealer_to_response(dealer: Dealer, db: Session) -> DealerResponse:
    unit_count = db.query(ScooterUnit).filter(
        ScooterUnit.current_dealer_id == dealer.id
    ).count()
    return DealerResponse(
        id=dealer.id,
        dealer_name=dealer.dealer_name,
        dealer_code=dealer.dealer_code,
        contact_name=dealer.contact_name,
        contact_phone=dealer.contact_phone,
        contact_email=dealer.contact_email,
        city=dealer.city,
        state=dealer.state,
        is_active=dealer.is_active,
        unit_count=unit_count,
    )


def _unit_to_response(unit: ScooterUnit) -> UnitAtDealer:
    return UnitAtDealer(
        id=unit.id,
        serial_number=unit.serial_number,
        chassis_number=unit.chassis_number,
        pdi_number=unit.pdi_number,
        model_name=unit.model.model_name if unit.model else None,
        color=unit.color,
        status=unit.status.value,
        delivered_date=str(unit.delivered_date) if unit.delivered_date else None,
    )


@router.get("/", response_model=List[DealerResponse])
def get_dealers(
    active_only:  bool    = True,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    q = db.query(Dealer)
    if active_only:
        q = q.filter(Dealer.is_active == True)
    dealers = q.order_by(Dealer.dealer_name).all()
    return [_dealer_to_response(d, db) for d in dealers]


@router.post("/", response_model=DealerResponse)
def create_dealer(
    data:         DealerCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above),
):
    dealer_code = _generate_dealer_code(data.dealer_name, db)

    dealer = Dealer(
        dealer_name=data.dealer_name,
        dealer_code=dealer_code,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
        address=data.address,
        city=data.city,
        state=data.state,
    )
    db.add(dealer)
    db.commit()
    db.refresh(dealer)
    return _dealer_to_response(dealer, db)


@router.patch("/{dealer_id}", response_model=DealerResponse)
def update_dealer(
    dealer_id:    str,
    data:         DealerUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above),
):
    dealer = db.query(Dealer).filter(Dealer.id == dealer_id).first()
    if not dealer:
        raise HTTPException(404, "Dealer not found.")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(dealer, field, value)
    db.commit()
    db.refresh(dealer)
    return _dealer_to_response(dealer, db)


@router.patch("/{dealer_id}/deactivate")
def deactivate_dealer(
    dealer_id:    str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_superadmin),
):
    dealer = db.query(Dealer).filter(Dealer.id == dealer_id).first()
    if not dealer:
        raise HTTPException(404, "Dealer not found.")
    dealer.is_active = False
    db.commit()
    return {"message": f"Dealer '{dealer.dealer_name}' deactivated."}


@router.patch("/{dealer_id}/reactivate")
def reactivate_dealer(
    dealer_id:    str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_superadmin),
):
    dealer = db.query(Dealer).filter(Dealer.id == dealer_id).first()
    if not dealer:
        raise HTTPException(404, "Dealer not found.")
    dealer.is_active = True
    db.commit()
    return {"message": f"Dealer '{dealer.dealer_name}' reactivated."}


@router.delete("/{dealer_id}")
def delete_dealer(
    dealer_id:    str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_superadmin),
):
    dealer = db.query(Dealer).filter(Dealer.id == dealer_id).first()
    if not dealer:
        raise HTTPException(404, "Dealer not found.")
    unit_count = db.query(ScooterUnit).filter(ScooterUnit.current_dealer_id == dealer_id).count()
    if unit_count > 0:
        raise HTTPException(
            400,
            f"Cannot delete '{dealer.dealer_name}' — {unit_count} scooter unit(s) are assigned to them. "
            "Deactivate instead."
        )
    db.delete(dealer)
    db.commit()
    return {"message": f"Dealer '{dealer.dealer_name}' permanently deleted."}


@router.get("/units/ready", response_model=List[UnitAtDealer])
def get_ready_units(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    """Return all pdi_done units not yet assigned to any dealer."""
    units = db.query(ScooterUnit).filter(
        ScooterUnit.status == VehicleStatus.pdi_done,
        ScooterUnit.current_dealer_id == None,
    ).order_by(ScooterUnit.serial_number).all()
    return [_unit_to_response(u) for u in units]


@router.get("/{dealer_id}/units", response_model=List[UnitAtDealer])
def get_dealer_units(
    dealer_id:    str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    dealer = db.query(Dealer).filter(Dealer.id == dealer_id).first()
    if not dealer:
        raise HTTPException(404, "Dealer not found.")
    units = db.query(ScooterUnit).filter(
        ScooterUnit.current_dealer_id == dealer_id
    ).order_by(ScooterUnit.delivered_date.desc()).all()
    return [_unit_to_response(u) for u in units]


@router.post("/dispatch")
def dispatch_units(
    data:         DispatchRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above),
):
    dealer = db.query(Dealer).filter(Dealer.id == data.dealer_id, Dealer.is_active == True).first()
    if not dealer:
        raise HTTPException(404, "Dealer not found or inactive.")

    if not data.unit_ids:
        raise HTTPException(400, "No units specified for dispatch.")

    dispatch_date = date.today()
    if data.dispatch_date:
        try:
            dispatch_date = date.fromisoformat(data.dispatch_date)
        except ValueError:
            raise HTTPException(400, "Invalid dispatch_date format. Use YYYY-MM-DD.")

    dispatched = []
    errors = []
    for unit_id in data.unit_ids:
        unit = db.query(ScooterUnit).filter(ScooterUnit.id == unit_id).first()
        if not unit:
            errors.append(f"Unit {unit_id} not found.")
            continue
        if unit.status != VehicleStatus.pdi_done:
            errors.append(f"{unit.serial_number} is not PDI Done (status: {unit.status.value}).")
            continue
        if unit.current_dealer_id:
            errors.append(f"{unit.serial_number} is already assigned to a dealer.")
            continue

        unit.current_dealer_id = dealer.id
        unit.status            = VehicleStatus.delivered
        unit.delivered_date    = dispatch_date
        dispatched.append(unit.serial_number)

    if errors and not dispatched:
        db.rollback()
        raise HTTPException(400, " | ".join(errors))

    db.commit()
    return {
        "dispatched": dispatched,
        "dealer":     dealer.dealer_name,
        "count":      len(dispatched),
        "errors":     errors,
    }
