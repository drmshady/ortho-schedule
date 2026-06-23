# Phase 0 Research: Clinic Patient Scheduling

This document resolves the technical unknowns for the implementation plan. The spec was
already clarified (see spec.md "Clarifications"); remaining unknowns are technology and
pattern choices. Each decision is recorded as Decision / Rationale / Alternatives considered.

## 1. Backend language & framework

- **Decision**: Python 3.12 with FastAPI (async), SQLAlchemy 2.0 async ORM, Pydantic v2 for
  validation, Alembic for migrations.
- **Rationale**: FastAPI gives first-class server-side validation (Pydantic), OpenAPI
  generation (drives our contract tests and the typed frontend client), and dependency
  injection that cleanly hosts the `CenterScope` tenant guard required by Principle II.
  Matches the operator's existing Python toolchain.
- **Alternatives considered**: Node/Express + Zod (viable, but weaker built-in OpenAPI +
  validation story); Django (heavier; its ORM/admin add scope we don't need for an MVP per
  Principle VI). Rejected to keep the smallest correct slice.

## 2. Datastore & the no-double-booking invariant

- **Decision**: PostgreSQL 16. Model each appointment's occupied time as a `tstzrange`
  `period` column and enforce non-overlap per doctor with a GiST **exclusion constraint**
  (`EXCLUDE USING gist (doctor_id WITH =, period WITH &&) WHERE (status = 'scheduled')`),
  enabled via the `btree_gist` extension. Booking runs inside a single transaction.
- **Rationale**: Principle IV demands atomic, concurrency-safe booking. A database exclusion
  constraint makes double-booking *impossible* even under simultaneous requests — the second
  transaction fails on commit — rather than relying on application-level check-then-insert,
  which is racy. `timestamptz` satisfies the UTC-canonical requirement.
- **Alternatives considered**: SQLite (no exclusion constraints, weak concurrent writes — see
  Complexity Tracking); application-level locking / `SELECT … FOR UPDATE` over a slot table
  (works but more code and easier to get wrong than a declarative constraint); optimistic
  retries only (still needs a DB invariant as backstop). The exclusion constraint is the
  minimal, strongest option.

## 3. Fixed-grid slot model

- **Decision**: Store a per-center/per-doctor `grid_minutes` (default 15). An appointment has
  a `starts_at` aligned to the grid and a `duration_minutes` that is a positive multiple of
  `grid_minutes`; `period = [starts_at, starts_at + duration)`. Validation: start alignment,
  duration is a grid multiple, period within resolved availability, no overlap (constraint).
- **Rationale**: Directly implements FR-019a (fixed base grid, variable length). Keeping the
  grid size as data (not hard-coded) honors "configurable per center/doctor." Deriving
  `period` from start+duration lets the single exclusion constraint cover any-length overlaps
  (FR-020).
- **Alternatives considered**: Materializing one row per grid unit (simpler overlap query but
  far more rows and bookkeeping; rejected for low-thousands/month scale and complexity).

## 4. Doctor availability resolution

- **Decision**: Two tables — `availability_template` (recurring weekly: weekday + start/end
  local time, per doctor) and `availability_exception` (a specific date that either blocks
  time off / a holiday, or adds/overrides hours). A pure `AvailabilityResolver` service
  computes the bookable intervals for a doctor on a given date: start from the weekday
  template, then apply that date's exceptions (override/add/remove). Booking validates the
  requested period falls entirely inside a resolved bookable interval.
- **Rationale**: Matches the clarified model (FR-012: weekly template + date-specific
  exceptions). A pure resolver function is trivially unit-testable (Principle V) and keeps
  timezone math in one place: templates/exceptions are authored in center-local time and
  converted to UTC for comparison.
- **Alternatives considered**: A single flattened "open slots" table regenerated nightly
  (stateful, needs a job; rejected — YAGNI); RRULE/iCal recurrence (overkill for weekly-only
  patterns in v1).

## 5. Authentication & session model

- **Decision**: Server-side sessions via a signed, HTTP-only, `Secure`, `SameSite=Strict`
  session cookie; session record holds `user_id` and the resolved `center_id` (active center
  scope). Passwords hashed with Argon2id (`argon2-cffi`). First-login forced password change
  enforced by a `must_change_password` flag gating all non-password endpoints. Super-admin
  sessions carry no center scope and are limited to cross-center provisioning endpoints.
- **Rationale**: Constitution mandates session-based auth, center-scoped sessions (Principle
  II), Argon2/bcrypt hashing, and OWASP-aligned session management. Server-side sessions make
  deactivation/suspension effective immediately (revoke session) — needed for FR-006/center
  suspension. Implements FR-004a (temp password + forced change).
- **Alternatives considered**: Stateless JWT (revocation is awkward — a deactivated user's
  token stays valid until expiry, conflicting with immediate suspension; rejected). OAuth/SSO
  (no external IdP requirement in v1; YAGNI).

## 6. Tenant isolation enforcement pattern

- **Decision**: (a) Every tenant-owned table has a non-null `center_id` FK. (b) A FastAPI
  `CenterScope` dependency reads the session's center and is a required argument of every
  tenant-scoped route; repository/query helpers always filter by it. (c) Default-deny: a
  non-super-admin request without a resolvable center scope returns 403 and no data;
  cross-center id references are rejected. (d) Defense-in-depth: enable PostgreSQL Row-Level
  Security with a `current_setting('app.center_id')` policy set per transaction, so even a
  missed `WHERE` cannot leak rows.
