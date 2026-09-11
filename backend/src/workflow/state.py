from typing import TypedDict, List, Annotated, Dict, Any
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    input: str
    needs_clarification: bool
    escalate: bool
    category: str
    evidence: List[dict]
    tool_history: List[str]
    status: str
    user_context: Dict[str, Any]
    sanitized_query: str = ""
    retrieval_score: float = 0.0
    needs_handoff: bool = False
    handoff_payload: Dict[str, Any] = {}
