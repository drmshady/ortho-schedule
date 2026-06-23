# Implementation Plan: Clinic Patient Scheduling

**Branch**: `001-clinic-scheduling` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-clinic-scheduling/spec.md`

## Summary

A multi-tenant web application that lets clinic reception staff book patients into doctors'
calendars, lets doctors hand off appointment requests to reception, and lets center admins
and a platform super-admin manage staff and centers — with strict per-center data isolation,
atomic (no-double-booking) scheduling on a fixed time grid, in-app notifications, and
patient privacy/security as gates.

Technical approach: a Python/FastAPI backend with PostgreSQL (ACID transactions and a GiST
exclusion constraint enforce the no-double-booking invariant at the database layer; a
mandatory `center_id` scope on every tenant-owned row, enforced server-side with a
default-deny query guard, provides tenant isolation), session-cookie authentication with
Argon2 password hashing, and a React + TypeScript single-page frontend (Vite) with an
accessible calendar UI. All timestamps are stored as UTC `timestamptz`; the booking grid and
display honor each center's single local timezone.

## Technical Context

**Language/Version**: Backend Python 3.12; Frontend TypeScript 5.x (React 18)
**Primary Dependencies**: Backend — FastAPI, SQLAlchemy 2.0 (async), Alembic, `argon2-cffi`,
Pydantic v2, `psycopg` (v3); Frontend — React 18, Vite, React Router, TanStack Query, a
WCAG-AA-friendly component layer (Radix UI primitives + Tailwind), FullCalendar for calendar views
**Storage**: PostgreSQL 16 (uses `timestamptz`, `btree_gist` extension for the booking
exclusion constraint, transactions for atomic booking)
**Testing**: Backend — pytest, pytest-asyncio, httpx `AsyncClient`, testcontainers/ephemeral
Postgres; Frontend — Vitest + React Testing Library; End-to-end — Playwright
**Target Platform**: Linux server (containerized) serving an HTTPS API + static SPA; current
desktop and mobile browsers
**Project Type**: Web application (separate `backend/` and `frontend/` projects)
**Performance Goals**: Pilot scale — API p95 < 200 ms for booking/list endpoints under ~50
concurrent users; calendar day view renders < 1 s; supports the success-criteria timings
(book < 90 s, patient lookup < 10 s) which are dominated by UI, not server latency
**Constraints**: TLS 1.2+ in transit and encryption at rest (deployment/infra); server is the
sole authority for authorization and tenant scope; default-deny on unscoped queries; UTC
canonical time storage; English-first UI with EGP/locale formatting (no RTL in v1); in-app
notifications only (no SMS/email/WhatsApp)
**Scale/Scope**: ~10 centers, ~50 concurrent users, low-thousands of appointments/month; 4
roles; ~7 core entities; roughly 25–30 API endpoints and ~12–15 frontend screens

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | How this plan satisfies it | Status |
|---|-----------|----------------------------|--------|
| I | Patient Data Security & Privacy (NON-NEGOTIABLE) | TLS + at-rest encryption at infra layer; Argon2 password hashing; role-based authz on every endpoint; immutable audit log table (`audit_event`) records every patient-data read/write and cross-center action; secrets via env/secret manager (never committed); no PHI in logs/errors (structured logging redacts patient fields); data classification recorded per field in data-model.md | PASS |
| II | Multi-Tenant Isolation (NON-NEGOTIABLE) | Every tenant-owned row carries non-null `center_id`; a server-side `CenterScope` dependency derives scope from the session and is applied to every query; default-deny — any query that cannot establish scope returns nothing/403; only super-admin operates cross-center, audited; cross-tenant access tests are mandatory (Principle V) | PASS |
| III | Web-First, Accessible & Localized Experience | Responsive React SPA; keyboard-reachable scheduling flows; WCAG 2.1 AA contrast/focus via Radix primitives; abbreviation tooltips via a shared `<Abbr>` + glossary; English-first UI with EGP currency + locale date/number formatting; no patient logins | PASS |
| IV | Appointment Integrity & Prioritization | Atomic booking via DB transaction + GiST exclusion constraint on `(doctor_id, period)` for active appointments (no double-booking under concurrency); explicit doctor→reception request handoff (only reception confirms); `urgency` is an explicit auditable column driving queue ordering; validated state-machine transitions recorded with timestamp + actor; bookings validated against weekly availability + date exceptions; cancellations retained (status, not delete); UTC storage | PASS |
| V | Test-First Quality Gates | Contracts generate failing contract tests first; mandatory tests for tenant isolation (cross-center attempts), booking concurrency/contention, and auth before merge; red-green discipline; CI runs full suite and blocks on failure | PASS |
| VI | MVP Simplicity (YAGNI) | Two deployables only (API + SPA), one datastore (Postgres); no message broker, no microservices, no external messaging; patient-merge reduced to duplicate detection; complexity additions tracked below | PASS |

**Security & Compliance gates**: data classification per field (data-model.md), OWASP-aligned
session/auth, server-side input validation (Pydantic), dependency scanning in CI, encrypted
backups + retention/erasure policy noted for ops, PDPL/MoHP/Dental-Syndicate considerations
recorded. No violations requiring justification.

**Result**: PASS (initial). Re-evaluated after Phase 1 design — still PASS (see end of plan).

## Project Structure

### Documentation (this feature)

```text
specs/001-clinic-scheduling/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── openapi.yaml      # REST API contract (all endpoints)
│   └── README.md         # How contracts map to contract tests
├── checklists/
│   └── requirements.md   # (already present)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── core/             # config, security (argon2, sessions), db engine/session, timezone
│   ├── tenancy/          # CenterScope dependency, default-deny query guard, audit log writer
│   ├── models/           # SQLAlchemy ORM models (Center, User, Patient, Appointment, ...)
│   ├── schemas/          # Pydantic request/response models
│   ├── services/         # booking engine, availability resolver, request workflow, notifications
│   ├── api/              # FastAPI routers (auth, centers, users, patients, availability,
│   │                     #   requests, appointments, notifications)
│   └── main.py           # app assembly, middleware (HTTPS/security headers), error handling
├── migrations/           # Alembic migrations (incl. btree_gist + exclusion constraint)
└── tests/
    ├── contract/         # generated from contracts/openapi.yaml
    ├── integration/      # booking concurrency, tenant isolation, request handoff, auth flows
    └── unit/             # availability resolver, grid math, state-machine validators

