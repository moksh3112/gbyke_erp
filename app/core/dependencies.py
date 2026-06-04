# app/core/dependencies.py
# FIX: removed duplicate require_superadmin definition (was defined twice)

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import decode_access_token
from app.models import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again."
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token structure."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account disabled."
        )
    return user


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """Only the owner — full access including financials and account management."""
    if current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required."
        )
    return current_user


def require_manager_or_above(current_user: User = Depends(get_current_user)) -> User:
    """Manager and Super Admin — all operations except financials."""
    if current_user.role not in ["superadmin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required."
        )
    return current_user


def require_any_role(current_user: User = Depends(get_current_user)) -> User:
    """All logged-in users — view stock, mark consumed/defective, update PDI."""
    return current_user


def is_superadmin(user: User) -> bool:
    return user.role == "superadmin"

def can_see_financials(user: User) -> bool:
    return user.role == "superadmin"

def can_manage_accounts(user: User) -> bool:
    return user.role == "superadmin"