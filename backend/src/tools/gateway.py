from fastapi import HTTPException
import logging

logger = logging.getLogger("ai_helpdesk.tools.gateway")

class ToolGateway:
    def __init__(self, allowed_tools: set):
        self.allowed_tools = allowed_tools

    def execute(self, user_context: dict, tool_name: str, **kwargs):
        if tool_name not in self.allowed_tools:
            logger.warning(f"Unauthorized tool call attempted: {tool_name} by {user_context.get('username')}")
            raise HTTPException(status_code=403, detail="Unauthorized tool call")
            
        # Dispatch to mock diagnostic endpoints or internal services
        return {"status": "executed", "tool": tool_name, "mocked": True, "target": kwargs.get("target_id")}

