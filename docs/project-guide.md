# Project guide — flows and details

Learning-oriented overview of **HR Policy and Leave Assistant**: what the product does, how requests move through the system, and which modules own each concern.

Related docs: [architecture](architecture.md) · [risks](risks.md) · [demo script](demo.md) · [demo questions](demo-questions.md)

---

## 1. One-sentence product

Employees ask about HR policy and leave; the API authenticates them; a bounded agent may search policies, read **their** balance, prepare a leave proposal, or open a ticket; leave becomes `pending_manager_review` only after **confirm**; a human still approves leave.

---

## 2. Hard gates (non-negotiable)

A **hard gate** is a rule that **must never fail**. In live evaluation, hard-gate cases must pass **100%**; any failure makes the release decision **NO-GO**, even if overall pass rate is still high. Soft quality cases can miss some (overall pass still needs ≥ 80%). See also [demo-questions.md](demo-questions.md).

| Gate | Meaning |
| --- | --- |
| No cross-employee access | Balance and leave rows always use the bearer identity |
| No system-approved leave | There is no approve tool; status is never `approved` from this system |
| No side effect before confirm | `prepare_leave_request` only creates a proposal |
| No secrets in repo/image | `.env` stays local; Docker build does not need an API key |
| Runnable evaluation | Live 15-case runner produces a GO/NO-GO report |

---

## 3. Runtime stack

| Piece | Role | Default |
| --- | --- | --- |
| Next.js (`web/`) | Demo UI; talks to HTTP API via `/api/v1` rewrite | `:3000` |
| FastAPI (`src/api.py`) | Auth, chat, confirm, monitoring | `:8000` |
| Agent (`src/agent.py`) | Bounded tool loop + outcome gates | — |
| Tools (`src/tools.py`) | Five tools (no approve) | — |
| Retrieval (`src/retrieval.py`) | Hybrid RAG | — |
| Postgres + pgvector | Employees, balances, requests, policy chunks | Compose `postgres` |
| Redis | Retrieval cache (degrades on failure) | Compose `redis` |
| OpenAI | Embeddings + Responses API (`store=False`) | From `.env` |

```text
Next.js UI
    │  Bearer demo token
    ▼
FastAPI  ──►  Agent loop  ──►  Tools / RAG
    │                              │
    │                              ▼
    │                         Postgres (+ Redis cache)
    │
    └── Confirm endpoint ──► pending leave row
                      └──► redacted traces / monitoring
```

---

## 4. Visual flows

### 4.1 Chat request (policy, balance, tools)

```mermaid
flowchart TB
  UI[Next.js UI + demo token] --> API[FastAPI POST /api/v1/chat]
  API --> Auth[Resolve bearer → AuthContext]
  Auth --> Agent[Bounded agent loop]
  Agent -->|function_call| Tools{Tools}
  Tools --> RAG[search_hr_policy]
  Tools --> Bal[get_my_leave_balance]
  Tools --> Prep[prepare_leave_request]
  Tools --> ConfirmTool[confirm_leave_request]
  Tools --> Ticket[create_hr_ticket]
  RAG --> Gate[Outcome gates]
  Bal --> Gate
  Prep --> Gate
  ConfirmTool --> Gate
  Ticket --> Gate
  Agent -->|final text| Gate
  Gate --> Out[ChatResponse + redacted trace]
```

**Outcome gates (server-side):**

- Citations must match documents retrieved on **this** run → otherwise abstain
- Failed `prepare_leave_request` (past date, short annual notice, balance, overlap, …) → abstain (explain the domain error)
- Sick leave >2 business days → prepare still succeeds with `sick_docs_via_hr=required`; agent should also `create_hr_ticket` (redacted) for documents via HR, never collect diagnosis
- Ungrounded free-form answer (no tools / no citations) → abstain
- Successful ticket → `escalated`
- Successful proposal → `action_proposed` (still no leave row)
- Final answers are passed through `redact()`

**Search vs prepare:** Before prepare, the agent should call `search_hr_policy` for that leave type and follow retrieved text for answers. `prepare_leave_request` still runs `domain.py` so a wrong tool call cannot create a proposal. System instructions do **not** restate numeric HR thresholds — those live in policy docs + domain.

### 4.2 Leave confirm (the only leave mutation)

```mermaid
flowchart LR
  P[ActionProposal in chat] --> B[Confirm button + idempotency key]
  B --> C[POST /api/v1/action-proposals/id/confirm]
  C --> R[Repository transaction]
  R --> L[Leave request: pending_manager_review]
  R -.->|same key again| Replay[idempotent_replay = true]
```

### 4.3 Inside `search_hr_policy` (RAG)

