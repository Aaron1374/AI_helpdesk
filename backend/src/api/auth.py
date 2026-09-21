import re
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, field_validator, model_validator
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

COMMON_PASSWORDS = {
    "password", "password123", "password123!", "password1!",
    "pass1234!", "12345678", "123456789", "qwertyuiop",
    "admin123!", "welcome123!", "letmein123!", "p@ssword123!",
    "iloveyou123!", "changeit123!", "password@123", "admin@123",
}

EASILY_GUESSED_TERMS = {
    "company", "helpdesk", "adrian", "employee", "admin",
    "support", "enterprise", "corporate",
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
        if not v or not v.strip():
            raise ValueError("Name cannot be blank")
        if not re.match(r"^[a-zA-Z]+$", v):
            raise ValueError("Name can only contain English letters with no spaces or special characters")
        return v

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if "@" not in clean or "." not in clean.split("@")[-1]:
            raise ValueError("Invalid email format")
        return clean

    @model_validator(mode="after")
    def validate_password_rules(self) -> "SignupRequest":
        password = self.password
        if not password or not password.strip():
            raise ValueError("Password cannot be blank")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must include at least 1 uppercase letter")
        if not re.search(r"[a-z]", password):
            raise ValueError("Password must include at least 1 lowercase letter")
        if not re.search(r"[0-9]", password):
            raise ValueError("Password must include at least 1 number")
        if not re.search(r"[!@#$%^&*]", password):
            raise ValueError("Password must include at least 1 special character (! @ # $ % ^ & *)")

        pw_lower = password.lower()

        # Check username / name in password
        name_clean = self.name.strip().lower() if self.name else ""
        if name_clean and name_clean in pw_lower:
            raise ValueError("Password must not contain your name")

        # Check email in password
        email_clean = self.email.strip().lower() if self.email else ""
        if email_clean and email_clean in pw_lower:
            raise ValueError("Password must not contain your email address")

        email_prefix = email_clean.split("@")[0] if "@" in email_clean else ""
        if len(email_prefix) >= 3 and email_prefix in pw_lower:
            raise ValueError("Password must not contain your email username")

        # Check common passwords
        if pw_lower in COMMON_PASSWORDS or any(cp == pw_lower for cp in COMMON_PASSWORDS):
            raise ValueError("Password must not use common passwords like Password123!")

        # Check easily guessed information: birthday / year patterns (e.g. 19xx, 20xx)
        if re.search(r"(19\d\d|20\d\d)", password):
            raise ValueError("Password must not contain easily guessed information such as birthday or year")

        # Check company name / workplace terms / department
        if any(term in pw_lower for term in EASILY_GUESSED_TERMS):
            raise ValueError("Password must not contain easily guessed information such as company or role names")

        dept_clean = (self.department or "").strip().lower()
        if len(dept_clean) >= 3 and dept_clean in pw_lower:
            raise ValueError("Password must not contain easily guessed information such as department name")

        return self



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
    if role_key != "employee":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public signup is restricted to employee accounts only. Engineer and admin accounts must be provisioned by an administrator.",
        )
    role = UserRole.employee
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