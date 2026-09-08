import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.core.db import Base
import enum

from pgvector.sqlalchemy import Vector

class TicketStatus(str, enum.Enum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    ESCALATED = "ESCALATED"

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    status = Column(Enum(TicketStatus), default=TicketStatus.NEW, nullable=False)
    category = Column(String, nullable=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    department = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TicketHistory(Base):
    __tablename__ = "ticket_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False)
    old_status = Column(Enum(TicketStatus), nullable=True)
    new_status = Column(Enum(TicketStatus), nullable=False)
    changed_by = Column(String, nullable=True) # None means system/AI
    changed_at = Column(DateTime, default=datetime.utcnow)

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
