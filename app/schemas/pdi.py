from pydantic import BaseModel
from typing import Optional

class ScooterUnitResponse(BaseModel):
    id: str
    serial_number: str
    chassis_number: Optional[str] = None
    model_name: Optional[str] = None
    color: Optional[str] = None
    power_spec: Optional[str] = None
    status: str

    class Config:
        from_attributes = True

class PDICompleteRequest(BaseModel):
    pdi_number: str
    serial_number: str
    chassis_number: str