# Deploy: Neon + Vercel (UI + API)

Production shape for this repo:

- **Neon** — Postgres + pgvector (`DATABASE_URL`)
- **Vercel (UI)** — Next.js under `web/`
- **Vercel (API)** — FastAPI via `src/main.py` (second project, same Git repo)
- **Redis** — skipped for v1 (omit `REDIS_URL`; cache uses `NullCache`)

You need **two Vercel projects** from the same repository.

## 1. Neon

1. Create a Neon project.
2. Enable the **pgvector** extension (Neon console SQL or Neon’s extension UI):

   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

   The seed script also runs `CREATE EXTENSION IF NOT EXISTS vector` (`python -m src.setup_lab`).
3. Copy a connection string that includes SSL, for example:

   `postgresql://USER:PASSWORD@HOST/DB?sslmode=require`

   Prefer Neon’s **direct** (or documented non-pooler) URL if you see pooler/idle connection issues with `psycopg_pool`.

## 2. FastAPI on Vercel (API project)

1. Push this repo to GitHub.
2. [Vercel](https://vercel.com) → **Add New** → **Project** → import the **same** repo.
3. Settings for this project:
   - **Root Directory:** leave empty / `.` (repo root — not `web`)
   - Framework: **FastAPI** (or auto-detect from `requirements.txt` + `src/main.py`)
4. Entrypoint is already wired:
   - [`src/main.py`](../src/main.py) exports `app = create_app()`
   - [`pyproject.toml`](../pyproject.toml) has `[tool.vercel] entrypoint = "src.main:app"`
   - [`vercel.json`](../vercel.json) sets `maxDuration: 300` for chat-length agent turns
5. Environment variables (Production + Preview as needed):

   | Key | Notes |
   | --- | --- |
   | `DATABASE_URL` | Neon URL with `sslmode=require` |
   | `OPENAI_API_KEY` | Live key |
   | `AGENT_MODEL` | Same as local `.env` |
   | `EMBEDDING_MODEL` | Same as local `.env` |
   | `OPENAI_BASE_URL` | Usually `https://api.openai.com/v1` |
   | `MODEL_MODE` | `live` |
   | `EMBEDDING_DIMENSIONS` | e.g. `1536` |
   | `POLICY_INDEX_VERSION` | e.g. `policies-2026-01` |
   | `REDIS_URL` | **omit** for v1 |

6. Deploy. Note the API URL (e.g. `https://hr-assistant-api.vercel.app`).
7. Smoke:

   ```bash
   curl -sS https://<api-host>/healthz
   curl -sS https://<api-host>/readyz
   ```

`readyz` should show database/index ok; `cache` may be `degraded` without Redis.

Local / Docker unchanged: `uvicorn src.api:create_app --factory` and the existing [`Dockerfile`](../Dockerfile).

## 3. Next.js UI on Vercel (UI project)

1. **Add New** → **Project** → import the **same** repo again (second project).
2. Set **Root Directory** to `web`.
3. Framework preset: **Next.js**. Install / build use Yarn (`yarn install`, `yarn build`).
4. Environment variables:

   | Key | Value |
   | --- | --- |
   | `API_URL` | Public HTTPS origin of the **API** Vercel project, **no trailing slash** |

   Optional: `DATA_DIR` — defaults to `../data` from `web/` in the git checkout.
5. Deploy. Open the UI URL → sign in as `alya@demo.local` / `demo`.

The browser calls same-origin `/api/v1/*`. Next rewrites those to `API_URL` (see `web/next.config.ts`).

### Local preview of production UI

```bash
cd web
yarn install
API_URL=https://<your-api-vercel-host> yarn build
API_URL=https://<your-api-vercel-host> yarn start
```

## 4. Seed once

Against Neon (local machine with production `DATABASE_URL` in the environment):

```bash
python -m src.setup_lab --reset
```

Needs a working `OPENAI_API_KEY` + `EMBEDDING_MODEL` so policy chunks get real embeddings. Re-run only when you intentionally reset demo data. Vercel does not run seed on deploy.

## 5. End-to-end check

Open the UI Vercel URL → `alya@demo.local` / `demo` → ask a question from [demo-questions.md](demo-questions.md).

Optional API-only check: `https://<api-host>/docs` with bearer `token-alya`.

## Local vs production env

| Variable | Local Compose / uvicorn | Production |
| --- | --- | --- |
| `DATABASE_URL` | local Postgres | Neon |
| `REDIS_URL` | local Redis | omit |
| `API_URL` | `http://localhost:8000` (Next rewrite default) | API Vercel HTTPS origin |
| OpenAI models | `.env` | API project secrets |

Never commit `.env` or real secrets.

## Notes

- Chat can take tens of seconds; `maxDuration` is 300s on the API function. If turns still time out on Hobby, shorten agent settings or use a plan that allows longer runs.
- Do not point both projects at Root Directory `web` — the API project must use the repo root.
