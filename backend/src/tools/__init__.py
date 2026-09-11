from src.tools.gateway import ToolGateway

# Singleton ToolGateway instance with the only two allowed mock tools.
tool_gateway = ToolGateway(allowed_tools={"vpn_check", "device_check"})
