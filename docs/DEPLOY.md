# Deploy (Railway)

Project `lifeline` in workspace **Akshat Thapa's Projects** (never Wordsmith Ops). ADR 0028.

- API: https://api-production-15615.up.railway.app (health: `/v1/health`, sources: `/v1/sources`)
- Services: `api`, `worker` (same Dockerfile; `ROLE=worker` runs the worker), `Postgres`, `Redis`.
- Data mode: `DATA_MODE=live` (ADR 0027): real data only; sources without real data show `unavailable`.

## Redeploy
```
cd services/api
railway whoami                       # must be Akshat Thapa; project linked to 'lifeline'
cp railway.api.json railway.json && railway up --service api --detach && rm railway.json
railway up --service worker --detach
railway status                       # wait for api and worker: Online
curl -s https://api-production-15615.up.railway.app/v1/health
```
The api deploy uses `railway.api.json` (health check). The worker has no health check (no HTTP port), so `railway.json` must not exist when deploying it.

## Logs
```
railway logs --service api           # runtime
railway logs --service api --build   # build
railway logs --service worker
```
Logs never contain key values (httpx request logging is off; query strings are redacted).

## Variables
- Set without printing values: `printf %s "$VALUE" | railway variable set NAME --stdin --service api --skip-deploys` (repeat for `worker` when the worker needs it).
- Never use `railway variable list --kv` or `--json` in a shared terminal: they print raw values.
- Rotate the JWT secret: `openssl rand -hex 32 | railway variable set JWT_SECRET --stdin --service api` (and `worker`). Every signed-in user must sign in again.

## iOS against Railway
- Demo configuration: `LIFELINE_CLIENT=live`, `LIFELINE_API_BASE_URL=https://api-production-15615.up.railway.app`.
- Phone: `make ios-device CONFIG=Demo`. Simulator: build the `Lifeline` scheme with `-configuration Demo`.

## TrueLayer redirect URI
TrueLayer is disabled (ADR 0027). If it is enabled later, add this redirect URI in the TrueLayer console:
`https://api-production-15615.up.railway.app/v1/bank/callback`
