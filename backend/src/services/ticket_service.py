from backend.src.models.ticket import Ticket, TicketStatus, TicketHistory, AuditEvent
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from backend.src.core.logging import trace_id_ctx_var

class TicketService:
    VALID_TRANSITIONS = {
        TicketStatus.NEW: {TicketStatus.TRIAGED, TicketStatus.ESCALATED},
        TicketStatus.TRIAGED: {TicketStatus.IN_PROGRESS, TicketStatus.ESCALATED},
        TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED, TicketStatus.ESCALATED},
        TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.ESCALATED},
        TicketStatus.CLOSED: set(),
        TicketStatus.ESCALATED: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED}
    }

    @staticmethod
    async def update_status(db: AsyncSession, ticket: Ticket, new_status: TicketStatus, changed_by=None):
        if new_status not in TicketService.VALID_TRANSITIONS.get(ticket.status, set()):
            raise HTTPException(status_code=400, detail=f"Invalid transition from {ticket.status} to {new_status}")
            
        old_status = ticket.status
        ticket.status = new_status
        
        history = TicketHistory(
            ticket_id=ticket.id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by
        )
        db.add(history)
        
        audit = AuditEvent(
            trace_id=trace_id_ctx_var.get(),
            action="TICKET_STATUS_CHANGED",
            entity_type="Ticket",
            entity_id=str(ticket.id),
            actor=str(changed_by) if changed_by else "system",
            details={"old_status": old_status.value, "new_status": new_status.value}
        )
        db.add(audit)
        
        await db.commit()
        return ticket
