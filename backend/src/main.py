from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from contextlib import asynccontextmanager

from src.core.logging import TraceIdMiddleware
from src.core.observability import flush
from src.core.db import AsyncSessionLocal
from src.core.seed import seed_default_users

from src.api.health import router as health_router
from src.api.auth import router as auth_router
from src.api.diagnostics import router as diagnostics_router
from src.api.conversations import router as conversations_router
from src.api.tickets import router as tickets_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as session:
        await seed_default_users(session)
    yield
    flush()


app = FastAPI(
    title="AI L1 IT Helpdesk API",
    lifespan=lifespan,
)

app.add_middleware(TraceIdMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = []
    for err in errors:
        loc = " -> ".join(str(l) for l in err.get("loc", []) if l != "body")
        msg = err.get("msg", "Invalid value")
        if isinstance(msg, str) and msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        messages.append(f"{loc}: {msg}" if loc else str(msg))
    detail_msg = ", ".join(messages) if messages else "Validation failed"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": detail_msg}),
    )



app.include_router(health_router, tags=["observability"])
app.include_router(auth_router)
app.include_router(diagnostics_router)
app.include_router(conversations_router)
app.include_router(tickets_router)


@app.get("/")
async def root():
    return {"message": "AI Helpdesk API is running"}