from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.database import get_db
from app.core.dependencies import require_any_role
from app.models import (
    DispatchNote, DispatchNotePart, Dealer, User,
    InventoryItem, Location,
)

router = APIRouter(prefix="/spare-parts", tags=["Spare Parts"])


@router.get("/summary")
def get_summary(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    total_qty = db.query(func.sum(DispatchNotePart.quantity)).scalar() or 0
    unique_parts = (
        db.query(func.count(func.distinct(DispatchNotePart.part_name))).scalar() or 0
    )
    unique_dealers = (
        db.query(func.count(func.distinct(DispatchNote.dealer_id)))
        .join(DispatchNotePart, DispatchNotePart.dispatch_note_id == DispatchNote.id)
        .scalar() or 0
    )
    return {
        "total_qty":       int(total_qty),
        "unique_parts":    int(unique_parts),
        "unique_dealers":  int(unique_dealers),
    }


@router.get("/dispatches")
def list_dispatches(
    dealer_id:  Optional[str] = None,
    from_date:  Optional[str] = None,
    to_date:    Optional[str] = None,
    search:     Optional[str] = None,
    db:         Session = Depends(get_db),
    current_user: User  = Depends(require_any_role),
):
    q = (
        db.query(DispatchNotePart, DispatchNote, Dealer)
        .join(DispatchNote, DispatchNotePart.dispatch_note_id == DispatchNote.id)
        .join(Dealer, DispatchNote.dealer_id == Dealer.id)
    )
    if dealer_id:
        q = q.filter(DispatchNote.dealer_id == dealer_id)
    if from_date:
        q = q.filter(DispatchNote.dispatch_date >= from_date)
    if to_date:
        q = q.filter(DispatchNote.dispatch_date <= to_date)
    if search:
        q = q.filter(DispatchNotePart.part_name.ilike(f"%{search}%"))

    rows = q.order_by(DispatchNote.dispatch_date.desc()).all()

    result = []
    for part, note, dealer in rows:
        loc_name = None
        if part.location_id:
            loc = db.query(Location).filter(Location.id == part.location_id).first()
            loc_name = loc.name if loc else None
        result.append({
            "id":            part.id,
            "dispatch_date": str(note.dispatch_date),
            "dealer_name":   dealer.dealer_name,
            "dealer_code":   dealer.dealer_code,
            "part_name":     part.part_name,
            "quantity":      part.quantity,
            "location_name": loc_name,
            "notes":         part.notes or "",
        })
    return result


@router.get("/by-dealer")
def by_dealer(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    rows = (
        db.query(
            Dealer.id,
            Dealer.dealer_name,
            Dealer.dealer_code,
            func.count(func.distinct(DispatchNotePart.part_name)).label("unique_parts"),
            func.sum(DispatchNotePart.quantity).label("total_qty"),
            func.max(DispatchNote.dispatch_date).label("last_dispatch"),
        )
        .join(DispatchNote, DispatchNote.dealer_id == Dealer.id)
        .join(DispatchNotePart, DispatchNotePart.dispatch_note_id == DispatchNote.id)
        .group_by(Dealer.id, Dealer.dealer_name, Dealer.dealer_code)
        .order_by(func.sum(DispatchNotePart.quantity).desc())
        .all()
    )
    return [
        {
            "dealer_id":    r.id,
            "dealer_name":  r.dealer_name,
            "dealer_code":  r.dealer_code,
            "unique_parts": int(r.unique_parts),
            "total_qty":    int(r.total_qty),
            "last_dispatch": str(r.last_dispatch) if r.last_dispatch else "—",
        }
        for r in rows
    ]
