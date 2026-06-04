from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.dependencies import (
    require_any_role, require_manager_or_above, require_superadmin
)
from app.models import ScooterModel, MasterColor, MasterBattery, Location, User
from app.schemas.models import (
    ScooterModelCreate, ScooterModelUpdate, ScooterModelResponse,
    MasterColorCreate, MasterColorResponse,
    MasterBatteryCreate, MasterBatteryResponse,
    LocationCreate, LocationUpdate, LocationResponse
)

router = APIRouter(prefix="/master", tags=["Master Data"])


# ── SCOOTER MODELS ────────────────────────────────────────────

@router.get("/models", response_model=List[ScooterModelResponse])
def get_models(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role),
    active_only:  bool    = True
):
    query = db.query(ScooterModel)
    if active_only:
        query = query.filter(ScooterModel.is_active == True)
    return query.order_by(ScooterModel.model_name).all()


@router.post("/models", response_model=ScooterModelResponse)
def create_model(
    data:         ScooterModelCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    # Check name uniqueness
    if db.query(ScooterModel).filter(
        ScooterModel.model_name == data.model_name
    ).first():
        raise HTTPException(
            400, f"Model '{data.model_name}' already exists."
        )
    # Check code uniqueness
    if db.query(ScooterModel).filter(
        ScooterModel.model_code == data.model_code.upper()
    ).first():
        raise HTTPException(
            400, f"Model code '{data.model_code}' already exists."
        )

    model = ScooterModel(
        model_name  = data.model_name.strip(),
        model_code  = data.model_code.upper().strip(),
        description = data.description
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@router.patch("/models/{model_id}", response_model=ScooterModelResponse)
def update_model(
    model_id:     str,
    data:         ScooterModelUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    model = db.query(ScooterModel).filter(
        ScooterModel.id == model_id
    ).first()
    if not model:
        raise HTTPException(404, "Model not found.")

    if data.model_name is not None:
        model.model_name = data.model_name.strip()
    if data.description is not None:
        model.description = data.description
    if data.is_active is not None:
        model.is_active = data.is_active

    db.commit()
    db.refresh(model)
    return model


@router.delete("/models/{model_id}")
def delete_model(
    model_id:     str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    model = db.query(ScooterModel).filter(
        ScooterModel.id == model_id
    ).first()
    if not model:
        raise HTTPException(404, "Model not found.")

    model.is_active = False
    db.commit()
    return {"message": f"Model '{model.model_name}' deactivated."}


# ── MASTER COLORS ─────────────────────────────────────────────

@router.get("/colors", response_model=List[MasterColorResponse])
def get_colors(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    return db.query(MasterColor).order_by(MasterColor.name).all()


@router.post("/colors", response_model=MasterColorResponse)
def create_color(
    data:         MasterColorCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    name_clean = data.name.strip()
    if db.query(MasterColor).filter(MasterColor.name == name_clean).first():
        raise HTTPException(400, f"Color '{name_clean}' already exists.")

    color = MasterColor(name=name_clean)
    db.add(color)
    db.commit()
    db.refresh(color)
    return color


@router.delete("/colors/{color_id}")
def delete_color(
    color_id:     str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    color = db.query(MasterColor).filter(MasterColor.id == color_id).first()
    if not color:
        raise HTTPException(404, "Color not found.")

    db.delete(color)
    db.commit()
    return {"message": f"Color '{color.name}' deleted successfully."}


# ── MASTER BATTERIES ──────────────────────────────────────────

@router.get("/batteries", response_model=List[MasterBatteryResponse])
def get_batteries(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_any_role)
):
    return db.query(MasterBattery).order_by(
        MasterBattery.battery_type, 
        MasterBattery.power_spec
    ).all()


@router.post("/batteries", response_model=MasterBatteryResponse)
def create_battery(
    data:         MasterBatteryCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    b_type_clean = data.battery_type.strip()
    p_spec_clean = data.power_spec.strip()

    exists = db.query(MasterBattery).filter(
        MasterBattery.battery_type == b_type_clean,
        MasterBattery.power_spec == p_spec_clean
    ).first()

    if exists:
        raise HTTPException(
            400, 
            f"Battery configuration '{b_type_clean}' with '{p_spec_clean}' already exists."
        )

    battery = MasterBattery(
        battery_type = b_type_clean,
        power_spec   = p_spec_clean
    )
    db.add(battery)
    db.commit()
    db.refresh(battery)
    return battery


@router.delete("/batteries/{battery_id}")
def delete_battery(
    battery_id:   str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    battery = db.query(MasterBattery).filter(MasterBattery.id == battery_id).first()
    if not battery:
        raise HTTPException(404, "Battery not found.")

    db.delete(battery)
    db.commit()
    return {"message": "Battery configuration deleted successfully."}


# ── LOCATIONS ─────────────────────────────────────────────────

@router.get("/locations", response_model=List[LocationResponse])
def get_locations(
    db:            Session       = Depends(get_db),
    current_user:  User          = Depends(require_any_role),
    location_type: Optional[str] = None,
    active_only:   bool          = True
):
    query = db.query(Location)
    if active_only:
        query = query.filter(Location.is_active == True)
    if location_type:
        query = query.filter(
            Location.location_type == location_type
        )
    return query.order_by(Location.name).all()


@router.post("/locations", response_model=LocationResponse)
def create_location(
    data:         LocationCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    if db.query(Location).filter(
        Location.name == data.name
    ).first():
        raise HTTPException(
            400, f"Location '{data.name}' already exists."
        )

    if data.location_type not in ["factory", "warehouse", "godown"]:
        raise HTTPException(
            400, "Location type must be factory, warehouse, or godown."
        )

    location = Location(
        name          = data.name.strip(),
        location_type = data.location_type,
        address       = data.address,
        city          = data.city,
        state         = data.state
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.patch("/locations/{location_id}", response_model=LocationResponse)
def update_location(
    location_id:  str,
    data:         LocationUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    location = db.query(Location).filter(
        Location.id == location_id
    ).first()
    if not location:
        raise HTTPException(404, "Location not found.")

    if data.name is not None:
        location.name = data.name.strip()
    if data.location_type is not None:
        location.location_type = data.location_type
    if data.address is not None:
        location.address = data.address
    if data.city is not None:
        location.city = data.city
    if data.state is not None:
        location.state = data.state
    if data.is_active is not None:
        location.is_active = data.is_active

    db.commit()
    db.refresh(location)
    return location


@router.delete("/locations/{location_id}")
def delete_location(
    location_id:  str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    location = db.query(Location).filter(
        Location.id == location_id
    ).first()
    if not location:
        raise HTTPException(404, "Location not found.")

    location.is_active = False
    db.commit()
    return {"message": f"Location '{location.name}' deactivated."}