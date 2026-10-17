# ADR 0028: Railway deployment

- Status: accepted
- Date: 2026-10-17

## Decision
- Workspace: **Akshat Thapa's Projects** (id `b674afd1-82fb-4dc1-a08d-4f40e37d4f46`), selected by exact id. Never Wordsmith Ops. Project `lifeline` (`5a21ec48-9b68-4769-81e8-bd9fe49079fb`).
- Services:
  - `Postgres` and `Redis` (Railway databases with volumes).
  - `api` and `worker`, both built from `services/api/Dockerfile`. The image runs the worker when `ROLE=worker`, otherwise uvicorn on `$PORT` with proxy headers.
- Public domain: `https://api-production-15615.up.railway.app`, api only. The worker has no public domain. WebSockets work over the same domain (Railway proxies upgrades).
- Health check `/v1/health` on the api only, through `services/api/railway.api.json`, copied in as `railway.json` for api deploys. The worker has no HTTP port and no health check.
- Variables:
  - Set with `railway variable set --stdin`, so no value appears in a command line or output.
  - Copied from `.env`: Anthropic, LLM settings, Companies House, EPC, Stat-Xplore, Apple bundle id, rate limit.
  - Set for Railway: `APP_ENV=prod`, `DATA_MODE=live`, `ROLE`, `PORT=8000`, `PUBLIC_BASE_URL`, `OB_REDIRECT_URI`.
  - `DATABASE_URL` = `postgresql+asyncpg://` built from `${{Postgres.PG*}}` references. `REDIS_URL` = `${{Redis.REDIS_URL}}`.
  - `JWT_SECRET` is a fresh `openssl rand -hex 32`, piped straight to Railway, never stored or printed.
- The Dockerfile has no BuildKit cache mounts: Railway's builder requires an `id` on them.
- Bank tokens: TrueLayer is disabled (ADR 0027), so there are no bank tokens yet. Monzo and Trading212 connections are Yaffy's area. When tokens are stored, they are encrypted in Postgres with a key from env (`TOKEN_ENCRYPTION_KEY`, set on Railway the same way as `JWT_SECRET`).
- Redeploy steps are in `docs/DEPLOY.md`.
