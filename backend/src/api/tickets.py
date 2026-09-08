from fastapi import APIRouter, Depends, HTTPException
from src.auth.security import RoleChecker, get_current_user
from src.core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.ticket import Ticket, TicketStatus
from src.services.ticket_service import TicketService
import uuid

router = APIRouter(prefix="/tickets", tags=["tickets"])

SUPPORT_ROLES = ["engineer", "l1", "l2", "support_lead", "admin"]

@router.get("")
async def get_tickets(user: dict = Depends(RoleChecker(SUPPORT_ROLES)), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ticket))
    tickets = result.scalars().all()
    return [{"id": str(t.id), "title": t.title, "status": t.status, "conversation_id": str(t.conversation_id) if t.conversation_id else None} for t in tickets]

@router.post("/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, user: dict = Depends(RoleChecker(SUPPORT_ROLES)), db: AsyncSession = Depends(get_db)):
    try:
        t_uuid = uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket ID")
        
    result = await db.execute(select(Ticket).where(Ticket.id == t_uuid))
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    await TicketService.update_status(db, ticket, TicketStatus.RESOLVED, changed_by=user.get("username"))
    return {"status": "success", "ticket_status": TicketStatus.RESOLVED}

@router.post("/{ticket_id}/confirm-resolution")
async def confirm_resolution(ticket_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        t_uuid = uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket ID")
        
    result = await db.execute(select(Ticket).where(Ticket.id == t_uuid))
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    if ticket.status != TicketStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="Can only confirm resolved tickets")
        
    await TicketService.update_status(db, ticket, TicketStatus.CLOSED, changed_by=user.get("username"))
    return {"status": "success"}

from src.services.retrieval_service import RetrievalService

@router.get("/{ticket_id}/similar")
async def get_similar_tickets(ticket_id: str, user: dict = Depends(RoleChecker(SUPPORT_ROLES)), db: AsyncSession = Depends(get_db)):
    try:
        t_uuid = uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket ID")
        
    result = await db.execute(select(Ticket).where(Ticket.id == t_uuid))
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    similar_docs = await RetrievalService.get_similar_documents(db, ticket.description, user.get("department"))
    
    # Filter out the current ticket if it appears in the results
    similar_incidents = [doc for doc in similar_docs if doc["type"] == "ticket" and doc["title"] != ticket.title]
    return similar_incidents
