## 1. Create a Langfuse account

Go to:

https://cloud.langfuse.com

Choose the **EU** region.

Create:

1. An Organization
2. A Project (for example: `ai-helpdesk`)

## 2. Create API keys

In Langfuse:

**Settings → API Keys → Create new API key**

Copy both:

- Public Key: `pk-lf-...`
- Secret Key: `sk-lf-...`

> Keep the secret key private. Do not commit it to Git.

## 3. Add Langfuse configuration to `.env`

In the project root `.env` file, add:

```env
# ── Observability ────────────────────────────────────
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_ENABLED=true
```

## 5. Test the Langfuse tracing

Once the project is running, open the frontend:

https://localhost:5173

### Step 1 — Open the Employee Portal

Log in as an employee and open the chat/helpdesk interface.

### Step 2 — Send an IT request

Send a test request such as:

> My VPN is not connecting to the company network.

Wait for the AI Helpdesk to respond.

### Step 3 — Open Langfuse

Go back to your Langfuse Cloud project.

Open:

**Tracing → Traces**

You should see a new trace for the request you just sent.

### Step 4 — Open the trace

Click the newly created trace.

You should be able to see the workflow execution and its individual operations, such as:

- `intake`
- `check_takeover`
- `injection_pre_check`
- `preprocess`
- `check_clarification`
- `classify`
- `retrieve`
- `diagnose`
- `check_diagnose`
- `resolve`

Depending on the request, not every node or operation may appear.

### Step 5 — Check the RAG execution

For requests that use the knowledge base, open the `retrieve` part of the trace.

You should be able to inspect the retrieval operation and see the retrieved knowledge-base documents and/or similar historical incidents.

### Step 6 — Check the LLM calls

Open the LLM observations inside the trace.

These should show information about the GPT-OSS calls, including the model used, inputs/outputs where captured, latency, and other available metadata.

The model may appear as:

```text
openai/gpt-oss-120b
```