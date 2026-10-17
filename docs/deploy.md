# Deploy: Neon + Render Free

Production shape for this repo:

- **Neon** — Postgres + pgvector (`DATABASE_URL`)
- **Render Free** — two web services from this GitHub repo (same Blueprint)
  - `hr-assistant-api` — FastAPI
  - `hr-assistant-ui` — Streamlit
- **Redis** — skipped for v1 (retrieval cache degrades; `/readyz` may show `cache: degraded`)

Git push to the tracked branch rebuilds and redeploys both services after the first Blueprint sync.

## 1. Neon

1. Create a Neon project.
2. Enable the **pgvector** extension (Neon console SQL or Neon’s extension UI):

   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

   The seed script also runs `CREATE EXTENSION IF NOT EXISTS vector` (`python -m src.setup_lab`).
3. Copy a connection string that includes SSL, for example:

   `postgresql://USER:PASSWORD@HOST/DB?sslmode=require`

   Prefer Neon’s **direct** (or documented non-pooler) URL if you see pooler/idle connection issues with `psycopg_pool`. Pooled URLs often work too; if `readyz` fails after seed, try the direct host.

Do **not** use Render’s free Postgres for this project (30-day expiry). Keep Neon.

## 2. Render Blueprint

1. Push this repo to GitHub (already: `haniialfiyyaah/hr-assistant`).
2. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**.
3. Select the repo; Render reads [`render.yaml`](../render.yaml).
4. When prompted for `sync: false` values on **hr-assistant-api**, set at least:

   | Key | Notes |
   | --- | --- |
   | `DATABASE_URL` | Neon URL with `sslmode=require` |
   | `OPENAI_API_KEY` | Live key |
   | `AGENT_MODEL` | Same as local `.env` |
   | `EMBEDDING_MODEL` | Same as local `.env` |

   `OPENAI_BASE_URL`, `MODEL_MODE`, `EMBEDDING_DIMENSIONS`, and `POLICY_INDEX_VERSION` are already set in the Blueprint.
5. Do **not** set `REDIS_URL` (leave unset so cache degrades cleanly).
6. **hr-assistant-ui** gets `API_URL` from the API service’s `RENDER_EXTERNAL_URL` automatically. Confirm it has no trailing slash after the first deploy.

Both services use the existing [`Dockerfile`](../Dockerfile). Start commands are [`scripts/start-api.sh`](../scripts/start-api.sh) and [`scripts/start-ui.sh`](../scripts/start-ui.sh) so Render’s `$PORT` expands correctly.

## 3. Seed once

After the API is live and env vars are set, open the **hr-assistant-api** service → **Shell** (or a one-off job) and run:

```bash
python -m src.setup_lab --reset
```

This needs a working `OPENAI_API_KEY` + `EMBEDDING_MODEL` so policy chunks get real embeddings. Re-run only when you intentionally reset demo data.

## 4. Smoke checks

```bash
curl -sS https://<api-host>/healthz
curl -sS https://<api-host>/readyz
```

Expect `readyz` → database/index ok; `cache` may be `degraded` without Redis.

Open the Streamlit URL → persona **Alya** → ask a question from [demo-questions.md](demo-questions.md).

Optional API-only check (Swagger): `https://<api-host>/docs` with bearer `token-alya`.

## Free-tier notes

- Idle ~15 minutes → cold start (~1 minute) on the next request.
- ~750 free instance-hours per workspace per month across free services.
- Two free web services are enough for a portfolio demo; upgrade only if you need always-on.

## Local vs production env

| Variable | Local Compose | Render |
| --- | --- | --- |
| `DATABASE_URL` | local Postgres | Neon |
| `REDIS_URL` | local Redis | omit |
| `API_URL` | `http://localhost:8000` (Streamlit default) | API `RENDER_EXTERNAL_URL` |
| OpenAI models | `.env` | API dashboard / Blueprint secrets |

Never commit `.env` or real secrets.