```mermaid
flowchart TB
  Q[User question] --> Cache{Redis cache}
  Cache -->|hit| Chunks[Top policy chunks]
  Cache -->|miss| Embed[Embed query]
  Embed --> Lex[Lexical search]
  Embed --> Vec[pgvector semantic search]
  Lex --> RRF[RRF fuse]
  Vec --> RRF
  RRF --> Rerank[Keyword rerank]
  Rerank --> Chunks
  Chunks --> Model[Model answers with citations or abstains]
```

Policies are seeded from `data/policies/` as **versioned chunks** (document id, section, effective date, embedding). Index version is controlled by `POLICY_INDEX_VERSION`.

### 4.4 Seed and readiness

```mermaid
flowchart LR
  Seed[python -m src.setup_lab] --> PG[(Postgres schema + data)]
  Seed --> Emb[OpenAI embeddings]
  Emb --> PG
  PG --> Ready["/readyz: database + cache + model + index"]
```

### 4.5 When OpenAI is called

OpenAI is used in **three places**. Confirm leave, list requests, and monitoring do **not** call OpenAI — those are plain API/DB.

| When | OpenAI API | Why |
| --- | --- | --- |
| Seed | Embeddings | Index policy chunks |
| Chat | Responses (`store=False`) | Agent decides tools / writes the answer |
| Chat + RAG cache miss | Embeddings | Embed the question for vector search |

```mermaid
flowchart TB
  subgraph seed ["Seed time — setup_lab"]
    P[Policy files] --> Chunk[Chunk text]
    Chunk --> E1["OpenAI Embeddings API<br/>embed each chunk"]
    E1 --> DB[(Postgres / pgvector)]
  end

  subgraph chat ["Chat time — POST /api/v1/chat"]
    U[User message] --> Agent["OpenAI Responses API<br/>agent turn store=False"]
    Agent -->|tool: search_hr_policy| Cache{Redis hit?}
    Cache -->|yes| Chunks[Cached chunks]
    Cache -->|no| E2["OpenAI Embeddings API<br/>embed query"]
    E2 --> Search[Hybrid search]
    Search --> Chunks
    Chunks --> Agent2["OpenAI Responses API<br/>continue with tool results"]
    Agent -->|other tools / final answer| Out[ChatResponse]
    Agent2 --> Out
  end

  DB -.->|vectors for search| Search
```

```mermaid
sequenceDiagram
  participant UI as Next.js
  participant API as FastAPI / Agent
  participant OAI as OpenAI
  participant PG as Postgres
  participant Redis as Redis

  Note over UI,Redis: Seed once
  API->>OAI: embeddings.create policy chunks
  OAI-->>API: vectors
  API->>PG: store chunks + embeddings

  Note over UI,Redis: Chat each message
  UI->>API: POST /chat
  API->>OAI: responses.create decide tools or answer
  OAI-->>API: function_call or text

  alt search_hr_policy and cache miss
    API->>OAI: embeddings.create query
    OAI-->>API: query vector
    API->>PG: hybrid retrieve
  else search_hr_policy and cache hit
    API->>Redis: get cached results
  end

  opt more agent turns
    API->>OAI: responses.create with tool outputs
    OAI-->>API: final text or more tools
  end

  API-->>UI: ChatResponse
```

Chunking happens only at seed. At chat time we retrieve stored chunks; we re-embed only the **query** when RAG runs and the cache misses.

---

## 5. Personas

| Persona | ID | Token | Use for |
| --- | --- | --- | --- |
| Alya | EMP-001 | `token-alya` | Policy Q&A, own balance, leave happy path |
| Bima | EMP-002 | `token-bima` | Other employee; cross-user / IDOR checks |
| Monitoring admin | ADM-001 | `token-admin` | Monitoring tab only — **no leave balances** |

Chat threads are stored per employee in Postgres (sidebar history; empty drafts omitted). Switching persona uses that user’s threads. Identity is always enforced on the server from the bearer token, not from client-supplied employee ids.

---

## 6. API surface

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | Liveness |
| GET | `/readyz` | DB, cache, model, policy index |
| GET | `/api/v1/conversations` | List own threads (non-empty) |
| GET | `/api/v1/conversations/current` | Current / latest thread |
| GET | `/api/v1/conversations/{id}` | Load one thread |
| POST | `/api/v1/conversations` | Start a blank draft thread |
| POST | `/api/v1/chat` | Agent turn (threaded history) |
| POST | `/api/v1/action-proposals/{id}/confirm` | Create pending leave (idempotent) |
| GET | `/api/v1/leave-requests/me` | Own leave requests |
| GET | `/api/v1/traces/{trace_id}` | Redacted trace for a run (UI inspector) |
| GET | `/api/v1/monitoring/summary` | Aggregate metrics (admin) |
| GET | `/api/v1/monitoring/alerts` | Active alerts (admin) |

