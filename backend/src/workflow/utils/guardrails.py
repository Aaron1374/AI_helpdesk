import re
import json
from typing import List, Dict, Any, Optional

def sanitize_input(text: str) -> str:
    """
    Sanitize prompt input by stripping template parameters, dangerous SQL/comment
    patterns, and truncating to a safe max length (512 tokens / ~2048 chars).
    """
    if not text:
        return ""
    
    sanitized = text
    # Remove mustache / jinja template patterns {{ ... }}
    sanitized = re.sub(r"\{\{.*?\}\}", "", sanitized)
    
    # Remove SQL comment and semicolon injection sequences
    sanitized = re.sub(r";|--|/\*|\*/", "", sanitized)
    
    # Truncate to maximum length representing ~512 tokens
    words = sanitized.split()
    if len(words) > 512:
        sanitized = " ".join(words[:512])
    elif len(sanitized) > 2048:
        sanitized = sanitized[:2048]
        
    return sanitized.strip()


def is_response_from_knowledge_base(
    answer: str,
    evidence: List[Dict[str, Any]]
) -> bool:
    """
    Verify that the generated response is grounded in retrieved
    knowledge-base documents or diagnostic tool evidence.

    Returns True only when the answer contains meaningful evidence
    from the supplied documents or tool results.
    """

    if not answer or not answer.strip():
        return False

    if not evidence:
        return False

    answer_lower = answer.lower()

    # Refusal/uncertainty responses should not be treated as grounded answers
    refusal_phrases = [
        "cannot answer",
        "don't know",
        "no information",
        "unable to assist",
        "no knowledge base",
        "not mentioned in the provided",
        "insufficient evidence",
    ]

    if any(phrase in answer_lower for phrase in refusal_phrases):
        return False

    # Check evidence
    for item in evidence:
        if not isinstance(item, dict):
            continue

        # --------------------------------------------------
        # Knowledge-base documents
        # --------------------------------------------------
        documents = item.get("documents")

        if isinstance(documents, list):
            for doc in documents:
                if not isinstance(doc, dict):
                    continue

                title = str(doc.get("title", "")).lower()
                content = str(doc.get("content", "")).lower()

                # Strong match: document title appears in answer
                if title and title in answer_lower:
                    return True

                # Match meaningful title words
                title_words = {
                    word
                    for word in re.findall(r"\w+", title)
                    if len(word) > 4
                }

                if title_words:
                    title_matches = sum(
                        1 for word in title_words
                        if word in answer_lower
                    )

                    if title_matches >= 2:
                        return True

                # Match meaningful content terms
                content_words = {
                    word
                    for word in re.findall(r"\w+", content)
                    if len(word) > 5
                }

                if content_words:
                    content_matches = sum(
                        1 for word in content_words
                        if word in answer_lower
                    )

                    # Require multiple independent matches
                    if content_matches >= 3:
                        return True

        # --------------------------------------------------
        # Direct evidence item
        # --------------------------------------------------
        title = str(item.get("title", "")).lower()

        if title and title in answer_lower:
            return True

        # --------------------------------------------------
        # Diagnostic tool evidence
        # --------------------------------------------------
        if item.get("source") == "diagnostic_tool":
            result = item.get("result")

            if result:
                result_text = json.dumps(result, default=str).lower()

                result_words = {
                    word
                    for word in re.findall(r"\w+", result_text)
                    if len(word) > 4
                }

                matches = sum(
                    1 for word in result_words
                    if word in answer_lower
                )

                if matches >= 2:
                    return True

    # IMPORTANT:
    # Do NOT automatically accept an answer just because it is long.
    return False


def select_mock_tool(query: str) -> Optional[str]:
    """
    Determine if a mock tool should be executed based on query keywords.
    Returns tool name string ('vpn_check' or 'device_check') or None.
    """
    if not query:
        return None
        
    q_lower = query.lower()
    if "vpn" in q_lower or "network connection" in q_lower:
        return "vpn_check"
    if "device" in q_lower or "laptop" in q_lower or "compliance" in q_lower:
        return "device_check"
        
    return None


