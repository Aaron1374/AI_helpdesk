from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.core.logging import TraceIdMiddleware
from src.core.db import init_db
from src.api.health import router as health_router
from src.api.auth import router as auth_router
from src.api.diagnostics import router as diagnostics_router
from src.api.conversations import router as conversations_router
from src.api.tickets import router as tickets_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they do not exist
    await init_db()
    yield

app = FastAPI(title="AI L1 IT Helpdesk API", lifespan=lifespan)

app.add_middleware(TraceIdMiddleware)
app.include_router(health_router, tags=["observability"])
app.include_router(auth_router)
app.include_router(diagnostics_router)
app.include_router(conversations_router)
app.include_router(tickets_router)

@app.get("/")
async def root():
    return {"message": "AI Helpdesk API is running"}
