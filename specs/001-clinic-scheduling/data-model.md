# Phase 1 Data Model: Clinic Patient Scheduling

Derived from the spec's Key Entities and Functional Requirements. Each field carries a **data
classification** per Constitution Principle I & Security/Compliance: `public` (non-sensitive
config/metadata), `internal` (operational, not patient-identifying), `PHI` (patient-
identifying / health-related — minimized, audited, never logged).

Conventions: all ids are UUIDs (`internal`). All tables except `center` and super-admin-owned
rows carry a non-null `center_id` FK enforcing tenant ownership (Principle II). Timestamps are
`timestamptz` stored in UTC. `created_at`/`updated_at` (`internal`) are implied on every table.

---

## Entity: Center

The unit of tenancy and isolation.

| Field | Type | Class | Notes |
|-------|------|-------|-------|
| id | UUID PK | internal | |
| name | text | public | Clinic/practice display name |
| timezone | text (IANA) | public | Single timezone per center (e.g., `Africa/Cairo`) |
| grid_minutes | int | public | Default booking grid unit (default 15); doctor may override |
| status | enum(`active`,`suspended`) | internal | Suspended → all its users blocked from login (FR-003) |
| created_by | UUID → User(super-admin) | internal | Provisioning audit |

**Rules**: Only super-admin creates/suspends/reactivates (FR-003). Suspension preserves all
records (edge case) and only blocks login.

---

## Entity: User

A person with login credentials and exactly one role.

| Field | Type | Class | Notes |
|-------|------|-------|-------|
| id | UUID PK | internal | |
| center_id | UUID → Center, **nullable** | internal | NULL only for super-admin; non-null for all other roles |
| role | enum(`super_admin`,`center_admin`,`doctor`,`reception`) | internal | FR-001 |
| email | text, unique (global) | internal | Login identifier (FR-007) |
| display_name | text | internal | |
| password_hash | text (Argon2id) | internal | Never returned by any API |
| must_change_password | bool | internal | True on creation; forces change on first login (FR-004a) |
| is_active | bool | internal | Deactivated users cannot log in; records retained (FR-006) |

**Rules**:
- `center_id` MUST be non-null for non-super-admin roles and MUST be NULL for super-admin
  (DB check constraint). Enforces Principle II scoping.
- `email` globally unique to keep login unambiguous; authorization is still center-scoped.
- Center admin manages only `doctor`/`reception` users within their own center (FR-004).
- Deactivation sets `is_active=false`; never hard-deleted (FR-006).

---

## Entity: DoctorProfile

Extends a `doctor`-role user with scheduling attributes (1:1 with User where role=doctor).

| Field | Type | Class | Notes |
|-------|------|-------|-------|
| user_id | UUID PK → User | internal | role MUST be `doctor` |
| center_id | UUID → Center | internal | Mirrors user's center |
| grid_minutes | int, nullable | public | Overrides center default for this doctor (FR-019a) |
| specialty | text, nullable | public | Optional display |

---

## Entity: Patient

A person receiving care; **no login** (FR-011).

| Field | Type | Class | Notes |
|-------|------|-------|-------|
| id | UUID PK | internal | |
| center_id | UUID → Center | internal | Belongs to exactly one center (Principle II) |
| full_name | text | **PHI** | FR-009 |
| phone | text | **PHI** | FR-009; used for duplicate detection |
| clinic_identifier | text, nullable | **PHI** | Clinic-relevant id (FR-009) |
| date_of_birth | date, nullable | **PHI** | Optional; data-minimized |
| notes | text, nullable | **PHI** | Free-text |

**Rules**:
- Duplicate detection: on registration, warn when an existing patient in the same center
  matches normalized `full_name` + `phone` (FR-010). Non-blocking. A DB index on
  `(center_id, phone)` supports lookup (FR-006/SC-006).
- Merge is deferred; at minimum duplicates are detectable (edge case).
- All reads/writes of Patient rows are audited (Principle I).

