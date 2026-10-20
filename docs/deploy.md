# Deploy: Neon + Vercel

Production shape for this repo:

- **Neon** — Postgres + pgvector (`DATABASE_URL`)
- **Vercel** — Next.js UI (`web/`)
- **API** — FastAPI must be reachable at a public HTTPS URL (`API_URL` on the UI project). You can host the API on Vercel (Python) or another long-timeout host; see [API hosting](#api-hosting) below.
- **Redis** — skipped for v1 (retrieval cache degrades; `/readyz` may show `cache: degraded`)

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

## 2. Next.js UI on Vercel

1. Push this repo to GitHub (`haniialfiyyaah/hr-assistant`).
2. [Vercel](https://vercel.com) → **Add New** → **Project** → import the repo.
3. Set **Root Directory** to `web`.
4. Framework preset: **Next.js**. Install / build use Yarn (`yarn install`, `yarn build`) — `packageManager` is set in `web/package.json`.
5. Environment variables for the UI project:

   | Key | Value |
   | --- | --- |
   | `API_URL` | Public HTTPS origin of the FastAPI service, **no trailing slash** (e.g. `https://hr-api.example.com`) |

   Optional: `DATA_DIR` — defaults to `../data` from `web/` (available in the Vercel git checkout when Root Directory is `web`).
6. Deploy. Open the UI URL → sign in as `alya@demo.local` / `demo`.

The browser calls same-origin `/api/v1/*`. Next rewrites those requests to `API_URL` (see `web/next.config.ts`).

### Local preview of production UI

```bash
cd web
yarn install
API_URL=https://<your-api-host> yarn build
API_URL=https://<your-api-host> yarn start
```

## 3. API hosting

Chat uses a bounded OpenAI tool loop and can take tens of seconds. Prefer a host with **request timeouts ≥ 60s** for `POST /api/v1/chat`.

**Option A — Vercel (Python FastAPI)**  
If you already run FastAPI on Vercel, point the UI’s `API_URL` at that deployment. Confirm the plan’s max duration covers agent chat (Hobby limits are often too short for multi-tool turns).

**Option B — Container / VM (Railway, Fly.io, etc.)**  
Deploy the existing [`Dockerfile`](../Dockerfile) + [`scripts/start-api.sh`](../scripts/start-api.sh) with Neon `DATABASE_URL` and OpenAI secrets. Set the UI `API_URL` to that service’s HTTPS URL.

API env (either option):

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
| `REDIS_URL` | omit for v1 |

## 4. Seed once

Against the live API environment (shell on the API host, or locally with production `DATABASE_URL`):

```bash
python -m src.setup_lab --reset
```

Needs a working `OPENAI_API_KEY` + `EMBEDDING_MODEL` so policy chunks get real embeddings. Re-run only when you intentionally reset demo data.

## 5. Smoke checks

```bash
curl -sS https://<api-host>/healthz
curl -sS https://<api-host>/readyz
```

Expect `readyz` → database/index ok; `cache` may be `degraded` without Redis.

Open the Vercel UI → `alya@demo.local` / `demo` → ask a question from [demo-questions.md](demo-questions.md).

Optional API-only check (Swagger): `https://<api-host>/docs` with bearer `token-alya`.

## Local vs production env

| Variable | Local Compose / uvicorn | Production |
| --- | --- | --- |
| `DATABASE_URL` | local Postgres | Neon |
| `REDIS_URL` | local Redis | omit |
| `API_URL` | `http://localhost:8000` (Next rewrite default) | Public API HTTPS origin |
| OpenAI models | `.env` | API host secrets |

Never commit `.env` or real secrets.
