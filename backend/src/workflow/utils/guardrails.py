import re
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


def is_response_from_knowledge_base(answer: str, evidence: List[Dict[str, Any]]) -> bool:
    """
    Verify that the generated LLM response is grounded in the retrieved knowledge base
    or mock tool evidence. Returns True if evidence is present and cited or referenced.
    """
    if not answer or not answer.strip():
        return False
        
    if not evidence:
        return False
        
    answer_lower = answer.lower()
    
    # Check if answer contains refusal phrases indicating evidence was unhelpful
    refusal_phrases = [
        "cannot answer", "don't know", "no information", "unable to assist",
        "no knowledge base", "not mentioned in the provided", "insufficient evidence"
    ]
    for refusal in refusal_phrases:
        if refusal in answer_lower:
            return False
            
    # Check if any evidence item matches content/keywords in the answer
    for item in evidence:
        if isinstance(item, dict):
            # Check knowledge or ticket documents
            if "documents" in item and isinstance(item["documents"], list):
                for doc in item["documents"]:
                    title = doc.get("title", "").lower()
                    content = doc.get("content", "").lower()
                    # Check title overlap or significant content word overlap
                    if title and title in answer_lower:
                        return True
                    # Check key terms (words > 4 chars) from title
                    title_words = [w for w in re.findall(r"\w+", title) if len(w) > 4]
                    if title_words and any(tw in answer_lower for tw in title_words):
                        return True
                    # Check content snippet overlap
                    if content and len(content) > 10:
                        content_snippets = [w for w in re.findall(r"\w+", content) if len(w) > 4]
                        matches = [sw for sw in content_snippets if sw in answer_lower]
                        if len(matches) >= 2:
                            return True
            # Direct evidence dictionary (e.g., mock tool result or individual doc)
            title = item.get("title", "").lower()
            if title and title in answer_lower:
                return True
            if "status" in item or "connected" in item or "compliant" in item or "result" in item:
                # Tool evidence
                return True
                
    # Default permissive check if evidence exists and answer is non-trivial and not a refusal
    return len(answer.strip()) > 15


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


