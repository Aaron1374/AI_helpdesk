"""
evaluate_retrieval.py — Evaluation script for Knowledge Base Chunk Retrieval (Task 17 & Task 18)
==================================================================================================
Runs realistic employee IT queries through RetrievalService, measures Top-1, Top-3, Top-5
retrieval accuracy against the 100 KB articles in PostgreSQL, and generates a report.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://helpdesk_user:helpdesk_password@localhost:5432/helpdesk_db"

from src.core.db import AsyncSessionLocal
from src.services.retrieval_service import RetrievalService


EVALUATION_QUERIES = [
    {
        "query": "My laptop is stuck on the Dell logo when I turn it on.",
        "expected_title": "Windows 11 Laptop Stuck at Manufacturer Logo on Boot",
        "category": "Boot / Hardware"
    },
    {
        "query": "My VPN keeps dropping and disconnecting after a few minutes.",
        "expected_title": "VPN Disconnects After Several Minutes of Inactivity",
        "category": "Network / VPN"
    },
    {
        "query": "Outlook is not sending or receiving my new emails.",
        "expected_title": "Outlook Not Sending or Receiving Emails",
        "category": "Software / Email"
    },
    {
        "query": "My MFA authenticator verification code is being rejected as invalid.",
        "expected_title": "MFA Code Rejected / 'Invalid Verification Code'",
        "category": "Access / Authentication"
    },
    {
        "query": "My external monitor is not detected when connected to the HDMI port.",
        "expected_title": "External Monitor Not Detected When Connected",
        "category": "Hardware / Display"
    },
    {
        "query": "My Windows laptop has high CPU memory usage and is running extremely slow.",
        "expected_title": "Slow Windows Performance With High CPU or Memory Usage",
        "category": "Hardware / Performance"
    },
    {
        "query": "My laptop Wi-Fi connects but has no internet access.",
        "expected_title": "Wi-Fi Connects But No Internet Access",
        "category": "Network / Wi-Fi"
    },
    {
        "query": "Laptop powers on with fan noise but the screen stays completely black.",
        "expected_title": "Laptop Powers On But Screen Stays Black",
        "category": "Hardware / Display"
    },
    {
        "query": "My account is locked out after multiple failed login attempts.",
        "expected_title": "Account Locked Out After Multiple Failed Login Attempts",
        "category": "Access / Authentication"
    },
    {
        "query": "CrowdStrike flagged a security alert and quarantined a file on my PC.",
        "expected_title": "CrowdStrike Falcon / Defender Security Alert on Laptop",
        "category": "Security"
    }
]


async def run_evaluation():
    print(f"\n{'=' * 70}")
    print("  Retrieval Evaluation Benchmark — Task 17 & 18")
    print(f"{'=' * 70}\n")

    top1_hits = 0
    top3_hits = 0
    top5_hits = 0
    total_queries = len(EVALUATION_QUERIES)

    query_results = []

    async with AsyncSessionLocal() as db:
        for idx, item in enumerate(EVALUATION_QUERIES, 1):
            q_text = item["query"]
            exp_title = item["expected_title"]
            cat = item["category"]

            docs, max_score = await RetrievalService.get_similar_documents(db, q_text, limit=5)

            retrieved_titles = [d.get("title", "") for d in docs]
            top1_hit = (len(retrieved_titles) > 0 and exp_title.lower() in retrieved_titles[0].lower())
            top3_hit = any(exp_title.lower() in t.lower() for t in retrieved_titles[:3])
            top5_hit = any(exp_title.lower() in t.lower() for t in retrieved_titles[:5])

            if top1_hit:
                top1_hits += 1
            if top3_hit:
                top3_hits += 1
            if top5_hit:
                top5_hits += 1

            query_results.append({
                "index": idx,
                "query": q_text,
                "expected": exp_title,
                "category": cat,
                "retrieved_top1": retrieved_titles[0] if retrieved_titles else "None",
                "top1_match": top1_hit,
                "top3_match": top3_hit,
                "top5_match": top5_hit,
                "top1_score": docs[0]["score"] if docs else 0.0,
                "retrieved_chunks": docs
            })

            print(f"[{idx}/{total_queries}] Query: '{q_text}'")
            print(f"      Expected: '{exp_title}'")
            print(f"      Top 1:    '{retrieved_titles[0] if retrieved_titles else 'None'}' (Score: {docs[0]['score'] if docs else 0.0:.4f})")
            print(f"      Match: Top1={top1_hit} | Top3={top3_hit} | Top5={top5_hit}\n")

    top1_acc = (top1_hits / total_queries) * 100
    top3_acc = (top3_hits / total_queries) * 100
    top5_acc = (top5_hits / total_queries) * 100

    report_lines = [
        "# Task 17 & Task 18 — Retrieval Evaluation Report\n",
        "## Executive Summary\n",
        "This evaluation benchmarks chunk-level vector retrieval accuracy against realistic employee IT support queries.\n",
        f"- **Total Queries Evaluated**: `{total_queries}`",
        f"- **Top-1 Accuracy**: **{top1_acc:.1f}%** ({top1_hits}/{total_queries})",
        f"- **Top-3 Accuracy**: **{top3_acc:.1f}%** ({top3_hits}/{total_queries})",
        f"- **Top-5 Accuracy**: **{top5_acc:.1f}%** ({top5_hits}/{total_queries})\n",
        "---",
        "## Detailed Query Benchmark\n"
    ]

    for res in query_results:
        report_lines.append(f"### Query {res['index']}: *\"{res['query']}\"*")
        report_lines.append(f"- **Category**: `{res['category']}`")
        report_lines.append(f"- **Expected Target**: `{res['expected']}`")
        report_lines.append(f"- **Top-1 Retrieved**: `{res['retrieved_top1']}`")
        report_lines.append(f"- **Top-1 Match Result**: {'✅ PASS (100%)' if res['top1_match'] else '❌ FAIL'}")
        report_lines.append(f"- **Similarity Score**: `{res['top1_score']:.4f}`\n")
        report_lines.append("#### Retrieved Top-5 Chunks:")

        for c_idx, doc in enumerate(res["retrieved_chunks"], 1):
            report_lines.append(f"1. **[{doc.get('type')}]** `{doc.get('title')}` — Chunk `{doc.get('chunk_index', 0)}` (Score: `{doc.get('score', 0.0):.4f}`)")
            snippet = doc.get("content", "").replace("\n", " ")[:160]
            report_lines.append(f"   > *{snippet}...*\n")

    report_lines.append("---")
    report_lines.append("## Task 18 — Evaluation & Document Expansion Decision\n")
    if top1_acc >= 90.0:
        report_lines.append(
            f"> [!NOTE]\n"
            f"> **Decision**: Full Document Expansion is **NOT REQUIRED**.\n"
            f"> Top-1 chunk retrieval accuracy achieved **{top1_acc:.1f}%** across all test categories. "
            f"The section-aware chunker with title prefixing and 150-char sliding overlap returns complete, focused, "
            f"and accurately grounded context to the Troubleshooting Agent without incurring additional latency or token bloat."
        )
    else:
        report_lines.append(
            f"> [!IMPORTANT]\n"
            f"> **Decision**: Document Expansion should be considered as Top-1 accuracy is {top1_acc:.1f}%."
        )

    report_text = "\n".join(report_lines)

    # Save to local backend directory
    backend_dir = Path(__file__).parent.parent
    out_path = backend_dir / "retrieval_evaluation_report.md"
    with open(out_path, "w", encoding="utf-8") as f_out:
        f_out.write(report_text)

    print(f"\n[SUCCESS] Evaluation complete! Report saved to {out_path}")
    print(f"Top-1 Accuracy: {top1_acc:.1f}% | Top-3 Accuracy: {top3_acc:.1f}% | Top-5 Accuracy: {top5_acc:.1f}%")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
