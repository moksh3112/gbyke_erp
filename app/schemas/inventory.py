from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date


class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class InventoryItemCreate(BaseModel):
    item_name:           str
    sku:                 str
    category_id:         Optional[str]   = None
    unit:                str             = "pcs"
    total_quantity:      int             = 0
    low_stock_threshold: int             = 10
    unit_cost:           Optional[float] = None
    is_spare_part:       bool            = False
    model_name:          str
    colour:              Optional[str]   = None
    import_date:         Optional[str]   = None
    location_id:         Optional[str]   = None


class InventoryItemUpdate(BaseModel):
    item_name:           Optional[str]   = None
    category_id:         Optional[str]   = None
    unit:                Optional[str]   = None
    low_stock_threshold: Optional[int]   = None
    unit_cost:           Optional[float] = None
    is_spare_part:       Optional[bool]  = None
    model_name:          Optional[str]   = None
    colour:              Optional[str]   = None
    location_id:         Optional[str]   = None


class InventoryItemResponse(BaseModel):
    id:                  str
    item_name:           str
    sku:                 str
    unit:                str
    total_quantity:      int
    remaining_quantity:  int
    consumed_quantity:   int
    defective_quantity:  int
    damaged_quantity:    int
    low_stock_threshold: int
    unit_cost:           Optional[float] = None
    is_spare_part:       bool
    is_active:           bool
    category_id:         Optional[str]   = None
    category_name:       Optional[str]   = None
    model_name:          Optional[str]   = None
    colour:              Optional[str]   = None
    import_date:         Optional[str]   = None
    location_id:         Optional[str]   = None
    location_name:       Optional[str]   = None

    class Config:
        from_attributes = True


class StockAdjustRequest(BaseModel):
    item_id:       str
    quantity:      int
    movement_type: str
    notes:         Optional[str] = None
    location_id:   Optional[str] = None  # ← add this


class StockMovementResponse(BaseModel):
    id:                str
    item_id:           str
    item_name:         Optional[str] = None
    movement_type:     str
    quantity:          int
    notes:             Optional[str] = None
    performed_by:      Optional[str] = None
    performed_by_name: Optional[str] = None
    created_at:        datetime

    class Config:
        from_attributes = True
        
class StockMoveRequest(BaseModel):
    item_id:          str
    from_location_id: str
    to_location_id:   str
    quantity:         int
    notes:            Optional[str] = None

class LocationStockResponse(BaseModel):
    location_id:   str
    location_name: str
    location_type: str
    quantity:      int