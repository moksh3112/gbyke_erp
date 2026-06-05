from pydantic import BaseModel
from typing import Optional, List


class DealerCreate(BaseModel):
    dealer_name:   str
    contact_name:  Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address:       Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None


class DealerUpdate(BaseModel):
    dealer_name:   Optional[str] = None
    contact_name:  Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address:       Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None
    is_active:     Optional[bool] = None


class DealerResponse(BaseModel):
    id:            str
    dealer_name:   str
    dealer_code:   str
    contact_name:  Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None
    is_active:     bool
    unit_count:    int = 0

    class Config:
        from_attributes = True


class UnitAtDealer(BaseModel):
    id:             str
    serial_number:  str
    chassis_number: Optional[str] = None
    pdi_number:     Optional[str] = None
    model_id:       Optional[str] = None
    model_name:     Optional[str] = None
    color:          Optional[str] = None
    status:         str
    delivered_date: Optional[str] = None


class DispatchRequest(BaseModel):
    unit_ids:      List[str]
    dealer_id:     str
    dispatch_date: Optional[str] = None
    notes:         Optional[str] = None
