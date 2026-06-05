from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.dependencies import (
    get_current_user, require_manager_or_above,
    require_any_role, can_see_financials
)
from app.models import (
    InventoryItem, InventoryCategory,
    StockMovement, User, Location,
    InventoryLocationStock,
    DispatchNotePart, DispatchNote, Dealer,
)
from app.schemas.inventory import (
    CategoryCreate, CategoryResponse,
    InventoryItemCreate, InventoryItemUpdate,
    StockAdjustRequest, StockMoveRequest,
    _COLOUR_UNSET
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ── HELPERS ───────────────────────────────────────────────────

def _item_to_response(item: InventoryItem, user: User) -> dict:
    return {
        "id":                  item.id,
        "item_name":           item.item_name,
        "sku":                 item.sku,
        "unit":                item.unit,
        "total_quantity":      item.total_quantity,
        "remaining_quantity":  item.remaining_quantity,
        "consumed_quantity":   item.consumed_quantity,
        "defective_quantity":  item.defective_quantity,
        "damaged_quantity":    item.damaged_quantity,
        "low_stock_threshold": item.low_stock_threshold,
        "unit_cost":           item.unit_cost if can_see_financials(user) else None,
        "is_spare_part":       item.is_spare_part,
        "is_active":           item.is_active,
        "category_id":         item.category_id,
        "category_name":       item.category.name if item.category else None,
        "model_name":          item.model_name,
        "colour":              item.colour,
        "import_date":         str(item.import_date) if item.import_date else None,
        "location_id":         item.location_id,
        "location_name":       item.location.name if item.location else None,
    }


def _get_or_create_location_stock(
    db: Session, item_id: str, location_id: str
) -> InventoryLocationStock:
    stock = db.query(InventoryLocationStock).filter(
        InventoryLocationStock.item_id     == item_id,
        InventoryLocationStock.location_id == location_id
    ).first()
    if not stock:
        stock = InventoryLocationStock(
            item_id     = item_id,
            location_id = location_id,
            quantity    = 0
        )
        db.add(stock)
        db.flush()
    return stock


# ── CATEGORIES ────────────────────────────────────────────────

@router.get("/categories", response_model=List[CategoryResponse])
def get_categories(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    return db.query(InventoryCategory).all()


@router.post("/categories", response_model=CategoryResponse)
def create_category(
    data:         CategoryCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    existing = db.query(InventoryCategory).filter(
        InventoryCategory.name == data.name
    ).first()
    if existing:
        raise HTTPException(400, f"Category '{data.name}' already exists.")
    cat = InventoryCategory(name=data.name, description=data.description)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ── INVENTORY ITEMS ───────────────────────────────────────────

@router.get("/items")
def get_items(
    db:               Session        = Depends(get_db),
    current_user:     User           = Depends(require_any_role),
    category_id:      Optional[str]  = None,
    low_stock_only:   bool           = False,
    spare_parts_only: bool           = False,
    search:           Optional[str]  = None,
    model_name:       Optional[str]  = None,
):
    query = db.query(InventoryItem).filter(
        InventoryItem.is_active == True
    )
    if category_id:
        query = query.filter(InventoryItem.category_id == category_id)
    if low_stock_only:
        query = query.filter(
            InventoryItem.remaining_quantity <= InventoryItem.low_stock_threshold
        )
    if spare_parts_only:
        query = query.filter(InventoryItem.is_spare_part == True)
    if model_name:
        query = query.filter(
            InventoryItem.model_name.ilike(f"%{model_name}%")
        )
    if search:
        query = query.filter(
            InventoryItem.item_name.ilike(f"%{search}%") |   
            InventoryItem.sku.ilike(f"{search}%") |          
            InventoryItem.model_name.ilike(f"{search}%")     
        )
    items = query.order_by(
        InventoryItem.model_name,
        InventoryItem.item_name
    ).all()
    return [_item_to_response(i, current_user) for i in items]


@router.get("/items/{item_id}")
def get_item(
    item_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id
    ).first()
    if not item:
        raise HTTPException(404, "Item not found.")
    return _item_to_response(item, current_user)


@router.get("/items/{item_id}/locations")
def get_item_locations(
    item_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    """Get stock breakdown by location for a specific item."""
    stocks = db.query(InventoryLocationStock).filter(
        InventoryLocationStock.item_id  == item_id,
        InventoryLocationStock.quantity >  0
    ).all()

    result = []
    for s in stocks:
        loc = db.query(Location).filter(
            Location.id == s.location_id
        ).first()
        if loc:
            result.append({
                "location_id":   s.location_id,
                "location_name": loc.name,
                "location_type": loc.location_type,
                "quantity":      s.quantity,
            })
    return result


@router.post("/items")
def create_item(
    data:         InventoryItemCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    if not data.model_name or not data.model_name.strip():
        raise HTTPException(400, "Model name is required.")

    # Check active items — if exists just add stock
    existing = db.query(InventoryItem).filter(
        InventoryItem.sku       == data.sku,
        InventoryItem.is_active == True
    ).first()

    if existing:
        existing.remaining_quantity += data.total_quantity
        existing.total_quantity     += data.total_quantity

        if data.location_id:
            loc_stock = _get_or_create_location_stock(
                db, existing.id, data.location_id
            )
            loc_stock.quantity += data.total_quantity

        movement = StockMovement(
            item_id       = existing.id,
            movement_type = "received",
            quantity      = data.total_quantity,
            notes         = f"Import — {data.import_date or 'no date'}",
            performed_by  = current_user.id
        )
        db.add(movement)
        db.commit()
        db.refresh(existing)
        return _item_to_response(existing, current_user)

    # Check deactivated item — reactivate
    deactivated = db.query(InventoryItem).filter(
        InventoryItem.sku       == data.sku,
        InventoryItem.is_active == False
    ).first()

    if deactivated:
        deactivated.is_active           = True
        deactivated.remaining_quantity  = data.total_quantity
        deactivated.total_quantity      = data.total_quantity
        deactivated.consumed_quantity   = 0
        deactivated.defective_quantity  = 0
        deactivated.damaged_quantity    = 0
        deactivated.import_date         = data.import_date
        deactivated.location_id         = data.location_id

        if data.location_id:
            loc_stock = _get_or_create_location_stock(
                db, deactivated.id, data.location_id
            )
            loc_stock.quantity = data.total_quantity

        movement = StockMovement(
            item_id       = deactivated.id,
            movement_type = "received",
            quantity      = data.total_quantity,
            notes         = f"Reactivated — {data.import_date or 'no date'}",
            performed_by  = current_user.id
        )
        db.add(movement)
        db.commit()
        db.refresh(deactivated)
        return _item_to_response(deactivated, current_user)

    # Brand new item
    item = InventoryItem(
        item_name           = data.item_name,
        sku                 = data.sku,
        category_id         = data.category_id,
        unit                = "pcs",
        total_quantity      = data.total_quantity,
        remaining_quantity  = data.total_quantity,
        low_stock_threshold = data.low_stock_threshold,
        unit_cost           = data.unit_cost if can_see_financials(current_user) else None,
        is_spare_part       = data.is_spare_part,
        model_name          = data.model_name.strip(),
        colour              = data.colour.strip() if data.colour else None,
        import_date         = data.import_date,
        location_id         = data.location_id,
    )
    db.add(item)
    db.commit()

    if data.total_quantity > 0:
        movement = StockMovement(
            item_id       = item.id,
            movement_type = "received",
            quantity      = data.total_quantity,
            notes         = f"Import — {data.import_date or 'no date'}",
            performed_by  = current_user.id
        )
        db.add(movement)

        if data.location_id:
            loc_stock = InventoryLocationStock(
                item_id     = item.id,
                location_id = data.location_id,
                quantity    = data.total_quantity
            )
            db.add(loc_stock)

        db.commit()

    db.refresh(item)
    return _item_to_response(item, current_user)


@router.patch("/items/{item_id}")
def update_item(
    item_id:      str,
    data:         InventoryItemUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id
    ).first()
    if not item:
        raise HTTPException(404, "Item not found.")

    if data.item_name           is not None: item.item_name           = data.item_name
    if data.category_id         is not None: item.category_id         = data.category_id
    if data.unit                is not None: item.unit                = data.unit
    if data.low_stock_threshold is not None: item.low_stock_threshold = data.low_stock_threshold
    if data.is_spare_part       is not None: item.is_spare_part       = data.is_spare_part
    if data.model_name          is not None:
        if not data.model_name.strip():
            raise HTTPException(400, "Model name cannot be empty.")
        item.model_name = data.model_name.strip()

    # Bug 4 fix: sentinel check — _COLOUR_UNSET means field was not sent at all,
    # anything else (including "") means explicitly set (empty string clears the colour)
    if data.colour != _COLOUR_UNSET:
        item.colour = data.colour.strip() if data.colour.strip() else None

    if data.location_id is not None: item.location_id = data.location_id or None
    if data.unit_cost is not None and can_see_financials(current_user):
        item.unit_cost = data.unit_cost
    if data.sku is not None:
        item.sku = data.sku
    db.commit()
    db.refresh(item)
    return _item_to_response(item, current_user)


@router.delete("/items/{item_id}")
def delete_item(
    item_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id
    ).first()
    if not item:
        raise HTTPException(404, "Item not found.")

    db.query(StockMovement).filter(
        StockMovement.item_id == item_id
    ).delete()

    db.query(InventoryLocationStock).filter(
        InventoryLocationStock.item_id == item_id
    ).delete()

    db.delete(item)
    db.commit()

    return {"message": f"'{item.item_name}' permanently deleted."}


@router.post("/adjust")
def adjust_stock(
    data:         StockAdjustRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    item = db.query(InventoryItem).filter(
        InventoryItem.id == data.item_id
    ).first()
    if not item:
        raise HTTPException(404, "Item not found.")
    if data.quantity <= 0:
        raise HTTPException(400, "Quantity must be greater than 0.")

    # Bug 2 fix: added "correction_remove" as a valid movement type
    allowed = ["consumed", "defective", "damaged", "adjusted", "received", "correction_remove"]
    if data.movement_type not in allowed:
        raise HTTPException(400, "Invalid movement type.")

    # Stock availability checks for all deduction types
    if data.movement_type in ["consumed", "defective", "damaged", "correction_remove"]:
        if item.remaining_quantity < data.quantity:
            raise HTTPException(
                400,
                f"Not enough stock. Available: {item.remaining_quantity} pcs"
            )
        if data.location_id:
            loc_stock = db.query(InventoryLocationStock).filter(
                InventoryLocationStock.item_id     == data.item_id,
                InventoryLocationStock.location_id == data.location_id
            ).first()
            if not loc_stock or loc_stock.quantity < data.quantity:
                available = loc_stock.quantity if loc_stock else 0
                raise HTTPException(
                    400,
                    f"Not enough stock at this location. "
                    f"Available: {available} pcs"
                )

    if data.movement_type in ["adjusted", "received"]:
        if current_user.role == "staff":
            raise HTTPException(403, "Staff cannot adjust stock manually.")

    # Update item totals
    if data.movement_type == "consumed":
        item.consumed_quantity  += data.quantity
        item.remaining_quantity -= data.quantity
    elif data.movement_type == "correction_remove":
        # Bug 2 fix: only deducts remaining_quantity — does NOT touch
        # consumed_quantity, so the Consumed column stays clean
        item.remaining_quantity -= data.quantity
    elif data.movement_type == "defective":
        item.defective_quantity += data.quantity
        item.remaining_quantity -= data.quantity
    elif data.movement_type == "damaged":
        item.damaged_quantity   += data.quantity
        item.remaining_quantity -= data.quantity
    elif data.movement_type in ["adjusted", "received"]:
        item.remaining_quantity += data.quantity
        item.total_quantity     += data.quantity

    # Update location stock
    if data.location_id:
        loc_stock = db.query(InventoryLocationStock).filter(
            InventoryLocationStock.item_id     == data.item_id,
            InventoryLocationStock.location_id == data.location_id
        ).first()
        if data.movement_type in ["consumed", "defective", "damaged", "correction_remove"]:
            if loc_stock:
                loc_stock.quantity -= data.quantity
        elif data.movement_type in ["adjusted", "received"]:
            if loc_stock:
                loc_stock.quantity += data.quantity
            else:
                loc_stock = InventoryLocationStock(
                    item_id     = data.item_id,
                    location_id = data.location_id,
                    quantity    = data.quantity
                )
                db.add(loc_stock)

    movement = StockMovement(
        item_id       = item.id,
        movement_type = data.movement_type,
        quantity      = data.quantity,
        notes         = data.notes,
        performed_by  = current_user.id
    )
    db.add(movement)
    db.commit()
    db.refresh(item)
    return {
        "message": "Stock updated successfully.",
        "item":    _item_to_response(item, current_user)
    }


# ── STOCK MOVE ────────────────────────────────────────────────

@router.post("/move")
def move_stock(
    data:         StockMoveRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    """Move stock from one location to another."""
    if data.from_location_id == data.to_location_id:
        raise HTTPException(400, "From and To locations cannot be the same.")
    if data.quantity <= 0:
        raise HTTPException(400, "Quantity must be greater than 0.")

    item = db.query(InventoryItem).filter(
        InventoryItem.id == data.item_id
    ).first()
    if not item:
        raise HTTPException(404, "Item not found.")

    from_stock = db.query(InventoryLocationStock).filter(
        InventoryLocationStock.item_id     == data.item_id,
        InventoryLocationStock.location_id == data.from_location_id
    ).first()

    if not from_stock or from_stock.quantity < data.quantity:
        available = from_stock.quantity if from_stock else 0
        raise HTTPException(
            400,
            f"Not enough stock at source location. "
            f"Available: {available} pcs"
        )

    to_stock = _get_or_create_location_stock(
        db, data.item_id, data.to_location_id
    )

    from_stock.quantity -= data.quantity
    to_stock.quantity   += data.quantity

    if from_stock.quantity == 0 and item.location_id == data.from_location_id:
        item.location_id = data.to_location_id

    from_loc = db.query(Location).filter(
        Location.id == data.from_location_id
    ).first()
    to_loc = db.query(Location).filter(
        Location.id == data.to_location_id
    ).first()

    movement = StockMovement(
        item_id       = data.item_id,
        movement_type = "transferred",
        quantity      = data.quantity,
        notes         = (
            f"Moved from {from_loc.name if from_loc else 'unknown'} "
            f"to {to_loc.name if to_loc else 'unknown'}"
            + (f" — {data.notes}" if data.notes else "")
        ),
        performed_by  = current_user.id
    )
    db.add(movement)
    db.commit()

    return {
        "message":  f"Successfully moved {data.quantity} pcs.",
        "from":     from_loc.name if from_loc else "unknown",
        "to":       to_loc.name   if to_loc   else "unknown",
        "quantity": data.quantity
    }


# ── MOVEMENTS ─────────────────────────────────────────────────

@router.get("/movements/{item_id}")
def get_movements(
    item_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    """Returns full history of a part — purchases, defectives, consumed, moves, corrections."""
    movements = db.query(StockMovement).filter(
        StockMovement.item_id == item_id
    ).order_by(StockMovement.created_at.desc()).limit(200).all()

    imports     = []
    defectives  = []
    consumed    = []
    transfers   = []
    corrections = []

    for m in movements:
        performer = db.query(User).filter(
            User.id == m.performed_by
        ).first()
        performer_name = performer.full_name if performer else "Unknown"

        created = (
            m.created_at.strftime("%d-%b-%Y  %H:%M")
            if m.created_at else "—"
        )

        entry = {
            "id":           m.id,
            "quantity":     m.quantity,
            "notes":        m.notes or "",
            "performed_by": performer_name,
            "created_at":   created,
            "type":         m.movement_type,
        }

        is_correction = "Quantity Correction" in (m.notes or "")

        if m.movement_type in ["received", "adjusted"]:
            if is_correction:
                corrections.append(entry)
            else:
                imports.append(entry)
        elif m.movement_type in ["defective", "damaged"]:
            defectives.append(entry)
        elif m.movement_type == "consumed":
            if is_correction:
                corrections.append(entry)
            else:
                consumed.append(entry)
        elif m.movement_type == "transferred":
            transfers.append(entry)
        elif m.movement_type == "correction_remove":
            # Bug 2 fix: correction_remove always goes to corrections section
            corrections.append(entry)

    # Spare part dispatches from dispatch notes
    dispatches = []
    parts = (
        db.query(DispatchNotePart)
        .filter(DispatchNotePart.inventory_item_id == item_id)
        .order_by(DispatchNotePart.id.desc())
        .all()
    )
    for p in parts:
        note   = p.dispatch_note
        dealer = note.dealer if note else None
        dispatches.append({
            "quantity":      p.quantity,
            "dealer_name":   dealer.dealer_name if dealer else "—",
            "dispatch_date": str(note.dispatch_date) if note else "—",
            "notes":         p.notes or "",
            "part_name":     p.part_name,
        })

    return {
        "imports":     imports,
        "defectives":  defectives,
        "consumed":    consumed,
        "transfers":   transfers,
        "corrections": corrections,
        "dispatches":  dispatches,
    }


# ── MODELS LIST ───────────────────────────────────────────────

@router.get("/models")
def get_distinct_models(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    results = db.query(InventoryItem.model_name).filter(
        InventoryItem.is_active  == True,
        InventoryItem.model_name != None
    ).distinct().order_by(InventoryItem.model_name).all()
    return [r[0] for r in results if r[0]]


# ── SUMMARY ───────────────────────────────────────────────────

@router.get("/summary")
def get_summary(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    items = db.query(InventoryItem).filter(
        InventoryItem.is_active == True
    ).all()

    result = {
        "total_items":     len(items),
        "low_stock_count": sum(
            1 for i in items
            if i.remaining_quantity <= i.low_stock_threshold
        ),
        "total_consumed":  sum(i.consumed_quantity  for i in items),
        "total_defective": sum((i.defective_quantity + i.damaged_quantity) for i in items),
    }

    if can_see_financials(current_user):
        result["total_inventory_value"] = round(sum(
            i.remaining_quantity * (i.unit_cost or 0)
            for i in items
        ), 2)

    return result