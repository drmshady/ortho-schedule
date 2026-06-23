# Phase 0 Research: Production Deployment

All Technical Context unknowns for `002-deploy-app` are resolved below. Each decision is grounded
in the existing `001-clinic-scheduling` codebase (FastAPI + Vite SPA + PostgreSQL 16) and the spec's
single-host, operator-run constraints.

## D1 — Hosting topology: single-host Docker Compose

- **Decision**: Deploy as one Docker Compose stack on a single Linux VM with three long-running
  services — `caddy`, `backend`, `db` — plus named volumes for Postgres data and Caddy certs.
- **Rationale**: The spec assumptions mandate "single managed Linux virtual server … via containers
  (Docker Compose)" and explicitly scope out PaaS/Kubernetes/multi-node. Pilot scale (~50 concurrent
  users) fits one host. Compose gives reproducibility (FR-012) from one `docker compose up -d`.
- **Alternatives considered**: Bare-metal systemd units (no reproducible, self-contained artifact;
  more OS-specific steps for a non-DevOps operator); Kubernetes/managed PaaS (explicitly out of
  scope, large complexity for one tenant host).

## D2 — TLS + front door: Caddy with automatic HTTPS

- **Decision**: Caddy 2 terminates TLS using automatic Let's Encrypt issuance/renewal for the
  operator's `DOMAIN`, redirects HTTP→HTTPS, serves the built SPA as static files, reverse-proxies
  `/api/*` to the backend, and serves a maintenance page when the backend is unreachable.
- **Rationale**: One dependency satisfies FR-002 (auto-renewing valid cert + HTTPS redirect), the
  static-host need, and FR-015 (maintenance page) with a ~10-line `Caddyfile` — the lowest-skill
  option for the operator (FR-011). Certs persist in `caddy_data` so renewals survive restarts.
- **Alternatives considered**: nginx + certbot (separate renewal timer, manual cert plumbing,
  more failure modes for the operator — see edge case "certificate issuance fails"); Traefik
  (dynamic-config/label model is overkill for a fixed 3-service host).

## D3 — Single public origin (SPA and API share the domain)

- **Decision**: Serve SPA and `/api/*` from the **same** Caddy origin; no separate API hostname,
  no CORS.
- **Rationale**: The generated API client is hard-wired to the relative `baseUrl: '/api/v1'`
  (`frontend/src/api/generated/client.gen.ts`) and the session is a cookie. Same-origin keeps the
  cookie **first-party**, lets `COOKIE_SECURE=true` work, and avoids CORS/SameSite pitfalls. It also
  matches the dev proxy (`vite.config.ts` proxies `/api` → backend), so prod mirrors dev.
- **Alternatives considered**: Split origins (api.example.com + app.example.com) — forces CORS,
  cross-site cookie handling, and reconfiguring the client base URL; rejected as needless risk.

## D4 — Migrations: migrate-on-start entrypoint

- **Decision**: The backend container entrypoint runs `alembic upgrade head`, then execs
  `uvicorn src.main:app`. Alembic already reads `DATABASE_URL` via `get_settings()`
  (`backend/migrations/env.py:13`), so no extra wiring is needed.
- **Rationale**: First-run creates the full schema including `btree_gist` + the no-double-booking
  exclusion constraint and the RLS backstops (migrations `0001`/`0003`); subsequent deploys apply
  pending migrations automatically with no manual SQL (FR-004). Failing the migration aborts startup,
  so a half-upgraded schema never serves traffic (edge case "migration fails mid-deploy").
- **Alternatives considered**: Manual `alembic upgrade` step in the runbook (undocumented-step risk,
  FR-001/FR-004 violation); a one-shot `migrate` service with `depends_on` (works, but ordering and
  failure surfacing are clearer when the API container owns its own schema readiness).

## D5 — Secrets & configuration: gitignored root `deploy/.env`

- **Decision**: All runtime config/secrets come from `deploy/.env` (gitignored), with a committed
  `deploy/.env.example` template. Compose injects them; the backend `Settings` already aliases
  `DATABASE_URL`, `SESSION_SECRET` (min 16), and `COOKIE_SECURE` from env.
- **Rationale**: `.gitignore` already excludes `.env`/`.env.*`. The backend fails fast on a missing
  or too-short `SESSION_SECRET` (`core/config.py`) → satisfies FR-003 and the "missing/weak secret"
  edge case with no new code. `COOKIE_SECURE=true` is set for prod (dev default in `.env` is false).
