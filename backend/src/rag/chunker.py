"""
chunker.py — Section-aware chunking for IT Support Knowledge Base articles.
=============================================================================
Provides section-aware chunking with target sizing, step-aware resolution splitting,
sliding overlap, title injection, and strict validation.
"""

import re
from typing import List, Dict, Any


SECTION_HEADER_RE = re.compile(
    r"^(Problem|Symptoms|Resolution Steps|Edge Case|Affected Systems|Category|IMPORTANT|NOTE):",
    re.IGNORECASE | re.MULTILINE
)


def parse_sections(content: str) -> List[Dict[str, str]]:
    """
    Split content into structured sections based on section headers or markdown headings.
    Returns a list of dicts: [{"header": str, "body": str}]
    """
    lines = content.splitlines(keepends=True)
    sections = []
    current_header = ""
    current_body_lines = []

    for line in lines:
        stripped = line.strip()
        header_match = re.match(
            r"^(Problem|Symptoms|Resolution Steps|Edge Case|Affected Systems|Category|IMPORTANT|NOTE):",
            stripped,
            re.IGNORECASE
        ) or re.match(r"^#{1,6}\s+(.+)", stripped)

        if header_match:
            if current_header or current_body_lines:
                sections.append({
                    "header": current_header,
                    "body": "".join(current_body_lines).strip()
                })
            current_header = stripped
            current_body_lines = []
        else:
            current_body_lines.append(line)

    if current_header or current_body_lines:
        sections.append({
            "header": current_header,
            "body": "".join(current_body_lines).strip()
        })

    return sections


def split_section_into_steps(body: str) -> List[str]:
    """
    Split a section body (e.g., Resolution Steps) into individual step items.
    """
    matches = list(re.finditer(r"(?:^|\n)(\d+\.\s)", body))
    if not matches or len(matches) <= 1:
        return [body] if body.strip() else []

    steps = []
    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        step_text = body[start:end].strip()
        if step_text:
            steps.append(step_text)
    return steps


def chunk_article(
    title: str,
    content: str,
    target_max_chars: int = 1800,
    overlap_chars: int = 150
) -> List[Dict[str, Any]]:
    """
    Section-aware chunking for KB articles with title prefixing and sliding overlap.

    Parameters:
      title: Article title
      content: Full text content of article
      target_max_chars: Target max characters per chunk (default 1800)
      overlap_chars: Sliding overlap characters across adjacent chunks (default 150)

    Returns:
      List of dicts:
      [
          {
              "chunk_index": 0,
              "content": "Article Title: ...\n\nProblem: ...\nSymptoms: ..."
          },
          ...
      ]
    """
    if not title or not title.strip():
        raise ValueError("Article title cannot be empty.")
    if not content or not content.strip():
        raise ValueError("Article content cannot be empty.")

    title = title.strip()
    content = content.strip()
    title_prefix = f"Article Title: {title}\n\n"

    # If full article with title fits in target_max_chars, return 1 single chunk
    full_text = f"{title_prefix}{content}"
    if len(full_text) <= target_max_chars:
        return [{
            "chunk_index": 0,
            "content": full_text
        }]

    # Parse into logical sections
    raw_sections = parse_sections(content)
    
    # Expand sections if Resolution Steps is long
    blocks = []
    for sec in raw_sections:
        header = sec["header"]
        body = sec["body"]
        sec_text = f"{header}\n{body}".strip() if header else body
        if not sec_text:
            continue

        # If Resolution Steps section is long, break into step groups
        if "resolution" in header.lower() and len(sec_text) > 600:
            steps = split_section_into_steps(body)
            if len(steps) > 1:
                if header:
                    blocks.append(header)
                blocks.extend(steps)
            else:
                blocks.append(sec_text)
        else:
            blocks.append(sec_text)

    # Group blocks into chunks based on target_max_chars with overlap
    chunks_content = []
    current_block_list = []
    current_len = len(title_prefix)

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        block_len = len(block) + 2  # +2 for \n\n
        if current_block_list and (current_len + block_len > target_max_chars):
            # Finalize current chunk
            chunk_body = "\n\n".join(current_block_list)
            chunks_content.append(chunk_body)
            
            # Extract sliding overlap from trailing portion of previous chunk body
            overlap_text = chunk_body[-overlap_chars:].strip() if overlap_chars > 0 else ""
            current_block_list = []
            if overlap_text:
                current_block_list.append(f"... {overlap_text}")
                current_len = len(title_prefix) + len(current_block_list[0]) + 2
            else:
                current_len = len(title_prefix)

        current_block_list.append(block)
        current_len += block_len

    if current_block_list:
        chunk_body = "\n\n".join(current_block_list)
        chunks_content.append(chunk_body)

    # Build and validate output list
    result = []
    for idx, c_text in enumerate(chunks_content):
        full_chunk = f"{title_prefix}{c_text}".strip()
        if not full_chunk:
            raise ValueError(f"Generated empty chunk at index {idx}")
        result.append({
            "chunk_index": idx,
            "content": full_chunk
        })

    if not result:
        raise ValueError(f"Article '{title}' produced zero valid chunks.")

    return result
