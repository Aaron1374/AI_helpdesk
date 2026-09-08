from fastapi import APIRouter, Depends
from src.auth.security import RoleChecker

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"], dependencies=[Depends(RoleChecker(["employee", "l1", "l2"]))])

@router.post("/vpn")
async def check_vpn(target_id: str):
    return {"status": "online", "mocked": True}

@router.post("/account")
async def check_account(target_id: str):
    return {"status": "active", "mocked": True}

@router.post("/device")
async def check_device(target_id: str):
    return {"status": "compliant", "mocked": True}
