from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.dependencies import (
    require_any_role, require_manager_or_above, require_superadmin
)
from app.models import ScooterModel, ScooterVariant, Location, User
from app.schemas.models import (
    ScooterModelCreate, ScooterModelUpdate, ScooterModelResponse,
    ScooterVariantCreate, ScooterVariantResponse,
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


# ── SCOOTER VARIANTS ──────────────────────────────────────────

@router.get("/variants", response_model=List[ScooterVariantResponse])
def get_variants(
    db:           Session       = Depends(get_db),
    current_user: User          = Depends(require_any_role),
    model_id:     Optional[str] = None
):
    query = db.query(ScooterVariant).filter(
        ScooterVariant.is_active == True
    )
    if model_id:
        query = query.filter(ScooterVariant.model_id == model_id)

    variants = query.all()
    result   = []
    for v in variants:
        model = db.query(ScooterModel).filter(
            ScooterModel.id == v.model_id
        ).first()
        result.append({
            "id":           v.id,
            "model_id":     v.model_id,
            "color":        v.color,
            "battery_type": v.battery_type,
            "power_spec":   v.power_spec,
            "variant_code": v.variant_code,
            "is_active":    v.is_active,
            "model_name":   model.model_name if model else None
        })
    return result


@router.post("/variants", response_model=ScooterVariantResponse)
def create_variant(
    data:         ScooterVariantCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    # Check model exists
    model = db.query(ScooterModel).filter(
        ScooterModel.id == data.model_id
    ).first()
    if not model:
        raise HTTPException(404, "Scooter model not found.")

    # Check variant code uniqueness
    if db.query(ScooterVariant).filter(
        ScooterVariant.variant_code == data.variant_code.upper()
    ).first():
        raise HTTPException(
            400, f"Variant code '{data.variant_code}' already exists."
        )

    variant = ScooterVariant(
        model_id     = data.model_id,
        color        = data.color.strip(),
        battery_type = data.battery_type.strip(),
        power_spec   = data.power_spec,
        variant_code = data.variant_code.upper().strip()
    )
    db.add(variant)
    db.commit()
    db.refresh(variant)

    return {
        "id":           variant.id,
        "model_id":     variant.model_id,
        "color":        variant.color,
        "battery_type": variant.battery_type,
        "power_spec":   variant.power_spec,
        "variant_code": variant.variant_code,
        "is_active":    variant.is_active,
        "model_name":   model.model_name
    }


@router.delete("/variants/{variant_id}")
def delete_variant(
    variant_id:   str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_manager_or_above)
):
    variant = db.query(ScooterVariant).filter(
        ScooterVariant.id == variant_id
    ).first()
    if not variant:
        raise HTTPException(404, "Variant not found.")

    variant.is_active = False
    db.commit()
    return {"message": "Variant deactivated."}


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