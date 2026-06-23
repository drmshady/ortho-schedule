---
description: "Task list for deploying the Clinic Scheduling app to production"
---

# Tasks: Deploy Clinic Scheduling App to Production

**Input**: Design documents from `/specs/002-deploy-app/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/deployment.md, quickstart.md

**Tests**: Test-First is a constitution gate (Principle V). The only NEW application code in this
feature is the `GET /api/v1/health` endpoint (contract C4), so a failing test for it is written
first. All other deployment artifacts are verified by the runbook's per-step **smoke checks**
(quickstart.md), not by automated unit tests.

**Organization**: Tasks are grouped by user story. US1 and US2 are both P1 and overlap heavily
(the artifacts US2's runbook drives are the same ones US1 needs to be reachable); shared build
plumbing therefore lives in the Foundational phase so each story stays independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, or US3 (maps to spec user stories)
- All paths are relative to the repository root (`e:\schedule`)

## Path Conventions

- Deployment artifacts: `deploy/` (new top-level directory)
- Application code: `backend/src/`, frontend build from `frontend/`
- Runbook: `specs/002-deploy-app/quickstart.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the deployment directory scaffolding and the committed, secret-free config template.

- [X] T001 Create the `deploy/` directory structure per plan.md (`deploy/` and `deploy/ops/`) so all subsequent deployment artifacts have a home
- [X] T002 [P] Create the committed env template `deploy/.env.example` documenting every variable from the C3 contract (`DOMAIN`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `SESSION_SECRET`, `COOKIE_SECURE`, `SUPERADMIN_EMAIL`, `SUPERADMIN_PASSWORD`, `BACKUP_AGE_RECIPIENT`) with safe placeholder values and inline comments â€” NO real secrets
- [X] T003 [P] Verify the root `.gitignore` excludes `.env` and `.env.*` (already present at `.gitignore:17-18`) and confirm `git check-ignore deploy/.env` would match (FR-003, SC-007)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The new app code (health endpoint) plus the container build/migrate/compose plumbing that **every** user story depends on. Nothing runs without these.

**âš ï¸ CRITICAL**: No user story work can begin until this phase is complete.

### New application code â€” health endpoint (Test-First, Principle V / contract C4)

- [X] T004 [P] Write the FAILING contract test for the health endpoint in `backend/tests/contract/test_health.py`: asserts `GET /api/v1/health` returns 200 + `{"status":"ok","database":"up"}` when the DB is up, returns 503 + `{"status":"degraded","database":"down"}` when the DB is unreachable, requires NO auth/session, and exposes no tenant/PHI fields
- [X] T005 Implement `GET /api/v1/health` in `backend/src/api/health.py`: unauthenticated router that runs `SELECT 1` via the async session and returns the 200/503 contract bodies (no internals leaked) â€” make T004 pass
- [X] T006 Wire `health_router` into the app in `backend/src/main.py` with `app.include_router(health_router, prefix="/api/v1")` alongside the existing routers (`backend/src/main.py:56-64`)

### Container build & migrate plumbing (shared by all stories)

- [X] T007 [P] Create `deploy/backend.Dockerfile` building the FastAPI image (Python 3.12 base, install backend deps, copy `backend/`), with `deploy/entrypoint.sh` as the entrypoint; must build natively on `linux/arm64` (Oracle host) and `linux/amd64`
- [X] T008 [P] Create `deploy/entrypoint.sh` implementing migrate-then-serve (research D4): run `alembic upgrade head`, abort startup on failure (never serve a half-upgraded schema), then `exec uvicorn src.main:app --host 0.0.0.0 --port 8000`
- [X] T009 [P] Create `deploy/frontend.Dockerfile` (or build stage) that runs `npm ci && npm run build` in `frontend/` and emits the static `frontend/dist` artifact for Caddy to serve
- [X] T010 Create `deploy/docker-compose.yml` per contract C1: services `caddy` (`caddy:2`, publishes 80/443, depends_on `backend`), `backend` (built image, internal `:8000`, depends_on `db` healthy, healthcheck `GET /api/v1/health`), `db` (`postgres:16`, internal `:5432`, healthcheck `pg_isready -U postgres`); named volumes `pgdata` and `caddy_data`; `restart: unless-stopped` on all three (FR-007, SC-008); env injected from `deploy/.env`

**Checkpoint**: Image builds, migrations run on start, and the stack definition exists â€” user stories can now proceed.

---

## Phase 3: User Story 1 - Get the app live and reachable by clinic staff (Priority: P1) ðŸŽ¯ MVP

**Goal**: A running production instance behind the operator's domain, served exclusively over HTTPS with a valid auto-renewing certificate, so staff can log in and book.

