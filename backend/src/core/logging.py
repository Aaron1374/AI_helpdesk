import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from contextvars import ContextVar

trace_id_ctx_var: ContextVar[str] = ContextVar("trace_id", default="")

logger = logging.getLogger("ai_helpdesk")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [trace_id=%(trace_id)s] - %(message)s'
)

class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_ctx_var.get()
        return True

handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addFilter(TraceIdFilter())

class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        token = trace_id_ctx_var.set(trace_id)
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            trace_id_ctx_var.reset(token)