- **Rationale**: Principle II requires server-enforced, default-deny isolation with tests for
  cross-tenant attempts. App-level scoping is primary; RLS is a cheap backstop that turns an
  accidental unscoped query into zero rows instead of a leak.
- **Alternatives considered**: Database-per-tenant (strongest isolation but heavy ops for ~10
  centers; rejected — YAGNI/scale); schema-per-tenant (migration and connection complexity;
  rejected). Shared-schema + `center_id` + RLS is the standard, simplest compliant choice at
  this scale.

## 7. In-app notifications

- **Decision**: A `notification` table (recipient user, type, payload, read/unread,
  created_at) written transactionally when request/appointment events occur. Frontend polls a
  `GET /notifications` endpoint (e.g., every 30–60 s) and shows unread counts/badges.
- **Rationale**: FR-026/Principle VI — in-app only, no external messaging, no broker. Polling
  at pilot scale (~50 users) is trivial and avoids WebSocket/infra complexity. Covers FR-017
  (notify doctor on fulfill/decline) and request-queue surfacing.
- **Alternatives considered**: WebSockets/SSE for realtime (adds infra and connection
  management; unjustified at this scale — defer); external push (explicitly out of scope).

## 8. Frontend stack & accessible calendar

- **Decision**: React 18 + TypeScript + Vite; React Router; TanStack Query for server state;
  Radix UI primitives + Tailwind for WCAG-AA-compliant, keyboard-accessible components;
  FullCalendar for day/week doctor calendars and the center day view; a shared `<Abbr>`
  component backed by a single `glossary.ts` for the mandatory abbreviation tooltips. A typed
  API client is generated from `contracts/openapi.yaml`.
- **Rationale**: Principle III requires responsive, keyboard-reachable, WCAG-AA UI with
  abbreviation tooltips. Radix gives accessible focus/contrast primitives; FullCalendar is a
  mature, keyboard-navigable scheduling view. Generating the client from the contract keeps
  frontend and backend in lockstep and supports contract-first testing.
- **Alternatives considered**: Material UI / Mantine (heavier opinionated themes; Radix +
  Tailwind is leaner and easier to meet contrast requirements explicitly); building a calendar
  from scratch (reinvents accessibility-sensitive interactions; rejected).

## 9. Localization & time handling

- **Decision**: English-only UI strings in v1 (no i18n framework yet, but copy kept in one
  module to ease later extraction); currency formatted as EGP and dates/numbers via
  `Intl.*` with the Egypt locale. Each center has a single IANA timezone; all instants stored
  as UTC `timestamptz`; conversion to/from center-local happens at the edges (availability
  authoring, calendar display, booking grid alignment).
- **Rationale**: Constitution sets English-first, EGP, locale formatting, no RTL in v1, and
  UTC-canonical timezone-aware storage with one timezone per center.
- **Alternatives considered**: Full i18n (Arabic/RTL) now — explicitly deferred by the
  constitution and spec; storing local time without offset (rejected — violates UTC-canonical
  rule and breaks DST-safe comparisons).

## 10. Testing strategy

- **Decision**: Backend pytest + pytest-asyncio with httpx `AsyncClient` against an ephemeral
  Postgres (testcontainers or a disposable docker db) so the exclusion constraint and RLS are
  exercised for real; contract tests generated from `openapi.yaml`; integration tests for the
  three NON-NEGOTIABLE paths — concurrent booking contention, cross-tenant access attempts,
  and auth/forced-password-change. Frontend Vitest + React Testing Library; Playwright e2e
  covering the spec's acceptance scenarios across roles. CI runs everything and blocks merge.
- **Rationale**: Principle V mandates red-green, with explicit concurrency and isolation
  tests; testing against real Postgres is the only way to prove the DB-level invariants.
- **Alternatives considered**: SQLite-in-memory for speed (would not exercise the exclusion
  constraint/RLS — defeats the purpose; rejected for those paths). Mock-only API tests
  (cannot prove integrity invariants).

## Resolved unknowns summary

| Unknown (from Technical Context) | Resolution |
|----------------------------------|------------|
| Backend language/framework | Python 3.12 + FastAPI |
| Storage + booking atomicity | PostgreSQL 16, GiST exclusion constraint + transactions |
| Slot/grid model | start-aligned + duration multiple of `grid_minutes`, `tstzrange` period |
| Availability model | weekly template + date exceptions, pure resolver service |
| Auth/session | server-side center-scoped session cookie, Argon2id, forced first-login change |
| Tenant isolation | `center_id` everywhere + CenterScope guard + default-deny + RLS backstop |
| Notifications | in-app `notification` table + polling |
| Frontend stack | React+TS+Vite, Radix+Tailwind, FullCalendar, generated typed client |
| Localization/time | English-first, EGP/locale formatting, UTC `timestamptz`, per-center tz |
| Testing | pytest/httpx against real Postgres, Vitest/RTL, Playwright, CI gate |

No NEEDS CLARIFICATION items remain.
