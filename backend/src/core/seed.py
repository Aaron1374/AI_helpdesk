import logging
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.security import get_password_hash, verify_password
from src.models.user import User, UserRole

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNTS = [
    {
        "email": os.getenv("DEV_USER_EMAIL", "employee@example.com").strip().lower(),
        "name": "Development Employee",
        "role": UserRole.employee,
        "department": "engineering",
        "password": os.getenv("DEV_USER_PASSWORD", "dev-password"),
    },
    {
        "email": "engineer@example.com",
        "name": "L1 Support Engineer",
        "role": UserRole.l1,
        "department": "engineering",
        "password": "dev-password",
    },
    {
        "email": "l1@example.com",
        "name": "L1 Support Engineer",
        "role": UserRole.l1,
        "department": "engineering",
        "password": "dev-password",
    },
    {
        "email": "admin@example.com",
        "name": "System Admin",
        "role": UserRole.admin,
        "department": "IT",
        "password": "dev-password",
    },
]


async def seed_default_users(db: AsyncSession) -> None:
    """
    Idempotent seeder: Ensures standard development and operational accounts
    exist in the database with valid hashed passwords, correct roles, and departments.
    """
    try:
        for acc in DEFAULT_ACCOUNTS:
            email = acc["email"].strip().lower()
            res = await db.execute(select(User).where(User.email == email))
            existing = res.scalar_one_or_none()

            if existing is None:
                new_user = User(
                    name=acc["name"],
                    email=email,
                    hashed_password=get_password_hash(acc["password"]),
                    role=acc["role"],
                    department=acc["department"],
                )
                db.add(new_user)
                logger.info("Seeded default user: %s (%s)", email, acc["role"].value)
            else:
                updated = False
                if not verify_password(acc["password"], existing.hashed_password):
                    existing.hashed_password = get_password_hash(acc["password"])
                    updated = True
                if not existing.department or existing.department != acc["department"]:
                    existing.department = acc["department"]
                    updated = True
                if existing.role != acc["role"]:
                    existing.role = acc["role"]
                    updated = True
                if updated:
                    db.add(existing)
                    logger.info("Updated default user credentials: %s", email)

        await db.commit()
    except Exception as e:
        logger.warning("Error seeding default users: %s", e)
        await db.rollback()
