# Data Model & State Machines

## Entities

### 1. User
- **Fields**: `id` (UUID), `name` (String), `email` (String), `role` (Enum)
- **Roles**: `employee`, `l1`, `l2`, `support_lead`, `admin`
- **Relationships**: Owns Tickets, Authors Messages, Subject of AuditEvents.

### 2. Conversation
- **Fields**: `id` (UUID), `user_id` (UUID), `owner_type` (Enum: `AI`, `HUMAN`), `status` (Enum), `created_at` (Timestamp), `updated_at` (Timestamp)
- **Relationships**: Belongs to User, Has many Messages, Has one Ticket.
- **Rules**: If `owner_type == HUMAN`, the AI workflow is suspended.

### 3. Message
- **Fields**: `id` (UUID), `conversation_id` (UUID), `sender_type` (Enum: `USER`, `AI`, `SYSTEM`), `content` (Text), `created_at` (Timestamp), `trace_id` (String)
- **Relationships**: Belongs to Conversation.

### 4. Ticket
- **Fields**: `id` (UUID), `conversation_id` (UUID), `user_id` (UUID), `category` (String), `priority` (String), `status` (Enum), `summary` (Text), `resolution` (Text), `created_at` (Timestamp), `updated_at` (Timestamp)
- **Relationships**: Belongs to Conversation, Belongs to User, Has many TicketHistory entries.

### 5. TicketHistory
- **Fields**: `id` (UUID), `ticket_id` (UUID), `from_status` (Enum), `to_status` (Enum), `actor_id` (UUID), `reason` (String), `created_at` (Timestamp), `trace_id` (String)
- **Relationships**: Belongs to Ticket.

### 6. AuditEvent
- **Fields**: `id` (UUID), `actor_id` (UUID), `event_type` (String), `resource_type` (String), `resource_id` (UUID), `metadata` (JSONB), `created_at` (Timestamp), `trace_id` (String)

### 7. KnowledgeDocument (pgvector)
- **Fields**: `id` (UUID), `title` (String), `source` (String), `content` (Text), `metadata` (JSONB), `embedding` (Vector)

### 8. DiagnosticResult
- **Fields**: `id` (UUID), `ticket_id` (UUID), `tool_name` (String), `input_summary` (JSONB), `result` (JSONB), `created_at` (Timestamp), `trace_id` (String)

## State Machines

### Ticket State Machine
- **Nodes**: `NEW`, `TRIAGED`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`, `ESCALATED`
- **Transitions**:
  - `NEW` → `TRIAGED` (AI completes classification)
  - `TRIAGED` → `IN_PROGRESS` (AI or Human starts working)
  - `TRIAGED` → `ESCALATED` (Immediate escalation policy fires)
  - `IN_PROGRESS` → `RESOLVED` (Resolution proposed)
  - `IN_PROGRESS` → `ESCALATED` (AI gets stuck or requests privileged action)
  - `RESOLVED` → `CLOSED` (User confirms resolution)
  - `RESOLVED` → `IN_PROGRESS` (User rejects resolution)
- **Constraints**: Server-enforced. A ticket cannot move to `CLOSED` without user confirmation. `CLOSED` tickets cannot be silently reopened.

### Conversation Ownership
- **States**: `AI`, `HUMAN`
- **Transitions**:
  - `AI` → `HUMAN` (Triggered upon Ticket Escalation)
  - `HUMAN` → `AI` (If explicitly returned by an engineer, though usually handled via a new ticket)
