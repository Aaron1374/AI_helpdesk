import re
import json
from typing import List, Dict, Any, Optional
from langchain_core.runnables import RunnableConfig
import logging

logger = logging.getLogger(__name__)

_ZERO_WIDTH_AND_CONTROL = re.compile(
    r"[\u200B-\u200F\u202A-\u202E\u2060-\u2064\uFEFF\x00-\x08\x0B\x0C\x0E-\x1F]"
)
_TEMPLATE_PATTERN = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")
_HTML_TAG_PATTERN = re.compile(r"<[^>]{1,200}>")

MAX_INPUT_CHARS = 2048
MAX_INPUT_WORDS = 512


from src.workflow.constants import CONFIRM_MARKER, CONFIRM_FINAL_MARKER

def sanitize_input(text: str) -> str:
    """
    Clean user input before it reaches an LLM prompt or embedding call.

    Handles what's actually a risk here: zero-width/bidi-override unicode
    (a known technique for smuggling hidden instructions past a human
    reviewer while an LLM still reads them), stray template markers, raw
    HTML tags (defense in depth), excess whitespace, and a hard length cap.

    Preserves internal confirmation state markers if present in message history.
    """
    if not text:
        return ""

    has_confirm = CONFIRM_MARKER in text
    has_confirm_final = CONFIRM_FINAL_MARKER in text
    if has_confirm:
        text = text.replace(CONFIRM_MARKER, " ___CONFIRM_MARKER___ ")
    if has_confirm_final:
        text = text.replace(CONFIRM_FINAL_MARKER, " ___CONFIRM_FINAL_MARKER___ ")

    sanitized = _ZERO_WIDTH_AND_CONTROL.sub("", text)
    sanitized = _TEMPLATE_PATTERN.sub("", sanitized)
    sanitized = _HTML_TAG_PATTERN.sub("", sanitized)

    sanitized = re.sub(r"[ \t]+", " ", sanitized)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)

    words = sanitized.split()
    if len(words) > MAX_INPUT_WORDS:
        sanitized = " ".join(words[:MAX_INPUT_WORDS])
    if len(sanitized) > MAX_INPUT_CHARS:
        sanitized = sanitized[:MAX_INPUT_CHARS]
    if has_confirm:
        sanitized = sanitized.replace("___CONFIRM_MARKER___", CONFIRM_MARKER)
    if has_confirm_final:
        sanitized = sanitized.replace("___CONFIRM_FINAL_MARKER___", CONFIRM_FINAL_MARKER)

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

def is_it_support_query(query: str, use_llm: bool = True, config: RunnableConfig = None,) -> bool:
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
                res = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=q_clean)], config=config)
                verdict = res.content.strip().upper() if hasattr(res, "content") else str(res).strip().upper()
                if "OUT_OF_SCOPE" in verdict:
                    return False
                if "IN_SCOPE" in verdict:
                    return True
        except Exception as exc:
            logger.warning(
                "LLM IT-scope classification failed; using heuristic fallback: %s",
                exc,
            )

    # Heuristic fallback: check for any IT keyword match
    for kw in _IT_KEYWORDS:
        if kw in q_lower:
            return True

    return False


_COMMON_SHORT_WORDS = {
    "a", "i", "to", "in", "it", "is", "be", "as", "at", "so", "we", "he", "by", "or",
    "on", "do", "if", "me", "my", "up", "an", "go", "no", "us", "am", "ok", "hi", "hey",
}

_COMMON_IT_TERMS = {
    "vpn", "wifi", "wi-fi", "sso", "mfa", "2fa", "pc", "mac", "ip", "dns", "usb",
    "lan", "wan", "os", "ios", "hdmi", "ram", "cpu", "gpu", "bios", "bsod", "ssl",
    "tls", "ssh", "ftp", "http", "https", "url", "api", "id", "app", "ui", "cli",
    "cmd", "gui", "kb", "mb", "gb", "tb", "ping", "log", "net", "dev", "sys",
    # Common device/platform/OS names that contain legitimate consonant clusters
    "laptop", "desktop", "smartphone", "android", "windows", "linux", "iphone",
    "ipad", "tablet", "printer", "monitor", "keyboard", "bluetooth", "ethernet",
    "internet", "browser", "chrome", "firefox", "outlook", "office", "teams",
    "microsoft", "google", "apple", "software", "hardware", "network", "wireless",
    "password", "username", "account", "screen", "display", "device", "system",
    "server", "client", "service", "process", "program", "update", "install",
    "driver", "adapter", "router", "switch", "firewall", "antivirus", "backup",
    "remote", "access", "login", "logout", "reboot", "restart", "shutdown",
    "connect", "disconnect", "upload", "download", "storage", "memory", "battery",
    "charger", "cable", "port", "slot", "disk", "drive", "folder", "file",
    "email", "inbox", "calendar", "meeting", "invite", "ticket", "support",
    "corporate", "enterprise", "policy", "compliance", "certificate", "domain",
    "active", "directory", "registry", "settings", "config", "configuration",
}


