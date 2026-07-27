# Deployment

This documents the path to a real deployment. Nothing here has actually been
provisioned — going from local `docker-compose` to a live, billable,
publicly-reachable service is a decision for whoever owns the AWS/Fly/Render
account and the API budget, not something to do silently.

## What's already deployment-shaped

- Backend and frontend are already containerized (`backend/Dockerfile`,
  implicit Next.js build) and orchestrated via `docker-compose.yml` — the
  same three services (`db`, `backend`, `frontend`) would move to any
  container host largely unchanged.
- `.github/workflows/ci.yml` builds the stack, seeds it, and runs the eval
  suite (`app.evals.run`) on every push — retrieval eval always runs (free,
  no API key needed); the LLM-judge eval runs too if an `ANTHROPIC_API_KEY`
  repo secret is set. This is a real regression gate: a change that hurts
  retrieval or answer quality fails CI, not just a green build check.

## Recommended path

1. **Database**: a managed Postgres with the `timescaledb` and `vector`
   extensions available — Timescale Cloud supports both natively. Self-hosted
   on a VPS via the existing `db` service also works; the extensions are
   already declared in `db/init.sql` / `init_db.py`.
2. **Backend**: any container host that takes a Dockerfile — Fly.io, Render,
   or a plain VPS behind a reverse proxy. No code changes needed beyond
   pointing `DATABASE_URL` at the managed Postgres instance.
3. **Frontend**: Vercel is the path of least resistance for Next.js, with
   `NEXT_PUBLIC_API_BASE_URL` pointed at the deployed backend. The existing
   `docker-compose` frontend service works too if you'd rather keep
   everything on one host.
4. **Secrets**: `ANTHROPIC_API_KEY` becomes a platform secret (Fly.io
   `fly secrets set`, Render environment group, GitHub Actions secret for
   CI) instead of a local `.env` file — never commit it.

## Before actually deploying

Read [ARCHITECTURE.md § Scaling notes](ARCHITECTURE.md#scaling-notes) first.
Two things there matter more once this is reachable by more than one
process:

- **Rate limiter and response cache are in-process memory.** Fine for one
  backend instance. The moment there's more than one (for uptime or load),
  they'd both need to move to Redis — the call-site interface
  (`rate_limiter.check(key)`, `cache.get`/`set`) is already isolated behind
  `app/services/`, so this is a backend swap, not a rewrite.
- **Cost isn't bounded beyond the rate limiter.** Ten requests/minute/IP
  still means real Claude spend at any nonzero traffic — check
  `GET /api/observability/requests` against expected volume before opening
  this up publicly, and consider whether the rate limit needs to be tighter
  for a public deployment than it is for local dev.

## Environment variables required in production

| Variable | Where it's read | Notes |
|---|---|---|
| `DATABASE_URL` | `backend/app/config.py` | Must point at Postgres with `timescaledb` + `vector` extensions installed |
| `ANTHROPIC_API_KEY` | `backend/app/config.py` | Without it, `/api/recommend*` return 503 rather than crash — see `recommend.py` |
| `CLAUDE_MODEL` | `backend/app/config.py` | Defaults to `claude-sonnet-5`; keep in sync with `app/services/observability.py`'s `PRICING` table if changed |
| `EMBEDDING_MODEL` | `backend/app/config.py` | Local model, no key needed, but changing it means re-embedding `procedure_documents` |
| `NEXT_PUBLIC_API_BASE_URL` | frontend build | Must point at the deployed backend's public URL |