---

## Entity: AvailabilityTemplate

Recurring weekly bookable hours for a doctor (FR-012).

| Field | Type | Class | Notes |
|-------|------|-------|-------|
| id | UUID PK | internal | |
| center_id | UUID → Center | internal | |
| doctor_id | UUID → User(doctor) | internal | |
| weekday | int 0–6 | internal | 0=Monday (documented) |
| start_local | time | internal | Center-local authoring time |
| end_local | time | internal | `end_local > start_local` |

**Rules**: Multiple rows per weekday allowed (e.g., morning + evening blocks). Authored in
center-local time; resolver converts to UTC for a concrete date.

---

## Entity: AvailabilityException

Date-specific override (time off, holiday, extra/changed hours) (FR-012).

| Field | Type | Class | Notes |
|-------|------|-------|-------|
| id | UUID PK | internal | |
| center_id | UUID → Center | internal | |
| doctor_id | UUID → User(doctor) | internal | |
| date | date | internal | The affected center-local date |
| kind | enum(`block`,`override`,`extra`) | internal | block=remove hours; override=replace day's template; extra=add hours |
| start_local | time, nullable | internal | Required for `override`/`extra`; null for full-day `block` |
| end_local | time, nullable | internal | As above |
| reason | text, nullable | internal | e.g., "holiday" |

**Resolution order** (AvailabilityResolver): start from weekday template intervals → apply
`override` (replaces the day) → subtract `block` intervals → add `extra` intervals → result
is the set of bookable local intervals, converted to UTC. Booking validates against this
(FR-013).

---

## Entity: AppointmentRequest

Doctor-originated request handed to reception (FR-014..FR-018).

| Field | Type | Class | Notes |
|-------|------|-------|-------|
| id | UUID PK | internal | |
| center_id | UUID → Center | internal | |
| doctor_id | UUID → User(doctor) | internal | Requesting doctor |
| patient_id | UUID → Patient | internal | Subject |
| reason | text | PHI | Visit type / reason (FR-014) |
| preferred_from | date, nullable | internal | Preferred timeframe start |
| preferred_to | date, nullable | internal | Preferred timeframe end |
| urgency | enum(`routine`,`soon`,`urgent`) | internal | Explicit, auditable; drives queue ordering (FR-018, Principle IV) |
| expected_duration_minutes | int | internal | Multiple of grid; seeds the booking length (FR-014) |
| notes | text, nullable | PHI | Free-text |
| status | enum(`pending`,`fulfilled`,`declined`) | internal | FR-015/FR-016 |
| decline_reason | text, nullable | internal | Required when `declined` (FR-016) |
| resulting_appointment_id | UUID → Appointment, nullable | internal | Set when fulfilled |

**State machine** (validated, each transition audited with actor+timestamp — Principle IV):
`pending → fulfilled` (reception assigns a slot) | `pending → declined` (reception, with
reason). No other transitions. Only reception may fulfill/decline (FR-016, Principle IV).
"Overdue" is derived (now > `preferred_to`) for queue highlighting (FR-018) — not stored.

---

## Entity: Appointment

A confirmed booking (FR-019..FR-025).

| Field | Type | Class | Notes |
|-------|------|-------|-------|
| id | UUID PK | internal | |
| center_id | UUID → Center | internal | |
| doctor_id | UUID → User(doctor) | internal | |
| patient_id | UUID → Patient | internal | |
| starts_at | timestamptz (UTC) | internal | Grid-aligned start |
| duration_minutes | int | internal | Positive multiple of effective `grid_minutes` |
| period | tstzrange (generated/maintained) | internal | `[starts_at, starts_at + duration)`; backs the exclusion constraint |
| status | enum(`scheduled`,`completed`,`cancelled`,`no_show`) | internal | FR-022 |
| origin | enum(`request`,`direct`) | internal | request handoff vs walk-in (FR-019) |
| source_request_id | UUID → AppointmentRequest, nullable | internal | Set when origin=request |
| created_by | UUID → User(reception) | internal | Only reception books (Principle IV) |
| cancel_reason | text, nullable | internal | |

