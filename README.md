# HR Policy and Leave Assistant

Employee HR assistant with **policy Q&A (RAG + citations)**, **own leave balance**, **leave proposals**, and **pending leave requests** only after explicit confirmation. A human still approves leave.

This repository is a portfolio product (API, agent, retrieval, UI, tests, Docker, synthetic demo data). It is not framed as a course assignment and does not brand a fictional company name in the product UI.

## Features

- Hybrid policy retrieval (lexical + vector + RRF + rerank) over versioned chunks
- Bounded tool-calling agent with citation validation and abstention
- Identity from bearer token only (`get_my_leave_balance` has no employee id argument)
- Confirm → `pending_manager_review` with idempotent replay
- Streamlit demo UI (Conversation / My leave requests / Monitoring)
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
streamlit run app.py
```

UI: http://localhost:8501 · API: http://localhost:8000

## Tests and evaluation

```bash
pytest -m "not live"
# Live evaluation (API must be up; costs model calls):
python -m src.run_evaluation --base-url http://localhost:8000 --token token-alya
```

Reports are written under `outputs/` (gitignored JSON/MD artifacts).

## Docker image

```bash
COMPOSE_PROJECT_NAME=hr_assistant docker-compose build api streamlit
COMPOSE_PROJECT_NAME=hr_assistant docker-compose up -d postgres redis
COMPOSE_PROJECT_NAME=hr_assistant docker-compose run --rm api python -m src.setup_lab
COMPOSE_PROJECT_NAME=hr_assistant docker-compose up -d api streamlit
COMPOSE_PROJECT_NAME=hr_assistant docker-compose run --rm api python -m pytest -m "not live"
```

Build does not require an API key. Runtime reads credentials from `.env`. The image runs as a non-root user.

## Demo personas

| Persona | ID | Token |
| --- | --- | --- |
| Alya (employee) | EMP-001 | `token-alya` |
| Bima (employee) | EMP-002 | `token-bima` |
| Monitoring admin | ADM-001 | `token-admin` |

Switching persona in the UI clears the previous chat. Identity is enforced on the server.

## Docs

- [Project guide — flows and details](docs/project-guide.md) (start here to learn the system)
- [Architecture](docs/architecture.md)
- [Risks](docs/risks.md)
- [Demo script](docs/demo.md)

## Hard gates

- No cross-employee balance or request access
- No leave request created or claimed as `approved` by the system
- No leave side effect before confirmation
- No secrets in the repository or image
- Runnable evaluation evidence for release

Do not commit `.env` or real secrets.
