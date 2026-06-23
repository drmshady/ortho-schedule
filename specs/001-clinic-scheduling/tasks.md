---
description: "Task list for Clinic Patient Scheduling implementation"
---

# Tasks: Clinic Patient Scheduling

**Input**: Design documents from `/specs/001-clinic-scheduling/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: INCLUDED. The constitution (Principle V, NON-NEGOTIABLE) and plan mandate
test-first development with explicit, gating tests for booking concurrency, cross-tenant
isolation, and auth/forced-password-change. Contract tests are generated from
`contracts/openapi.yaml`.

**Organization**: Tasks are grouped by user story (US1–US4) for independent implementation
and testing. Each story phase is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1, US2, US3, US4 — maps to the spec's user stories
- All paths assume the web-app structure from plan.md: `backend/`, `frontend/`, `e2e/`

## Path Conventions

- Backend: `backend/src/...`, `backend/tests/...`, `backend/migrations/...`
- Frontend: `frontend/src/...`, `frontend/tests/...`
- End-to-end: `e2e/...`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and tooling

- [X] T001 Create the monorepo structure (`backend/src/{core,tenancy,models,schemas,services,api}`, `backend/{migrations,tests/{contract,integration,unit}}`, `frontend/src/{api,components,pages,lib}`, `frontend/tests`, `e2e/`) per plan.md
- [X] T002 Initialize the backend Python 3.12 project in `backend/pyproject.toml` with FastAPI, SQLAlchemy 2.0 (async), Alembic, `psycopg` (v3), `argon2-cffi`, Pydantic v2, and dev deps (pytest, pytest-asyncio, httpx, testcontainers, ruff, mypy)
- [X] T003 [P] Initialize the frontend in `frontend/` with Vite + React 18 + TypeScript, React Router, TanStack Query, Radix UI, Tailwind, FullCalendar, and the OpenAPI client generator
- [X] T004 [P] Configure backend linting/formatting/type-checking (ruff + mypy) in `backend/pyproject.toml` and `mypy.ini`
- [X] T005 [P] Configure frontend ESLint + Prettier + Tailwind config in `frontend/` and wire `npm run gen:api` to generate the typed client from `specs/001-clinic-scheduling/contracts/openapi.yaml`
- [X] T006 [P] Add the ephemeral-Postgres test harness (testcontainers/disposable docker DB with `btree_gist`) and shared pytest fixtures in `backend/tests/conftest.py`
- [X] T007 [P] Add CI pipeline config running backend (pytest), frontend (Vitest), and e2e (Playwright) suites with dependency scanning, blocking merge on failure

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure — tenancy, auth, audit, base models — that EVERY user story depends on

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete

- [X] T008 Implement env-driven config (`DATABASE_URL`, `SESSION_SECRET`, `COOKIE_SECURE`) in `backend/src/core/config.py` (secrets never committed — Principle I)
- [X] T009 Implement the async SQLAlchemy engine + session factory in `backend/src/core/db.py`
- [X] T010 Initialize Alembic and the migrations environment in `backend/migrations/` (async-aware `env.py`)
- [X] T011 Add the initial migration enabling `CREATE EXTENSION IF NOT EXISTS btree_gist` in `backend/migrations/versions/`
- [X] T012 [P] Implement timezone utilities (UTC `timestamptz` canonical storage; center-local ↔ UTC conversion; grid alignment helpers) in `backend/src/core/timezone.py`
- [X] T013 [P] Implement security primitives — Argon2id password hashing/verify and signed session-cookie helpers — in `backend/src/core/security.py`
- [X] T014 Create the `Center` model (name, timezone, grid_minutes, status, created_by) in `backend/src/models/center.py`
- [X] T015 [P] Create the `User` model (center_id nullable-only-for-super-admin check constraint, role, email unique, password_hash, must_change_password, is_active) in `backend/src/models/user.py`
- [X] T016 Implement the server-side session store and `current_user` auth dependency (rejects inactive users / suspended centers) in `backend/src/core/session.py`
- [X] T017 Implement the `CenterScope` dependency and default-deny query guard (resolves session center; 403 + no data when scope is unestablished; rejects cross-center id references) in `backend/src/tenancy/scope.py`
- [X] T018 Add the PostgreSQL Row-Level-Security backstop migration (per-transaction `app.center_id` policy on tenant-owned tables) in `backend/migrations/versions/`
- [X] T019 Create the immutable `AuditEvent` model and the append-only audit writer (records patient reads/writes and cross-center actions; ids/metadata only, never PHI) in `backend/src/models/audit_event.py` and `backend/src/tenancy/audit.py`
- [X] T020 Assemble the FastAPI app with security-headers/HTTPS middleware, structured PHI-redacting logging, and the `Error` schema → 403/409/422 exception handlers in `backend/src/main.py` and `backend/src/schemas/common.py`
- [X] T021 Implement the auth router — `POST /auth/login`, `POST /auth/logout`, `GET /auth/session`, `POST /auth/change-password` (clears `must_change_password`) — in `backend/src/api/auth.py`
- [X] T022 Implement the `must_change_password` gate dependency that blocks all non-password endpoints until first-login change is done, wired in `backend/src/api/auth.py`
- [X] T023 [P] Generate the typed frontend API client from `contracts/openapi.yaml` into `frontend/src/api/` and add TanStack Query setup in `frontend/src/lib/query.ts`
- [X] T024 [P] Implement the frontend auth/session context, login page, forced-change-password page, and role-gated routing in `frontend/src/lib/auth.tsx` and `frontend/src/pages/{Login,ChangePassword}.tsx`
- [X] T025 [P] Implement the shared `<Abbr>` component + single `glossary.ts`, Radix/Tailwind design primitives, and EGP/locale (`Intl.*`) formatting helpers in `frontend/src/components/Abbr.tsx`, `frontend/src/lib/glossary.ts`, `frontend/src/lib/format.ts`
- [X] T026 [P] Contract tests for the auth endpoints (login/logout/session/change-password) in `backend/tests/contract/test_auth.py`
- [X] T027 [P] Integration test: forced first-login password change blocks other endpoints until completed, in `backend/tests/integration/test_forced_password_change.py`
- [X] T028 [P] Integration test: default-deny baseline — a session without resolvable center scope gets 403/empty on any tenant endpoint, in `backend/tests/integration/test_default_deny.py`

**Checkpoint**: Foundation ready — any logged-in role can authenticate and is center-scoped; user stories can now begin

---

## Phase 3: User Story 1 - Reception schedules patient appointments (Priority: P1) 🎯 MVP

**Goal**: Reception registers/finds a patient and books, reschedules, cancels appointments into a doctor's grid-aligned calendar with no double-booking, validated against availability.

**Independent Test**: Log in as reception (using a seeded center + doctor + availability), create/find a patient, pick an open slot, confirm — verify it appears on the reception day view and the doctor schedule; attempt the same slot again → blocked with `double_booking`.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [X] T029 [P] [US1] Contract test for `/patients` (search + create with duplicate `409`) in `backend/tests/contract/test_patients.py`
- [X] T030 [P] [US1] Contract test for `/doctors` and `/availability/{templates,exceptions,slots}` in `backend/tests/contract/test_availability.py`
- [X] T031 [P] [US1] Contract test for `/appointments` (list/create), `/appointments/{id}/reschedule`, `/appointments/{id}/status` in `backend/tests/contract/test_appointments.py`
- [X] T032 [P] [US1] Integration test: concurrent double-booking contention — two simultaneous bookings of the same doctor/slot, exactly one succeeds, in `backend/tests/integration/test_booking_concurrency.py`
- [X] T033 [P] [US1] Integration test: booking rejected when off-grid or outside resolved availability (`422` off_grid / outside_availability), in `backend/tests/integration/test_availability_validation.py`
- [X] T034 [P] [US1] Integration test: patient-overlap warning, cancel frees slot (retained in history), and reschedule releases old slot atomically, in `backend/tests/integration/test_appointment_lifecycle.py`
- [X] T035 [P] [US1] Unit tests for `AvailabilityResolver` (template → override → block → extra) and grid-alignment math in `backend/tests/unit/test_availability_resolver.py`

### Implementation for User Story 1

- [X] T036 [P] [US1] Create the `DoctorProfile` model (user_id, center_id, grid_minutes override, specialty) in `backend/src/models/doctor_profile.py`
- [X] T037 [P] [US1] Create the `Patient` model (PHI fields, `(center_id, phone)` index) in `backend/src/models/patient.py`
- [X] T038 [P] [US1] Create the `AvailabilityTemplate` model (weekday, start_local, end_local) in `backend/src/models/availability_template.py`
- [X] T039 [P] [US1] Create the `AvailabilityException` model (date, kind block/override/extra, start/end_local, reason) in `backend/src/models/availability_exception.py`
- [X] T040 [US1] Create the `Appointment` model (starts_at, duration_minutes, generated `period` tstzrange, status, origin, source_request_id, created_by, cancel_reason) in `backend/src/models/appointment.py`
- [X] T041 [US1] Add the migration creating the `appointment` table with the GiST exclusion constraint `EXCLUDE USING gist (doctor_id WITH =, period WITH &&) WHERE (status='scheduled')` plus RLS policy, in `backend/migrations/versions/`
- [X] T042 [US1] Implement the pure `AvailabilityResolver` service (resolves bookable UTC intervals for a doctor/date from template + exceptions) in `backend/src/services/availability_resolver.py`
- [X] T043 [US1] Implement the `PatientService` with normalized name+phone duplicate detection (non-blocking warning) in `backend/src/services/patient_service.py`
- [X] T044 [US1] Implement the `BookingService` — atomic create/reschedule/cancel/status in a single transaction, grid + availability + patient-overlap validation, exclusion-constraint conflict → `409 double_booking`, state machine + audit — in `backend/src/services/booking_service.py`
- [X] T045 [US1] Add Pydantic request/response schemas for patients, availability, and appointments in `backend/src/schemas/{patient,availability,appointment}.py`
- [X] T046 [US1] Implement the patients router (`GET /patients` search, `POST /patients` with duplicate `409`) in `backend/src/api/patients.py`
- [X] T047 [US1] Implement the `GET /doctors` list endpoint and the availability router (`GET/POST /availability/templates`, `POST /availability/exceptions`, `GET /availability/slots`) in `backend/src/api/availability.py`
- [X] T048 [US1] Implement the appointments router (`GET/POST /appointments`, `POST /appointments/{id}/reschedule`, `PUT /appointments/{id}/status`) in `backend/src/api/appointments.py`
- [X] T049 [P] [US1] Implement the patient search/register UI (with duplicate-warning confirm) in `frontend/src/pages/Patients.tsx`
- [X] T050 [P] [US1] Implement the reception center-wide day view with FullCalendar in `frontend/src/pages/ReceptionCalendar.tsx`
- [X] T051 [P] [US1] Implement the doctor day/week schedule view in `frontend/src/pages/DoctorSchedule.tsx`
- [X] T052 [US1] Implement the booking modal (pick doctor + open slot, set duration, confirm; surface double_booking/outside_availability/patient_conflict) wired into the calendars in `frontend/src/components/BookingModal.tsx`
- [X] T053 [US1] Add TanStack Query hooks for patients/availability/appointments in `frontend/src/api/hooks/`
- [X] T054 [US1] Playwright e2e for the US1 acceptance scenarios (book, reschedule, cancel, prevented double-book) in `e2e/us1_reception_booking.spec.ts`

**Checkpoint**: User Story 1 is fully functional and independently testable — the bookable MVP

---

## Phase 4: User Story 2 - Doctor sends an appointment request to reception (Priority: P1)

**Goal**: A doctor submits an appointment request; reception sees it in a pending queue (urgent/overdue highlighted) and fulfills it into a concrete slot or declines it with a reason — with in-app notifications back to the doctor.

**Independent Test**: Log in as doctor, submit a request (patient, reason, urgency, expected duration); log in as reception, see it queued, fulfill it into a slot; verify the request is `fulfilled`, an appointment exists, and the doctor receives an in-app notification. Decline path notifies the doctor with reason.

### Tests for User Story 2 ⚠️ (write first, ensure they FAIL)

- [X] T055 [P] [US2] Contract test for `/requests` (list/create), `/requests/{id}/fulfill`, `/requests/{id}/decline` in `backend/tests/contract/test_requests.py`
- [X] T056 [P] [US2] Contract test for `/notifications` (list + mark read) in `backend/tests/contract/test_notifications.py`
- [X] T057 [P] [US2] Integration test: reception fulfill creates a `scheduled` appointment, marks the request `fulfilled`, and writes a `request_fulfilled` notification to the doctor, in `backend/tests/integration/test_request_fulfill.py`
- [X] T058 [P] [US2] Integration test: decline writes reason + `request_declined` notification; only reception may fulfill/decline (doctor attempt → 403); overdue flag derived from `preferred_to`, in `backend/tests/integration/test_request_decline.py`

### Implementation for User Story 2

- [X] T059 [P] [US2] Create the `AppointmentRequest` model (reason, preferred_from/to, urgency, expected_duration_minutes, status, decline_reason, resulting_appointment_id) in `backend/src/models/appointment_request.py`
- [X] T060 [P] [US2] Create the `Notification` model (recipient_user_id, type, jsonb payload of ids only, is_read) in `backend/src/models/notification.py`
- [X] T061 [US2] Implement the `NotificationService` (transactional writer; PHI-free payloads) in `backend/src/services/notification_service.py`
- [X] T062 [US2] Implement the `RequestWorkflowService` — create/fulfill (delegates to `BookingService`)/decline, state machine `pending→fulfilled|declined`, audited, reception-only — in `backend/src/services/request_service.py`
- [X] T063 [US2] Add Pydantic schemas for requests and notifications in `backend/src/schemas/{request,notification}.py`
- [X] T064 [US2] Implement the requests router (`GET/POST /requests`, `POST /requests/{id}/fulfill`, `POST /requests/{id}/decline`) in `backend/src/api/requests.py`
- [X] T065 [US2] Implement the notifications router (`GET /notifications`, `POST /notifications/{id}/read`) in `backend/src/api/notifications.py`
- [X] T066 [P] [US2] Implement the doctor appointment-request form in `frontend/src/pages/DoctorRequestForm.tsx`
- [X] T067 [P] [US2] Implement the reception pending-requests queue with urgency/overdue visual highlighting in `frontend/src/pages/RequestQueue.tsx`
- [X] T068 [US2] Wire the fulfill-from-queue flow (reuse `BookingModal`) and decline-with-reason action in `frontend/src/pages/RequestQueue.tsx`
- [X] T069 [P] [US2] Implement the notification badge + polling (30–60s) in `frontend/src/components/NotificationBell.tsx`
- [X] T070 [US2] Playwright e2e for the US2 acceptance scenarios (submit → queue → fulfill/decline → notify) in `e2e/us2_request_handoff.spec.ts`

**Checkpoint**: User Stories 1 AND 2 both work independently — the full core booking loop

---

## Phase 5: User Story 3 - Center admin manages staff accounts (Priority: P2)

**Goal**: A center admin creates/edits/deactivates doctor and reception accounts within their own center, setting temp passwords (forced change on first login) and seeing only their center's staff.

**Independent Test**: Log in as a center admin, create a doctor and a reception account, verify each logs in with their own credentials and role-appropriate screens, deactivate one and verify login is blocked while historical records remain; verify the staff list shows only this center's users.

### Tests for User Story 3 ⚠️ (write first, ensure they FAIL)

- [X] T071 [P] [US3] Contract test for `/users` (list/create) and `/users/{id}` (edit) in `backend/tests/contract/test_users.py`
- [X] T072 [P] [US3] Integration test: deactivating a user blocks login but retains their appointments/requests; staff list is center-scoped (other centers' users invisible), in `backend/tests/integration/test_staff_management.py`

### Implementation for User Story 3

- [X] T073 [US3] Implement the `UserManagementService` (create doctor/reception with temp password + `must_change_password=true`; edit display_name/is_active; deactivate/reactivate; center-admin scoped; audited) in `backend/src/services/user_service.py`
- [X] T074 [US3] Add Pydantic schemas and implement the users router (`GET/POST /users`, `PUT /users/{id}`) in `backend/src/schemas/user.py` and `backend/src/api/users.py`
- [X] T075 [US3] Implement the admin staff-management page (list, create-with-temp-password, edit, deactivate/reactivate) in `frontend/src/pages/AdminStaff.tsx`
- [X] T076 [US3] Playwright e2e for the US3 acceptance scenarios (create accounts, role-scoped login, deactivate blocks login) in `e2e/us3_staff_management.spec.ts`

**Checkpoint**: Center admins can self-provision their center's staff

---

## Phase 6: User Story 4 - Platform super-admin provisions centers (Priority: P2)

**Goal**: A super-admin creates centers, configures profiles, creates each center's first admin, and suspends/reactivates centers — with strict isolation between centers.

**Independent Test**: Log in as super-admin, create a center and assign its first admin, verify that admin logs in and manages only their center and cannot see another center's data; suspend the center and verify its users are blocked from login.

### Tests for User Story 4 ⚠️ (write first, ensure they FAIL)

- [X] T077 [P] [US4] Contract test for `/centers` (list/create) and `/centers/{id}/status` in `backend/tests/contract/test_centers.py`
- [X] T078 [P] [US4] Integration test: comprehensive cross-tenant isolation — a user from center A cannot view/search/access center B's patients, appointments, requests, or staff (403/empty), in `backend/tests/integration/test_cross_tenant_isolation.py`
- [X] T079 [P] [US4] Integration test: creating a center provisions its first admin atomically; suspending a center blocks all its users' logins until reactivated, in `backend/tests/integration/test_center_provisioning.py`

### Implementation for User Story 4

- [X] T080 [US4] Implement the `CenterProvisioningService` (create center + first center-admin atomically; suspend/reactivate; super-admin only; cross-center actions audited) in `backend/src/services/center_service.py`
- [X] T081 [US4] Add Pydantic schemas and implement the centers router (`GET/POST /centers`, `PUT /centers/{id}/status`) in `backend/src/schemas/center.py` and `backend/src/api/centers.py`
- [X] T082 [P] [US4] Implement the `seed_superadmin` one-off script in `backend/src/scripts/seed_superadmin.py`
- [X] T083 [US4] Implement the super-admin centers page (list, create with first admin, suspend/reactivate) in `frontend/src/pages/SuperAdminCenters.tsx`
- [X] T084 [US4] Playwright e2e for the US4 acceptance scenarios (provision center + admin, isolation, suspend blocks login) in `e2e/us4_center_provisioning.spec.ts`

**Checkpoint**: All four user stories are independently functional — multi-center onboarding complete

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Hardening and verification spanning all stories

- [ ] T085 [P] Unit tests for the appointment and request state-machine validators in `backend/tests/unit/test_state_machines.py`
- [ ] T086 [P] Verify audit coverage: every patient read/write and cross-center super-admin action writes an `AuditEvent` (no PHI in payloads) — assertions in `backend/tests/integration/test_audit_coverage.py`
- [ ] T087 [P] Security hardening pass: cookie flags (`HttpOnly`/`Secure`/`SameSite=Strict`), security headers, OWASP session handling, dependency-scan clean
- [ ] T088 [P] Accessibility audit: WCAG 2.1 AA contrast/focus, keyboard-reachable scheduling flows, every abbreviation covered by `<Abbr>`/`glossary.ts`
- [ ] T089 Performance check against plan targets (API p95 < 200 ms for booking/list; calendar day view < 1 s; SC-001/SC-002/SC-006 timings)
- [ ] T090 Run `quickstart.md` end-to-end to validate the full local stack and core loop
- [ ] T091 [P] Documentation: `backend/README.md` and `frontend/README.md` (run/test instructions, env vars, PHI-handling notes)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Stories (Phases 3–6)**: All depend on Foundational completion
  - US1 (P1) and US2 (P1) deliver the core loop; US3 and US4 (P2) follow
  - Stories are independently testable via seeded fixtures and can be parallelized across developers
- **Polish (Phase 7)**: Depends on the desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: After Foundational. No hard dependency on other stories (uses seeded center/doctor/availability).
- **US2 (P1)**: After Foundational. Reuses `BookingService` from US1 at fulfill time; if built in parallel, coordinate that interface. Independently testable.
- **US3 (P2)**: After Foundational. Independent (operates on Center + User from Foundational).
- **US4 (P2)**: After Foundational. Independent; its cross-tenant isolation test (T078) exercises data created by US1–US3 when present but stands alone with seeded data.

### Within Each User Story

- Write tests first and confirm they FAIL before implementing
- Models → services → endpoints → frontend → e2e
- Migrations accompany their models

### Parallel Opportunities

- Setup tasks T003–T007 run in parallel
- Foundational [P] tasks (T012/T013, T015, T023–T028) run in parallel once their deps land
- Within each story, all [P] test tasks run together, then all [P] model tasks together
- With multiple developers, US1–US4 proceed in parallel after Phase 2

---

## Parallel Example: User Story 1

```bash
# Tests first (all fail), in parallel:
Task: "Contract test for /patients in backend/tests/contract/test_patients.py"          # T029
Task: "Contract test for availability in backend/tests/contract/test_availability.py"   # T030
Task: "Integration test booking concurrency in backend/tests/integration/test_booking_concurrency.py"  # T032

# Then models in parallel:
Task: "Create DoctorProfile model in backend/src/models/doctor_profile.py"   # T036
Task: "Create Patient model in backend/src/models/patient.py"                 # T037
Task: "Create AvailabilityTemplate model in backend/src/models/availability_template.py"  # T038
Task: "Create AvailabilityException model in backend/src/models/availability_exception.py" # T039
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: book/reschedule/cancel a patient with no double-booking
5. Deploy/demo the bookable MVP

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → the core booking system (MVP)
3. US2 → the doctor→reception handoff (completes the core loop)
4. US3 → center-admin staff self-service
5. US4 → multi-center onboarding + isolation hardening
6. Phase 7 → polish, security, accessibility, performance

---

## Notes

- [P] = different files, no dependencies on incomplete tasks
- The three NON-NEGOTIABLE gating test paths are T032 (booking concurrency), T078 (cross-tenant isolation), and T027 (forced password change) — these must pass before merge
- Cancelled appointments are status changes, never deletes; only `scheduled` rows reserve time
- All times stored UTC `timestamptz`; convert at the edges (availability authoring, calendar display, grid alignment)
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
