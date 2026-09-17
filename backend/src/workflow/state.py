from typing import TypedDict, List, Annotated, Dict, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    input: str
    sanitized_query: str
    needs_clarification: bool
    escalate: bool
    needs_handoff: bool
    out_of_scope: bool
    retrieval_score: float
    category: str
    priority: str
    priority_rationale: str
    evidence: List[dict]
    tool_history: List[str]
    status: str
    user_context: Dict[str, Any]
    confirmation_decision: str
    awaiting_confirmation_reply: bool