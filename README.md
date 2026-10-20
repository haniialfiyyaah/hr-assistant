# HR Policy and Leave Assistant

Employee HR assistant with **policy Q&A (RAG + citations)**, **own leave balance**, **leave proposals**, and **pending leave requests** only after explicit confirmation. A human still approves leave.

This repository is a portfolio product (API, agent, retrieval, UI, tests, Docker, synthetic demo data). It is not framed as a course assignment and does not brand a fictional company name in the product UI.

## Features

- Hybrid policy retrieval (lexical + vector + RRF + rerank) over versioned chunks
- Bounded tool-calling agent with citation validation and abstention
- Identity from bearer token only (`get_my_leave_balance` has no employee id argument)
- Confirm → `pending_manager_review` with idempotent replay
- Next.js demo UI (sign-in, dashboard, chat thread, leave, people, policies, monitoring)
- Offline tests, overlap regression, and a 15-case live evaluation runner

## Quick start (local)

```bash
cp .env.example .env
# Fill OPENAI_API_KEY, AGENT_MODEL, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Colima / Docker: this machine uses docker-compose (hyphen)
COMPOSE_PROJECT_NAME=hr_assistant docker-compose up -d postgres redis
python -m src.setup_lab --reset

uvicorn src.api:create_app --factory --host 127.0.0.1 --port 8000
# other terminal:
cd web && yarn install && yarn dev
```

UI: http://localhost:3000 · API: http://localhost:8000

Demo sign-in (password `demo` for all): `alya@demo.local`, `bima@demo.local`, `admin@demo.local`. Chat history is browser-only; each send still posts a single message to the API.

## Tests and evaluation

```bash
pytest -m "not live"
# Live evaluation (API must be up; costs model calls):
python -m src.run_evaluation --base-url http://localhost:8000 --token token-alya
```

Reports are written under `outputs/` (gitignored JSON/MD artifacts).

## Docker image

One command (build, Postgres/Redis, seed, API, Next UI):

```bash
./scripts/compose-up.sh
```

Or step by step:

```bash
COMPOSE_PROJECT_NAME=hr_assistant docker-compose build api web
COMPOSE_PROJECT_NAME=hr_assistant docker-compose up -d postgres redis
COMPOSE_PROJECT_NAME=hr_assistant docker-compose run --rm api python -m src.setup_lab
COMPOSE_PROJECT_NAME=hr_assistant docker-compose up -d api web
COMPOSE_PROJECT_NAME=hr_assistant docker-compose run --rm api python -m pytest -m "not live"
```

UI http://localhost:3000 · API http://localhost:8000 · stop with `COMPOSE_PROJECT_NAME=hr_assistant docker-compose down`.

Lighter local option (Postgres, Redis, and API in Docker; Next UI on the host — skips building the web image):

```bash
COMPOSE_PROJECT_NAME=hr_assistant docker-compose up -d postgres redis
COMPOSE_PROJECT_NAME=hr_assistant docker-compose build api
COMPOSE_PROJECT_NAME=hr_assistant docker-compose run --rm api python -m src.setup_lab
COMPOSE_PROJECT_NAME=hr_assistant docker-compose up -d api
cd web && yarn install && yarn dev
```

Build does not require an API key. Runtime reads credentials from `.env`. The API image runs as a non-root user. The UI image is the Next.js app under `web/`.

## Demo personas

| Persona | ID | Token |
| --- | --- | --- |
| Alya (employee) | EMP-001 | `token-alya` |
| Bima (employee) | EMP-002 | `token-bima` |
| Monitoring admin | ADM-001 | `token-admin` |

Signing out and signing in as another demo user clears the previous chat. Identity is enforced on the server.

## Deploy (Neon + Vercel)

Production: **Neon** (Postgres/pgvector) + **Vercel** (Next.js UI under `web/`). Point the UI’s `API_URL` at your FastAPI HTTPS origin (Vercel Python or another long-timeout host). Redis is optional and skipped for v1.

See [Deploy guide](docs/deploy.md).

## Docs

- [Project guide — flows and details](docs/project-guide.md) (start here to learn the system)
- [Deploy — Neon + Vercel](docs/deploy.md)
- [Architecture](docs/architecture.md)
- [Risks](docs/risks.md)
- [Demo script](docs/demo.md)
- [Demo questions cheat sheet](docs/demo-questions.md) (English + Indonesian)

## Hard gates

- No cross-employee balance or request access
- No leave request created or claimed as `approved` by the system
- No leave side effect before confirmation
- No secrets in the repository or image
- Runnable evaluation evidence for release

Do not commit `.env` or real secrets.
