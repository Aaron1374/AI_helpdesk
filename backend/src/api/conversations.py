from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from src.auth.security import RoleChecker, get_current_user
from src.core.db import get_db
from src.core.llm import normalize_content
from src.models.chat import Conversation, ConversationOwner, ConversationStatus, Message, SenderType
from src.models.user import User, UserRole
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from src.workflow.graph import app as graph_app

router = APIRouter(prefix="/conversations", tags=["conversations"])

class MessageCreate(BaseModel):
    content: str

@router.get("")
async def list_conversations(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user["username"]))
    account = result.scalar_one_or_none()
    if account is None:
        return []

    from src.models.ticket import Ticket

    stmt = (
        select(Conversation)
        .where(Conversation.user_id == account.id)
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
    )
    conv_res = await db.execute(stmt)
    conversations = conv_res.scalars().all()

    items = []
    for conv in conversations:
        msg_stmt = (
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
        )
        msg_res = await db.execute(msg_stmt)
        msgs = msg_res.scalars().all()

        first_user_msg = ""
        last_msg = ""
        for m in msgs:
            if m.sender_type == SenderType.USER and not first_user_msg:
                first_user_msg = m.content
            if m.content:
                last_msg = m.content

        raw_title = first_user_msg.strip().split("\n")[0] if first_user_msg else "New Support Request"
        title = (raw_title[:45] + "...") if len(raw_title) > 45 else raw_title

        t_stmt = select(Ticket).where(Ticket.conversation_id == conv.id)
        t_res = await db.execute(t_stmt)
        ticket = t_res.scalar_one_or_none()

        items.append({
            "id": str(conv.id),
            "title": title,
            "preview": (last_msg[:60] + "...") if len(last_msg) > 60 else (last_msg or "No messages"),
            "owner_type": conv.owner_type.value,
            "status": conv.status.value,
            "ticket_status": ticket.status.value if ticket else None,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "message_count": len(msgs),
        })

    return items

@router.post("")
async def create_conversation(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user["username"]))
    account = result.scalar_one_or_none()
    if account is None:
        account = User(
            name=user["username"],
            email=user["username"],
            hashed_password="development-user",
            role=UserRole(user.get("role", "employee")),
        )
        db.add(account)
        await db.flush()

    new_conv = Conversation(user_id=account.id)
    db.add(new_conv)
    await db.commit()
    await db.refresh(new_conv)
    return {"id": str(new_conv.id), "status": new_conv.status}

