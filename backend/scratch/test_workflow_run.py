import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.workflow.graph import app as graph_app

async def main():
    initial_state = {
        "input": "I did update my windows a moment ago and it just doesn't allow my VPN to get connected",
        "messages": [],
        "evidence": [],
        "tool_history": [],
        "user_context": {"username": "employee@example.com", "department": "IT", "role": "employee"},
        "status": "ACTIVE"
    }
    final_state = await graph_app.ainvoke(initial_state)
    print("--- FINAL STATE ---")
    print("Status:", final_state.get("status"))
    print("Escalate:", final_state.get("escalate"))
    print("Needs Handoff:", final_state.get("needs_handoff"))
    print("Retrieval Score:", final_state.get("retrieval_score"))
    print("Messages:")
    for m in final_state.get("messages", []):
        print("  -", getattr(m, "content", str(m)))
    print("Evidence:")
    for ev in final_state.get("evidence", []):
        print("  -", ev)

if __name__ == "__main__":
    asyncio.run(main())
