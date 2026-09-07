import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.src.core.db import Base
import enum

class ConversationOwner(str, enum.Enum):
    AI = "AI"
    HUMAN = "HUMAN"

class ConversationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    owner_type = Column(Enum(ConversationOwner), default=ConversationOwner.AI, nullable=False)
    status = Column(Enum(ConversationStatus), default=ConversationStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="conversation")

class SenderType(str, enum.Enum):
    USER = "USER"
    AI = "AI"
    SYSTEM = "SYSTEM"

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    sender_type = Column(Enum(SenderType), nullable=False)
    content = Column(String, nullable=False)
    trace_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
