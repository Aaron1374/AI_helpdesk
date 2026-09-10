from typing import TypedDict, List, Annotated, Dict, Any
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    input: str
    sanitized_query: str
    needs_clarification: bool
    escalate: bool
    needs_handoff: bool
    retrieval_score: float
    category: str
    evidence: List[dict]
    tool_history: List[str]
    status: str
    user_context: Dict[str, Any]

