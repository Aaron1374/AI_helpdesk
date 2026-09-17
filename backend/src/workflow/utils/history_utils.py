import logging
from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from src.core.llm import get_chat_model
from src.workflow.constants import RECENT_HISTORY_KEEP

logger = logging.getLogger(__name__)


async def build_bounded_history(raw_messages: List[BaseMessage], config=None) -> List[BaseMessage]:
    """
    Keep the most recent RECENT_HISTORY_KEEP messages verbatim. Anything
    older is condensed into a single summary SystemMessage prepended to the
    front — never dropped silently, never kept forever.
    """
    if len(raw_messages) <= RECENT_HISTORY_KEEP:
        return raw_messages

    older = raw_messages[:-RECENT_HISTORY_KEEP]
    recent = raw_messages[-RECENT_HISTORY_KEEP:]

    summary_text = await _summarize(older, config)
    return [SystemMessage(content=f"Summary of earlier conversation: {summary_text}"), *recent]


async def _summarize(older_messages: List[BaseMessage], config=None) -> str:
    transcript = "\n".join(
        f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
        for m in older_messages
        if getattr(m, "content", None)
    )

    llm = get_chat_model()
    if not llm:
        # No LLM available — naive truncation rather than losing older
        # context entirely. Degrades weaker, never fails silently.
        return transcript[:500]

    try:
        prompt = [
            SystemMessage(content=(
                "Summarize this earlier part of an IT helpdesk conversation in "
                "2-3 sentences. Keep only facts relevant to diagnosing the issue: "
                "the system/software involved, symptoms, error messages, and "
                "anything already tried. Drop pleasantries."
            )),
            HumanMessage(content=transcript),
        ]
        res = await llm.ainvoke(prompt, config=config)
        return res.content.strip()
    except Exception as exc:
        logger.warning("History summarization failed, using naive truncation: %s", exc)
        return transcript[:500]