from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from datetime import date

from app.database import get_db
from app.core.dependencies import require_any_role, require_manager_or_above
from app.models import (
    Dealer, ScooterUnit, VehicleStatus, User,
    DispatchNote, DispatchNoteScooter, DispatchNotePart,
    InventoryItem, InventoryLocationStock,
)

router = APIRouter(prefix="/shipments", tags=["Shipments"])


# ── SCHEMAS ───────────────────────────────────────────────────

class ScooterDispatchItem(BaseModel):
    pdi_number: str

class PartDispatchItem(BaseModel):
    part_name:         str
    quantity:          int
    inventory_item_id: Optional[str] = None
    location_id:       Optional[str] = None
    notes:             Optional[str] = None

class DispatchNoteCreate(BaseModel):
    dealer_id:     str
    dispatch_date: Optional[str] = None
    notes:         Optional[str] = None
    scooters:      List[ScooterDispatchItem] = []
    parts:         List[PartDispatchItem]    = []

class DispatchNoteScooterOut(BaseModel):
    scooter_unit_id: str
    serial_number:   str
    pdi_number:      Optional[str] = None
    model_name:      Optional[str] = None
    color:           Optional[str] = None

class DispatchNotePartOut(BaseModel):
    part_name: str
    quantity:  int
    notes:     Optional[str] = None

class DispatchNoteDetail(BaseModel):
    id:            str
    dealer_id:     str
    dealer_name:   str
    dealer_code:   str
    dispatch_date: str
    notes:         Optional[str] = None
    created_at:    str
    scooters:      List[DispatchNoteScooterOut] = []
    parts:         List[DispatchNotePartOut]    = []

class DispatchNoteSummary(BaseModel):
    id:            str
    dealer_name:   str
    dealer_code:   str
    dispatch_date: str
    scooter_count: int
    part_count:    int
    notes:         Optional[str] = None
    created_at:    str


# ── HELPERS ───────────────────────────────────────────────────

def _note_to_detail(note: DispatchNote) -> DispatchNoteDetail:
    return DispatchNoteDetail(
        id=note.id,
        dealer_id=note.dealer_id,
        dealer_name=note.dealer.dealer_name,
        dealer_code=note.dealer.dealer_code,
        dispatch_date=str(note.dispatch_date),
        notes=note.notes,
        created_at=str(note.created_at)[:19],
        scooters=[
            DispatchNoteScooterOut(
                scooter_unit_id=s.scooter_unit_id,
                serial_number=s.scooter_unit.serial_number,
                pdi_number=s.scooter_unit.pdi_number,
                model_name=s.scooter_unit.model.model_name if s.scooter_unit.model else None,
                color=s.scooter_unit.color,
            )
            for s in note.scooters
        ],
        parts=[
            DispatchNotePartOut(
                part_name=p.part_name,
                quantity=p.quantity,
                notes=p.notes,
            )
            for p in note.parts
        ],
    )

def _note_to_summary(note: DispatchNote) -> DispatchNoteSummary:
    return DispatchNoteSummary(
        id=note.id,
        dealer_name=note.dealer.dealer_name,
        dealer_code=note.dealer.dealer_code,
        dispatch_date=str(note.dispatch_date),
        scooter_count=len(note.scooters),
        part_count=len(note.parts),
        notes=note.notes,
        created_at=str(note.created_at)[:19],
    )


# ── ENDPOINTS ─────────────────────────────────────────────────

