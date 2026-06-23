<!-- SPECKIT START -->
Active feature: **002-deploy-app** (production deployment of the
`001-clinic-scheduling` app). For technologies, project structure, shell
commands, and other important information, read the current plan:
`specs/002-deploy-app/plan.md` (with `research.md`, `data-model.md`,
`contracts/deployment.md`, and `quickstart.md` — the operator runbook —
alongside it). The underlying app plan is `specs/001-clinic-scheduling/plan.md`.

Stack: Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 16 backend;
React 18 + TypeScript + Vite frontend. Sessions are center-scoped (cookie,
Argon2id). No double-booking is enforced by a Postgres GiST exclusion
constraint; every tenant-owned row carries `center_id` with default-deny
server-side scoping. Times stored as UTC `timestamptz`. In-app notifications
only.

Deployment (002): single-host Docker Compose in `deploy/` — `caddy`
(auto-HTTPS + reverse proxy + SPA static + maintenance page) · `backend`
(uvicorn; entrypoint runs `alembic upgrade head` then serves) · `db`
(postgres:16, `pgdata` volume). One public origin keeps the session cookie
first-party (`COOKIE_SECURE=true`). Secrets live only in gitignored
`deploy/.env`; the backend fails fast on a missing/short `SESSION_SECRET`.
Adds `GET /api/v1/health` (DB liveness). Encrypted `pg_dump`+`age` backups.
See the constitution for the NON-NEGOTIABLE security, tenant-isolation, and
appointment-integrity gates — deployment must preserve all of them in prod.
<!-- SPECKIT END -->
