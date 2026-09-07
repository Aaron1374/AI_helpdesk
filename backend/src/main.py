from fastapi import FastAPI
from backend.src.core.logging import TraceIdMiddleware
from backend.src.api.health import router as health_router
from backend.src.api.diagnostics import router as diagnostics_router
from backend.src.api.conversations import router as conversations_router
from backend.src.api.tickets import router as tickets_router

app = FastAPI(title="AI L1 IT Helpdesk API")

app.add_middleware(TraceIdMiddleware)

app.include_router(health_router, tags=["observability"])
app.include_router(diagnostics_router)
app.include_router(conversations_router)
app.include_router(tickets_router)

@app.get("/")
async def root():
    return {"message": "AI Helpdesk API is running"}
