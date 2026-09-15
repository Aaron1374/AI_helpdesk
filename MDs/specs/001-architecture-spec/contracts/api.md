# API Interface Contracts

This document outlines the core public interfaces exposed by the FastAPI backend for the Employee Portal and Engineer Dashboard.

## Authentication
`POST /auth/login`
- **Request**: `{ "username": "...", "password": "..." }`
- **Response**: `{ "access_token": "jwt...", "token_type": "bearer", "role": "employee|l1|l2" }`

## Conversations (AI Interaction)
`POST /conversations`
- **Response**: `{ "id": "uuid", "status": "active" }`

`POST /conversations/{id}/messages`
- **Request**: `{ "content": "I need help with my VPN." }`
- **Response**: `{ "messages": [ { "sender": "AI", "content": "Let me check that..." } ] }`

`POST /conversations/{id}/takeover` (Engineer Only)
- **Response**: `{ "owner_type": "HUMAN" }`

## Tickets
`POST /tickets`
- **Headers**: `Idempotency-Key`
- **Request**: `{ "conversation_id": "uuid", "category": "Network", "priority": "High", "summary": "..." }`
- **Response**: `{ "id": "uuid", "status": "NEW" }`

`GET /tickets/{id}`
- **Response**: `{ "id": "uuid", "status": "...", "history": [...] }`

`POST /tickets/{id}/confirm-resolution`
- **Response**: `{ "status": "CLOSED" }`

`POST /tickets/{id}/reject-resolution`
- **Response**: `{ "status": "IN_PROGRESS" }`

## Diagnostics (Mock Tools - Internal / Engineer View)
`POST /diagnostics/vpn`
`POST /diagnostics/application`
`POST /diagnostics/account`
`POST /diagnostics/device`
- **Request**: `{ "target_id": "..." }`
- **Response**: `{ "status": "online|offline", "trace_id": "abc-123" }`

## Observability
`GET /health`
- **Response**: `{ "status": "ok", "db": "ok" }`

`GET /ready`
- **Response**: `{ "status": "ready" }`
