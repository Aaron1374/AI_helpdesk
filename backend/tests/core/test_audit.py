import pytest
from backend.src.services.ticket_service import TicketService
from backend.src.models.ticket import Ticket, TicketStatus
from backend.src.core.logging import trace_id_ctx_var
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_audit_events_capture_trace_id():
    # Set context var manually to simulate middleware
    test_trace_id = "test-trace-12345"
    token = trace_id_ctx_var.set(test_trace_id)
    
    mock_db = AsyncMock()
    
    ticket = Ticket(
        id="00000000-0000-0000-0000-000000000001",
        status=TicketStatus.NEW
    )
    
    try:
        # Action that creates an audit event
        await TicketService.update_status(mock_db, ticket, TicketStatus.TRIAGED)
        
        # Verify db.add was called for TicketHistory and AuditEvent
        assert mock_db.add.call_count == 2
        
        # Check that the AuditEvent captured the trace_id
        audit_event = mock_db.add.call_args_list[1][0][0]
        assert audit_event.__tablename__ == "audit_events"
        assert audit_event.trace_id == test_trace_id
        assert audit_event.action == "TICKET_STATUS_CHANGED"
        
    finally:
        trace_id_ctx_var.reset(token)
