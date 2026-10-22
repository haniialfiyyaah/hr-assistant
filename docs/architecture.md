# Architecture

Problem and core ideas: [background.md](background.md).

## Product

HR Policy and Leave Assistant is an employee-facing service that:

1. Answers HR policy questions with citations from a versioned RAG index
2. Returns only the signed-in employee’s leave balance
3. Prepares leave proposals and creates `pending_manager_review` requests only after explicit confirmation
4. Can open HR tickets for escalation

A human still approves leave. There is no approve tool.

## Runtime view

```text
Next.js UI (port 3000)
  -> FastAPI (port 8000) + Bearer auth
  -> Threaded conversations (Postgres) + bounded agent loop
       -> search_hr_policy (hybrid retrieval)
       -> get_my_leave_balance (auth-bound)
       -> prepare_leave_request (domain gate → proposal only)
       -> confirm_leave_request (pending_manager_review)
       -> create_hr_ticket
  -> Confirm endpoint (UI button) → pending leave row
  -> PostgreSQL / pgvector + Redis cache (degradable)
  -> Redacted traces (+ in-chat trace inspector) + monitoring (admin)
```

## Trust boundaries

| Boundary | Rule |
| --- | --- |
| Browser → API | Persona token is a demo bearer; server authenticates and binds identity |
| User text / retrieved policy | Untrusted data, never treated as system instructions |
| Model output | Citations must match documents retrieved on the same run |
| Leave mutation | No leave row until confirm; status is always pending_manager_review |
| Open proposals | At most one `open` proposal per employee; replace requires consent, validates first, then supersedes |
| Prepare gate | `domain.py` refuses invalid prepares even if the model skips or misreads policy |
| Redis | Cache only; failure is a miss, not an outage |
| Telemetry | No raw prompts or chain-of-thought; PII redacted |

## Policy search vs domain gates

| Layer | Source | Job |
| --- | --- | --- |
| **RAG** (`search_hr_policy`) | Versioned chunks from `data/policies/` | Explain and cite rules; soft guidance before prepare |
| **Domain** (`validate_leave_request`) | Deterministic code in `src/domain.py` | Hard refuse bad prepares (notice period, balance, overlap, past dates); flag sick docs-via-HR when needed |
| **System prompt** | Process instructions only | Search first, follow retrieved policy, explain domain errors, no diagnosis — **not** a second copy of HR thresholds |

Critical prepare checks currently mirrored in domain (keep in sync when policy text changes): annual leave ≥ 3 business days’ notice (`HR-LEAVE-001`); sick leave **more than** 2 consecutive business days still **prepares**, with `sick_docs_via_hr=required` so the agent opens a redacted HR ticket for documents (`HR-LEAVE-002` — docs via HR system, not chat).

## Architecture decision

**Decision:** RAG over versioned policy chunks plus one bounded tool-calling agent, with deterministic domain validation on leave prepare.

**Context:** Policies change (version / effective date). Leave decisions need deterministic validation and human approval. Retrieval alone is not safe for mutations.

**Alternatives considered:** Prompt-only policies; fine-tuned model as source of truth; multi-agent orchestration; parsing free-text policy inside prepare.

**Trade-offs:** RAG needs indexing and retrieval quality, but stays auditable and updateable. Domain thresholds can drift from markdown until they share typed config. A single bounded agent is simpler to evaluate than a multi-agent graph.

**Production follow-up:** Replace demo tokens with OIDC, add holiday calendars, retention jobs, stronger evaluation automation, and typed policy rules seeded with chunks so prepare gates track policy versions.