# IT-related keyword signals — if NONE of these appear, the query is likely out of scope.
_IT_KEYWORDS = {
    # hardware
    "laptop", "computer", "pc", "desktop", "monitor", "screen", "keyboard", "mouse",
    "printer", "headset", "webcam", "camera", "microphone", "speaker", "usb", "dock",
    "charger", "battery", "overheating", "bsod", "blue screen",
    # software
    "software", "install", "update", "upgrade", "crash", "error", "bug", "freeze",
    "slow", "loading", "application", "app", "program", "outlook", "teams", "excel",
    "word", "office", "microsoft", "adobe", "browser", "chrome", "edge", "firefox",
    # network
    "vpn", "wifi", "wi-fi", "network", "internet", "connectivity", "dns", "proxy",
    "firewall", "bandwidth", "latency", "ping", "connection",
    # access / auth
    "password", "login", "sign in", "sign-in", "signin", "locked", "lockout",
    "mfa", "2fa", "two-factor", "authentication", "permission", "access", "reset",
    "account", "credentials", "sso", "single sign",
    # email
    "email", "e-mail", "mail", "inbox", "spam", "phishing", "outlook", "exchange",
    "calendar", "meeting", "invite",
    # IT ops
    "ticket", "helpdesk", "help desk", "support", "it support", "service desk",
    "server", "database", "backup", "restore", "deploy", "certificate", "ssl",
    "encryption", "security", "antivirus", "malware", "virus",
    # device management
    "onboarding", "setup", "provision", "compliance", "mdm", "intune", "domain",
    "active directory", "group policy", "driver",
}

def is_it_support_query(query: str, use_llm: bool = True) -> bool:
    """
    Determine whether the user's query is within the scope of Enterprise IT support.
    Uses LLM triage gatekeeper if available, falling back to keyword heuristics.
    Returns True for legitimate corporate IT problems/requests, False for out-of-scope queries
    (e.g., 'what colour is the laptop', personal mobile issues, food delivery, trivia, etc.).
    """
    if not query or not query.strip():
        return False

    q_clean = query.strip()
    q_lower = q_clean.lower()

    # Fast rejection for obvious non-IT patterns
    trivia_patterns = [
        r"what colour\b", r"what color\b", r"who is\b", r"what is the weather\b",
        r"tell me a joke\b", r"zomato\b", r"swiggy\b", r"uber\b", r"order food\b",
        r"my mobile\b", r"my personal phone\b", r"my phone wifi\b"
    ]
    for pattern in trivia_patterns:
        if re.search(pattern, q_lower):
            return False

    if use_llm:
        try:
            from src.core.llm import get_chat_model
            from langchain_core.messages import SystemMessage, HumanMessage
            llm = get_chat_model()
            if llm:
                sys_prompt = (
                    "You are a triage gatekeeper for an Enterprise Corporate IT Helpdesk.\n"
                    "Determine if the user's message is a legitimate corporate IT support request "
                    "(such as troubleshooting corporate laptop/workstation, software, VPN, corporate email/network, "
                    "SSO, passwords, enterprise hardware issues, or permissions/access).\n\n"
                    "Answer OUT_OF_SCOPE for:\n"
                    "- Trivia or nonsensical questions (e.g., 'what colour is the laptop')\n"
                    "- Personal consumer devices (e.g., personal mobile phone, home router, personal tablet)\n"
                    "- Non-IT requests (food delivery, weather, general knowledge, jokes, casual chat)\n\n"
                    "Answer IN_SCOPE only for genuine enterprise IT issues and troubleshooting requests.\n"
                    "Reply with ONLY 'IN_SCOPE' or 'OUT_OF_SCOPE'."
                )
                res = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=q_clean)])
                verdict = res.content.strip().upper() if hasattr(res, "content") else str(res).strip().upper()
                if "OUT_OF_SCOPE" in verdict:
                    return False
                if "IN_SCOPE" in verdict:
                    return True
        except Exception:
            # Fall back to heuristic keyword matching
            pass

    # Heuristic fallback: check for any IT keyword match
    for kw in _IT_KEYWORDS:
        if kw in q_lower:
            return True

    return False


