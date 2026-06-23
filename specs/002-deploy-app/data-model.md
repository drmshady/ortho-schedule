# Phase 1 Data Model: Deployment Entities

This feature adds **no application data entities** — the product schema is owned by
`001-clinic-scheduling` and is deployed unchanged. The "entities" here are the **deployment-time
artifacts and configuration objects** the operator works with. Each maps to a spec Key Entity and to
the concrete file/resource that realizes it.

## E1 — Deployment Environment

The target server and its running stack.

| Attribute | Value / Source | Notes |
|-----------|----------------|-------|
| Host | Single Linux VM (Ubuntu 22.04/24.04 LTS), x86_64 | Inbound 80/443 + SSH |
| Public origin | `https://<DOMAIN>` | One origin for SPA + `/api/*` (research D3) |
| Services | `caddy`, `backend`, `db` | `deploy/docker-compose.yml` |
| Volumes | `pgdata` (Postgres), `caddy_data` (certs) | Named, survive container recreation |
| Restart policy | `unless-stopped` (all services) | FR-007, SC-008 |

**State**: `not-provisioned → provisioned → configured → live → healthy`. Each transition has a
runbook verification gate (SC-002).

## E2 — Configuration & Secrets

Environment-specific values and protected credentials, injected at deploy time.

| Key | Classification | Required | Validation | Source of truth |
|-----|----------------|----------|------------|-----------------|
| `DOMAIN` | public | yes | resolvable A/AAAA → host IP before cert issuance | `deploy/.env` |
| `DATABASE_URL` | secret | yes | must start `postgresql+psycopg://` (enforced in `core/config.py`) | `deploy/.env` |
| `POSTGRES_PASSWORD` | secret | yes | non-empty, strong; matches `DATABASE_URL` | `deploy/.env` |
| `SESSION_SECRET` | secret | yes | ≥ 16 chars, non-placeholder (fail-fast in `core/config.py`) | `deploy/.env` |
| `COOKIE_SECURE` | internal | yes (prod) | `true` in production | `deploy/.env` |
| `SUPERADMIN_EMAIL` | internal | first-run | valid email | `deploy/.env` (bootstrap only) |
| `SUPERADMIN_PASSWORD` | secret | first-run | ≥ 12 chars; one-time, must-change | `deploy/.env` (bootstrap only) |
| `BACKUP_AGE_RECIPIENT` | secret | for backups | valid `age` public key | `deploy/.env` |

**Rules**: lives only in `deploy/.env` (gitignored); never committed (FR-003, Principle I); the
backend refuses to start if `SESSION_SECRET`/`DATABASE_URL` are missing or invalid; `deploy/.env.example`
is the committed, secret-free template.

## E3 — Backup Artifact

A restorable, encrypted copy of all persistent data.

| Attribute | Value | Notes |
|-----------|-------|-------|
| Format | `pg_dump -Fc` (custom) piped through `age` | Portable to a clean host (FR-008 edge case) |
| Naming | `clinic-YYYYMMDDTHHMMSSZ.dump.age` | UTC timestamp = creation time + known location |
| Location | Host backup dir (e.g. `/srv/clinic/backups/`), known to operator | FR-008 |
| Encryption | `age` recipient = `BACKUP_AGE_RECIPIENT` | Principle I, Security & Compliance § |
| Restore target | A clean instance (fresh `db` + empty `pgdata`) | Verified in runbook |

**State**: `created → encrypted-at-rest → (verified by test-restore) → retained/expired`. Retention
and erasure follow the constitution's documented policy (Security & Compliance §).

## E4 — Release / Version

A deployable build of the application.

| Attribute | Value | Notes |
|-----------|-------|-------|
| Identity | Git commit / tag on `main` | Reproducible (FR-012) |
| Images | `backend` + built SPA static (`frontend/dist`) | `docker compose build` |
| Carries | Pending Alembic migrations (auto-applied on start) | FR-004, FR-009 |
| Rollback (conceptual) | Re-deploy prior commit + restore pre-update backup if needed | SC-005 |

**State**: `built → migrated → serving`. Deploying a release preserves the `pgdata` volume so
existing data survives (SC-005).

## E5 — Deployment Guide / Runbook

The ordered, verifiable operator instructions.

| Attribute | Value | Notes |
|-----------|-------|-------|
| Location | `specs/002-deploy-app/quickstart.md` | The US2 deliverable |
| Coverage | provision → configure → go-live → verify → backup/restore → update | FR-011 |
| Per-step gate | every step ends with a concrete check (command/URL/status) | SC-002 = 100% |
| Failure aid | each step lists likely symptom + corrective action | Spec edge cases |

## Mapping to spec Key Entities

| Spec Key Entity | Data-model entity |
|-----------------|-------------------|
| Deployment environment | E1 |
| Configuration & secrets | E2 |
| Backup artifact | E3 |
| Release/version | E4 |
| Deployment guide / runbook | E5 |
