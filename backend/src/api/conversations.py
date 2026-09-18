import logging
import uuid

from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from langchain_core.messages import HumanMessage, AIMessage

from src.auth.security import RoleChecker, get_current_user
from src.core.db import get_db
from src.core.llm import normalize_content
from src.core.observability import get_langchain_config
from src.services.retrieval_service import RetrievalService

from src.models.chat import (
    Conversation,
    ConversationOwner,
    ConversationStatus,
    Message,
    SenderType,
)
from src.models.user import User, UserRole
from src.models.ticket import TicketPriority

from src.workflow.graph import app as graph_app
from src.workflow.utils.history_utils import build_bounded_history
from src.workflow.constants import (
    CONFIRM_MARKER,
    CONFIRM_FINAL_MARKER,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _resolve_ticket_priority(
    priority_val: Any,
    default: TicketPriority = TicketPriority.MEDIUM,
) -> TicketPriority:
    if isinstance(priority_val, TicketPriority):
        return priority_val
    if not priority_val:
        return default
    try:
        return TicketPriority(str(priority_val).strip().upper())
    except (ValueError, KeyError):
        return default


class MessageCreate(BaseModel):
    content: str


async def _load_history(
    db: AsyncSession,
    conv_uuid: uuid.UUID,
) -> list:
    """
    Load previous USER/AI conversation messages for LangGraph context.

    History is bounded and summarized by build_bounded_history().
    SYSTEM messages such as engineer notes and conversation-closure
    messages are intentionally excluded from LLM context.
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv_uuid)
        .order_by(Message.created_at.asc())
    )

    res = await db.execute(stmt)

    raw = []

    for m in res.scalars().all():
        if m.sender_type == SenderType.USER and m.content:
            raw.append(HumanMessage(content=m.content))

        elif m.sender_type == SenderType.AI and m.content:
            raw.append(AIMessage(content=m.content))

    return await build_bounded_history(raw)


@router.get("")
async def list_conversations(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == user["username"])
    )

    account = result.scalar_one_or_none()

    if account is None:
        return []

    from src.models.ticket import Ticket

    stmt = (
        select(Conversation)
        .where(Conversation.user_id == account.id)
        .order_by(
            Conversation.updated_at.desc(),
            Conversation.created_at.desc(),
        )
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

        raw_title = (
            first_user_msg.strip().split("\n")[0]
            if first_user_msg
            else "New Support Request"
        )

        title = (
            raw_title[:45] + "..."
            if len(raw_title) > 45
            else raw_title
        )

        t_stmt = select(Ticket).where(
            Ticket.conversation_id == conv.id
        )

        t_res = await db.execute(t_stmt)
        ticket = t_res.scalar_one_or_none()

        items.append(
            {
                "id": str(conv.id),
                "title": title,
                "preview": (
                    last_msg[:60] + "..."
                    if len(last_msg) > 60
                    else (last_msg or "No messages")
                ),
                "owner_type": conv.owner_type.value,
                "status": conv.status.value,
                "ticket_status": (
                    ticket.status.value
                    if ticket
                    else None
                ),
                "created_at": (
                    conv.created_at.isoformat()
                    if conv.created_at
                    else None
                ),
                "updated_at": (
                    conv.updated_at.isoformat()
                    if conv.updated_at
                    else None
                ),
                "message_count": len(msgs),
            }
        )

    return items


@router.post("")
async def create_conversation(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == user["username"])
    )

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

    return {
        "id": str(new_conv.id),
        "status": new_conv.status,
    }


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation ID",
        )

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid
        )
    )

    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    # Authorize: user must be conversation owner or support staff
    user_res = await db.execute(
        select(User).where(User.email == user["username"])
    )

    current_user_obj = user_res.scalar_one_or_none()

    is_support = user.get("role") in {
        "engineer",
        "l1",
        "l2",
        "support_lead",
        "admin",
    }

    if not is_support and (
        current_user_obj is None
        or conversation.user_id != current_user_obj.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this conversation",
        )

    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conv_uuid)
        .order_by(Message.created_at.asc())
    )

    msg_res = await db.execute(msg_stmt)
    messages = msg_res.scalars().all()

    return [
        {
            "id": str(m.id),
            "sender_type": m.sender_type.value,
            "content": m.content,
            "created_at": (
                m.created_at.isoformat()
                if m.created_at
                else None
            ),
        }
        for m in messages
    ]


@router.post("/{conversation_id}/takeover")
async def takeover_conversation(
    conversation_id: str,
    user: dict = Depends(
        RoleChecker(
            [
                "engineer",
                "l1",
                "l2",
                "support_lead",
                "admin",
            ]
        )
    ),
    db: AsyncSession = Depends(get_db),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation ID",
        )

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid
        )
    )

    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    conversation.owner_type = ConversationOwner.HUMAN

    # Transition linked ticket to IN_PROGRESS
    from src.models.ticket import (
        Ticket,
        TicketStatus,
        TicketHistory,
        AuditEvent,
    )
    from src.core.logging import trace_id_ctx_var

    t_res = await db.execute(
        select(Ticket).where(
            Ticket.conversation_id == conv_uuid
        )
    )

    ticket = t_res.scalar_one_or_none()

    if ticket and ticket.status == TicketStatus.ESCALATED:
        ticket.status = TicketStatus.IN_PROGRESS

        db.add(ticket)

        history = TicketHistory(
            ticket_id=ticket.id,
            old_status=TicketStatus.ESCALATED,
            new_status=TicketStatus.IN_PROGRESS,
            changed_by=user.get(
                "username",
                "Engineer",
            ),
        )

        db.add(history)

        audit = AuditEvent(
            trace_id=trace_id_ctx_var.get()
            or str(uuid.uuid4()),
            action="TICKET_TAKEOVER",
            entity_type="Ticket",
            entity_id=str(ticket.id),
            actor=user.get(
                "username",
                "Engineer",
            ),
            details={
                "action": "human_takeover",
                "conversation_id": str(conv_uuid),
            },
        )

        db.add(audit)

    await db.commit()

    return {
        "status": "human_takeover"
    }


@router.post("/{conversation_id}/close")
async def close_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation ID",
        )

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid
        )
    )

    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    user_res = await db.execute(
        select(User).where(User.email == user["username"])
    )

    current_user_obj = user_res.scalar_one_or_none()

    is_support = user.get("role") in {
        "engineer",
        "l1",
        "l2",
        "support_lead",
        "admin",
    }

    if not is_support and (
        current_user_obj is None
        or conversation.user_id != current_user_obj.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to close this conversation",
        )

    conversation.status = ConversationStatus.CLOSED

    # Close or resolve linked ticket
    from src.models.ticket import (
        Ticket,
        TicketStatus,
        TicketHistory,
        AuditEvent,
    )
    from src.core.logging import trace_id_ctx_var

    t_res = await db.execute(
        select(Ticket).where(
            Ticket.conversation_id == conv_uuid
        )
    )

    ticket = t_res.scalar_one_or_none()

    if ticket and ticket.status not in (
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    ):
        old_stat = ticket.status

        ticket.status = (
            TicketStatus.RESOLVED
            if is_support
            else TicketStatus.CLOSED
        )

        db.add(ticket)

        history = TicketHistory(
            ticket_id=ticket.id,
            old_status=old_stat,
            new_status=ticket.status,
            changed_by=user.get(
                "username",
                "User",
            ),
        )

        db.add(history)

        audit = AuditEvent(
            trace_id=trace_id_ctx_var.get()
            or str(uuid.uuid4()),
            action="CONVERSATION_CLOSED",
            entity_type="Conversation",
            entity_id=str(conv_uuid),
            actor=user.get(
                "username",
                "User",
            ),
            details={
                "action": "close_conversation",
                "ticket_id": str(ticket.id),
            },
        )

        db.add(audit)

    close_msg = Message(
        conversation_id=conv_uuid,
        sender_type=SenderType.SYSTEM,
        content="This conversation has been ended.",
    )

    db.add(close_msg)

    await db.commit()

    return {
        "status": "CLOSED",
        "conversation_id": str(conv_uuid),
    }


@router.post("/{conversation_id}/messages")
async def add_message(
    conversation_id: str,
    message: MessageCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation ID",
        )

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid
        )
    )

    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    if conversation.status == ConversationStatus.CLOSED:
        raise HTTPException(
            status_code=400,
            detail="This conversation has ended and is closed.",
        )

    is_support = user.get("role") in {
        "engineer",
        "l1",
        "l2",
        "support_lead",
        "admin",
    }

    # 1. If support engineer sends a message,
    # record as SYSTEM message and bypass LangGraph
    if is_support:
        formatted_content = (
            message.content
            if message.content.startswith("[Engineer]")
            else f"[Engineer] {message.content}"
        )

        eng_msg = Message(
            conversation_id=conv_uuid,
            sender_type=SenderType.SYSTEM,
            content=formatted_content,
        )

        db.add(eng_msg)
        await db.commit()

        return {
            "messages": [
                {
                    "sender": "SYSTEM",
                    "content": formatted_content,
                }
            ],
            "status": "human_takeover",
        }

    # 2. If employee sends a message
    #
    # Load previous conversation history BEFORE adding the
    # current user message. This prevents the current message
    # from appearing twice in the LLM context.
    history_messages = await _load_history(
        db,
        conv_uuid,
    )

    # Explicit signal for confirmation replies.
    # This is intentionally checked from the persisted last AI
    # message rather than inferred from LangGraph message ordering.
    last_ai_stmt = (
        select(Message)
        .where(
            Message.conversation_id == conv_uuid,
            Message.sender_type == SenderType.AI,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )

    last_ai_res = await db.execute(last_ai_stmt)
    last_ai_msg = last_ai_res.scalar_one_or_none()

    awaiting_confirmation_reply = bool(
        last_ai_msg
        and (
            CONFIRM_MARKER in (last_ai_msg.content or "")
            or CONFIRM_FINAL_MARKER in (
                last_ai_msg.content or ""
            )
        )
    )

    user_msg = Message(
        conversation_id=conv_uuid,
        sender_type=SenderType.USER,
        content=message.content,
    )

    db.add(user_msg)
    await db.commit()

    # If a human took over, bypass AI completely
    if (
        conversation.owner_type == ConversationOwner.HUMAN
        and user.get("role") == "employee"
    ):
        return {
            "messages": [],
            "status": "human_takeover",
        }

    # 3. Invoke LangGraph for active AI conversations
    from src.models.ticket import (
        Ticket,
        TicketStatus,
        TicketHistory,
        AuditEvent,
    )
    from src.core.logging import trace_id_ctx_var

    # Check if a ticket already exists for this conversation to retain classification metadata across turns
    t_check_stmt = select(Ticket).where(Ticket.conversation_id == conv_uuid)
    t_check_res = await db.execute(t_check_stmt)
    existing_conv_ticket = t_check_res.scalar_one_or_none()

    prior_category = (existing_conv_ticket.category or "") if existing_conv_ticket else ""
    prior_priority = (
        (existing_conv_ticket.priority.value if hasattr(existing_conv_ticket.priority, "value") else str(existing_conv_ticket.priority))
        if (existing_conv_ticket and existing_conv_ticket.priority)
        else ""
    )
    prior_rationale = (existing_conv_ticket.priority_rationale or "") if existing_conv_ticket else ""

    workflow_status = (
        "human_takeover"
        if conversation.owner_type == ConversationOwner.HUMAN
        else conversation.status.value
    )

    initial_state = {
        "input": message.content,
        "sanitized_query": "",
        "search_query": "",
        "messages": history_messages,
        "evidence": [],
        "tool_history": [],
        "user_context": user,
        "status": workflow_status,
        "retrieval_score": 0.0,
        "needs_handoff": False,
        "needs_clarification": False,
        "escalate": False,
        "out_of_scope": False,
        "category": prior_category,
        "priority": prior_priority,
        "priority_rationale": prior_rationale,
        "awaiting_confirmation_reply": (
            awaiting_confirmation_reply
        ),
    }

    lf_config = get_langchain_config(
        conversation_id=str(conv_uuid),
        user_email=user.get("username"),
        extra_metadata={
            "department": user.get("department"),
            "role": user.get("role"),
            "owner_type": conversation.owner_type.value,
        },
    )

    history_len = len(initial_state["messages"]) 

    final_state = await graph_app.ainvoke(initial_state, config=lf_config)

    new_messages = final_state.get("messages", [])[history_len:]

    responses = []
    for msg in new_messages:
        if isinstance(msg, AIMessage) and msg.content:
            content = normalize_content(msg.content)
            ai_msg = Message(conversation_id=conv_uuid, sender_type=SenderType.AI, content=content)
            db.add(ai_msg)
            responses.append({"sender": "AI", "content": content})

    # 3b. Gibberish session termination — close conversation so subsequent
    #     messages don't re-trigger the same termination message endlessly.
    #     Detected by: out_of_scope=True, escalate=False, sanitized_query=""
    #     (the specific signature set by the >= 2 consecutive gibberish path).
    if (
        final_state.get("out_of_scope")
        and not final_state.get("escalate")
        and not (final_state.get("sanitized_query") or "").strip()
        and final_state.get("status") == "resolved"
    ):
        conversation.status = ConversationStatus.CLOSED
        db.add(conversation)

    # 4. Handle user confirmation of successful resolution
    #
    # This only fires when the confirmation classifier determines
    # that the user genuinely confirmed the issue is resolved.
    confirmation_decision = final_state.get(
        "confirmation_decision"
    )

    if confirmation_decision == "resolved":
        from src.models.ticket import (
            Ticket,
            TicketStatus,
            TicketHistory,
            AuditEvent,
        )
        from src.core.logging import trace_id_ctx_var

        conversation.status = ConversationStatus.CLOSED
        db.add(conversation)

        t_res = await db.execute(
            select(Ticket).where(
                Ticket.conversation_id == conv_uuid
            )
        )

        existing_ticket = t_res.scalar_one_or_none()

        if existing_ticket:
            if existing_ticket.status not in (
                TicketStatus.RESOLVED,
                TicketStatus.CLOSED,
            ):
                old = existing_ticket.status

                existing_ticket.status = TicketStatus.CLOSED

                db.add(existing_ticket)

                db.add(
                    TicketHistory(
                        ticket_id=existing_ticket.id,
                        old_status=old,
                        new_status=TicketStatus.CLOSED,
                        changed_by="user_confirmation",
                    )
                )

        else:
            cat = final_state.get("category") or "General Support"

            # IMPORTANT:
            # message.content is the current confirmation
            # ("yes", "yeah that fixed it", etc.).
            # The ticket must represent the original incident,
            # not the confirmation reply.
            original_issue = next(
                (
                    m.content
                    for m in history_messages
                    if isinstance(m, HumanMessage)
                    and m.content
                ),
                message.content,
            )

            title_snippet = (
                original_issue
                .strip()
                .split("\n")[0][:50]
            )

            ticket_title = f"[{cat}] {title_snippet}"
            ticket_description = original_issue

            new_ticket = Ticket(
                user_id=conversation.user_id,
                conversation_id=conv_uuid,
                title=ticket_title,
                description=ticket_description,
                category=cat,
                priority=_resolve_ticket_priority(
                    final_state.get("priority")
                ),
                priority_rationale=final_state.get(
                    "priority_rationale"
                ),
                status=TicketStatus.RESOLVED,
                department=user.get("department"),
            )

            try:
                new_ticket.embedding = (
                    RetrievalService.generate_ticket_embedding(
                        title=ticket_title,
                        description=ticket_description,
                        category=cat,
                    )
                )
            except Exception as e:
                logger.warning(
                    f"Failed to generate ticket embedding: {e}"
                )

            db.add(new_ticket)

            await db.flush()

            db.add(
                TicketHistory(
                    ticket_id=new_ticket.id,
                    old_status=None,
                    new_status=TicketStatus.RESOLVED,
                    changed_by="AI Workflow",
                )
            )

            db.add(
                AuditEvent(
                    trace_id=trace_id_ctx_var.get()
                    or str(uuid.uuid4()),
                    action="TICKET_AUTO_RESOLVED",
                    entity_type="Ticket",
                    entity_id=str(new_ticket.id),
                    actor="AI Workflow",
                    details={
                        "reason": "Resolved by AI workflow",
                        "conversation_id": str(conv_uuid),
                    },
                )
            )

    # 5. Handle escalation
    is_escalated = (
        final_state.get("status")
        in {
            "human_takeover",
            "escalated",
        }
        or final_state.get("escalate") is True
    )

    if is_escalated:
        from src.models.ticket import (
            Ticket,
            TicketStatus,
            TicketHistory,
            AuditEvent,
        )
        from src.core.logging import trace_id_ctx_var

        conversation.owner_type = ConversationOwner.HUMAN

        db.add(conversation)

        # Check if a ticket already exists for this conversation
        t_res = await db.execute(
            select(Ticket).where(
                Ticket.conversation_id == conv_uuid
            )
        )

        existing_ticket = t_res.scalar_one_or_none()

        active_ticket = existing_ticket
        if not existing_ticket:
            cat = final_state.get(
                "category",
                "General Support",
            ) or "General Support"

            # Preserve the original incident rather than using
            # the current confirmation/reply as ticket content.
            original_issue = next(
                (
                    m.content
                    for m in history_messages
                    if isinstance(m, HumanMessage)
                    and m.content
                ),
                message.content,
            )

            title_snippet = (
                original_issue
                .strip()
                .split("\n")[0][:50]
            )

            ticket_title = f"[{cat}] {title_snippet}"
            ticket_description = original_issue

            new_ticket = Ticket(
                user_id=conversation.user_id,
                conversation_id=conv_uuid,
                title=ticket_title,
                description=ticket_description,
                category=cat,
                priority=_resolve_ticket_priority(
                    final_state.get("priority")
                ),
                priority_rationale=final_state.get(
                    "priority_rationale"
                ),
                status=TicketStatus.ESCALATED,
                department=user.get("department"),
            )

            try:
                new_ticket.embedding = (
                    RetrievalService.generate_ticket_embedding(
                        title=ticket_title,
                        description=ticket_description,
                        category=cat,
                    )
                )
            except Exception as e:
                logger.warning(
                    f"Failed to generate ticket embedding: {e}"
                )

            db.add(new_ticket)
            await db.flush()
            active_ticket = new_ticket

            history = TicketHistory(
                ticket_id=new_ticket.id,
                old_status=None,
                new_status=TicketStatus.ESCALATED,
                changed_by="AI Workflow",
            )
            db.add(history)

            audit = AuditEvent(
                trace_id=trace_id_ctx_var.get()
                or str(uuid.uuid4()),
                action="TICKET_ESCALATED",
                entity_type="Ticket",
                entity_id=str(new_ticket.id),
                actor="AI Workflow",
                details={
                    "reason": "Escalated by AI workflow",
                    "conversation_id": str(conv_uuid),
                },
            )
            db.add(audit)
        else:
            if existing_ticket.status != TicketStatus.ESCALATED:
                old_st = existing_ticket.status
                existing_ticket.status = TicketStatus.ESCALATED
                db.add(existing_ticket)
                db.add(
                    TicketHistory(
                        ticket_id=existing_ticket.id,
                        old_status=old_st,
                        new_status=TicketStatus.ESCALATED,
                        changed_by="AI Workflow",
                    )
                )

        # Ticket Reference Transparency
        if active_ticket:
            ticket_ref_text = f"**Ticket Reference:** `#{str(active_ticket.id)[:8].upper()}`"
            if responses and responses[-1].get("sender") == "AI":
                responses[-1]["content"] = f"{responses[-1]['content'].strip()}\n\n{ticket_ref_text}"
                last_ai_msg_stmt = (
                    select(Message)
                    .where(
                        Message.conversation_id == conv_uuid,
                        Message.sender_type == SenderType.AI,
                    )
                    .order_by(Message.created_at.desc())
                    .limit(1)
                )
                last_ai_msg_res = await db.execute(last_ai_msg_stmt)
                last_ai_msg_rec = last_ai_msg_res.scalar_one_or_none()
                if last_ai_msg_rec:
                    last_ai_msg_rec.content = responses[-1]["content"]
                    db.add(last_ai_msg_rec)
            else:
                escalation_content = (
                    f"I have recorded your issue and created an escalated support ticket for an L1 Support Engineer.\n\n{ticket_ref_text}"
                )
                fallback_msg = Message(
                    conversation_id=conv_uuid,
                    sender_type=SenderType.AI,
                    content=escalation_content,
                )
                db.add(fallback_msg)
                responses.append({"sender": "AI", "content": escalation_content})

    # Persist newly classified ticket metadata in NEW status if not already created
    if not is_escalated and confirmation_decision != "resolved":
        t_exist_stmt = select(Ticket).where(Ticket.conversation_id == conv_uuid)
        t_exist_res = await db.execute(t_exist_stmt)
        if not t_exist_res.scalar_one_or_none():
            cat = final_state.get("category")
            if cat and cat != "general_support":
                original_issue = next(
                    (
                        m.content
                        for m in history_messages
                        if isinstance(m, HumanMessage)
                        and m.content
                    ),
                    message.content,
                )
                title_snippet = original_issue.strip().split("\n")[0][:50]
                new_ticket = Ticket(
                    user_id=conversation.user_id,
                    conversation_id=conv_uuid,
                    title=f"[{cat}] {title_snippet}",
                    description=original_issue,
                    category=cat,
                    priority=_resolve_ticket_priority(
                        final_state.get("priority")
                    ),
                    priority_rationale=final_state.get("priority_rationale"),
                    status=TicketStatus.NEW,
                    department=user.get("department"),
                )
                db.add(new_ticket)

    await db.commit()

    return {
        "messages": responses,
        "state": final_state,
    }