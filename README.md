# HR Policy and Leave Assistant

Employee HR assistant with **policy Q&A (RAG + citations)**, **own leave balance**, **leave proposals**, and **pending leave requests** only after explicit confirmation. A human still approves leave.

This repository is a portfolio product (API, agent, retrieval, UI, tests, Docker, synthetic demo data). It is not framed as a course assignment and does not brand a fictional company name in the product UI.

## Features

- Hybrid policy retrieval (lexical + vector + RRF + rerank) over versioned chunks
- Bounded tool-calling agent with citation validation and abstention
- Deterministic leave domain gates (annual notice, balance, overlap; sick >2 BD prepares + docs-via-HR flag) plus RAG for explanations
- Identity from bearer token only (`get_my_leave_balance` has no employee id argument)
- Server-persisted chat threads; in-chat redacted trace inspector
- Confirm → `pending_manager_review` with idempotent replay
- Next.js demo UI (sign-in, dashboard, chat, leave, people, policies, monitoring)
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

Demo sign-in (password `demo` for all): `alya@demo.local`, `bima@demo.local`, `admin@demo.local`. Chat threads are stored per employee in Postgres; New Chat starts a blank draft (empty threads stay out of the sidebar).

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

Signing out and signing in as another demo user loads that employee’s own threads. Identity is enforced on the server.

## Live demo and slides

- **App:** [hr-assistant-self.vercel.app](https://hr-assistant-self.vercel.app/)
- **Class slides:** [HR Policy and Leave Assistant (Gamma)](https://gamma.app/docs/HR-Policy-and-Leave-Assistant-t0qdea0pkkd2lj6)
- Demo sign-in: `alya@demo.local` / `demo` (also `bima@demo.local`, `admin@demo.local`)

## Deploy (Neon + Vercel)

Production: **Neon** (Postgres/pgvector) + Vercel from this repo. Redis is optional and skipped for v1.

See [Deploy guide](docs/deploy.md).

## Docs

- [Background — problem, user, and core ideas](docs/background.md)
- [Project guide — flows and details](docs/project-guide.md)
- [AI guide — models, tool loop, and RAG](docs/ai-guide.md)
- [Code guide — how a request moves through the files](docs/code-guide.md)
- [Deploy — Neon + Vercel](docs/deploy.md)
- [Architecture](docs/architecture.md)
- [Risks](docs/risks.md)

## Hard gates

- No cross-employee balance or request access
- No leave request created or claimed as `approved` by the system
- No leave side effect before confirmation
- No secrets in the repository or image
- Runnable evaluation evidence for release

Do not commit `.env` or real secrets.
