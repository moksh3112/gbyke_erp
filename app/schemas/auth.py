from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    user_id: str

class UserCreate(BaseModel):
    full_name: str
    username: str
    password: str
    role: str = "user"

class UserResponse(BaseModel):
    id: str
    full_name: str
    username: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True