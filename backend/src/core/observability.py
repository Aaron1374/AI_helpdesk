import os
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
_handler = None


def _init() -> None:
    """Lazily construct a single process-wide CallbackHandler."""
    global _handler
    if _handler is not None or not _ENABLED:
        return
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        logger.warning("LANGFUSE_ENABLED=true but keys are missing; tracing disabled.")
        return
    try:
        from langfuse.langchain import CallbackHandler
        _handler = CallbackHandler()  # reads LANGFUSE_* from env
        logger.info("Langfuse tracing enabled (host=%s)", os.getenv("LANGFUSE_HOST"))
    except Exception as exc:
        logger.warning("Failed to initialise Langfuse: %s", exc)


def get_langchain_config(
    *,
    conversation_id: str,
    user_email: Optional[str] = None,
    trace_name: str = "helpdesk_workflow",
    extra_metadata: Optional[dict] = None,
) -> dict[str, Any]:
    """Build the RunnableConfig passed to graph_app.ainvoke()."""
    _init()
    if _handler is None:
        return {}

    metadata = {
        "langfuse_session_id": conversation_id,   # groups a whole chat thread
        "langfuse_tags": ["langgraph", "helpdesk"],
    }
    if user_email:
        metadata["langfuse_user_id"] = user_email
    if extra_metadata:
        metadata.update(extra_metadata)

    return {
        "callbacks": [_handler],
        "run_name": trace_name,
        "metadata": metadata,
    }


def flush() -> None:
    if _handler is None:
        return
    try:
        from langfuse import get_client
        get_client().flush()
    except Exception as exc:
        logger.warning("Langfuse flush failed: %s", exc)