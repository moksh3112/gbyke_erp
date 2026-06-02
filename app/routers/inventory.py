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
    StockMovement, User
)
from app.schemas.inventory import (
    CategoryCreate, CategoryResponse,
    InventoryItemCreate, InventoryItemUpdate,
    StockAdjustRequest
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
    }


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
        query = query.filter(
            InventoryItem.category_id == category_id
        )
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
            InventoryItem.sku.ilike(f"%{search}%") |
            InventoryItem.model_name.ilike(f"%{search}%")
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

@router.post("/items")
def create_item(
    data:         InventoryItemCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    if not data.model_name or not data.model_name.strip():
        raise HTTPException(400, "Model name is required.")

    # Check active items first
    existing = db.query(InventoryItem).filter(
        InventoryItem.sku       == data.sku,
        InventoryItem.is_active == True
    ).first()

    if existing:
        # Add to existing active item
        existing.remaining_quantity += data.total_quantity
        existing.total_quantity     += data.total_quantity
        movement = StockMovement(
            item_id       = existing.id,
            movement_type = "received",
            quantity      = data.total_quantity,
            notes         = f"Import entry — {data.import_date or 'no date'}",
            performed_by  = current_user.id
        )
        db.add(movement)
        db.commit()
        db.refresh(existing)
        return _item_to_response(existing, current_user)

    # Check if a deactivated item exists with same SKU — reactivate it
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
        movement = StockMovement(
            item_id       = deactivated.id,
            movement_type = "received",
            quantity      = data.total_quantity,
            notes         = f"Reactivated — import on {data.import_date or 'no date'}",
            performed_by  = current_user.id
        )
        db.add(movement)
        db.commit()
        db.refresh(deactivated)
        return _item_to_response(deactivated, current_user)

    # Completely new item
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
    )
    db.add(item)
    db.commit()

    if data.total_quantity > 0:
        movement = StockMovement(
            item_id       = item.id,
            movement_type = "received",
            quantity      = data.total_quantity,
            notes         = f"Import entry — {data.import_date or 'no date'}",
            performed_by  = current_user.id
        )
        db.add(movement)
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

    if data.item_name is not None:
        item.item_name = data.item_name
    if data.category_id is not None:
        item.category_id = data.category_id
    if data.unit is not None:
        item.unit = data.unit
    if data.low_stock_threshold is not None:
        item.low_stock_threshold = data.low_stock_threshold
    if data.unit_cost is not None and can_see_financials(current_user):
        item.unit_cost = data.unit_cost
    if data.is_spare_part is not None:
        item.is_spare_part = data.is_spare_part
    if data.model_name is not None:
        if not data.model_name.strip():
            raise HTTPException(400, "Model name cannot be empty.")
        item.model_name = data.model_name.strip()
    if data.colour is not None:
        item.colour = data.colour.strip() if data.colour.strip() else None

    db.commit()
    db.refresh(item)
    return _item_to_response(item, current_user)


@router.delete("/items/{item_id}")
def deactivate_item(
    item_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id
    ).first()
    if not item:
        raise HTTPException(404, "Item not found.")

    item.is_active = False
    db.commit()
    return {"message": f"'{item.item_name}' deactivated successfully."}


# ── STOCK MOVEMENTS ───────────────────────────────────────────

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

    allowed = ["consumed", "defective", "damaged", "adjusted", "received"]
    if data.movement_type not in allowed:
        raise HTTPException(400, "Invalid movement type.")

    if data.movement_type in ["consumed", "defective", "damaged"]:
        if item.remaining_quantity < data.quantity:
            raise HTTPException(
                400,
                f"Not enough stock. Available: {item.remaining_quantity} pcs"
            )

    if data.movement_type in ["adjusted", "received"]:
        if current_user.role == "staff":
            raise HTTPException(
                403, "Staff cannot make manual stock adjustments."
            )

    if data.movement_type == "consumed":
        item.consumed_quantity  += data.quantity
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


@router.get("/movements/{item_id}")
def get_movements(
    item_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    movements = db.query(StockMovement).filter(
        StockMovement.item_id == item_id
    ).order_by(StockMovement.created_at.desc()).limit(50).all()

    result = []
    for m in movements:
        performer = db.query(User).filter(
            User.id == m.performed_by
        ).first()
        result.append({
            "id":                m.id,
            "item_id":           m.item_id,
            "movement_type":     m.movement_type,
            "quantity":          m.quantity,
            "notes":             m.notes,
            "performed_by_name": performer.full_name if performer else "Unknown",
            "created_at":        m.created_at.isoformat() if m.created_at else None
        })
    return result


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


@router.get("/summary")
def get_summary(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    items = db.query(InventoryItem).filter(
        InventoryItem.is_active == True
    ).all()

    total_items     = len(items)
    low_stock       = sum(
        1 for i in items
        if i.remaining_quantity <= i.low_stock_threshold
    )
    total_consumed  = sum(i.consumed_quantity  for i in items)
    total_defective = sum(i.defective_quantity for i in items)

    result = {
        "total_items":     total_items,
        "low_stock_count": low_stock,
        "total_consumed":  total_consumed,
        "total_defective": total_defective,
    }

    if can_see_financials(current_user):
        total_value = sum(
            i.remaining_quantity * (i.unit_cost or 0)
            for i in items
        )
        result["total_inventory_value"] = round(total_value, 2)

    return result