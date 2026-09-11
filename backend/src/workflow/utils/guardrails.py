import re
from typing import Optional

# -------------------------------------------------------------------
# Guardrail utilities for the strict RAG workflow
# -------------------------------------------------------------------

# Keywords that strongly indicate an IT-related query.
# A query must match at least ONE of these to be considered on-topic.
_IT_KEYWORDS = [
    # Devices & hardware
    "laptop", "computer", "pc", "desktop", "monitor", "printer", "scanner",
    "keyboard", "mouse", "headset", "webcam", "docking", "dock", "usb",
    "battery", "charger", "cable", "display", "screen", "hardware",
    # Network & connectivity
    "vpn", "wifi", "wi-fi", "internet", "network", "ethernet", "firewall",
    "proxy", "dns", "ip address", "bandwidth", "router", "switch",
    "connectivity", "connection", "offline", "disconnect",
    # Software & OS
    "software", "install", "uninstall", "update", "upgrade", "patch",
    "windows", "mac", "linux", "os", "operating system", "driver",
    "app", "application", "crash", "error", "bug", "freeze", "slow",
    "microsoft", "office", "outlook", "teams", "excel", "word", "powerpoint",
    "browser", "chrome", "edge", "firefox", "safari",
    # Access & security
    "password", "login", "sign in", "sign-in", "authentication", "mfa",
    "two-factor", "2fa", "account", "access", "permission", "blocked",
    "locked", "reset", "credentials", "sso", "active directory", "ldap",
    "certificate", "ssl", "tls", "encryption",
    # IT operations
    "ticket", "helpdesk", "help desk", "support", "issue", "problem",
    "incident", "request", "outage", "downtime", "backup", "restore",
    "server", "cloud", "storage", "disk", "memory", "ram", "cpu",
    "email", "calendar", "sharepoint", "onedrive", "azure", "aws",
    "remote", "rdp", "remote desktop", "citrix", "virtual",
    "antivirus", "malware", "virus", "ransomware", "spam", "phishing",
    "port", "firewall", "proxy", "ping", "latency",
]

# Compile a single regex from all keywords for efficiency.
_IT_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _IT_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def is_it_related(text: str) -> bool:
    """Return True if the query appears to be IT-related.

    Uses keyword matching against a curated list of IT terms.
    This is intentionally strict: if no IT keyword is found the query
    is considered off-topic and should be rejected before reaching the
    RAG pipeline or LLM.
    """
    return bool(_IT_PATTERN.search(text))


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent prompt injection.

    - Removes templating patterns like ``{{ ... }}``.
    - Strips potentially dangerous characters used in SQL/command injection.
    - Truncates the result to a maximum of 512 tokens (approx words).
    """
    # Remove {{ ... }} blocks
    text = re.sub(r"\{\{.*?\}\}", "", text)
    # Remove dangerous characters/sequences
    dangerous_patterns = [";", "--", "/*", "*/", "\n", "\r"]
    for pat in dangerous_patterns:
        text = text.replace(pat, " ")
    # Collapse whitespace
    text = " ".join(text.split())
    # Truncate to 512 tokens (naïve split on whitespace)
    tokens = text.split()
    if len(tokens) > 512:
        tokens = tokens[:512]
    return " ".join(tokens)


def is_response_from_knowledge_base(answer: str, evidence: list) -> bool:
    """Lightweight guard that checks whether the LLM answer cites at least one
    document identifier from the retrieved evidence.
    The evidence list is expected to contain dicts with an ``id`` key.
    """
    if not evidence:
        return False
    answer_lower = answer.lower()
    for doc in evidence:
        doc_id = str(doc.get("id", "")).lower()
        if doc_id and doc_id in answer_lower:
            return True
    return False


def select_mock_tool(query: str) -> Optional[str]:
    """Select a mock tool based on simple keyword matching.

    Returns the name of the tool to invoke (e.g., ``"vpn_check"``) or ``None``
    if no mock tool is applicable.
    """
    q = query.lower()
    if "vpn" in q:
        return "vpn_check"
    if "device" in q:
        return "device_check"
    return None
