import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from sqlalchemy import select

from src.auth.security import (
    create_access_token,
    get_password_hash,
    verify_password,
    RoleChecker,
    get_current_user,
)
from src.models.user import User, UserRole
from src.api.auth import login, signup, get_me, SignupRequest


def test_password_hashing():
    raw = "super-secret-password-123"
    hashed = get_password_hash(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_jwt_token_roundtrip():
    data = {
        "sub": "test@example.com",
        "user_id": str(uuid.uuid4()),
        "role": "employee",
        "department": "engineering",
    }
    token = create_access_token(data)
    assert isinstance(token, str)
    assert len(token) > 20


def test_role_checker():
    checker = RoleChecker(["employee"])
    allowed_user = {"username": "emp@example.com", "role": "employee"}
    assert checker(allowed_user) == allowed_user

    denied_user = {"username": "admin@example.com", "role": "admin"}
    with pytest.raises(HTTPException) as exc:
        checker(denied_user)
    assert exc.value.status_code == 403

    # Engineer / l1 alias support
    engineer_checker = RoleChecker(["engineer"])
    l1_user = {"username": "l1@example.com", "role": "l1"}
    assert engineer_checker(l1_user) == l1_user


@pytest.mark.asyncio
async def test_get_current_user_from_db():
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        name="Test User",
        email="test@example.com",
        hashed_password="hashed_pw",
        role=UserRole.employee,
        department="sales",
    )

    token = create_access_token({"sub": "test@example.com", "role": "employee"})

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    current = await get_current_user(token=token, db=mock_db)
    assert current["id"] == str(user_id)
    assert current["email"] == "test@example.com"
    assert current["name"] == "Test User"
    assert current["role"] == "employee"
    assert current["department"] == "sales"


@pytest.mark.asyncio
async def test_login_invalid_credentials():
    form_data = MagicMock()
    form_data.username = "unknown@example.com"
    form_data.password = "wrong-pass"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc:
        await login(form_data=form_data, db=mock_db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_valid_credentials():
    raw_pw = "correct-password"
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        name="Valid User",
        email="valid@example.com",
        hashed_password=get_password_hash(raw_pw),
        role=UserRole.l1,
        department="engineering",
    )

    form_data = MagicMock()
    form_data.username = "valid@example.com"
    form_data.password = raw_pw

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    res = await login(form_data=form_data, db=mock_db)
    assert "access_token" in res
    assert res["token_type"] == "bearer"
    assert res["user"]["email"] == "valid@example.com"
    assert res["user"]["role"] == "l1"
    assert res["user"]["department"] == "engineering"


@pytest.mark.asyncio
async def test_signup_creates_new_user():
    req = SignupRequest(
        name="New Employee",
        email="new@example.com",
        password="securepassword123",
        role="employee",
        department="HR",
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    async def fake_refresh(instance):
        instance.id = uuid.uuid4()

    mock_db.refresh.side_effect = fake_refresh

    res = await signup(data=req, db=mock_db)
    assert "access_token" in res
    assert res["user"]["email"] == "new@example.com"
    assert res["user"]["name"] == "New Employee"
    assert res["user"]["role"] == "employee"
    assert res["user"]["department"] == "HR"
    assert mock_db.add.called
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_signup_conflict_existing_email():
    req = SignupRequest(
        name="Duplicate User",
        email="existing@example.com",
        password="securepassword123",
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc:
        await signup(data=req, db=mock_db)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_signup_rejects_privileged_roles():
    for privileged_role in ["engineer", "admin", "l1"]:
        req = SignupRequest(
            name="Hacker",
            email=f"{privileged_role}@example.com",
            password="securepassword123",
            role=privileged_role,
        )
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc:
            await signup(data=req, db=mock_db)
        assert exc.value.status_code == 400
        assert "restricted to employee accounts" in exc.value.detail


@pytest.mark.asyncio
async def test_get_me_endpoint():
    user = {
        "id": "1234",
        "username": "user@example.com",
        "email": "user@example.com",
        "name": "User",
        "role": "employee",
        "department": "IT",
    }
    res = await get_me(user=user)
    assert res["user"] == user
