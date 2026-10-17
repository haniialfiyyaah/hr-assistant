# Nusantara Digital — HR Policy and Leave Assistant

Employee assistant for the fictional company **Nusantara Digital**. It answers HR policy questions with citations, shows the signed-in employee's leave balance, prepares a leave proposal, and creates a leave request with status `pending_manager_review` only after explicit confirmation. A human still approves leave.

This repository is the portfolio product checkout (API, agent, retrieval, UI, tests, Docker, synthetic data).

## Status

**Step 1 scaffold complete.** Contracts, synthetic data, acceptance tests, and Compose wiring are in place. Backend stubs (`TODO(M2)`) will be implemented in later steps.

## Quick start (later steps)

```bash
cp .env.example .env
# Fill OPENAI_API_KEY, AGENT_MODEL, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS

docker compose -p hr_assistant up -d postgres redis
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -m "not live"
```

Full Docker-only grader sequence and architecture notes will be documented after the API and seed land.

## Demo personas

| Persona | ID | Token |
| --- | --- | --- |
| Alya (employee) | EMP-001 | `token-alya` |
| Bima (employee) | EMP-002 | `token-bima` |
| Monitoring admin | ADM-001 | `token-admin` |

Identity always comes from the bearer token on the server. Do not commit `.env` or real secrets.
