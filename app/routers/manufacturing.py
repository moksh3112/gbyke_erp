from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.dependencies import (
    require_manager_or_above, require_any_role, require_superadmin
)
from app.models import (
    BOMItem, InventoryItem, ScooterModel,
    AssemblyJob, ScooterUnit, StockMovement, Location, User,
    InventoryLocationStock
)
from app.models import AssemblyStatus
from app.schemas.manufacturing import (
    BOMItemCreate, BOMItemUpdate,
    AssemblyJobCreate,
    StockCheckResponse,
    AddBOMStockRequest,
)
from pydantic import BaseModel
import re
import uuid

router = APIRouter(prefix="/manufacturing", tags=["Manufacturing"])


def gen_uuid():
    return str(uuid.uuid4())


def _clean(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '', str(text)).upper()[:8]


def _generate_sku(model_code: str, part_name: str, colour: str = "") -> str:
    """Backend mirror of the desktop generate_sku — used only as a fallback
    when a BOM row has no SKU of its own."""
    sku = f"{model_code}-{_clean(part_name)}"
    if colour and colour.strip():
        sku += f"-{_clean(colour)}"
    return sku


def _effective_colour(bom: "BOMItem", scooter_colour: str):
    """The colour the inventory row for this BOM part should carry for a given
    scooter colour. Colour-specific parts take the scooter's colour; generic
    parts stay None; legacy rows keep their pinned colour."""
    if bom.is_colour_specific:
        return scooter_colour or None
    return bom.colour or None


def _effective_sku(bom: "BOMItem", scooter_colour: str):
    """SKU of the inventory row for this BOM part. Colour-specific parts append
    the scooter colour to their base SKU; everything else uses the stored SKU."""
    if bom.is_colour_specific and scooter_colour and bom.sku:
        return f"{bom.sku}-{_clean(scooter_colour)}"
    return bom.sku


# ── HELPERS ───────────────────────────────────────────────────

def _bom_to_response(b: BOMItem, db: Session) -> dict:
    # Resolve display name: prefer part_name, fall back to linked inventory item
    part_name = b.part_name
    item_name = None
    if b.inventory_item_id:
        inv = db.query(InventoryItem).filter(
            InventoryItem.id == b.inventory_item_id
        ).first()
        if inv:
            item_name = inv.item_name
            if not part_name:
                part_name = inv.item_name

    return {
        "id":                b.id,
        "model_id":          b.model_id,
        "model_name":        b.model.model_name if b.model else None,
        "part_name":         part_name,
        "sku":               b.sku,
        "inventory_item_id": b.inventory_item_id,
        "item_name":         item_name,
        "quantity_required": b.quantity_required,
        "colour":            b.colour,
        "is_colour_specific": b.is_colour_specific,
        "battery_type":      b.battery_type,
        "power_spec":        b.power_spec,
        "notes":             b.notes,
    }


def _job_to_response(job: AssemblyJob, db: Session) -> dict:
    model = db.query(ScooterModel).filter(
        ScooterModel.id == job.model_id
    ).first()
    location = db.query(Location).filter(
        Location.id == job.location_id
    ).first() if job.location_id else None
    performer = db.query(User).filter(
        User.id == job.performed_by
    ).first() if job.performed_by else None

    units_created = db.query(ScooterUnit).filter(
        ScooterUnit.assembly_job_id == job.id
    ).count()

    return {
        "id":                job.id,
        "model_id":          job.model_id,
        "model_name":        model.model_name if model else None,
        "color":             job.color,
        "battery_type":      job.battery_type,
        "power_spec":        job.power_spec,
        "quantity":          job.quantity,
        "location_id":       job.location_id,
        "location_name":     location.name if location else None,
        "status":            job.status.value if job.status else "pending",
        "started_at":        job.started_at.strftime("%d-%b-%Y %H:%M") if job.started_at else None,
        "completed_at":      job.completed_at.strftime("%d-%b-%Y %H:%M") if job.completed_at else None,
        "performed_by":      job.performed_by,
        "performed_by_name": performer.full_name if performer else None,
        "notes":             job.notes,
        "created_at":        job.created_at.strftime("%d-%b-%Y %H:%M") if job.created_at else None,
        "units_created":     units_created,
    }


