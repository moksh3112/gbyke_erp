from pydantic import BaseModel
from typing import Optional


# ── SCOOTER MODELS ────────────────────────────────────────────

class ScooterModelCreate(BaseModel):
    model_name:  str
    model_code:  str
    description: Optional[str] = None

class ScooterModelUpdate(BaseModel):
    model_name:  Optional[str] = None
    description: Optional[str] = None
    is_active:   Optional[bool] = None

class ScooterModelResponse(BaseModel):
    id:          str
    model_name:  str
    model_code:  str
    description: Optional[str] = None
    is_active:   bool

    class Config:
        from_attributes = True


# ── MASTER COLORS & BATTERIES ─────────────────────────────────

class MasterColorCreate(BaseModel):
    name: str

class MasterColorResponse(BaseModel):
    id:   str
    name: str

    class Config:
        from_attributes = True


class MasterBatteryCreate(BaseModel):
    battery_type: str
    power_spec:   str

class MasterBatteryResponse(BaseModel):
    id:           str
    battery_type: str
    power_spec:   str

    class Config:
        from_attributes = True


# ── LOCATIONS ─────────────────────────────────────────────────

class LocationCreate(BaseModel):
    name:          str
    location_type: str  # factory / warehouse / godown
    address:       Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None

class LocationUpdate(BaseModel):
    name:          Optional[str] = None
    location_type: Optional[str] = None
    address:       Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None
    is_active:     Optional[bool] = None

class LocationResponse(BaseModel):
    id:            str
    name:          str
    location_type: str
    address:       Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None
    is_active:     bool

    class Config:
        from_attributes = True