frontend/
├── src/
│   ├── api/              # typed client (generated from openapi.yaml), TanStack Query hooks
│   ├── components/       # Abbr, calendar, queue, forms, role-gated nav, design primitives
│   ├── pages/            # login/force-change-pw, reception calendar, doctor schedule,
│   │                     #   request queue, admin staff mgmt, super-admin centers
│   ├── lib/              # auth/session context, locale/EGP formatting, glossary.ts
│   └── main.tsx
└── tests/                # Vitest + RTL component/integration tests

e2e/                      # Playwright cross-role scenarios (acceptance scenarios)
```

**Structure Decision**: Web application with two deployables — a `backend/` FastAPI service
and a `frontend/` React SPA — plus a top-level `e2e/` Playwright suite. This matches the
"frontend + backend" shape of the spec (staff-facing web UI over a secured, tenant-scoped
API) while keeping to two deployables and one datastore per Principle VI. The `backend/src/
tenancy/` package is isolated so the Principle II default-deny scope guard has a single,
testable home.

## Complexity Tracking

> No constitution violations require justification. The choices below are deliberately the
> simplest that satisfy NON-NEGOTIABLE principles, recorded here for transparency.

| Choice | Why Needed | Simpler Alternative Rejected Because |
|--------|------------|--------------------------------------|
| PostgreSQL (vs SQLite) | GiST exclusion constraint gives DB-enforced no-double-booking under concurrency (Principle IV) and robust `timestamptz`; transactions enforce atomic booking | SQLite lacks exclusion constraints and concurrent-write story; would push the integrity invariant into app code, weakening the Principle IV/V guarantee |
| Dedicated `audit_event` table | Principles I & II require an immutable record of patient-data access and cross-center actions | Application logs alone are mutable and risk leaking PHI; a structured table is the minimal compliant option |
