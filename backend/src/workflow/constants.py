# Workflow constants for strict RAG implementation
# All values are overridable via environment variables.
import os

# Similarity threshold for retrieval (must be >= this to attempt auto-resolve)
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.72"))

# Deterministic LLM settings
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_SEED = int(os.getenv("LLM_SEED", "42"))
