from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from backend.src.auth.security import RoleChecker, get_current_user
from backend.src.core.db import get_db
from backend.src.models.chat import Conversation, Message, SenderType
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from backend.src.workflow.graph import app as graph_app

router = APIRouter(prefix="/conversations", tags=["conversations"])

class MessageCreate(BaseModel):
    content: str

@router.post("")
async def create_conversation(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Create conversation mapped to user
    user_id = uuid.uuid4() 
    new_conv = Conversation(user_id=user_id)
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
        
    conversation.status = "human_takeover"
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
    if conversation.status == "human_takeover" and user.get("role") == "employee":
        # We don't invoke LangGraph for the employee anymore, we just wait for engineer to reply
        return {"messages": [], "status": "human_takeover"}

    # Invoke LangGraph
    initial_state = {"input": message.content, "messages": [], "evidence": [], "tool_history": [], "user_context": user, "status": conversation.status}
    final_state = await graph_app.ainvoke(initial_state)

    responses = []
    for msg in final_state.get("messages", []):
        if hasattr(msg, "content") and msg.content:
            ai_msg = Message(conversation_id=conv_uuid, sender_type=SenderType.AI, content=msg.content)
            db.add(ai_msg)
            responses.append({"sender": "AI", "content": msg.content})
    
    if final_state.get("status") == "human_takeover" or final_state.get("status") == "escalated":
        conversation.status = "human_takeover"
        
    await db.commit()
    return {"messages": responses, "state": final_state}
