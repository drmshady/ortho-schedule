# API Contracts

`openapi.yaml` is the single source of truth for the Clinic Patient Scheduling REST API. It
drives two generated artifacts:

1. **Backend contract tests** (`backend/tests/contract/`) — one test per operation asserting
   status codes, request/response schema shape, and auth/scope behavior. These are written to
   **fail first** (no implementation), per Constitution Principle V (test-first).
2. **Frontend typed client** (`frontend/src/api/`) — generated types + fetch hooks so the SPA
   and API never drift.

## Conventions

- **Auth**: session cookie (`session`), HTTP-only, `Secure`, `SameSite=Strict`. All paths
  require it except `POST /auth/login`. The session carries the center scope.
- **Tenant scope (Principle II)**: every non-super-admin response is implicitly filtered to
  the caller's center server-side. Any reference to an id outside the caller's center returns
  `403` (default-deny) — never `404`-by-leak and never another center's data.
- **Times**: all `date-time` fields are UTC RFC 3339. `*_local` availability fields are
  center-local wall-clock strings resolved against the center timezone.
- **Error codes** (in `Error.code`) that contract/integration tests assert:
  - `409 double_booking` / `409 slot_taken` — concurrent or overlapping booking (FR-020).
  - `409 invalid_transition` — disallowed state-machine change (Principle IV).
  - `422 outside_availability` — period not within resolved availability (FR-013).
  - `422 off_grid` — start not grid-aligned or duration not a grid multiple (FR-019a).
  - `422 patient_conflict` — patient already booked in an overlapping time; resubmit with
    `confirm_patient_conflict=true` to proceed (FR-021, warn-not-block).
  - `409 possible_duplicate` — patient name+phone match; resubmit with
    `confirm_possible_duplicate=true` (FR-010).

## Mandatory integration tests beyond per-operation contract tests

These prove the NON-NEGOTIABLE principles and must accompany the endpoints they cover:

- **Cross-tenant isolation** (Principle II): a center-A user calling every list/detail/mutate
  endpoint with center-B ids receives `403`/empty — for users, patients, requests,
  appointments, availability, notifications.
- **Booking concurrency** (Principle IV): two simultaneous `POST /appointments` (or
  `/requests/{id}/fulfill`) for the same doctor/overlapping period — exactly one `201`, the
  other `409`.
- **Auth lifecycle**: forced password change on first login blocks other endpoints until
  done; deactivated user and suspended center are blocked at `/auth/login`.
- **Request handoff** (Principle IV): only `reception` can fulfill/decline; fulfilling creates
  the appointment, marks the request `fulfilled`, and emits the doctor notification.
