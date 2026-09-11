import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.retrieval_service import RetrievalService
from src.workflow.constants import SIMILARITY_THRESHOLD

# Deterministic simple embedding model based on sum of character code points
class SimpleEmbeddingModel:
    def embed_query(self, text: str):
        # Return a single‑dimensional vector: sum of Unicode code points of the text
        return [sum(ord(ch) for ch in text)]

# Dummy embedding wrapper that can compute cosine distance for 1‑D vectors
class SimpleEmbedding:
    def __init__(self, vector):
        self.vector = vector
    def cosine_distance(self, other_vector):
        # Cosine distance for 1‑D vectors reduces to absolute difference / max magnitude
        a = self.vector[0]
        b = other_vector[0]
        if a == 0 and b == 0:
            return 0.0
        return abs(a - b) / max(abs(a), abs(b), 1)

class SimpleDoc:
    def __init__(self, title, content):
        self.title = title
        self.content = content
        # Use the same deterministic embedding logic on the content
        self.embedding = SimpleEmbedding([sum(ord(ch) for ch in content)])

class SimpleTicket:
    def __init__(self, title, description, status):
        self.title = title
        self.description = description
        self.status = MagicMock(value=status)
        self.embedding = SimpleEmbedding([sum(ord(ch) for ch in description)])

@pytest.mark.asyncio
async def test_dynamic_embedding_similarity_detection():
    """Validate that a query is embedded, similarity is computed dynamically,
    and a matching record is identified without hard‑coding numeric values.
    """
    query = "VPN not connecting"

    # Patch the embedding model to use our deterministic SimpleEmbeddingModel
    with patch("src.services.retrieval_service.get_embedding_model", return_value=SimpleEmbeddingModel()):
        fake_session = AsyncMock()

        # Knowledge document that matches the query exactly – should yield distance 0 (similarity 1.0)
        matching_doc = SimpleDoc("VPN Issue", query)
        # Another unrelated document
        other_doc = SimpleDoc("Printer Issue", "Printer offline")
        # Ticket with description similar to the query (identical in this case)
        similar_ticket = SimpleTicket("VPN Ticket", query, "open")

        # Mock DB execute calls: first for knowledge docs, second for tickets
        kb_result = AsyncMock()
        kb_result.scalars.return_value.all.return_value = [matching_doc, other_doc]
        ticket_result = AsyncMock()
        ticket_result.scalars.return_value.all.return_value = [similar_ticket]
        fake_session.execute.side_effect = [kb_result, ticket_result]

        docs, max_similarity = await RetrievalService.get_similar_documents(
            db=fake_session,
            query_text=query,
            user_department=None,
            limit=3,
        )

        # Expect three documents (two knowledge, one ticket)
        assert len(docs) == 3
        # The highest similarity should be 1.0 because of the exact match
        assert max_similarity == pytest.approx(1.0)
        # Ensure the similarity meets or exceeds the system threshold
        assert max_similarity >= SIMILARITY_THRESHOLD
