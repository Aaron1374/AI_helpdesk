from fastapi import APIRouter
from sqlalchemy import text
from backend.src.core.db import AsyncSessionLocal

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.get("/ready")
async def ready_check():
    # Verify DB connection
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
        
    return {"status": "ready" if db_status == "ok" else "not_ready", "db": db_status}
