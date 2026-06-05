from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.database import get_db
from app.core.dependencies import require_any_role
from app.models import (
    InventoryItem, StockMovement,
    ScooterUnit, VehicleStatus,
    AssemblyJob, AssemblyStatus, ScooterModel, BOMItem,
    DispatchNote,
    PDIRecord, PDIResult, User,
    DamageRecord, Location,
)
from fastapi import HTTPException

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

    # Max buildable per model
    models = db.query(ScooterModel).filter(ScooterModel.is_active == True).all()
    buildable_rows = []
    for model in models:
        bom_all = model.bom_items

        if not bom_all:
            buildable_rows.append({
                "model_name":      model.model_name,
                "max_buildable":   "—",
                "bottleneck_part": "No BOM defined",
                "stock":           "—",
                "needed_per_unit": "—",
                "severity":        "none",
            })
            continue

        # Resolve inventory item for each BOM entry using same logic as manufacturing:
        # direct ID → SKU match → exact name → partial name
        def _resolve(b: BOMItem):
            if b.inventory_item_id:
                i = db.query(InventoryItem).filter(InventoryItem.id == b.inventory_item_id).first()
                if i:
                    return i
            if b.sku:
                i = db.query(InventoryItem).filter(
                    InventoryItem.sku == b.sku, InventoryItem.is_active == True
                ).first()
                if i:
                    return i
            if b.part_name:
                i = db.query(InventoryItem).filter(
                    InventoryItem.item_name == b.part_name, InventoryItem.is_active == True
                ).first()
                if i:
                    return i
                i = db.query(InventoryItem).filter(
                    InventoryItem.item_name.ilike(f"%{b.part_name}%"), InventoryItem.is_active == True
                ).first()
                if i:
                    return i
            return None

        ratios = []
        for b in bom_all:
            inv_item  = _resolve(b)
            qty_needed = b.quantity_required or 1
            qty_have   = (inv_item.remaining_quantity or 0) if inv_item else 0
            display    = (inv_item.item_name if inv_item else None) or b.part_name or "Unknown"
            ratios.append((qty_have // qty_needed, b, qty_have, qty_needed, display))

        if not ratios:
            buildable_rows.append({
                "model_name":      model.model_name,
                "max_buildable":   "—",
                "bottleneck_part": "Parts not linked to inventory",
                "stock":           "—",
                "needed_per_unit": "—",
                "severity":        "none",
            })
            continue

        ratios.sort(key=lambda x: x[0])
        max_build, bottleneck_bom, have, need, part_name = ratios[0]

        # Severity: red <5, orange <20, green otherwise
        severity = "critical" if max_build < 5 else ("warning" if max_build < 20 else "ok")

        buildable_rows.append({
            "model_name":      model.model_name,
            "max_buildable":   int(max_build),
            "bottleneck_part": part_name,
            "stock":           int(have),
            "needed_per_unit": int(need),
            "severity":        severity,
        })

    buildable_rows.sort(key=lambda x: (x["max_buildable"] == "—", x["max_buildable"] if x["max_buildable"] != "—" else 999))

    # Low stock items
    low_stock = [
        {
            "item_name":  i.item_name,
            "sku":        i.sku or "—",
            "remaining":  i.remaining_quantity  or 0,
            "threshold":  i.low_stock_threshold or 0,
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
        "buildable": buildable_rows,
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
    total_assembled = sum(j.quantity or 0 for j in jobs if j.status == AssemblyStatus.completed)
    total_damaged   = 0

    # By model
    by_model = {}
    for j in jobs:
        name = j.model.model_name if j.model else "Unknown"
        if name not in by_model:
            by_model[name] = {"jobs": 0, "assembled": 0, "cancelled": 0}
        by_model[name]["jobs"] += 1
        if j.status == AssemblyStatus.completed:
            by_model[name]["assembled"] += j.quantity or 0
        if j.status == AssemblyStatus.cancelled:
            by_model[name]["cancelled"] += 1

    return {
        "summary": {
            "total_jobs":      total_jobs,
            "completed":       completed,
            "cancelled":       cancelled,
            "total_assembled": total_assembled,
            "total_damaged":   total_damaged,
        },
        "by_model": [
            {"model": k, "damaged": 0, **v} for k, v in sorted(by_model.items())
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

    pdi_failed   = sum(1 for p in pdi_records if p.result == PDIResult.failed)

    # Completed/passed are derived from unit status so historical units
    # (passed PDI before PDIRecords were tracked) are still counted.
    # A delivered unit has, by definition, already passed PDI.
    pdi_passed = db.query(func.count(ScooterUnit.id)).filter(
        ScooterUnit.status.in_([VehicleStatus.pdi_done, VehicleStatus.delivered])
    ).scalar() or 0
    total_pdi = pdi_passed + pdi_failed

    # "Pending PDI" = anything awaiting inspection (matches the PDI screen).
    pdi_pending  = db.query(func.count(ScooterUnit.id)).filter(
        ScooterUnit.status.in_([
            VehicleStatus.manufacturing_done,
            VehicleStatus.pdi_pending,
            VehicleStatus.pdi_in_progress,
        ])
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


# ── FINISHED GOODS ────────────────────────────────────────────

# Finished = built scooters still in our inventory (everything except delivered).
_FINISHED_STATUSES = [
    VehicleStatus.manufacturing_done,
    VehicleStatus.pdi_pending,
    VehicleStatus.pdi_in_progress,
    VehicleStatus.pdi_done,
]


@router.get("/finished-goods")
def finished_goods_report(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    """Count of finished scooters in inventory, grouped by model."""
    rows = (
        db.query(
            ScooterModel.id,
            ScooterModel.model_name,
            func.count(ScooterUnit.id),
        )
        .join(ScooterUnit, ScooterUnit.model_id == ScooterModel.id)
        .filter(ScooterUnit.status.in_(_FINISHED_STATUSES))
        .group_by(ScooterModel.id, ScooterModel.model_name)
        .order_by(ScooterModel.model_name)
        .all()
    )
    models = [
        {"model_id": mid, "model_name": name, "count": int(cnt)}
        for mid, name, cnt in rows
    ]
    return {
        "total":  sum(m["count"] for m in models),
        "models": models,
    }


@router.get("/finished-goods/{model_id}")
def finished_goods_detail(
    model_id:     str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
):
    """Colour-wise breakdown + unit details for one model's finished stock."""
    model = db.query(ScooterModel).filter(ScooterModel.id == model_id).first()
    if not model:
        raise HTTPException(404, "Model not found.")

    units = (
        db.query(ScooterUnit)
        .filter(
            ScooterUnit.model_id == model_id,
            ScooterUnit.status.in_(_FINISHED_STATUSES),
        )
        .order_by(ScooterUnit.color, ScooterUnit.serial_number)
        .all()
    )

    # Batch-fetch location names
    loc_ids = {u.current_location_id for u in units if u.current_location_id}
    loc_names = {}
    if loc_ids:
        for loc in db.query(Location).filter(Location.id.in_(loc_ids)).all():
            loc_names[loc.id] = loc.name

    by_color: dict = {}
    for u in units:
        color = u.color or "—"
        by_color.setdefault(color, []).append({
            "serial_number": u.serial_number or "—",
            "color":         color,
            "pdi_number":    u.pdi_number or "—",
            "pdi_status":    u.status.value if u.status else "—",
            "location":      loc_names.get(u.current_location_id, "—"),
        })

    colors = [
        {"color": c, "count": len(us), "units": us}
        for c, us in sorted(by_color.items())
    ]
    return {
        "model_id":   model_id,
        "model_name": model.model_name,
        "total":      len(units),
        "colors":     colors,
    }
