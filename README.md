# HR Policy and Leave Assistant

A general employee HR assistant: policy Q&A with citations, leave balance for the signed-in user, leave proposals, and a pending leave request only after explicit confirmation. A human still approves leave.

This repository is a portfolio product (API, agent, retrieval, UI, tests, Docker, synthetic demo data). It is not framed as a course assignment.

## Status

Scaffold is in place: API contracts, synthetic data, acceptance tests, and Compose wiring. Backend modules are implemented step by step.

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