def _get_applicable_bom_items(
    db: Session, model_id: str, colour: str
) -> List[BOMItem]:
    """
    Returns BOM items applicable for this configuration.
    - Generic parts (no colour, not colour-specific) → always included
    - Colour-specific parts → always included (the caller materialises the colour)
    - Legacy rows with a pinned colour → only if they match the selected colour
    """
    all_items = db.query(BOMItem).filter(
        BOMItem.model_id == model_id
    ).all()

    applicable = []
    for item in all_items:
        # Legacy pinned-colour rows still filter by exact colour match
        if not item.is_colour_specific and item.colour \
                and item.colour.lower() != (colour or "").lower():
            continue
        applicable.append(item)
    return applicable


def _model_has_colour_specific(db: Session, model_id: str) -> bool:
    return db.query(BOMItem).filter(
        BOMItem.model_id           == model_id,
        BOMItem.is_colour_specific == True
    ).first() is not None


def _find_inventory_item(
    db: Session, bom: BOMItem, sku: str = None, colour: str = None
) -> Optional[InventoryItem]:
    """
    Find the matching inventory item for a BOM part.
    `sku`/`colour` are the *effective* values (already colour-resolved by the
    caller for colour-specific parts). Priority: direct link → SKU → name(+colour).
    """
    eff_sku = sku if sku is not None else bom.sku

    # Direct legacy link — never for colour-specific parts (they span colours)
    if bom.inventory_item_id and not bom.is_colour_specific:
        item = db.query(InventoryItem).filter(
            InventoryItem.id       == bom.inventory_item_id,
            InventoryItem.is_active == True
        ).first()
        if item: return item

    if eff_sku:
        item = db.query(InventoryItem).filter(
            InventoryItem.sku       == eff_sku,
            InventoryItem.is_active == True
        ).first()
        if item: return item

    if bom.part_name:
        q = db.query(InventoryItem).filter(
            InventoryItem.item_name == bom.part_name,
            InventoryItem.is_active == True
        )
        if colour:
            q = q.filter(InventoryItem.colour.ilike(colour))
        item = q.first()
        if item: return item

    return None


# ── BOM ENDPOINTS ─────────────────────────────────────────────