# Matches hex escape sequences like \x15, \x03, \x1F in error messages
_HEX_ESCAPE_RE = re.compile(r"\\x[0-9a-fA-F]{2}")
# Matches URLs/IPs so they don't pollute word analysis
_URL_IP_RE = re.compile(
    r"https?://[^\s]+|[0-9]{1,3}(?:\.[0-9]{1,3}){3}(?::[0-9]+)?(?:/[^\s]*)?"
)
# Error messages typically contain these patterns — fast-pass as not gibberish
_ERROR_MSG_RE = re.compile(
    r"\b(error|exception|failed|failure|daemon|response|malformed|\bwarning\b|traceback|\bconn(?:ection)?\b|unauthorized|forbidden|timeout|refused|\bfatal\b)\b",
    re.I,
)


def is_gibberish(text: str) -> bool:
    """
    Detects random keystroke mashing, nonsense character sequences, or unpronounceable gibberish.
    Returns True if the text is deemed meaningless gibberish, False for legitimate text.

    Correctly handles technical error messages (Docker, HTTP, system errors) that may
    contain hex escape sequences, IP addresses, or error codes.
    """
    if not text:
        return True

    clean = text.strip()

    # Fast-pass: looks like a system/application error message — definitely not gibberish
    if _ERROR_MSG_RE.search(clean):
        return False

    # Strip hex escape sequences (\x15, \x03, etc.) before word analysis
    # to prevent \xNN from contributing stray 'x' characters
    clean_for_analysis = _HEX_ESCAPE_RE.sub(" ", clean)
    # Strip URLs and IP addresses too
    clean_for_analysis = _URL_IP_RE.sub(" ", clean_for_analysis)

    words = re.findall(r"[a-zA-Z]+", clean_for_analysis.lower())
    if not words:
        return len(clean) > 0 and not any(c.isalnum() for c in clean)

    total_alpha_chars = sum(len(w) for w in words)
    if total_alpha_chars == 0:
        return True

    # Fast check for keyboard mashing patterns
    mash_patterns = [
        r"(asdf|sdfg|dfgh|fghj|ghjk|hjkl|jkl|qwerty|werty|ertyu|rtyui|tyuio|yuio|zxcvb|xcvbn|cvbnm)",
        r"(qazwsx|wsxedc|edcrfv|rfvtgb|tgbyhn|yhnujm|ujmik|ikol)",
        r"(.)\1{3,}",  # 4+ repeated characters like 'aaaa', 'zzzz'
    ]
    for pattern in mash_patterns:
        if re.search(pattern, clean.lower()):
            return True

    vowels = set("aeiouy")
    invalid_word_count = 0
    invalid_chars_count = 0
    has_severe_consonant_cluster = False

    for w in words:
        if w in _COMMON_SHORT_WORDS or w in _COMMON_IT_TERMS:
            continue

        is_word_invalid = False

        # Single letter words other than 'a', 'i', and common abbreviations
        if len(w) == 1 and w not in {"a", "i", "x", "e", "v"}:
            is_word_invalid = True

        # Words of length 2 with no vowels (e.g. 'hs', 'w')
        elif len(w) == 2 and not any(c in vowels for c in w):
            is_word_invalid = True

        # Words of length >= 3 with no vowels at all (e.g. 'dfg', 'whfdd')
        elif len(w) >= 3 and not any(c in vowels for c in w):
            is_word_invalid = True

        # 4+ consecutive consonants unless known valid cluster
        # Threshold is 5+ to avoid false-positives on real compound words
        # like 'smartphone' (rtph), 'strength' (ngth), 'throughout' (ghth), etc.
        else:
            consonant_cluster = re.search(r"[bcdfghjklmnpqrstvwxz]{5,}", w)
            if consonant_cluster:
                cluster = consonant_cluster.group(0)
                if cluster not in {"ngth", "nstr", "rthm", "tsch", "ndst", "xplo"}:
                    is_word_invalid = True
                    has_severe_consonant_cluster = True

            # Unnatural consonant trigrams in English (on any word length)
            if not is_word_invalid and re.search(r"(bdb|skd|dhw|hdw|hfd|whf|fbw|hfb|qwe|wqu|ewh|zxc|xcv|cvb|vbn|bnm)", w):
                is_word_invalid = True

            if not is_word_invalid and len(w) >= 5:
                # Vowel to consonant ratio check for words >= 5 chars
                v_count = sum(1 for c in w if c in vowels)
                ratio = v_count / len(w)
                if ratio < 0.18 or ratio > 0.82:
                    is_word_invalid = True

        if is_word_invalid:
            invalid_word_count += 1
            invalid_chars_count += len(w)

    if has_severe_consonant_cluster:
        return True

    if invalid_word_count > 0:
        if (invalid_word_count / len(words)) >= 0.34:
            return True
        if total_alpha_chars > 0 and (invalid_chars_count / total_alpha_chars) >= 0.35:
            return True

    return False



