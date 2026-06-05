from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import Optional

from app.database import get_db
from app.core.dependencies import require_any_role
from app.models import (
    InventoryItem, InventoryCategory, StockMovement,
    ScooterUnit, VehicleStatus,
    AssemblyJob, AssemblyStatus, ScooterModel,
    DispatchNote, DispatchNoteScooter, DispatchNotePart, Dealer,
    PDIRecord, User,
    DamageRecord, DamageStage,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


# ── INVENTORY SUMMARY ─────────────────────────────────────────

@router.get("/inventory")
def inventory_report(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    items = db.query(InventoryItem).all()

    total_items      = len(items)
    total_remaining  = sum(i.remaining_quantity  or 0 for i in items)
    total_consumed   = sum(i.consumed_quantity   or 0 for i in items)
    total_defective  = sum((i.defective_quantity or 0) + (i.damaged_quantity or 0) for i in items)
    low_stock_count  = sum(
        1 for i in items
        if (i.remaining_quantity or 0) <= (i.low_stock_threshold or 0)
    )

    # By category
    by_category = {}
    for item in items:
        cat_name = item.category.name if item.category else "Uncategorised"
        if cat_name not in by_category:
            by_category[cat_name] = {"items": 0, "remaining": 0, "consumed": 0}
        by_category[cat_name]["items"]     += 1
        by_category[cat_name]["remaining"] += item.remaining_quantity  or 0
        by_category[cat_name]["consumed"]  += item.consumed_quantity   or 0

    # Low stock items
    low_stock = [
        {
            "item_name":      i.item_name,
            "sku":            i.sku or "—",
            "remaining":      i.remaining_quantity  or 0,
            "threshold":      i.low_stock_threshold or 0,
            "category":       i.category.name if i.category else "—",
        }
        for i in items
        if (i.remaining_quantity or 0) <= (i.low_stock_threshold or 0)
    ]

    return {
        "summary": {
            "total_items":     total_items,
            "total_remaining": total_remaining,
            "total_consumed":  total_consumed,
            "total_defective": total_defective,
            "low_stock_count": low_stock_count,
        },
        "by_category": [
            {"category": k, **v} for k, v in sorted(by_category.items())
        ],
        "low_stock_items": sorted(low_stock, key=lambda x: x["remaining"]),
    }


# ── PRODUCTION / MANUFACTURING ────────────────────────────────

@router.get("/manufacturing")
def manufacturing_report(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    db:        Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    q = db.query(AssemblyJob)
    if from_date:
        q = q.filter(AssemblyJob.created_at >= from_date)
    if to_date:
        q = q.filter(AssemblyJob.created_at <= to_date + " 23:59:59")
    jobs = q.all()

    total_jobs      = len(jobs)
    completed       = sum(1 for j in jobs if j.status == AssemblyStatus.completed)
    cancelled       = sum(1 for j in jobs if j.status == AssemblyStatus.cancelled)
    total_assembled = sum(j.quantity         or 0 for j in jobs if j.status == AssemblyStatus.completed)
    total_damaged   = sum(j.damaged_quantity or 0 for j in jobs)

    # By model
    by_model = {}
    for j in jobs:
        name = j.model.model_name if j.model else "Unknown"
        if name not in by_model:
            by_model[name] = {"jobs": 0, "assembled": 0, "damaged": 0, "cancelled": 0}
        by_model[name]["jobs"] += 1
        if j.status == AssemblyStatus.completed:
            by_model[name]["assembled"] += j.quantity or 0
        if j.status == AssemblyStatus.cancelled:
            by_model[name]["cancelled"] += 1
        by_model[name]["damaged"] += j.damaged_quantity or 0

    return {
        "summary": {
            "total_jobs":      total_jobs,
            "completed":       completed,
            "cancelled":       cancelled,
            "total_assembled": total_assembled,
            "total_damaged":   total_damaged,
        },
        "by_model": [
            {"model": k, **v} for k, v in sorted(by_model.items())
        ],
    }


# ── DISPATCH & DEALER PERFORMANCE ────────────────────────────

@router.get("/dispatch")
def dispatch_report(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    db:        Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    q = db.query(DispatchNote)
    if from_date:
        q = q.filter(DispatchNote.dispatch_date >= from_date)
    if to_date:
        q = q.filter(DispatchNote.dispatch_date <= to_date)
    notes = q.all()

    total_dispatches  = len(notes)
    total_scooters    = sum(len(n.scooters) for n in notes)
    total_parts_qty   = sum(sum(p.quantity for p in n.parts) for n in notes)

    # By dealer
    by_dealer = {}
    for note in notes:
        dname = note.dealer.dealer_name if note.dealer else "Unknown"
        dcode = note.dealer.dealer_code if note.dealer else "—"
        key   = (dname, dcode)
        if key not in by_dealer:
            by_dealer[key] = {"dispatches": 0, "scooters": 0, "parts_qty": 0, "last_dispatch": ""}
        by_dealer[key]["dispatches"]    += 1
        by_dealer[key]["scooters"]      += len(note.scooters)
        by_dealer[key]["parts_qty"]     += sum(p.quantity for p in note.parts)
        d = str(note.dispatch_date)
        if d > by_dealer[key]["last_dispatch"]:
            by_dealer[key]["last_dispatch"] = d

    return {
        "summary": {
            "total_dispatches": total_dispatches,
            "total_scooters":   total_scooters,
            "total_parts_qty":  total_parts_qty,
            "dealers_served":   len(by_dealer),
        },
        "by_dealer": [
            {
                "dealer_name":   k[0],
                "dealer_code":   k[1],
                **v,
            }
            for k, v in sorted(by_dealer.items(), key=lambda x: x[1]["scooters"], reverse=True)
        ],
    }


# ── PDI & DAMAGE SUMMARY ──────────────────────────────────────

@router.get("/pdi-damage")
def pdi_damage_report(
    from_date: Optional[str] = None,
    to_date:   Optional[str] = None,
    db:        Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    # PDI stats
    pdi_q = db.query(PDIRecord)
    if from_date:
        pdi_q = pdi_q.filter(PDIRecord.completed_at >= from_date)
    if to_date:
        pdi_q = pdi_q.filter(PDIRecord.completed_at <= to_date + " 23:59:59")
    pdi_records = pdi_q.all()

    total_pdi    = len(pdi_records)
    pdi_passed   = sum(1 for p in pdi_records if p.result == "pass")
    pdi_failed   = sum(1 for p in pdi_records if p.result == "fail")
    pdi_pending  = db.query(func.count(ScooterUnit.id)).filter(
        ScooterUnit.status == VehicleStatus.pdi_pending
    ).scalar() or 0

    # Scooter status breakdown
    status_counts = {}
    for status in VehicleStatus:
        count = db.query(func.count(ScooterUnit.id)).filter(
            ScooterUnit.status == status
        ).scalar() or 0
        if count > 0:
            status_counts[status.value] = count

    # Damage records by stage
    dmg_q = db.query(DamageRecord)
    if from_date:
        dmg_q = dmg_q.filter(DamageRecord.created_at >= from_date)
    if to_date:
        dmg_q = dmg_q.filter(DamageRecord.created_at <= to_date + " 23:59:59")
    damage_records = dmg_q.all()

    by_stage = {}
    for rec in damage_records:
        stage = rec.stage.value if rec.stage else "unknown"
        by_stage[stage] = by_stage.get(stage, 0) + 1

    # Inventory damage from stock movements
    inv_dmg = db.query(func.sum(StockMovement.quantity)).filter(
        StockMovement.movement_type.in_(["defective", "damaged"])
    ).scalar() or 0

    return {
        "pdi": {
            "total_completed": total_pdi,
            "passed":          pdi_passed,
            "failed":          pdi_failed,
            "pending":         int(pdi_pending),
            "pass_rate":       round(pdi_passed / total_pdi * 100, 1) if total_pdi > 0 else 0,
        },
        "scooter_status": [
            {"status": k.replace("_", " ").title(), "count": v}
            for k, v in status_counts.items()
        ],
        "damage_by_stage": [
            {"stage": k.replace("_", " ").title(), "count": v}
            for k, v in sorted(by_stage.items())
        ],
        "inventory_damage_qty": int(inv_dmg),
    }
