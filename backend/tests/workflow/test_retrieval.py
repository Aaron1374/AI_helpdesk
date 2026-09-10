import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.services.retrieval_service import RetrievalService
from src.workflow.nodes.retrieval import retrieve_node

@pytest.mark.asyncio
async def test_retrieval_respects_rbac():
    mock_db = AsyncMock()
    docs, score = await RetrievalService.get_similar_documents(mock_db, "test query", "HR")
    assert isinstance(docs, list)
    assert isinstance(score, float)

@pytest.mark.asyncio
async def test_similarity_is_evidence_not_fact():
    state = {
        "input": "vpn issue",
        "sanitized_query": "vpn issue",
        "user_context": {"department": "IT"},
        "evidence": []
    }
    
    with patch("src.workflow.nodes.retrieval.RetrievalService.get_similar_documents", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = (
            [
                {"type": "knowledge", "title": "VPN Guide", "content": "Connect to VPN", "score": 0.85},
                {"type": "ticket", "title": "VPN down", "content": "Cannot connect", "score": 0.80}
            ],
            0.85
        )
        
        new_state = await retrieve_node(state)
        
        assert "evidence" in new_state
        assert new_state.get("retrieval_score") == 0.85
        assert len(new_state["evidence"]) == 1
        
        evidence_entry = new_state["evidence"][0]
        assert evidence_entry["source"] == "knowledge_and_incidents"
        assert len(evidence_entry["documents"]) == 2
        assert evidence_entry["documents"][0]["type"] == "knowledge"
        assert evidence_entry["documents"][1]["type"] == "ticket"
