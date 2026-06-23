# Implementation Plan: Deploy Clinic Scheduling App to Production

**Branch**: `002-deploy-app` | **Date**: 2026-06-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-deploy-app/spec.md`

## Summary

Make the existing `001-clinic-scheduling` application (FastAPI backend + React/Vite SPA +
PostgreSQL 16) publicly reachable, secure, and operable on a single Linux server, and hand the
operator a verifiable, step-by-step runbook to stand it up and keep it running.

Technical approach: ship the app as a **single-host Docker Compose** stack — `caddy` (automatic
HTTPS via Let's Encrypt + reverse proxy + static SPA host + maintenance page), `backend`
(uvicorn/FastAPI, runs `alembic upgrade head` on start), and `db` (PostgreSQL 16 with
`btree_gist`, named volume). One public origin terminates TLS at Caddy and serves the built SPA
plus `/api/*` from the same domain, so the center-scoped session cookie stays first-party and
`COOKIE_SECURE=true` works without CORS. Secrets are injected at deploy time from a gitignored
root `.env`; the backend already refuses to start on a missing/short `SESSION_SECRET`. Operations
(first-run schema + bootstrap super-admin, health checks, encrypted `pg_dump` backups + restore,
zero-config-change updates, restart-on-reboot) are delivered as Compose policies plus documented,
verification-gated commands. Two small code additions are required: an unauthenticated
`GET /api/v1/health` DB-liveness endpoint (FR-006) and a Caddy maintenance/error page (FR-015).

## Technical Context

**Language/Version**: Deploys the existing app — backend Python 3.12, frontend TypeScript 5.x /
React 18 — unchanged. New deployment tooling: Docker Engine 26+ with Compose v2, Caddy 2.x.
**Primary Dependencies**: Docker + Docker Compose plugin; Caddy 2 (automatic ACME HTTPS); existing
runtime deps (uvicorn, SQLAlchemy 2.0 async, Alembic, `psycopg` v3, argon2-cffi); `pg_dump`/
`pg_restore` (in the `postgres:16` image) + `age` for backup encryption.
**Storage**: PostgreSQL 16 in a named Docker volume (`pgdata`); Caddy persists certificates/keys
in its own named volume (`caddy_data`). Encrypted backup artifacts written to a host directory.
**Testing**: The existing `pytest` / Vitest / Playwright suites are the merge gate (run before
building images). Deployment itself is verified by **smoke checks** baked into the runbook: TLS/cert
validation, `/api/v1/health`, seeded-admin login + one booking, a concurrent double-booking attempt,
and a cross-center access attempt (SC-003, SC-006).
**Target Platform**: A single internet-reachable Linux VM, Ubuntu 22.04/24.04 LTS, with inbound
80/443 and SSH; Docker-capable. No Kubernetes, no managed PaaS, no multi-node. Host-agnostic; the
recommended **free** host for the first single-clinic deploy is an **Oracle Cloud "Always Free"
Ampere A1 (ARM/aarch64) VM** (real VM → self-hosted Postgres 16 + `btree_gist` works unchanged;
free PaaS tiers are rejected because their free Postgres expires and web dynos sleep). Images build
natively for `linux/arm64`; Oracle requires opening 80/443 in both the OCI Security List/NSG and the
instance `iptables`, and keeping backups off-box since idle Always-Free instances may be reclaimed.
Production parity path: a ~€4–5/mo x86 Hetzner VM runs the identical Compose stack.
**Project Type**: Single-host containerized web-app deployment (adds `deploy/` to the existing
`backend/` + `frontend/` repo).
**Performance Goals**: Operational, not throughput — go-live in < 60 min by guide alone (SC-001);
update with < 5 min user-visible downtime (SC-005); restore in < 30 min, zero data loss (SC-004);
automatic healthy return after reboot (SC-008). Pilot load ~50 concurrent users on one host.
**Constraints**: HTTPS-only with a valid auto-renewing cert, HTTP→HTTPS redirect (FR-002); no
secret or PHI in committed files, logs, or user-facing errors (FR-003/013, Principle I); fail-fast
on missing/placeholder secrets (FR-003); single public origin so the session cookie is first-party;
every constitution behavior gate preserved in production (FR-010).
**Scale/Scope**: ~10 centers, ~50 concurrent users, low-thousands of appointments/month — a single
server is sufficient per the spec assumptions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This feature ships no new product behavior; its gate obligation is to **preserve every existing
gate in the production runtime** (FR-010) and add no new isolation/security regressions.

| # | Principle | How this deployment plan satisfies it | Status |
|---|-----------|----------------------------------------|--------|
| I | Patient Data Security & Privacy (NON-NEGOTIABLE) | TLS 1.2+ terminated at Caddy with auto-renewing cert and HTTP→HTTPS redirect (TLS in transit); PostgreSQL volume on an encrypted-at-rest host disk + encrypted backups (`age`); all secrets injected from a gitignored `.env`, backend fails fast on missing/short `SESSION_SECRET`; existing `PhiRedactionFilter` keeps PHI out of logs and `docker compose logs` is the only log surface; no default credentials — super-admin bootstrapped with a one-time, must-change password | PASS |
| II | Multi-Tenant Isolation (NON-NEGOTIABLE) | Deployment changes none of the server-side `center_id` scoping, default-deny guard, or RLS backstop (migration `0003`) — they ship as-is; the runbook's go-live smoke test includes a cross-center access attempt that must be denied (SC-006) | PASS |
| III | Web-First, Accessible & Localized Experience | Same built SPA served byte-for-byte from `frontend/dist` behind Caddy; single-origin so locale/EGP formatting and keyboard flows are unchanged; a non-technical maintenance page is shown when the backend is down (FR-015) | PASS |
| IV | Appointment Integrity & Prioritization | The GiST exclusion constraint and atomic-booking transactions live in Postgres and migrations, deployed unchanged; `alembic upgrade head` runs automatically before the API serves traffic so the schema (incl. the constraint) is always present; go-live smoke test runs a concurrent double-booking attempt (SC-006); UTC storage unaffected | PASS |
| V | Test-First Quality Gates | The existing suite (isolation, booking concurrency, auth) is the pre-build gate; new code (`/health` endpoint, settings) gets a test before merge; deployment adds verification checks per runbook step (SC-002) rather than weakening any test | PASS |
| VI | MVP Simplicity (YAGNI) | Three long-running services on one host, one datastore, no orchestrator/CI-CD/message broker; Caddy chosen specifically because it collapses TLS + reverse proxy + static host + maintenance page into one dependency a non-DevOps operator can run; deviations tracked below (none requiring justification) | PASS |

**Security & Compliance gates**: secrets via env only (never committed) — `.gitignore` already
excludes `.env`/`.env.*`; OWASP-aligned session/cookie hardened in prod (`COOKIE_SECURE=true`,
`Secure`/`HttpOnly` first-party cookie); server remains the authority for authz/scope; `pip-audit`
(already a dev dep) is the documented pre-release dependency scan; encrypted backups + a documented
restore/retention procedure (FR-008, Security & Compliance §); PDPL/MoHP pilot posture recorded in
the spec Assumptions. No violations requiring justification.

**Result**: PASS (initial). Re-evaluated after Phase 1 design — still PASS (see end of plan).

## Project Structure

### Documentation (this feature)

```text
specs/002-deploy-app/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output — deployment decisions & rationale
├── data-model.md        # Phase 1 output — deployment entities (env, secrets, backup, release)
├── quickstart.md        # Phase 1 output — the operator runbook (the US2 deliverable)
├── contracts/           # Phase 1 output
│   └── deployment.md     # Compose service contract, env-var contract, ops endpoint/CLI contracts
├── checklists/
│   └── requirements.md   # (already present)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

```text
deploy/                          # NEW — all deployment artifacts live here
├── docker-compose.yml           # caddy + backend + db services, volumes, restart policy
├── Caddyfile                    # TLS (auto-HTTPS), HTTP→HTTPS, SPA static, /api reverse proxy,
│                                #   maintenance page on backend down
├── .env.example                 # documented template (DOMAIN, secrets, superadmin) — committed
├── .env                         # real secrets — gitignored, created on the server
├── backend.Dockerfile           # builds the FastAPI image; entrypoint: alembic upgrade head → uvicorn
├── frontend.Dockerfile          # builds the SPA (npm ci && npm run build) → static dist artifact
├── entrypoint.sh                # migrate-then-serve for the backend container
├── maintenance.html             # non-technical "temporarily unavailable" page (FR-015)
└── ops/
    ├── backup.sh                # pg_dump | age → encrypted, timestamped artifact (FR-008)
    └── restore.sh               # age -d | pg_restore into a clean instance (FR-008)

backend/                         # existing — minimal additions only
└── src/
    ├── api/health.py            # NEW — GET /api/v1/health (DB liveness, unauthenticated) (FR-006)
    ├── main.py                  # include health_router
    └── core/config.py           # (already enforces secret presence; no change expected)
```

**Structure Decision**: Add a single top-level `deploy/` directory holding the entire stack
definition, keeping deployment concerns out of `backend/` and `frontend/` (Principle VI — the app
projects stay deployment-agnostic). The only application-source changes are the additive
`/api/v1/health` endpoint and its router wiring; everything else is configuration and the runbook.
Caddy is the single front door (TLS + static SPA + `/api` proxy + maintenance page), which is why
the topology stays at three services and one datastore.

## Complexity Tracking

> No constitution violations require justification. Choices recorded for transparency.

| Choice | Why Needed | Simpler Alternative Rejected Because |
|--------|------------|--------------------------------------|
| Caddy as front door | Automatic, auto-renewing Let's Encrypt HTTPS + reverse proxy + static host + maintenance page in one config a non-DevOps operator can run (FR-002, FR-011, FR-015) | nginx + certbot needs a separate cert-renewal cron/timer and more moving parts; Traefik adds label/router complexity unneeded at one host |
| Migrate-on-start entrypoint (`alembic upgrade head` → uvicorn) | First-run schema init and per-deploy migrations with no manual SQL (FR-004); keeps the running instance from serving a half-upgraded schema | A separate manual migration step is an undocumented foot-gun for the operator and risks a serving instance on a stale schema |
| `age`-encrypted `pg_dump` backups | Encrypted, restorable, portable to a clean host (FR-008, Security & Compliance §) | Plain `pg_dump` is unencrypted (violates Principle I); volume snapshots are host-specific and not portable per the spec edge case |
