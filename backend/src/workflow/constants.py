import os

SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.62"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_SEED = int(os.getenv("LLM_SEED", "42"))

# Clarification loop — bumped 2 → 5 per your spec. Still a hard cap: once
# hit, preprocess stops asking and lets the query through regardless.
MAX_CLARIFICATION_ROUNDS = int(os.getenv("MAX_CLARIFICATION_ROUNDS", "5"))

# Relevance floor — a doc below this never reaches evidence.
MIN_DOC_SCORE = float(os.getenv("MIN_DOC_SCORE", "0.55"))

# History bounding — most recent N raw messages kept verbatim; anything
# older gets condensed into one summary block instead of dropped or kept
# forever, so prompt size stays bounded on long conversations.
RECENT_HISTORY_KEEP = int(os.getenv("RECENT_HISTORY_KEEP", "10"))

# Invisible markers used purely so the NEXT turn's routing can detect
# "this reply is answering a confirmation prompt." Zero-width Unicode
# characters, not HTML comments — HTML comments only render invisibly if
# the markdown pipeline has raw-HTML parsing enabled, which isn't
# guaranteed. Zero-width characters are truly invisible in any renderer,
# HTML-aware or not, because there's no markup to interpret.
CONFIRM_MARKER = "\u200b\u200b\u200c\u200b"
CONFIRM_FINAL_MARKER = "\u200b\u200c\u200c\u200b"