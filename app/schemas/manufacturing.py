# app/schemas/manufacturing.py
# ONLY CHANGE from original: StockCheckResponse.shortages is now List[str]
# Everything else is identical to the original file.

from pydantic import BaseModel
from typing import Optional, List


# ── BOM ───────────────────────────────────────────────────────

class BOMItemCreate(BaseModel):
    model_id:           str
    part_name:          str                    # free text — no inventory dependency
    sku:                Optional[str] = None   # optional, used to match inventory
    inventory_item_id:  Optional[str] = None   # optional backward compat
    quantity_required:  int
    colour:             Optional[str] = None
    is_colour_specific: bool = False           # True = applies to every colour
    battery_type:       Optional[str] = None
    power_spec:         Optional[str] = None
    notes:              Optional[str] = None


class BOMItemUpdate(BaseModel):
    part_name:          Optional[str] = None
    sku:                Optional[str] = None
    quantity_required:  Optional[int] = None
    colour:             Optional[str] = None
    is_colour_specific: Optional[bool] = None
    battery_type:       Optional[str] = None
    power_spec:         Optional[str] = None
    notes:              Optional[str] = None


class BOMItemResponse(BaseModel):
    id:                str
    model_id:          str
    model_name:        Optional[str] = None
    part_name:         Optional[str] = None
    sku:               Optional[str] = None
    inventory_item_id: Optional[str] = None
    item_name:         Optional[str] = None
    quantity_required: int
    colour:            Optional[str] = None
    is_colour_specific: bool = False
    battery_type:      Optional[str] = None
    power_spec:        Optional[str] = None
    notes:             Optional[str] = None

    class Config:
        from_attributes = True


# ── ASSEMBLY JOBS ─────────────────────────────────────────────

class AssemblyJobCreate(BaseModel):
    model_id:    str
    color:       str
    quantity:    int
    location_id: Optional[str] = None
    notes:       Optional[str] = None


class AssemblyJobUpdate(BaseModel):
    status:      Optional[str] = None
    notes:       Optional[str] = None
    location_id: Optional[str] = None


class AddBOMStockRequest(BaseModel):
    model_id:    str
    colour:      Optional[str] = None
    quantity:    int                       # number of scooters
    location_id: Optional[str] = None
    import_date: Optional[str] = None


class AssemblyJobResponse(BaseModel):
    id:                str
    model_id:          str
    model_name:        Optional[str] = None
    color:             Optional[str] = None
    battery_type:      Optional[str] = None
    power_spec:        Optional[str] = None
    quantity:          int
    location_id:       Optional[str] = None
    location_name:     Optional[str] = None
    status:            str
    started_at:        Optional[str] = None
    completed_at:      Optional[str] = None
    performed_by:      Optional[str] = None
    performed_by_name: Optional[str] = None
    notes:             Optional[str] = None
    created_at:        Optional[str] = None
    units_created:     int = 0

    class Config:
        from_attributes = True


# ── STOCK SHORTAGE ────────────────────────────────────────────

# Kept for backward compatibility — still importable by the router
class StockShortageItem(BaseModel):
    part_name:  str
    sku:        Optional[str] = None
    required:   int
    available:  int
    shortage:   int


class StockCheckResponse(BaseModel):
    can_produce: bool
    shortages:   List[str] = []   # FIX 6: was List[StockShortageItem], router returns strings