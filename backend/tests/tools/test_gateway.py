import pytest
from fastapi import HTTPException
from src.tools.gateway import ToolGateway

def test_tool_gateway_rejects_unauthorized():
    gateway = ToolGateway({"vpn_check"})
    
    # Allowed
    res = gateway.execute({"username": "test"}, "vpn_check", target_id="123")
    assert res["status"] == "executed"

    # Rejected
    with pytest.raises(HTTPException) as exc:
        gateway.execute({"username": "test"}, "dangerous_tool")
    
    assert exc.value.status_code == 403
    assert "Unauthorized" in exc.value.detail
