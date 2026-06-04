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
    BOMItemCreate, BOMItemUpdate, BOMItemResponse,
    AssemblyJobCreate, AssemblyJobUpdate, AssemblyJobResponse,
    StockCheckResponse, StockShortageItem
)
import uuid

router = APIRouter(prefix="/manufacturing", tags=["Manufacturing"])


def gen_uuid():
    return str(uuid.uuid4())


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
    db: Session, model_id: str, colour: str, battery_type: str, power_spec: str
) -> List[BOMItem]:
    """
    Returns BOM items applicable for this specific configuration.
    - Items with no filter → always included
    - Items with specific filters → only if they match the selected attribute
    """
    all_items = db.query(BOMItem).filter(
        BOMItem.model_id == model_id
    ).all()

    applicable = []
    for item in all_items:
        if item.colour and item.colour.lower() != (colour or "").lower():
            continue
        if item.battery_type and item.battery_type.lower() != (battery_type or "").lower():
            continue
        if item.power_spec and item.power_spec.lower() != (power_spec or "").lower():
            continue
        applicable.append(item)
    return applicable


def _find_inventory_item(db: Session, bom: BOMItem) -> Optional[InventoryItem]:
    """
    Find matching inventory item for a BOM item.
    Priority: SKU match → exact name match → partial name match
    """
    if bom.inventory_item_id:
        item = db.query(InventoryItem).filter(
            InventoryItem.id       == bom.inventory_item_id,
            InventoryItem.is_active == True
        ).first()
        if item: return item

    if bom.sku:
        item = db.query(InventoryItem).filter(
            InventoryItem.sku       == bom.sku,
            InventoryItem.is_active == True
        ).first()
        if item: return item

    if bom.part_name:
        item = db.query(InventoryItem).filter(
            InventoryItem.item_name == bom.part_name,
            InventoryItem.is_active == True
        ).first()
        if item: return item

        item = db.query(InventoryItem).filter(
            InventoryItem.item_name.ilike(f"%{bom.part_name}%"),
            InventoryItem.is_active == True
        ).first()
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

    bom_item = BOMItem(
        id                = gen_uuid(),
        model_id          = data.model_id,
        part_name         = data.part_name.strip() if data.part_name else None,
        sku               = data.sku.strip().upper() if data.sku else None,
        inventory_item_id = data.inventory_item_id or None,
        quantity_required = data.quantity_required,
        colour            = data.colour.strip() if data.colour else None,
        battery_type      = data.battery_type.strip() if data.battery_type else None,
        power_spec        = data.power_spec.strip() if data.power_spec else None,
        notes             = data.notes,
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

    if data.part_name         is not None: item.part_name         = data.part_name.strip()
    if data.sku               is not None: item.sku               = data.sku.strip().upper() or None
    if data.quantity_required is not None: item.quantity_required = data.quantity_required
    if data.colour            is not None: item.colour            = data.colour.strip() or None
    if data.battery_type      is not None: item.battery_type      = data.battery_type.strip() or None
    if data.power_spec        is not None: item.power_spec        = data.power_spec.strip() or None
    if data.notes             is not None: item.notes             = data.notes

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

    bom_items = _get_applicable_bom_items(
        db, data.model_id, data.color, data.battery_type, data.power_spec
    )
    
    shortages = []
    for bom in bom_items:
        inv = _find_inventory_item(db, bom)
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

    bom_items = _get_applicable_bom_items(
        db, data.model_id, data.color, data.battery_type, data.power_spec
    )

    if not bom_items:
        raise HTTPException(
            400,
            f"No BOM defined for {model.model_name} ({data.battery_type} - {data.power_spec}). "
            "Please configure the BOM first."
        )

    shortages = []
    for bom in bom_items:
        inv = _find_inventory_item(db, bom)
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
        battery_type = data.battery_type,
        power_spec   = data.power_spec,
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
        inv = _find_inventory_item(db, bom)
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
        db, job.model_id, job.color, job.battery_type, job.power_spec
    )

    for bom in bom_items:
        inv = _find_inventory_item(db, bom)
        if not inv:
            continue
        returned = bom.quantity_required * job.quantity
        inv.consumed_quantity  -= returned
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
    current_user: User    = Depends(require_manager_or_above)
):
    job = db.query(AssemblyJob).filter(AssemblyJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Assembly job not found.")
        
    if job.status != AssemblyStatus.cancelled:
        bom_items = _get_applicable_bom_items(
            db, job.model_id, job.color, job.battery_type, job.power_spec
        )
        
        for bom in bom_items:
            inv = _find_inventory_item(db, bom)
            if not inv:
                continue
                
            returned = bom.quantity_required * job.quantity
            inv.consumed_quantity  -= returned
            inv.remaining_quantity += returned
            
            if job.location_id:
                loc_stock = db.query(InventoryLocationStock).filter(
                    InventoryLocationStock.item_id     == inv.id,
                    InventoryLocationStock.location_id == job.location_id
                ).first()
                if loc_stock:
                    loc_stock.quantity += returned

    db.query(StockMovement).filter(StockMovement.reference_id == job.id).delete()
    db.query(ScooterUnit).filter(ScooterUnit.assembly_job_id == job.id).delete()
    
    db.delete(job)
    db.commit()
    return {"message": "Job deleted and parts successfully returned to inventory."}