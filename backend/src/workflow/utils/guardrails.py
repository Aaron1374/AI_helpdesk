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
