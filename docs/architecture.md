# Architecture

## Product

HR Policy and Leave Assistant is an employee-facing service that:

1. Answers HR policy questions with citations from a versioned RAG index
2. Returns only the signed-in employee’s leave balance
3. Prepares leave proposals and creates `pending_manager_review` requests only after explicit confirmation
4. Can open HR tickets for escalation

A human still approves leave. There is no approve tool.

## Runtime view

```text
Streamlit UI (port 8501)
  -> FastAPI (port 8000) + Bearer auth
  -> Bounded agent loop
       -> search_hr_policy (hybrid retrieval)
       -> get_my_leave_balance (auth-bound)
       -> prepare_leave_request (proposal only)
       -> create_hr_ticket
  -> Confirm endpoint -> pending leave row
  -> PostgreSQL / pgvector + Redis cache (degradable)
  -> Redacted traces + monitoring (admin)
```

## Trust boundaries

| Boundary | Rule |
| --- | --- |
| Browser → API | Persona token is a demo bearer; server authenticates and binds identity |
| User text / retrieved policy | Untrusted data, never treated as system instructions |
| Model output | Citations must match documents retrieved on the same run |
| Leave mutation | No leave row until confirm; status is always pending_manager_review |
| Redis | Cache only; failure is a miss, not an outage |
| Telemetry | No raw prompts or chain-of-thought; PII redacted |

## Architecture decision

**Decision:** RAG over versioned policy chunks plus one bounded tool-calling agent.

**Context:** Policies change (version / effective date). Leave decisions need deterministic validation and human approval.

**Alternatives considered:** Prompt-only policies; fine-tuned model as source of truth; multi-agent orchestration.

**Trade-offs:** RAG needs indexing and retrieval quality, but stays auditable and updateable. A single bounded agent is simpler to evaluate than a multi-agent graph.

**Production follow-up:** Replace demo tokens with OIDC, add holiday calendars, retention jobs, and stronger evaluation automation.