- **Alternatives considered**: Docker secrets / external secret manager (more infra than a pilot
  needs, Principle VI); baking secrets into the image (forbidden by Principle I).

## D6 — Health check: new unauthenticated `GET /api/v1/health`

- **Decision**: Add a small `GET /api/v1/health` that runs `SELECT 1` against the DB and returns
  `{"status":"ok","database":"up"}` (200) or 503 if the DB is unreachable. Wire it as a Docker
  `healthcheck` for the backend service and as Caddy's upstream signal for the maintenance page.
- **Rationale**: No health endpoint exists today (only the auth-gated `/api/v1/_scope-check`). FR-006
  needs an operator-checkable app+DB status; SC-008 needs an automatic post-reboot readiness signal.
  Must be unauthenticated and reveal no PHI/tenant data.
- **Alternatives considered**: Reusing `_scope-check` (requires a session — unusable for an
  unauthenticated health probe); TCP-only check (doesn't prove DB connectivity).

## D7 — Restart & reboot survival

- **Decision**: All services use `restart: unless-stopped`; Docker is enabled on boot
  (`systemctl enable docker`). Postgres readiness gates the backend via `depends_on` + `db`
  healthcheck (`pg_isready`).
- **Rationale**: Satisfies FR-007 and SC-008 — after a crash or reboot the stack returns to a healthy
  serving state with no operator action.
- **Alternatives considered**: `restart: always` (would fight an intentional operator stop);
  external process supervisor (redundant with Docker's own policy).

## D8 — Backups: encrypted `pg_dump`, restore to a clean host

- **Decision**: `ops/backup.sh` runs `pg_dump -Fc` inside the `db` container and pipes through `age`
  to a timestamped, encrypted artifact in a host backup dir; `ops/restore.sh` reverses it
  (`age -d | pg_restore`) into a clean instance. Both documented in the runbook with a verification
  restore.
- **Rationale**: FR-008 + Principle I require encrypted, restorable, portable backups. `-Fc` custom
  format restores cleanly onto a fresh host (edge case "restore onto a different machine"). `age` is a
  single static binary — simple for the operator and stronger than a passphrase-only dump.
- **Alternatives considered**: Plain unencrypted `pg_dump` (violates Principle I); volume snapshots
  (host-specific, not portable, fails the clean-host restore requirement); managed DB PITR
  (out of scope — self-hosted single node).

## D9 — Updates with brief downtime

- **Decision**: Update procedure = `git pull` → `docker compose build` → `docker compose up -d`.
  The new backend container runs migrations on start before replacing the old one; data persists in
  the `pgdata` volume. Documented with a pre-update backup step.
- **Rationale**: FR-009 + SC-005 (< 5 min downtime, data preserved, migrations auto-applied). Volume
  persistence guarantees existing appointments/accounts survive image rebuilds.
- **Alternatives considered**: Blue-green / rolling deploy (needs >1 host or an orchestrator — out of
  scope at pilot); in-place `pip install` upgrades (non-reproducible, violates FR-012).

## D10 — Logs & maintenance page

- **Decision**: Application logs go to stdout/stderr, read via `docker compose logs` (operator's log
  surface); the existing `PhiRedactionFilter` keeps PHI out. Caddy serves `maintenance.html` (a
  plain, non-technical page) when the backend upstream is down, and never exposes stack traces to end
  users (the API already returns structured `Error` bodies).
- **Rationale**: FR-013 (accessible logs, no PHI/secrets) and FR-015 (clean maintenance/error page).
- **Alternatives considered**: Centralized logging stack (ELK/Loki) — out of scope for a pilot,
  Principle VI; exposing FastAPI debug errors (would leak internals — forbidden).

## Resolved unknowns summary

| Unknown | Resolution |
|---------|------------|
| Hosting model | Single Linux VM, Docker Compose (D1) |
| TLS / domain | Caddy automatic HTTPS, operator `DOMAIN` (D2) |
| API/SPA origin | Single shared origin, first-party cookie (D3) |
| Schema init/migrations | Migrate-on-start entrypoint (D4) |
| Secrets delivery | Gitignored `deploy/.env`, fail-fast (D5) |
| Health status | New `GET /api/v1/health` (D6) |
| Reboot survival | `restart: unless-stopped` + boot-enabled Docker (D7) |
| Backup/restore | Encrypted `pg_dump`+`age`, clean-host restore (D8) |
| Updates | git pull + compose build/up, migrate-on-start (D9) |
| Logs / error page | `docker compose logs` (PHI-redacted) + Caddy maintenance page (D10) |
