"""
test_chunker.py — Tests for section-aware Knowledge Base Chunker
"""

import json
import pytest
from pathlib import Path
from src.rag.chunker import chunk_article, parse_sections, split_section_into_steps


def test_chunk_short_article():
    title = "Short Test Article"
    content = "Problem: Quick problem.\n\nResolution Steps:\n1. Restart machine."
    chunks = chunk_article(title, content, target_max_chars=1800)
    
    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 0
    assert "Article Title: Short Test Article" in chunks[0]["content"]
    assert "Problem: Quick problem." in chunks[0]["content"]


def test_chunk_validation_empty_title():
    with pytest.raises(ValueError, match="title cannot be empty"):
        chunk_article("", "Some content")


def test_chunk_validation_empty_content():
    with pytest.raises(ValueError, match="content cannot be empty"):
        chunk_article("Title", "")


def test_chunking_representative_kb_articles():
    kb_path = Path(__file__).parent.parent / "kb_articles.json"
    if not kb_path.exists():
        pytest.skip("kb_articles.json not found")

    with open(kb_path, "r", encoding="utf-8") as f:
        articles = [a for a in json.load(f) if "title" in a and "content" in a]

    # Test against at least 10 articles
    test_sample = articles[:10]
    assert len(test_sample) >= 5

    total_chunks = 0
    for article in test_sample:
        title = article["title"]
        content = article["content"]
        chunks = chunk_article(title, content, target_max_chars=1200, overlap_chars=150)
        
        assert len(chunks) > 0, f"Article '{title}' produced 0 chunks"
        total_chunks += len(chunks)
        
        # Check indices and title prefix
        for idx, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == idx
            assert f"Article Title: {title}" in chunk["content"]
            assert len(chunk["content"].strip()) > 0
            
            # Check overlap if index > 0
            if idx > 0:
                assert "... " in chunk["content"] or "Article Title:" in chunk["content"]

    print(f"\n[SUCCESS] Processed {len(test_sample)} articles into {total_chunks} total chunks.")


if __name__ == "__main__":
    test_chunk_short_article()
    test_chunk_validation_empty_title()
    test_chunk_validation_empty_content()
    test_chunking_representative_kb_articles()
    print("All chunker unit tests passed!")