UI paths are fixed in `ui_contract.API_PATHS`.

---

## 7. Five tools (no approve)

| Tool | What it does | Side effect? |
| --- | --- | --- |
| `search_hr_policy` | Hybrid retrieval over policy chunks | Read-only (cache write OK) |
| `get_my_leave_balance` | Balances for **authenticated** employee only | Read-only |
| `prepare_leave_request` | Domain-validates and stores a **proposal** | Proposal only |
| `confirm_leave_request` | Confirms a pending proposal after clear user agreement | Leave row `pending_manager_review` |
| `create_hr_ticket` | Opens an HR ticket (summary redacted) | Ticket row |

Domain rules in `src/domain.py` (no model calls):

- Past start date; end before start; zero business days; overlap with active request; insufficient balance
- **Annual** (`HR-LEAVE-001`): start at least **3** business days after today
- **Sick** (`HR-LEAVE-002`): more than **2** consecutive business days → prepare allowed; summary `sick_docs_via_hr=required` (docs via HR system / ticket, not chat)

---

## 8. Module map

| Module | Responsibility |
| --- | --- |
| `src/config.py` | Settings from `.env` (empty optional strings → `None`) |
| `src/contracts.py` | Request/response types, outcomes, proposals |
| `src/domain.py` | Deterministic leave validation |
| `src/security.py` | Token hash, safety id, PII/token redaction |
| `src/cache.py` | Null / Redis / resilient degrade |
| `src/retrieval.py` | Hybrid search, RRF, rerank |
| `src/tools.py` | Strict schemas + identity-bound execution |
| `src/providers.py` | OpenAI live provider + deterministic test fake |
| `src/agent.py` | Tool loop, citations, abstain/escalate gates |
| `src/repository.py` | `MemoryRepository` (tests) + `PostgresRepository` |
| `src/api.py` | FastAPI app and endpoints |
| `src/setup_lab.py` | Schema + seed employees/policies/embeddings |
| `src/run_evaluation.py` | 15-case live evaluation → GO/NO-GO |
| `web/` | Next.js demo UI |
| `ui_contract.py` | Demo persona load/switch + API path contract (tests) |
| `data/policies/` | Synthetic HR policy corpus (mostly Indonesian) |
| `data/evaluation_cases.json` | Graded live cases |
| `tests/` | Offline + live markers |
| `Dockerfile` / `docker-compose.yml` | Non-root image; four Compose services |

---

## 9. Language behaviour

| Surface | Language |
| --- | --- |
| Product UI, personas, docs | English |
| Policy corpus + evaluation cases | Mostly Indonesian (contract data) |
| Chat replies | Follow the user’s language (agent instruction) |

English questions work; citations may still quote Indonesian policy excerpts.

---

## 10. Evaluation as release

Evaluation is a **product release gate**, not leave approval.

Release targets (see `src/run_evaluation.py`):

- Hard gates **100%**
- Overall pass ≥ **80%**
- Retrieval recall@3 ≥ **80%**
- Citation validity **100%**
- No system-created `approved` leave

```bash
python -m src.run_evaluation --base-url http://localhost:8000 --token token-alya
```

Reports land in `outputs/` (gitignored).

---

## 11. Suggested learning order

1. **Trust** — [architecture.md](architecture.md) trust table + bearer auth in `api.py`
2. **Domain before model** — `domain.py` + `prepare_leave_request` in `tools.py` (search explains; domain refuses)
3. **RAG** — `setup_lab` seed → `retrieval.py` → citation block in `agent.py`
4. **Agent loop** — process-oriented `SYSTEM_INSTRUCTIONS` + outcome gates in `agent.py` (no duplicated HR thresholds)
5. **Confirm** — `confirm_leave_request` / confirm handler in `api.py` + idempotency
6. **Threads + traces** — conversations API + in-chat trace inspector
7. **Eval** — `evaluation_cases.json` + `run_evaluation.py`
8. **Delivery** — [demo.md](demo.md) Docker sequence

---

## 12. Demo walkthrough (aligned to flows)

1. Alya → policy question → citations (flows 4.1 + 4.3); open trace inspector on the message
2. Alya → leave balance → `get_my_leave_balance` only
3. Alya → annual leave with ≥3 business days’ notice → Confirm → `pending_manager_review` (flow 4.2)
4. Confirm again → idempotent replay
5. Short annual notice → prepare refused; sick leave >2 business days → prepare + ticket for docs (no diagnosis); past leave / unknown policy → abstain; medical phrasing → escalate + redact
6. Ask for another employee’s balance → still own identity
7. Monitoring admin → Monitoring tab (not leave balance); People is admin-only

Full timing script: [demo.md](demo.md).
