# Demo Script (5–7 minutes)

Docker-only stack: API http://localhost:8000 · UI http://localhost:3000

Full question list (English + Indonesian): [demo-questions.md](demo-questions.md).

Demo sign-in: `alya@demo.local` / `demo` (also `bima@demo.local`, `admin@demo.local`).

1. **Problem and user** (30s) — Employees need grounded HR policy answers and a safe way to propose leave without the system approving it.
2. **Architecture and trust boundary** (45s) — Bearer identity on the server; tools cannot take another employee id; Redis may degrade; Postgres holds balances, requests, and policy chunks.
3. **Policy Q&A with citation** (60s) — Sign in as Alya: “How many annual leave days do permanent employees get?” Expect citation `[HR-LEAVE-001]`; open the in-chat trace inspector.
4. **Own balance and blocked cross-user** (60s) — “What is my leave balance?” Then ask for another employee’s data; server still scopes to Alya.
5. **Proposal → confirm → pending → replay** (90s) — Propose annual leave with ≥3 business days’ notice, confirm once (`pending_manager_review`), confirm again (idempotent replay).
6. **Domain refuse / abstention / redaction** (60s) — Annual with too little notice, or sick leave longer than two business days → prepare refused (escalate for docs via HR, no diagnosis). Past-dated leave or unknown policy → abstain. Medical/PII phrasing → escalated ticket with redacted answer/trace.
7. **Evaluation and risks** (60s) — Show `outputs/evaluation_report.md` release decision and skim `docs/risks.md` (including policy/domain drift).

## Acceptance commands

```bash
COMPOSE_PROJECT_NAME=hr_assistant docker-compose build api web
COMPOSE_PROJECT_NAME=hr_assistant docker-compose up -d postgres redis
COMPOSE_PROJECT_NAME=hr_assistant docker-compose run --rm api python -m src.setup_lab
COMPOSE_PROJECT_NAME=hr_assistant docker-compose up -d api web
curl -fsS http://localhost:8000/healthz
curl -fsS http://localhost:8000/readyz
COMPOSE_PROJECT_NAME=hr_assistant docker-compose run --rm api python -m pytest -m "not live"
COMPOSE_PROJECT_NAME=hr_assistant docker-compose exec -T api \
  python -m src.run_evaluation --base-url http://localhost:8000 --token token-alya
COMPOSE_PROJECT_NAME=hr_assistant docker-compose cp api:/app/outputs/. ./outputs/
```
