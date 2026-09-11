# Quickstart & Validation Guide

This guide describes how to validate the AI Helpdesk architecture end-to-end once implemented.

## Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local UI testing)
- Python 3.11+ (for local API testing)
- LLM API Key (e.g., OpenAI or Anthropic)

## Setup
1. **Clone and configure:**
   ```bash
   cp .env.example .env
   # Add your LLM API Key to .env
   ```
2. **Start the modular monolith:**
   ```bash
   docker-compose up --build -d
   ```
3. **Verify Health:**
   ```bash
   curl http://localhost:8000/health
   # Expected: {"status": "ok", "db": "ok"}
   ```

## Validation Scenarios

### Scenario 1: AI Ticket Triage
1. **Login as an employee**:
   ```bash
   TOKEN=$(curl -X POST http://localhost:8000/auth/login -d '{"username":"emp1","password":"pw"}' | jq -r .access_token)
   ```
2. **Start a conversation**:
   ```bash
   CONV_ID=$(curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/conversations | jq -r .id)
   ```
3. **Submit an issue**:
   ```bash
   curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/conversations/$CONV_ID/messages -d '{"content": "I cannot access the HR portal."}'
   ```
4. **Expected Outcome**: The AI should respond, and checking the backend logs should reveal a `trace_id` showing the LangGraph workflow executing the Intake → Classify nodes.

### Scenario 2: Escalation & Human Takeover
1. **Submit a privileged request** (e.g., "Reset my password"):
   ```bash
   curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/conversations/$CONV_ID/messages -d '{"content": "Please reset my domain password immediately."}'
   ```
2. **Expected Outcome**: The deterministic policy fires. The API returns an escalation message. 
3. **Verify State**:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/conversations/$CONV_ID
   # Expected: {"owner_type": "HUMAN"}
   ```

### Scenario 3: Traceability
1. **Check Logs**:
   ```bash
   docker logs helpdesk-backend | grep "trace_id"
   ```
2. **Expected Outcome**: A contiguous audit trail from request intake, through tool execution, to ticket escalation, all sharing the same `trace_id`.
