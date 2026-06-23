# Deployment Contracts

For a deployment feature, the "interfaces" are the **operational contracts** the runbook and
automation depend on: the Compose service contract, the environment-variable contract, the new
health endpoint contract, and the backup/restore CLI contract. Each is the testable surface a
deployment task and its verification check target.

---

## C1 — Compose service contract (`deploy/docker-compose.yml`)

Three services + two named volumes. Network is the default Compose bridge (services reach each other
by name; only Caddy publishes ports).

| Service | Image / build | Published ports | Depends on | Restart | Healthcheck |
|---------|---------------|-----------------|------------|---------|-------------|
| `caddy` | `caddy:2` | `80:80`, `443:443` | `backend` | `unless-stopped` | Caddy admin / built-in |
| `backend` | build `deploy/backend.Dockerfile` | none (internal `:8000`) | `db` (healthy) | `unless-stopped` | `GET /api/v1/health` → 200 |
| `db` | `postgres:16` | none (internal `:5432`) | — | `unless-stopped` | `pg_isready -U postgres` |

| Volume | Mounted by | Purpose |
|--------|------------|---------|
| `pgdata` | `db` at `/var/lib/postgresql/data` | Persistent app data (survives recreation) |
| `caddy_data` | `caddy` at `/data` | ACME certs/keys (survive restart → no re-issue) |

Contract guarantees:
- `caddy` is the **only** service binding host ports; `backend` and `db` are not internet-reachable.
- `backend` does not accept traffic until its `alembic upgrade head` completes (entrypoint, D4) and
  `/api/v1/health` returns 200.
- Built SPA static files (`frontend/dist`) are served by `caddy` from a read-only mount/copy.
- `docker compose up -d` from `deploy/` is the single documented start command (FR-001).

## C2 — Caddy routing contract (`deploy/Caddyfile`)

```
<DOMAIN> {
    encode gzip
    handle /api/* {
        reverse_proxy backend:8000
    }
    handle {
        root * /srv/www        # frontend/dist
        try_files {path} /index.html   # SPA history fallback
        file_server
    }
    handle_errors {
        rewrite * /maintenance.html
        file_server
    }
}
# HTTP→HTTPS redirect is automatic in Caddy for a named site address.
```

Guarantees: valid auto-renewing TLS cert for `<DOMAIN>` (FR-002); HTTP redirected to HTTPS;
same-origin SPA + API (research D3); `maintenance.html` served on backend/upstream errors (FR-015).

## C3 — Environment-variable contract (`deploy/.env`)

The consumer is `backend/src/core/config.py` (`Settings`) + Compose interpolation. Committed
template is `deploy/.env.example` (no real values).

| Var | Consumed by | Constraint | Failure mode if violated |
|-----|-------------|------------|--------------------------|
| `DOMAIN` | Caddy | resolvable to host IP | cert issuance fails (edge case) |
| `POSTGRES_PASSWORD` | `db`, `DATABASE_URL` | non-empty, strong | DB auth failure |
| `DATABASE_URL` | backend, Alembic | `postgresql+psycopg://…@db:5432/clinic` | backend refuses to start (validator) |
| `SESSION_SECRET` | backend | ≥ 16 chars, not placeholder | backend refuses to start (min_length) |
| `COOKIE_SECURE` | backend | `true` in prod | cookie sent over HTTP (insecure) |
| `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` | seed script | email / ≥ 12 chars | bootstrap exits non-zero |
| `BACKUP_AGE_RECIPIENT` | `ops/backup.sh` | valid `age` pubkey | backup aborts |

Contract: no secret appears in any committed file (SC-007); `.env` is gitignored; the app's
fail-fast behavior is the enforcement point for FR-003.

## C4 — Health endpoint contract (`GET /api/v1/health`) — NEW CODE

Unauthenticated, no tenant scope, no PHI.

| Aspect | Contract |
|--------|----------|
| Method/Path | `GET /api/v1/health` |
| Auth | none (must work without a session) |
| Behavior | runs `SELECT 1` on the DB |
| 200 body | `{"status": "ok", "database": "up"}` |
| 503 body | `{"status": "degraded", "database": "down"}` (structured `Error`-style, no internals) |
| Used by | Docker `healthcheck` for `backend`; operator check (FR-006); reboot readiness (SC-008) |

Test (Principle V, write first): asserts 200 + body when DB up; asserts 503 when DB unreachable;
asserts no auth required and no tenant/PHI fields in the response.

## C5 — Backup / restore CLI contract (`deploy/ops/`)

| Script | Invocation | Input | Output / effect | Verify |
|--------|------------|-------|-----------------|--------|
| `backup.sh` | `./ops/backup.sh` | running `db`, `BACKUP_AGE_RECIPIENT` | writes `clinic-<UTC>.dump.age` to backup dir, prints its path | file exists & non-zero size; `age` header present |
| `restore.sh` | `./ops/restore.sh <artifact>` | encrypted artifact, age identity, clean `db` | `pg_restore`s into a fresh DB | post-restore row counts of appointments/accounts/audit match source (SC-004) |

Guarantees: backup artifact is encrypted at rest (Principle I) and restorable onto a **clean** host
(FR-008 edge case); restore procedure recovers 100% of appointments, accounts, audit records
(SC-004).

## C6 — Bootstrap contract (existing `src.scripts.seed_superadmin`)

| Aspect | Contract |
|--------|----------|
| Invocation | `docker compose exec backend python -m src.scripts.seed_superadmin` with `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` set |
| Idempotent | re-running leaves an existing super-admin untouched (returns "already exists") |
| Security | password never logged; account flagged `must_change_password=true` |
| Satisfies | FR-005 (initial admin so operator can sign in immediately); "first-run empty DB" edge case |
