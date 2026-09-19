from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, field_validator
from passlib.exc import UnknownHashError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from src.core.db import get_db
from src.models.user import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])

ROLE_MAP = {
    "employee": UserRole.employee,
    "engineer": UserRole.l1,
    "l1": UserRole.l1,
    "l2": UserRole.l2,
    "support_lead": UserRole.support_lead,
    "admin": UserRole.admin,
}


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Optional[str] = "employee"
    department: Optional[str] = "general"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Name cannot be empty")
        return clean

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if "@" not in clean or "." not in clean.split("@")[-1]:
            raise ValueError("Invalid email format")
        return clean



@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    email = form_data.username.strip().lower()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        valid_password = verify_password(form_data.password, user.hashed_password)
    except (ValueError, UnknownHashError):
        valid_password = False

    if not valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    token = create_access_token(
        {
            "sub": user.email,
            "user_id": str(user.id),
            "role": role_val,
            "department": user.department or "general",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": role_val,
            "department": user.department or "general",
        },
    }


@router.post("/signup")
async def signup(
    data: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    email = data.email.strip().lower()

    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    role_key = (data.role or "employee").strip().lower()
    role = ROLE_MAP.get(role_key, UserRole.employee)
    department = (data.department or "general").strip()

    user = User(
        name=data.name.strip(),
        email=email,
        hashed_password=get_password_hash(data.password),
        role=role,
        department=department,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    token = create_access_token(
        {
            "sub": user.email,
            "user_id": str(user.id),
            "role": role_val,
            "department": user.department or "general",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": role_val,
            "department": user.department or "general",
        },
    }


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"user": user}