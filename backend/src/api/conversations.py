from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from src.auth.security import RoleChecker, get_current_user
from src.core.db import get_db
from src.core.llm import normalize_content
from src.models.chat import Conversation, ConversationOwner, Message, SenderType
from src.models.user import User, UserRole
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from src.workflow.graph import app as graph_app

router = APIRouter(prefix="/conversations", tags=["conversations"])

class MessageCreate(BaseModel):
    content: str

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

@router.post("/{conversation_id}/takeover")
async def takeover_conversation(conversation_id: str, user: dict = Depends(RoleChecker(["engineer"])), db: AsyncSession = Depends(get_db)):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
        
    result = await db.execute(select(Conversation).where(Conversation.id == conv_uuid))
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    conversation.owner_type = ConversationOwner.HUMAN
    await db.commit()
    return {"status": "human_takeover"}

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

    user_msg = Message(conversation_id=conv_uuid, sender_type=SenderType.USER, content=message.content)
    db.add(user_msg)
    await db.commit()
    
    # If a human took over, bypass AI completely
    if conversation.owner_type == ConversationOwner.HUMAN and user.get("role") == "employee":
        # We don't invoke LangGraph for the employee anymore, we just wait for engineer to reply
        return {"messages": [], "status": "human_takeover"}

    # Invoke LangGraph
    workflow_status = "human_takeover" if conversation.owner_type == ConversationOwner.HUMAN else conversation.status.value
    initial_state = {"input": message.content, "messages": [], "evidence": [], "tool_history": [], "user_context": user, "status": workflow_status}
    final_state = await graph_app.ainvoke(initial_state)

    responses = []
    for msg in final_state.get("messages", []):
        if hasattr(msg, "content") and msg.content:
            content = normalize_content(msg.content)
            ai_msg = Message(conversation_id=conv_uuid, sender_type=SenderType.AI, content=content)
            db.add(ai_msg)
            responses.append({"sender": "AI", "content": content})
    
    if final_state.get("status") in {"human_takeover", "escalated"}:
        conversation.owner_type = ConversationOwner.HUMAN
        db.add(conversation)
        await db.flush()
        
    await db.commit()
    return {"messages": responses, "state": final_state}