@router.get("/bom/{model_id}")
def get_bom(
    model_id:     str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    items = db.query(BOMItem).filter(
        BOMItem.model_id == model_id
    ).all()
    return [_bom_to_response(i, db) for i in items]


@router.get("/bom/{model_id}/parts")
def get_bom_part_names(
    model_id:     str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    items = db.query(BOMItem).filter(
        BOMItem.model_id == model_id
    ).all()
    result = []
    for item in items:
        name = item.part_name or (
            item.inventory_item.item_name
            if item.inventory_item_id and item.inventory_item else None
        )
        if name:
            result.append({
                "part_name":    name,
                "sku":          item.sku,
                "colour":       item.colour,
                "battery_type": item.battery_type,
                "power_spec":   item.power_spec,
            })
    return result


@router.post("/bom")
def create_bom_item(
    data:         BOMItemCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    model = db.query(ScooterModel).filter(
        ScooterModel.id == data.model_id
    ).first()
    if not model:
        raise HTTPException(404, "Scooter model not found.")

    if not data.part_name and not data.inventory_item_id:
        raise HTTPException(400, "Either part_name or inventory_item_id is required.")

    if data.part_name:
        existing = db.query(BOMItem).filter(
            BOMItem.model_id == data.model_id,
            BOMItem.part_name == data.part_name.strip()
        ).first()
        if existing:
            raise HTTPException(400, f"'{data.part_name.strip()}' already exists in this model's BOM.")

    # Colour-specific parts span every colour: store no pinned colour and a
    # base SKU (the colour suffix is appended per scooter colour at stock time).
    bom_item = BOMItem(
        id                 = gen_uuid(),
        model_id           = data.model_id,
        part_name          = data.part_name.strip() if data.part_name else None,
        sku                = data.sku.strip().upper() if data.sku else None,
        inventory_item_id  = data.inventory_item_id or None,
        quantity_required  = data.quantity_required,
        colour             = None if data.is_colour_specific else (data.colour.strip() if data.colour else None),
        is_colour_specific = bool(data.is_colour_specific),
        battery_type       = data.battery_type.strip() if data.battery_type else None,
        power_spec         = data.power_spec.strip() if data.power_spec else None,
        notes              = data.notes,
    )
    db.add(bom_item)
    db.commit()
    db.refresh(bom_item)
    return _bom_to_response(bom_item, db)


@router.patch("/bom/{bom_id}")
def update_bom_item(
    bom_id:       str,
    data:         BOMItemUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    item = db.query(BOMItem).filter(BOMItem.id == bom_id).first()
    if not item:
        raise HTTPException(404, "BOM item not found.")

    if data.part_name          is not None: item.part_name          = data.part_name.strip()
    if data.sku                is not None: item.sku                = data.sku.strip().upper() or None
    if data.quantity_required  is not None: item.quantity_required  = data.quantity_required
    if data.colour             is not None: item.colour             = data.colour.strip() or None
    if data.is_colour_specific is not None: item.is_colour_specific = bool(data.is_colour_specific)
    if data.battery_type       is not None: item.battery_type       = data.battery_type.strip() or None
    if data.power_spec         is not None: item.power_spec         = data.power_spec.strip() or None
    if data.notes              is not None: item.notes              = data.notes

    # Colour-specific parts never keep a pinned colour
    if item.is_colour_specific:
        item.colour = None

    db.commit()
    db.refresh(item)
    return _bom_to_response(item, db)


@router.delete("/bom/{bom_id}")
def delete_bom_item(
    bom_id:       str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    item = db.query(BOMItem).filter(BOMItem.id == bom_id).first()
    if not item:
        raise HTTPException(404, "BOM item not found.")
    db.delete(item)
    db.commit()
    return {"message": "BOM item deleted."}


# ── STOCK CHECK ───────────────────────────────────────────────

@router.post("/check-stock")
def check_stock(
    data:         AssemblyJobCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    model = db.query(ScooterModel).filter(
        ScooterModel.id == data.model_id
    ).first()
    if not model:
        raise HTTPException(404, "Model not found.")

    if not data.color and _model_has_colour_specific(db, data.model_id):
        raise HTTPException(
            400, "Select a colour — this model has colour-specific parts."
        )

    bom_items = _get_applicable_bom_items(
        db, data.model_id, data.color
    )

    shortages = []
    for bom in bom_items:
        eff_colour = _effective_colour(bom, data.color)
        eff_sku    = _effective_sku(bom, data.color)
        inv = _find_inventory_item(db, bom, sku=eff_sku, colour=eff_colour)
        part_name = bom.part_name or (inv.item_name if inv else "Unknown Part")
        required = bom.quantity_required * data.quantity

        if not inv:
            shortages.append(
                f"'{part_name}' — completely missing from inventory (need {required})"
            )
            continue  

        if data.location_id:
            loc_stock = db.query(InventoryLocationStock).filter(
                InventoryLocationStock.item_id == inv.id,
                InventoryLocationStock.location_id == data.location_id
            ).first()
            
            available = loc_stock.quantity if loc_stock else 0
            if available < required:
                shortages.append(
                    f"'{part_name}' — need {required}, have {available} at this location"
                )
        else:
            available = inv.remaining_quantity
            if available < required:
                shortages.append(
                    f"'{part_name}' — need {required}, have {available} globally"
                )

    if shortages:
        raise HTTPException(
            400,
            "Insufficient stock for the following parts:\n" +
            "\n".join(shortages)
        )
    return StockCheckResponse(
        can_produce = len(shortages) == 0,
        shortages   = shortages,
    )


# ── ASSEMBLY JOBS ─────────────────────────────────────────────

@router.get("/jobs")
def get_jobs(
    db:           Session       = Depends(get_db),
    current_user: User          = Depends(require_any_role),
    status:       Optional[str] = None,
):
    query = db.query(AssemblyJob)
    if status:
        try:
            status_enum = AssemblyStatus(status)
            query = query.filter(AssemblyJob.status == status_enum)
        except ValueError:
            pass
    jobs = query.order_by(AssemblyJob.created_at.desc()).all()
    return [_job_to_response(j, db) for j in jobs]


@router.get("/jobs/{job_id}")
def get_job(
    job_id:       str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    job = db.query(AssemblyJob).filter(AssemblyJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Assembly job not found.")
    return _job_to_response(job, db)

@router.post("/jobs")
def create_job(
    data:         AssemblyJobCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    model = db.query(ScooterModel).filter(
        ScooterModel.id == data.model_id
    ).first()
    if not model:
        raise HTTPException(404, "Scooter Model not found.")

    if data.quantity <= 0:
        raise HTTPException(400, "Quantity must be greater than 0.")

    if not data.color and _model_has_colour_specific(db, data.model_id):
        raise HTTPException(
            400, "Select a colour — this model has colour-specific parts."
        )

    bom_items = _get_applicable_bom_items(
        db, data.model_id, data.color
    )

    if not bom_items:
        raise HTTPException(
            400,
            f"No BOM defined for {model.model_name}. Please configure the BOM first."
        )

    shortages = []
    for bom in bom_items:
        eff_colour = _effective_colour(bom, data.color)
        eff_sku    = _effective_sku(bom, data.color)
        inv = _find_inventory_item(db, bom, sku=eff_sku, colour=eff_colour)
        part_name = bom.part_name or (inv.item_name if inv else "Unknown Part")
        required = bom.quantity_required * data.quantity

        if not inv:
            shortages.append(f"'{part_name}' — completely missing from inventory (need {required})")
            continue

        if data.location_id:
            loc_stock = db.query(InventoryLocationStock).filter(
                InventoryLocationStock.item_id == inv.id,
                InventoryLocationStock.location_id == data.location_id
            ).first()
            
            available = loc_stock.quantity if loc_stock else 0
            if available < required:
                shortages.append(f"'{part_name}' — need {required}, have {available} at this location")
        else:
            available = inv.remaining_quantity
            if available < required:
                shortages.append(f"'{part_name}' — need {required}, have {available} globally")

    if shortages:
        raise HTTPException(
            status_code=400,
            detail="Insufficient stock for the following parts:\n" + "\n".join(shortages)
        )

    from datetime import datetime, timezone
    job = AssemblyJob(
        id           = gen_uuid(),
        model_id     = data.model_id,
        color        = data.color,
        quantity     = data.quantity,
        location_id  = data.location_id,
        status       = AssemblyStatus.in_progress,
        started_at   = datetime.now(timezone.utc),
        performed_by = current_user.id,
        notes        = data.notes,
    )
    db.add(job)
    db.flush()

    for bom in bom_items:
        eff_colour = _effective_colour(bom, data.color)
        eff_sku    = _effective_sku(bom, data.color)
        inv = _find_inventory_item(db, bom, sku=eff_sku, colour=eff_colour)
        if not inv: continue

        required = bom.quantity_required * data.quantity
        inv.consumed_quantity  += required
        inv.remaining_quantity -= required

        if data.location_id:
            loc_stock = db.query(InventoryLocationStock).filter(
                InventoryLocationStock.item_id     == inv.id,
                InventoryLocationStock.location_id == data.location_id
            ).first()
            if loc_stock: 
                loc_stock.quantity -= required

        movement = StockMovement(
            id             = gen_uuid(),
            item_id        = inv.id,
            movement_type  = "consumed",
            quantity       = required,
            location_id    = data.location_id,
            reference_id   = job.id,
            reference_type = "assembly_job",
            notes          = f"Assembly Job — {model.model_name} ({data.color}) × {data.quantity} units",
            performed_by   = current_user.id,
        )
        db.add(movement)

    db.commit()
    db.refresh(job)
    return _job_to_response(job, db)

@router.post("/jobs/{job_id}/complete")
def complete_job(
    job_id:       str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    from datetime import datetime, timezone
    from app.models import VehicleStatus

    job = db.query(AssemblyJob).filter(AssemblyJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Assembly job not found.")
    if job.status == AssemblyStatus.completed:
        raise HTTPException(400, "Job is already completed.")
    if job.status == AssemblyStatus.cancelled:
        raise HTTPException(400, "Cannot complete a cancelled job.")

    job.status       = AssemblyStatus.completed
    job.completed_at = datetime.now(timezone.utc)

    for i in range(job.quantity):
        unit = ScooterUnit(
            id                  = gen_uuid(),
            serial_number       = f"PENDING-{job_id[:8]}-{i+1:04d}",
            chassis_number      = None,
            model_id            = job.model_id,
            color               = job.color,
            battery_type        = job.battery_type,
            power_spec          = job.power_spec,
            assembly_job_id     = job.id,
            current_location_id = job.location_id,
            status              = VehicleStatus.manufacturing_done,
        )
        db.add(unit)

    db.commit()
    db.refresh(job)
    return _job_to_response(job, db)

@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id:       str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    job = db.query(AssemblyJob).filter(AssemblyJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Assembly job not found.")
    if job.status == AssemblyStatus.completed:
        raise HTTPException(400, "Cannot cancel a completed job.")
    if job.status == AssemblyStatus.cancelled:
        raise HTTPException(400, "Job is already cancelled.")
 
    bom_items = _get_applicable_bom_items(
        db, job.model_id, job.color
    )

    for bom in bom_items:
        eff_colour = _effective_colour(bom, job.color)
        eff_sku    = _effective_sku(bom, job.color)
        inv = _find_inventory_item(db, bom, sku=eff_sku, colour=eff_colour)
        if not inv:
            continue
        returned = bom.quantity_required * job.quantity

        # FIX 8: guard against going negative
        inv.consumed_quantity  = max(0, inv.consumed_quantity - returned)
        inv.remaining_quantity += returned

        if job.location_id:
            loc_stock = db.query(InventoryLocationStock).filter(
                InventoryLocationStock.item_id     == inv.id,
                InventoryLocationStock.location_id == job.location_id
            ).first()
            if loc_stock:
                loc_stock.quantity += returned

        movement = StockMovement(
            id             = gen_uuid(),
            item_id        = inv.id,
            movement_type  = "adjusted",
            quantity       = returned,
            location_id    = job.location_id,
            reference_id   = job.id,
            reference_type = "assembly_job_cancel",
            notes          = "Job Cancelled — parts returned to stock",
            performed_by   = current_user.id,
        )
        db.add(movement)

    job.status = AssemblyStatus.cancelled
    db.commit()
    db.refresh(job)
    return _job_to_response(job, db)
 
# ── ADD BOM STOCK (explode a scooter's BOM into part inventory) ──

@router.post("/add-bom-stock")
def add_bom_stock(
    data:         AddBOMStockRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above),
):
    """
    Inverse of create_job: instead of consuming parts to build scooters,
    add stock for every part in a model's BOM.

    Quantities are quantity_required * data.quantity. Generic parts are added
    with no colour; colour-specific parts are materialised with the selected
    colour and a colour-suffixed SKU (one inventory row per colour). Missing
    inventory items are auto-created from the BOM row.
    """
    from datetime import date as _date

    model = db.query(ScooterModel).filter(
        ScooterModel.id == data.model_id
    ).first()
    if not model:
        raise HTTPException(404, "Scooter model not found.")
    if data.quantity <= 0:
        raise HTTPException(400, "Quantity must be greater than 0.")

    if not data.colour and _model_has_colour_specific(db, data.model_id):
        raise HTTPException(
            400, "Select a colour — this model has colour-specific parts."
        )

    import_date = None
    if data.import_date:
        try:
            import_date = _date.fromisoformat(data.import_date)
        except ValueError:
            raise HTTPException(400, "Invalid import_date. Use YYYY-MM-DD.")

    bom_items = _get_applicable_bom_items(db, data.model_id, data.colour)
    if not bom_items:
        raise HTTPException(
            400,
            f"No BOM defined for {model.model_name}. Please configure the BOM first."
        )

    note = (
        f"BOM stock — {model.model_name}"
        f" ({data.colour or 'no colour'}) × {data.quantity}"
    )
    parts_added = []

    for bom in bom_items:
        eff_colour = _effective_colour(bom, data.colour)
        eff_sku    = _effective_sku(bom, data.colour)
        required   = bom.quantity_required * data.quantity
        inv = _find_inventory_item(db, bom, sku=eff_sku, colour=eff_colour)

        if inv:
            inv.remaining_quantity += required
            inv.total_quantity     += required
            created = False
        else:
            # Auto-create the inventory item from the BOM row
            part_name = bom.part_name or (
                bom.inventory_item.item_name
                if bom.inventory_item_id and bom.inventory_item else None
            )
            if not part_name:
                # Nothing identifiable to create — skip safely
                continue
            sku = eff_sku or _generate_sku(
                model.model_code, part_name, eff_colour or ""
            )
            # SKU is unique — a deactivated item with this SKU would clash on
            # insert, so reactivate it instead of creating a duplicate.
            deactivated = db.query(InventoryItem).filter(
                InventoryItem.sku       == sku,
                InventoryItem.is_active == False
            ).first()
            if deactivated:
                deactivated.is_active          = True
                deactivated.item_name          = part_name
                deactivated.model_name         = model.model_name
                deactivated.colour             = eff_colour
                deactivated.total_quantity     = required
                deactivated.remaining_quantity = required
                deactivated.consumed_quantity  = 0
                deactivated.defective_quantity = 0
                deactivated.damaged_quantity   = 0
                deactivated.import_date        = import_date
                deactivated.location_id        = data.location_id
                inv = deactivated
            else:
                inv = InventoryItem(
                    id                  = gen_uuid(),
                    item_name           = part_name,
                    sku                 = sku,
                    unit                = "pcs",
                    total_quantity      = required,
                    remaining_quantity  = required,
                    low_stock_threshold = 10,
                    is_spare_part       = False,
                    model_name          = model.model_name,
                    colour              = eff_colour,
                    import_date         = import_date,
                    location_id         = data.location_id,
                )
                db.add(inv)
            db.flush()
            created = True

        # Update / create location stock
        if data.location_id:
            loc_stock = db.query(InventoryLocationStock).filter(
                InventoryLocationStock.item_id     == inv.id,
                InventoryLocationStock.location_id == data.location_id
            ).first()
            if loc_stock:
                loc_stock.quantity += required
            else:
                loc_stock = InventoryLocationStock(
                    item_id     = inv.id,
                    location_id = data.location_id,
                    quantity    = required,
                )
                db.add(loc_stock)

        movement = StockMovement(
            id             = gen_uuid(),
            item_id        = inv.id,
            movement_type  = "received",
            quantity       = required,
            location_id    = data.location_id,
            reference_type = "bom_stock",
            notes          = note,
            performed_by   = current_user.id,
        )
        db.add(movement)

        parts_added.append({
            "part_name":      inv.item_name,
            "sku":            inv.sku,
            "colour":         inv.colour,
            "quantity_added": required,
            "created":        created,
        })

    db.commit()
    return {
        "message":     f"Added stock for {len(parts_added)} part(s) from {model.model_name}'s BOM.",
        "parts_added": parts_added,
        "total_parts": len(parts_added),
    }


# ── SUMMARY ───────────────────────────────────────────────────

@router.get("/summary")
def get_summary(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    from app.models import VehicleStatus

    total_jobs       = db.query(AssemblyJob).count()
    in_progress_jobs = db.query(AssemblyJob).filter(
        AssemblyJob.status == AssemblyStatus.in_progress
    ).count()
    completed_jobs   = db.query(AssemblyJob).filter(
        AssemblyJob.status == AssemblyStatus.completed
    ).count()
    units_mfg_done   = db.query(ScooterUnit).filter(
        ScooterUnit.status == VehicleStatus.manufacturing_done
    ).count()

    return {
        "total_jobs":         total_jobs,
        "in_progress_jobs":   in_progress_jobs,
        "completed_jobs":     completed_jobs,
        "units_awaiting_pdi": units_mfg_done,
    }

@router.delete("/jobs/{job_id}")
def delete_job(
    job_id:       str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_superadmin)
):
    job = db.query(AssemblyJob).filter(AssemblyJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Assembly job not found.")
 
    if job.status != AssemblyStatus.cancelled:
        bom_items = _get_applicable_bom_items(
            db, job.model_id, job.color
        )
        for bom in bom_items:
            eff_colour = _effective_colour(bom, job.color)
            eff_sku    = _effective_sku(bom, job.color)
            inv = _find_inventory_item(db, bom, sku=eff_sku, colour=eff_colour)
            if not inv:
                continue
            returned = bom.quantity_required * job.quantity

            # FIX 8: guard against going negative
            inv.consumed_quantity  = max(0, inv.consumed_quantity - returned)
            inv.remaining_quantity += returned
 
            if job.location_id:
                loc_stock = db.query(InventoryLocationStock).filter(
                    InventoryLocationStock.item_id     == inv.id,
                    InventoryLocationStock.location_id == job.location_id
                ).first()
                if loc_stock:
                    loc_stock.quantity += returned
 
    db.query(StockMovement).filter(StockMovement.reference_id == job.id).delete()
    unit_ids = [u.id for u in db.query(ScooterUnit.id).filter(ScooterUnit.assembly_job_id == job.id)]
    if unit_ids:
        from app.models import DamageRecord
        db.query(DamageRecord).filter(DamageRecord.scooter_unit_id.in_(unit_ids)).delete(synchronize_session=False)
    db.query(ScooterUnit).filter(ScooterUnit.assembly_job_id == job.id).delete()
    db.delete(job)
    db.commit()
    return {"message": "Job deleted and parts successfully returned to inventory."}


# ── LOG EXISTING (already-manufactured) SCOOTERS ──────────────

class LogExistingScootersRequest(BaseModel):
    model_id:          str
    color:             Optional[str] = None
    battery_type:      Optional[str] = None
    power_spec:        Optional[str] = None
    location_id:       Optional[str] = None
    quantity:          int
    status:            str           = "manufacturing_done"  # or "pdi_done"
    manufactured_date: Optional[str] = None


@router.post("/log-existing")
def log_existing_scooters(
    data:         LogExistingScootersRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above),
):
    """Bulk-log already-manufactured scooters into inventory (no assembly job)."""
    from app.models import VehicleStatus
    from datetime import date as _date

    model = db.query(ScooterModel).filter(ScooterModel.id == data.model_id).first()
    if not model:
        raise HTTPException(404, "Scooter model not found.")
    if data.quantity < 1 or data.quantity > 10000:
        raise HTTPException(400, "Quantity must be between 1 and 10000.")
    try:
        status = VehicleStatus(data.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status '{data.status}'.")
    if status not in (VehicleStatus.manufacturing_done, VehicleStatus.pdi_done):
        raise HTTPException(400, "Status must be 'manufacturing_done' or 'pdi_done'.")

    mfg_date = None
    if data.manufactured_date:
        try:
            mfg_date = _date.fromisoformat(data.manufactured_date)
        except ValueError:
            raise HTTPException(400, "Invalid manufactured_date. Use YYYY-MM-DD.")

    batch = gen_uuid()[:8]
    for i in range(data.quantity):
        unit = ScooterUnit(
            id                  = gen_uuid(),
            serial_number       = f"LOG-{batch}-{i+1:04d}",
            model_id            = data.model_id,
            color               = (data.color or None),
            battery_type        = (data.battery_type or None),
            power_spec          = (data.power_spec or None),
            current_location_id = data.location_id,
            status              = status,
            manufactured_date   = mfg_date,
        )
        db.add(unit)

    db.commit()
    return {"message": f"Logged {data.quantity} scooter(s).", "count": data.quantity, "batch": batch}


@router.get("/logged-units")
def list_logged_units(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
    limit:        int     = 300,
):
    """Recently logged (manually entered) scooter units — those without an assembly job."""
    units = (
        db.query(ScooterUnit)
        .filter(ScooterUnit.assembly_job_id.is_(None))
        .order_by(ScooterUnit.created_at.desc())
        .limit(limit)
        .all()
    )
    loc_ids = {u.current_location_id for u in units if u.current_location_id}
    loc_names = {}
    if loc_ids:
        for loc in db.query(Location).filter(Location.id.in_(loc_ids)).all():
            loc_names[loc.id] = loc.name

    return [
        {
            "id":                u.id,
            "serial_number":     u.serial_number,
            "model_name":        u.model.model_name if u.model else "—",
            "color":             u.color or "—",
            "battery_type":      u.battery_type or "—",
            "power_spec":        u.power_spec or "—",
            "status":            u.status.value if u.status else "—",
            "location":          loc_names.get(u.current_location_id, "—"),
            "manufactured_date": str(u.manufactured_date) if u.manufactured_date else "—",
        }
        for u in units
    ]
 
