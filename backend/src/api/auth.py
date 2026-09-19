import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from passlib.exc import UnknownHashError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)
from src.core.db import get_db
from src.models.user import User, UserRole

class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str
    department: str

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    email = form_data.username.strip().lower()
    dev_email = os.getenv("DEV_USER_EMAIL", "employee@example.com").strip().lower()
    dev_password = os.getenv("DEV_USER_PASSWORD", "dev-password")
    dev_role = os.getenv("DEV_USER_ROLE", "employee")

    DEV_ACCOUNTS = {
        dev_email: {
            "password": dev_password,
            "role": UserRole(dev_role),
            "name": "Development Employee",
        },
        "engineer@example.com": {
            "password": "dev-password11",
            "role": UserRole.l1,
            "name": "L1 Support Engineer",
        },
        "l1@example.com": {
            "password": "dev-password",
            "role": UserRole.l1,
            "name": "L1 Support Engineer",
        },
        "admin@example.com": {
            "password": "dev-password",
            "role": UserRole.admin,
            "name": "System Admin",
        },
    }

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None and email in DEV_ACCOUNTS and form_data.password == DEV_ACCOUNTS[email]["password"]:
        account_info = DEV_ACCOUNTS[email]
        user = User(
            name=account_info["name"],
            email=email,
            hashed_password=get_password_hash(account_info["password"]),
            role=account_info["role"],
        )
        db.add(user)
        await db.flush()

    try:
        valid_password = user is not None and verify_password(
            form_data.password, user.hashed_password
        )
    except (ValueError, UnknownHashError):
        valid_password = False

    if (
        user is not None
        and email in DEV_ACCOUNTS
        and form_data.password == DEV_ACCOUNTS[email]["password"]
        and not valid_password
    ):
        user.hashed_password = get_password_hash(DEV_ACCOUNTS[email]["password"])
        valid_password = True

    if user is None or not valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        {"sub": user.email, "role": user.role.value},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    await db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"email": user.email, "role": user.role.value},
    }
    
@router.post("/signup")
async def signup(
    data: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    email = data.email.strip().lower()

    allowed_roles = {
        "employee": UserRole.employee,
        "engineer": UserRole.l1,
        "admin": UserRole.admin,
    }

    role = allowed_roles.get(data.role.strip().lower())

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    result = await db.execute(
        select(User).where(User.email == email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        name=data.name.strip(),
        email=email,
        hashed_password=get_password_hash(data.password),
        role=role,
        department=data.department.strip(),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(
        {
            "sub": user.email,
            "role": user.role.value,
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "role": user.role.value,
        },
    }