@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    result = await db.execute(select(Conversation).where(Conversation.id == conv_uuid))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Authorize: user must be conversation owner or support staff
    user_res = await db.execute(select(User).where(User.email == user["username"]))
    current_user_obj = user_res.scalar_one_or_none()

    is_support = user.get("role") in {"engineer", "l1", "l2", "support_lead", "admin"}
    if not is_support and (current_user_obj is None or conversation.user_id != current_user_obj.id):
        raise HTTPException(status_code=403, detail="Not authorized to view this conversation")

    msg_stmt = select(Message).where(Message.conversation_id == conv_uuid).order_by(Message.created_at.asc())
    msg_res = await db.execute(msg_stmt)
    messages = msg_res.scalars().all()

    return [
        {
            "id": str(m.id),
            "sender_type": m.sender_type.value,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]

@router.post("/{conversation_id}/takeover")
async def takeover_conversation(conversation_id: str, user: dict = Depends(RoleChecker(["engineer", "l1", "l2", "support_lead", "admin"])), db: AsyncSession = Depends(get_db)):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
        
    result = await db.execute(select(Conversation).where(Conversation.id == conv_uuid))
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    conversation.owner_type = ConversationOwner.HUMAN

    # Transition linked ticket to IN_PROGRESS
    from src.models.ticket import Ticket, TicketStatus, TicketHistory, AuditEvent
    from src.core.logging import trace_id_ctx_var

    t_res = await db.execute(select(Ticket).where(Ticket.conversation_id == conv_uuid))
    ticket = t_res.scalar_one_or_none()
    if ticket and ticket.status == TicketStatus.ESCALATED:
        ticket.status = TicketStatus.IN_PROGRESS
        db.add(ticket)

        history = TicketHistory(
            ticket_id=ticket.id,
            old_status=TicketStatus.ESCALATED,
            new_status=TicketStatus.IN_PROGRESS,
            changed_by=user.get("username", "Engineer"),
        )
        db.add(history)

        audit = AuditEvent(
            trace_id=trace_id_ctx_var.get() or str(uuid.uuid4()),
            action="TICKET_TAKEOVER",
            entity_type="Ticket",
            entity_id=str(ticket.id),
            actor=user.get("username", "Engineer"),
            details={"action": "human_takeover", "conversation_id": str(conv_uuid)},
        )
        db.add(audit)

    await db.commit()
    return {"status": "human_takeover"}

@router.post("/{conversation_id}/close")
async def close_conversation(conversation_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    result = await db.execute(select(Conversation).where(Conversation.id == conv_uuid))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_res = await db.execute(select(User).where(User.email == user["username"]))
    current_user_obj = user_res.scalar_one_or_none()

    is_support = user.get("role") in {"engineer", "l1", "l2", "support_lead", "admin"}
    if not is_support and (current_user_obj is None or conversation.user_id != current_user_obj.id):
        raise HTTPException(status_code=403, detail="Not authorized to close this conversation")

    conversation.status = ConversationStatus.CLOSED

    # Close or resolve linked ticket
    from src.models.ticket import Ticket, TicketStatus, TicketHistory, AuditEvent
    from src.core.logging import trace_id_ctx_var

    t_res = await db.execute(select(Ticket).where(Ticket.conversation_id == conv_uuid))
    ticket = t_res.scalar_one_or_none()
    if ticket and ticket.status not in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        old_stat = ticket.status
        ticket.status = TicketStatus.RESOLVED if is_support else TicketStatus.CLOSED
        db.add(ticket)

        history = TicketHistory(
            ticket_id=ticket.id,
            old_status=old_stat,
            new_status=ticket.status,
            changed_by=user.get("username", "User"),
        )
        db.add(history)

        audit = AuditEvent(
            trace_id=trace_id_ctx_var.get() or str(uuid.uuid4()),
            action="CONVERSATION_CLOSED",
            entity_type="Conversation",
            entity_id=str(conv_uuid),
            actor=user.get("username", "User"),
            details={"action": "close_conversation", "ticket_id": str(ticket.id)},
        )
        db.add(audit)

    close_msg = Message(
        conversation_id=conv_uuid,
        sender_type=SenderType.SYSTEM,
        content="This conversation has been ended.",
    )
    db.add(close_msg)

    await db.commit()
    return {"status": "CLOSED", "conversation_id": str(conv_uuid)}

@router.post("/{conversation_id}/messages")
async def add_message(conversation_id: str, message: MessageCreate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
        
    result = await db.execute(select(Conversation).where(Conversation.id == conv_uuid))
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.status == ConversationStatus.CLOSED:
        raise HTTPException(status_code=400, detail="This conversation has ended and is closed.")

    is_support = user.get("role") in {"engineer", "l1", "l2", "support_lead", "admin"}

    # 1. If support engineer sends a message, record as SYSTEM message and bypass LangGraph
    if is_support:
        formatted_content = message.content if message.content.startswith("[Engineer]") else f"[Engineer] {message.content}"
        eng_msg = Message(conversation_id=conv_uuid, sender_type=SenderType.SYSTEM, content=formatted_content)
        db.add(eng_msg)
        await db.commit()
        return {"messages": [{"sender": "SYSTEM", "content": formatted_content}], "status": "human_takeover"}

    # 2. If employee sends a message
    user_msg = Message(conversation_id=conv_uuid, sender_type=SenderType.USER, content=message.content)
    db.add(user_msg)
    await db.commit()
    
    # If a human took over, bypass AI completely
    if conversation.owner_type == ConversationOwner.HUMAN and user.get("role") == "employee":
        return {"messages": [], "status": "human_takeover"}

    # 3. Invoke LangGraph for active AI conversations
    workflow_status = "human_takeover" if conversation.owner_type == ConversationOwner.HUMAN else conversation.status.value
    initial_state = {
            "input": message.content,
            "sanitized_query": "",
            "messages": [],
            "evidence": [],
            "tool_history": [],
            "user_context": user,
            "status": workflow_status,
            "retrieval_score": 0.0,
            "needs_handoff": False,
            "needs_clarification": False,
            "escalate": False,
            "category": "",
        }

    final_state = await graph_app.ainvoke(initial_state)

    responses = []
    for msg in final_state.get("messages", []):
        if hasattr(msg, "content") and msg.content:
            content = normalize_content(msg.content)
            ai_msg = Message(conversation_id=conv_uuid, sender_type=SenderType.AI, content=content)
            db.add(ai_msg)
            responses.append({"sender": "AI", "content": content})
    
    is_escalated = (
        final_state.get("status") in {"human_takeover", "escalated"}
        or final_state.get("escalate") is True
    )

    if is_escalated:
        from src.models.ticket import Ticket, TicketStatus, TicketHistory, AuditEvent
        from src.core.logging import trace_id_ctx_var

        conversation.owner_type = ConversationOwner.HUMAN
        db.add(conversation)

        # Check if a ticket already exists for this conversation
        t_res = await db.execute(select(Ticket).where(Ticket.conversation_id == conv_uuid))
        existing_ticket = t_res.scalar_one_or_none()

        if not existing_ticket:
            cat = final_state.get("category", "General Support")
            title_snippet = message.content.strip().split("\n")[0][:50]
            new_ticket = Ticket(
                user_id=conversation.user_id,
                conversation_id=conv_uuid,
                title=f"[{cat}] {title_snippet}",
                description=message.content,
                category=cat,
                status=TicketStatus.ESCALATED,
                department=user.get("department"),
            )
            db.add(new_ticket)
            await db.flush()

            history = TicketHistory(
                ticket_id=new_ticket.id,
                old_status=None,
                new_status=TicketStatus.ESCALATED,
                changed_by="AI Workflow",
            )
            db.add(history)

            audit = AuditEvent(
                trace_id=trace_id_ctx_var.get() or str(uuid.uuid4()),
                action="TICKET_ESCALATED",
                entity_type="Ticket",
                entity_id=str(new_ticket.id),
                actor="AI Workflow",
                details={"reason": "Escalated by AI workflow", "conversation_id": str(conv_uuid)},
            )
            db.add(audit)
        
    await db.commit()
    return {"messages": responses, "state": final_state}