**Constraints & rules**:
- **No double-booking** (FR-020, Principle IV): GiST exclusion constraint
  `EXCLUDE USING gist (doctor_id WITH =, period WITH &&) WHERE (status = 'scheduled')`.
  Only `scheduled` rows reserve time, so cancelling frees the slot (FR-025) without deleting.
- Booking validated server-side: start grid-aligned, duration a grid multiple, `period`
  fully inside resolved availability (FR-013/FR-019a), patient overlap → warn (FR-021).
- **State machine** (validated + audited): `scheduled → completed` | `scheduled → cancelled`
  | `scheduled → no_show`; `cancelled` is terminal but retained in history (FR-025). Reschedule
  = update `starts_at`/`duration` of a `scheduled` appointment (re-validated, freeing/old slot
  released atomically), audited.
- Only `reception` creates/reschedules/cancels (FR-019, Principle IV).

---

## Entity: Notification

In-app notification (FR-017, FR-026).

| Field | Type | Class | Notes |
|-------|------|-------|-------|
| id | UUID PK | internal | |
| center_id | UUID → Center | internal | |
| recipient_user_id | UUID → User | internal | |
| type | enum(`request_fulfilled`,`request_declined`,`request_created`,`appt_reassign_needed`) | internal | |
| payload | jsonb | internal | Ids/labels only — **no PHI** (Principle I) |
| is_read | bool | internal | |

**Rules**: Written transactionally with the triggering event. Polled by the frontend. Payload
carries references (ids) not patient-identifying text, keeping PHI out of notification storage.

---

## Entity: AuditEvent (immutable)

Append-only record for Principles I & II.

| Field | Type | Class | Notes |
|-------|------|-------|-------|
| id | UUID PK | internal | |
| center_id | UUID → Center, nullable | internal | Null for cross-center super-admin actions |
| actor_user_id | UUID → User | internal | Who acted |
| actor_role | enum | internal | Role at time of action |
| action | text | internal | e.g., `patient.read`, `appointment.create`, `center.suspend` |
| target_type | text | internal | Entity type |
| target_id | UUID, nullable | internal | Entity id (never PHI values) |
| at | timestamptz | internal | UTC |

**Rules**: Insert-only (no update/delete). Every patient-data read/write and every
cross-center super-admin action writes a row (Principle I & II). Stores ids/metadata, never
PHI field values, so the audit log itself carries no patient-identifying content.

---

## Relationships (summary)

```text
Center 1───* User           (User.center_id; null only for super_admin)
Center 1───* Patient
Center 1───* AppointmentRequest ───1 Patient   ───1 User(doctor)
Center 1───* Appointment        ───1 Patient   ───1 User(doctor)   ───1 User(reception=created_by)
User(doctor) 1───1 DoctorProfile
User(doctor) 1───* AvailabilityTemplate
User(doctor) 1───* AvailabilityException
AppointmentRequest 0..1───1 Appointment   (source_request_id / resulting_appointment_id)
Center 1───* Notification ───1 User(recipient)
AuditEvent * (references actor User; center_id nullable)
```

## Validation & integrity invariants (cross-cutting)

1. Every tenant-owned row's `center_id` equals the acting session's center scope; cross-center
   id references are rejected before write (Principle II, default-deny).
2. No two `scheduled` appointments for the same doctor have overlapping `period` (DB
   exclusion constraint — FR-020).
3. Appointment `period` ⊆ resolved availability for that doctor/date (FR-013).
4. `starts_at` grid-aligned and `duration_minutes` a positive multiple of effective
   `grid_minutes` (FR-019a).
5. All entity state transitions follow the documented machines and are audited with actor +
   timestamp (Principle IV).
6. Cancelled appointments are retained (status change, never delete) and free their slot
   (FR-025).