**Independent Test**: From a clean device outside the build environment, open the public URL, confirm the connection is encrypted (valid cert, no browser warning), log in as a seeded center admin, and complete one real booking that persists after reload.

### Implementation for User Story 1

- [X] T011 [US1] Create `deploy/Caddyfile` per contract C2: `<DOMAIN>` site block with automatic HTTPS (Let's Encrypt) + automatic HTTPâ†’HTTPS redirect (FR-002), `handle /api/*` â†’ `reverse_proxy backend:8000`, `handle` â†’ SPA static root `/srv/www` with `try_files {path} /index.html` history fallback, and `encode gzip`
- [X] T012 [P] [US1] Create `deploy/maintenance.html` â€” a plain, non-technical "temporarily unavailable" page (FR-015) â€” and wire Caddy `handle_errors` to serve it when the backend upstream is down
- [X] T013 [US1] Ensure Caddy serves the built SPA: mount/copy `frontend/dist` to `/srv/www` (read-only) in `deploy/docker-compose.yml` so the single origin serves SPA + `/api/*` first-party (research D3)
- [ ] T014 [US1] Verify the go-live smoke path from a device outside the build env (quickstart Steps 4â€“7): `docker compose up -d` brings `caddy`/`backend`/`db` to running/healthy; `https://<DOMAIN>` loads with a valid cert and no warning; HTTP redirects to HTTPS; seeded admin logs in and creates a booking that survives reload (SC-003); a concurrent double-booking attempt yields exactly one success and a cross-center read is denied (SC-006, FR-010)

**Checkpoint**: The app is live, secure, and usable â€” MVP delivered and independently testable.

---

## Phase 4: User Story 2 - Walk the operator through deployment step by step (Priority: P1)

**Goal**: A non-DevOps operator can stand up production confidently following only the written runbook, with every step gated by a verification check and equipped with failure remedies.

**Independent Test**: Following only `specs/002-deploy-app/quickstart.md` (no outside help), the operator provisions a fresh server and reaches a healthy deployment, each step confirmed before the next.

### Implementation for User Story 2

- [X] T015 [US2] Finalize `specs/002-deploy-app/quickstart.md` so 100% of steps end with a concrete ✅ Verify check (command/URL/status) and ⚠️ failure remedies (SC-002, FR-011), covering the edge cases in spec.md (DNS not propagated, cert issuance failure, missing/weak secret, migration fails mid-deploy, reboot, clean-host restore, first-run empty DB)
- [X] T016 [P] [US2] Reconcile `deploy/.env.example` with quickstart Step 3 so every variable the runbook tells the operator to set is documented in the template (and vice-versa), with secret-generation guidance (`openssl rand`, `age-keygen`)
- [X] T017 [US2] Cross-check every command and path in `quickstart.md` against the actual artifacts — compose service names (`backend`/`db`/`caddy`), script paths (`./ops/backup.sh`, `./ops/restore.sh`), the bootstrap command `docker compose exec backend python -m src.scripts.seed_superadmin`, and the health URL `/api/v1/health` — so the guide is reproducible on a fresh server (FR-012)
- [X] T018 [US2] Verify the bootstrap step (contract C6, FR-005): `seed_superadmin` reads `SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD`, prints `Super-admin created: …` on first run and `already exists` on re-run (idempotent), never logs the password, and the runbook's Step 6 verify matches that output (`backend/src/scripts/seed_superadmin.py:69-71`)

**Checkpoint**: An operator can follow the guide end-to-end to a healthy, verified deployment.

---

## Phase 5: User Story 3 - Keep the live system healthy, recoverable, and updatable (Priority: P2)

**Goal**: The production instance is observable, backed up with encrypted restorable backups, survives reboots automatically, and accepts new versions without data loss.

**Independent Test**: Trigger a backup, restore it into a fresh instance and confirm appointments/accounts/audit records are intact, then deploy a new version and confirm existing data is preserved and the new version serves traffic.

### Implementation for User Story 3

- [x] T019 [P] [US3] Create `deploy/ops/backup.sh` per contract C5: `pg_dump -Fc` inside the `db` container piped through `age` (recipient `BACKUP_AGE_RECIPIENT`) to `clinic-<UTC>.dump.age` in the host backup dir, printing the artifact path; abort with a clear message if the recipient is missing/invalid (Principle I, FR-008)
- [x] T020 [P] [US3] Create `deploy/ops/restore.sh <artifact>` per contract C5: `age -d` with the private identity piped to `pg_restore` into a clean `db` instance; usable on a fresh host (FR-008 clean-host edge case)
- [x] T021 [US3] Verify the health/observability surface (FR-006): operator can run `curl -s https://<DOMAIN>/api/v1/health` → `{"status":"ok","database":"up"}`, the backend Docker `healthcheck` reflects DB liveness, and `docker compose logs -f backend` is PHI-redacted and secret-free (FR-013)
- [x] T022 [US3] Verify reboot survival (FR-007, SC-008): with `restart: unless-stopped` set in compose (T010) and Docker enabled on boot, `sudo reboot` returns the stack to healthy with no operator action (quickstart Step 9)
- [x] T023 [US3] Verify the update procedure (FR-009, SC-005, quickstart Step 10): backup → `git pull` → `docker compose build` → `docker compose up -d` applies pending migrations automatically, preserves the `pgdata` volume (existing data intact), and keeps downtime under a few minutes
- [x] T024 [US3] Run the restore drill on a throwaway instance (SC-004): restore a backup and confirm appointment/account/audit row counts match the source (100% recovery, zero data loss)

**Checkpoint**: The deployment is observable, recoverable, and safely updatable â€” all stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final hardening and end-to-end validation across the whole deployment.

- [X] T025 [P] Run the pre-release dependency scan `pip-audit` on the backend (documented gate, plan.md Security & Compliance) and resolve/triage findings before building images
- [X] T026 [P] Run the existing `pytest` / Vitest / Playwright suites as the pre-build merge gate (plan.md Testing) — confirms isolation, booking-concurrency, and auth gates still pass before shipping images
- [X] T027 Inspect committed files, logs, and user-facing error output to confirm no secret or patient identifier is present (SC-007, FR-003/FR-013)
- [X] T028 Execute the full `quickstart.md` runbook on a fresh VM end-to-end and time it (target < 60 min to live, SC-001) — the definitive reproducibility + go-live validation (FR-012)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories (no stack runs without the image, entrypoint, and compose file; the health endpoint is consumed by the backend healthcheck and US1/US3 verifications).
- **User Stories (Phase 3â€“5)**: All depend on Foundational. Given one operator, run in priority order US1 â†’ US2 â†’ US3; with capacity, US1/US2/US3 artifacts can be authored in parallel.
- **Polish (Phase 6)**: Depends on all targeted stories being complete.

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational. The MVP.
- **US2 (P1)**: Depends on Foundational; its runbook references US1's `Caddyfile`/compose and US3's `ops/` scripts, so author US1/US3 artifacts before US2's final cross-check (T017) â€” but US2 is independently testable as "fresh server â†’ healthy via guide alone."
- **US3 (P2)**: Depends on Foundational (esp. T010 compose for restart policy + healthcheck); independently testable via backupâ†’restoreâ†’update drills.

### Within Each Story

- T004 (failing test) before T005/T006 (implementation).
- Models/config before the artifacts that consume them; compose (T010) before US1's SPA mount (T013) and US3's restart/health verifications.
- Verification tasks run last within their story.

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T004 (test) and the three build artifacts T007/T008/T009 in parallel; T005â†’T006 are sequential (same logical wiring); T010 after T007â€“T009 exist.
- US1: T012 parallel with T011/T013.
- US2: T016 parallel with the prose tasks.
- US3: T019 and T020 in parallel.
- Polish: T025, T026 in parallel.

---

## Parallel Example: Foundational Phase

```bash
# After T001 scaffolding, launch the independent build artifacts and the failing test together:
Task: "Write failing health endpoint contract test in backend/tests/contract/test_health.py"   # T004
Task: "Create deploy/backend.Dockerfile"                                                          # T007
Task: "Create deploy/entrypoint.sh (alembic upgrade head -> uvicorn)"                             # T008
Task: "Create deploy/frontend.Dockerfile (npm ci && npm run build -> dist)"                       # T009
# Then T005 -> T006 (health impl + wiring), then T010 (compose ties it together).
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (health endpoint + build/migrate/compose â€” CRITICAL, blocks all).
3. Complete Phase 3: User Story 1 (Caddyfile/TLS, SPA serving, maintenance page).
4. **STOP and VALIDATE**: from a clean device, load over HTTPS, log in, book, confirm double-booking + cross-center gates (T014).
5. This is a live, usable production instance â€” deploy/demo.

### Incremental Delivery

1. Setup + Foundational â†’ stack builds and migrates.
2. US1 â†’ live & secure (MVP) â†’ validate â†’ demo.
3. US2 â†’ operator can reproduce go-live from the runbook â†’ validate â†’ demo.
4. US3 â†’ backups, restore, reboot survival, updates â†’ validate â†’ demo.

---

## Notes

- [P] tasks = different files, no dependencies.
- The only new application code is the `/api/v1/health` endpoint (T004â€“T006); everything else is deployment config + the runbook.
- Each user story is independently testable per its Independent Test above.
- Verification/smoke tasks map to the constitution's NON-NEGOTIABLE gates (no double-booking, tenant isolation, no PHI/secrets in logs) â€” a gate failure is release-blocking.
- Commit after each task or logical group.