@router.get("/summary")
def get_summary(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    total_notes    = db.query(DispatchNote).count()
    total_scooters = db.query(DispatchNoteScooter).count()
    total_parts    = db.query(func.sum(DispatchNotePart.quantity)).scalar() or 0
    return {
        "total_dispatches":  total_notes,
        "total_scooters":    total_scooters,
        "total_parts":       int(total_parts),
    }


@router.get("/", response_model=List[DispatchNoteSummary])
def list_dispatch_notes(
    dealer_id:  Optional[str] = None,
    from_date:  Optional[str] = None,
    to_date:    Optional[str] = None,
    db:         Session = Depends(get_db),
    current_user: User  = Depends(require_any_role),
):
    q = db.query(DispatchNote).options(
        joinedload(DispatchNote.dealer),
        selectinload(DispatchNote.scooters),
        selectinload(DispatchNote.parts),
    )
    if dealer_id:
        q = q.filter(DispatchNote.dealer_id == dealer_id)
    if from_date:
        q = q.filter(DispatchNote.dispatch_date >= from_date)
    if to_date:
        q = q.filter(DispatchNote.dispatch_date <= to_date)
    notes = q.order_by(DispatchNote.dispatch_date.desc(), DispatchNote.created_at.desc()).all()
    return [_note_to_summary(n) for n in notes]


@router.get("/{note_id}", response_model=DispatchNoteDetail)
def get_dispatch_note(
    note_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    note = db.query(DispatchNote).options(
        joinedload(DispatchNote.dealer),
        selectinload(DispatchNote.scooters).joinedload(DispatchNoteScooter.scooter_unit).joinedload(ScooterUnit.model),
        selectinload(DispatchNote.parts),
    ).filter(DispatchNote.id == note_id).first()
    if not note:
        raise HTTPException(404, "Dispatch note not found.")
    return _note_to_detail(note)


@router.post("/", response_model=DispatchNoteDetail)
def create_dispatch_note(
    data:         DispatchNoteCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above),
):
    if not data.scooters and not data.parts:
        raise HTTPException(400, "A dispatch must include at least one scooter or one part.")

    dealer = db.query(Dealer).filter(Dealer.id == data.dealer_id, Dealer.is_active == True).first()
    if not dealer:
        raise HTTPException(404, "Dealer not found or inactive.")

    dispatch_date = date.today()
    if data.dispatch_date:
        try:
            dispatch_date = date.fromisoformat(data.dispatch_date)
        except ValueError:
            raise HTTPException(400, "Invalid dispatch_date. Use YYYY-MM-DD.")

    # Validate and resolve all scooters first
    resolved_units = []
    for item in data.scooters:
        unit = db.query(ScooterUnit).filter(ScooterUnit.pdi_number == item.pdi_number).first()
        if not unit:
            raise HTTPException(400, f"No scooter found with PDI number '{item.pdi_number}'.")
        if unit.status != VehicleStatus.pdi_done:
            raise HTTPException(
                400,
                f"Scooter '{item.pdi_number}' is not PDI Done (status: {unit.status.value})."
            )
        if unit.current_dealer_id:
            raise HTTPException(400, f"Scooter '{item.pdi_number}' is already dispatched to a dealer.")
        resolved_units.append(unit)

    # Validate inventory for all parts BEFORE committing anything
    resolved_parts = []   # (part, inv_item, loc_stock_or_None)
    for part in data.parts:
        if part.quantity <= 0:
            raise HTTPException(400, f"Quantity for '{part.part_name}' must be greater than 0.")
        inv_item  = None
        loc_stock = None
        if part.inventory_item_id:
            inv_item = db.query(InventoryItem).filter(
                InventoryItem.id == part.inventory_item_id
            ).first()
            if not inv_item:
                raise HTTPException(400, f"Inventory item not found for '{part.part_name}'.")

            if part.location_id:
                loc_stock = db.query(InventoryLocationStock).filter(
                    InventoryLocationStock.item_id     == part.inventory_item_id,
                    InventoryLocationStock.location_id == part.location_id,
                ).first()
                available = loc_stock.quantity if loc_stock else 0
                if available < part.quantity:
                    raise HTTPException(
                        400,
                        f"Insufficient stock for '{part.part_name}' at selected location: "
                        f"requested {part.quantity}, available {available}."
                    )
            else:
                if inv_item.remaining_quantity < part.quantity:
                    raise HTTPException(
                        400,
                        f"Insufficient stock for '{part.part_name}': "
                        f"requested {part.quantity}, available {inv_item.remaining_quantity}."
                    )
        resolved_parts.append((part, inv_item, loc_stock))

    # Create dispatch note
    note = DispatchNote(
        dealer_id=dealer.id,
        dispatch_date=dispatch_date,
        notes=data.notes,
        dispatched_by=current_user.id,
    )
    db.add(note)
    db.flush()

    # Dispatch scooters — clear warehouse location, mark delivered
    for unit in resolved_units:
        unit.current_dealer_id  = dealer.id
        unit.current_location_id = None
        unit.status             = VehicleStatus.delivered
        unit.delivered_date     = dispatch_date
        db.add(DispatchNoteScooter(
            dispatch_note_id=note.id,
            scooter_unit_id=unit.id,
        ))

    # Add parts — deduct inventory where linked
    for part, inv_item, loc_stock in resolved_parts:
        if inv_item:
            inv_item.remaining_quantity -= part.quantity
            inv_item.consumed_quantity  += part.quantity
            if loc_stock:
                loc_stock.quantity -= part.quantity
        db.add(DispatchNotePart(
            dispatch_note_id=note.id,
            inventory_item_id=part.inventory_item_id,
            location_id=part.location_id,
            part_name=part.part_name,
            quantity=part.quantity,
            notes=part.notes,
        ))

    db.commit()
    db.refresh(note)
    return _note_to_detail(note)


@router.delete("/{note_id}")
def delete_dispatch_note(
    note_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above),
):
    note = db.query(DispatchNote).filter(DispatchNote.id == note_id).first()
    if not note:
        raise HTTPException(404, "Dispatch note not found.")

    # Reverse scooter status back to pdi_done
    for dns in note.scooters:
        unit = dns.scooter_unit
        if unit:
            unit.current_dealer_id   = None
            unit.current_location_id = None
            unit.status              = VehicleStatus.pdi_done
            unit.delivered_date      = None

    # Restore inventory stock
    for part in note.parts:
        if part.inventory_item_id and part.inventory_item:
            inv = part.inventory_item
            inv.remaining_quantity = (inv.remaining_quantity or 0) + part.quantity
            inv.consumed_quantity  = max(0, (inv.consumed_quantity or 0) - part.quantity)
            if part.location_id:
                loc_stock = db.query(InventoryLocationStock).filter(
                    InventoryLocationStock.item_id     == part.inventory_item_id,
                    InventoryLocationStock.location_id == part.location_id,
                ).first()
                if loc_stock:
                    loc_stock.quantity += part.quantity

    db.delete(note)
    db.commit()
    return {"message": "Dispatch note deleted and changes reversed."}
