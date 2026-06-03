from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.dependencies import require_superadmin
from app.models import User
from pydantic import BaseModel
import bcrypt

router = APIRouter(prefix="/users", tags=["Users"])


# ── SCHEMAS ───────────────────────────────────────────────────

class UserCreate(BaseModel):
    full_name: str
    username:  str
    password:  str
    role:      str  # manager / staff


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    username:  Optional[str] = None
    password:  Optional[str] = None
    role:      Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id:        str
    full_name: str
    username:  str
    role:      str
    is_active: bool

    class Config:
        from_attributes = True


# ── HELPERS ───────────────────────────────────────────────────

def _hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode(), bcrypt.gensalt(12)
    ).decode()


# ── ENDPOINTS ─────────────────────────────────────────────────

@router.get("", response_model=List[UserResponse])
def get_users(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_superadmin)
):
    return db.query(User).filter(
        User.role != "superadmin"
    ).order_by(User.full_name).all()


@router.post("", response_model=UserResponse)
def create_user(
    data:         UserCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_superadmin)
):
    if data.role not in ["manager", "staff"]:
        raise HTTPException(400, "Role must be manager or staff.")

    existing = db.query(User).filter(
        User.username == data.username
    ).first()
    if existing:
        raise HTTPException(
            400, f"Username '{data.username}' already exists."
        )

    user = User(
        full_name       = data.full_name.strip(),
        username        = data.username.strip(),
        hashed_password = _hash(data.password),
        role            = data.role,
        is_active       = True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id:      str,
    data:         UserUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_superadmin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found.")
    if user.role == "superadmin":
        raise HTTPException(403, "Cannot modify superadmin.")

    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.username is not None:
        # Check uniqueness
        existing = db.query(User).filter(
            User.username == data.username,
            User.id       != user_id
        ).first()
        if existing:
            raise HTTPException(
                400, f"Username '{data.username}' already taken."
            )
        user.username = data.username.strip()
    if data.password is not None and data.password.strip():
        user.hashed_password = _hash(data.password)
    if data.role is not None:
        if data.role not in ["manager", "staff"]:
            raise HTTPException(400, "Role must be manager or staff.")
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id:      str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_superadmin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found.")
    if user.role == "superadmin":
        raise HTTPException(403, "Cannot delete superadmin.")

    user.is_active = False
    db.commit()
    return {"message": f"User '{user.username}' deactivated."}