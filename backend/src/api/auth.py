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
    RoleChecker,
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

ENGINEER_ROLE_MAP = {
    "engineer": UserRole.l1,
    "l1": UserRole.l1,
    "l2": UserRole.l2,
    "support_lead": UserRole.support_lead,
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
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Optional[str] = "employee"
    department: Optional[str] = "general"

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_part(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name fields cannot be blank")
        if not re.match(r"^[a-zA-Z]+$", v.strip()):
            raise ValueError("First and Last Name can only contain English letters with no spaces or special characters")
        return v.strip()

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

        # Check first_name and last_name in password
        fn_clean = self.first_name.lower() if self.first_name else ""
        ln_clean = self.last_name.lower() if self.last_name else ""
        if fn_clean and fn_clean in pw_lower:
            raise ValueError("Password must not contain your first name")
        if ln_clean and ln_clean in pw_lower:
            raise ValueError("Password must not contain your last name")

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


class ProvisionEngineerRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Optional[str] = "l1"
    department: Optional[str] = "engineering"

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_part(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name fields cannot be blank")
        if not re.match(r"^[a-zA-Z]+$", v.strip()):
            raise ValueError("First and Last Name can only contain English letters with no spaces or special characters")
        return v.strip()

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if "@" not in clean or "." not in clean.split("@")[-1]:
            raise ValueError("Invalid email format")
        return clean

    @model_validator(mode="after")
    def validate_password_rules(self) -> "ProvisionEngineerRequest":
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

        fn_clean = self.first_name.lower() if self.first_name else ""
        ln_clean = self.last_name.lower() if self.last_name else ""
        if fn_clean and fn_clean in pw_lower:
            raise ValueError("Password must not contain engineer's first name")
        if ln_clean and ln_clean in pw_lower:
            raise ValueError("Password must not contain engineer's last name")

        email_clean = self.email.strip().lower() if self.email else ""
        if email_clean and email_clean in pw_lower:
            raise ValueError("Password must not contain engineer's email address")

        email_prefix = email_clean.split("@")[0] if "@" in email_clean else ""
        if len(email_prefix) >= 3 and email_prefix in pw_lower:
            raise ValueError("Password must not contain engineer's email username")

        if pw_lower in COMMON_PASSWORDS or any(cp == pw_lower for cp in COMMON_PASSWORDS):
            raise ValueError("Password must not use common passwords like Password123!")

        if re.search(r"(19\d\d|20\d\d)", password):
            raise ValueError("Password must not contain easily guessed information such as birthday or year")

        if any(term in pw_lower for term in EASILY_GUESSED_TERMS):
            raise ValueError("Password must not contain easily guessed information such as company or role names")

        dept_clean = (self.department or "").strip().lower()
        if len(dept_clean) >= 3 and dept_clean in pw_lower:
            raise ValueError("Password must not contain easily guessed information such as department name")

        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_new_password_rules(self) -> "ChangePasswordRequest":
        password = self.new_password
        if not password or not password.strip():
            raise ValueError("New password cannot be blank")
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

        if pw_lower in COMMON_PASSWORDS or any(cp == pw_lower for cp in COMMON_PASSWORDS):
            raise ValueError("Password must not use common passwords like Password123!")

        if re.search(r"(19\d\d|20\d\d)", password):
            raise ValueError("Password must not contain easily guessed information such as birthday or year")

        if any(term in pw_lower for term in EASILY_GUESSED_TERMS):
            raise ValueError("Password must not contain easily guessed information such as company or role names")

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

    full_name = f"{data.first_name.strip()} {data.last_name.strip()}"

    user = User(
        name=full_name,
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


@router.post("/provision-engineer")
async def provision_engineer(
    data: ProvisionEngineerRequest,
    current_admin: dict = Depends(RoleChecker(["admin"])),
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

    role_key = (data.role or "l1").strip().lower()
    if role_key not in ENGINEER_ROLE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid engineer role '{role_key}'. Must be one of: {list(ENGINEER_ROLE_MAP.keys())}",
        )
    role = ENGINEER_ROLE_MAP[role_key]
    department = (data.department or "engineering").strip()

    full_name = f"{data.first_name.strip()} {data.last_name.strip()}"

    user = User(
        name=full_name,
        email=email,
        hashed_password=get_password_hash(data.password),
        role=role,
        department=department,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)

    return {
        "status": "success",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": role_val,
            "department": user.department or "engineering",
        },
    }


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    email = current_user["email"].strip().lower()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found",
        )

    try:
        valid_password = verify_password(data.current_password, user.hashed_password)
    except (ValueError, UnknownHashError):
        valid_password = False

    if not valid_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if verify_password(data.new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be identical to current password",
        )

    # Validate that new password does not contain user's name parts or email
    name_parts = user.name.lower().split()
    for part in name_parts:
        if len(part) >= 3 and part in data.new_password.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"New password must not contain your name ({part})",
            )

    if user.email.lower() in data.new_password.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must not contain your email address",
        )

    user.hashed_password = get_password_hash(data.new_password)
    db.add(user)
    await db.commit()

    return {"status": "success", "message": "Password changed successfully"}


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"user": user}