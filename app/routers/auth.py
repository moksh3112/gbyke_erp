from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import verify_password, create_access_token, hash_password
from app.core.dependencies import get_current_user, require_superadmin
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserResponse
from typing import List

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── LOGIN ─────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account has been disabled. Contact admin."
        )

    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password."
        )

    token = create_access_token(data={
        "sub": user.id,
        "role": user.role,
        "username": user.username
    })

    return TokenResponse(
        access_token=token,
        role=user.role,
        full_name=user.full_name,
        user_id=user.id
    )


# ── GET CURRENT USER INFO ─────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ── CREATE USER (superadmin only) ─────────────────────────────

@router.post("/users", response_model=UserResponse)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_superadmin)
):
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{data.username}' is already taken."
        )

    if data.role not in ["superadmin", "manager", "staff"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'superadmin', 'manager', or 'staff'."
        )

    new_user = User(
        full_name=data.full_name,
        username=data.username,
        hashed_password=hash_password(data.password),
        role=data.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ── LIST ALL USERS (superadmin only) ──────────────────────────

@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_superadmin)
):
    return db.query(User).all()


# ── DISABLE / ENABLE USER (superadmin only) ───────────────────

@router.patch("/users/{user_id}/toggle")
def toggle_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_superadmin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot disable your own account."
        )

    user.is_active = not user.is_active
    db.commit()
    return {
        "message": f"User '{user.username}' {'enabled' if user.is_active else 'disabled'}.",
        "is_active": user.is_active
    }