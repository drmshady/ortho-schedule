<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 1.1.1
Bump rationale: 1.0.0 → 1.1.0 (MINOR): added one new NON-NEGOTIABLE core principle
(Multi-Tenant Isolation) and materially expanded existing guidance (Egypt context in
the web-experience principle and Security & Compliance section; four-role model and
doctor→reception handoff in Appointment Integrity); no principle removed; the patients-
are-not-users correction narrows scope rather than an incompatible change.
1.1.0 → 1.1.1 (PATCH): corrected the web-experience principle to set English as the
primary UI language and defer Arabic/RTL to a future version (operator clarification);
EGP/locale formatting retained.

Modified principles:
  - II. Web-First, Accessible Experience → III. Web-First, Accessible & Localized
    Experience (patients removed as users; Arabic/RTL + EGP localization added)
  - III. Appointment Integrity & Prioritization → IV. Appointment Integrity &
    Prioritization (four-role model + doctor→reception request handoff added)
  - IV. Test-First Quality Gates → V. Test-First Quality Gates (renumbered)
  - V. MVP Simplicity (YAGNI) → VI. MVP Simplicity (YAGNI) (renumbered)
Added principles:
  - II. Multi-Tenant Isolation (NON-NEGOTIABLE)
Added sections: None (Security & Compliance Requirements expanded in place)
Removed sections: None

Templates requiring updates:
  - .specify/templates/plan-template.md ✅ compatible (generic Constitution Check gate)
  - .specify/templates/spec-template.md ✅ compatible (no constitution-specific edits needed)
  - .specify/templates/tasks-template.md ✅ compatible (security/test/isolation tasks map to principles)
  - .specify/templates/checklist-template.md ✅ compatible
  - specs/001-clinic-scheduling/spec.md ✅ aligned (tenant isolation, no patient logins, 4 roles, in-app notifications)
  - CLAUDE.md ⚠ pending (auto-generated agent guidance; will refresh on next /speckit.plan)

Deferred TODOs: None (RATIFICATION_DATE retained as 2026-06-22).
-->

# DSD MVP Platform Constitution

The DSD MVP Platform is a multi-tenant web application for scheduling and managing
patient appointments across independent clinic centers. This constitution defines the
non-negotiable principles that govern how the platform is designed, built, and operated.
Because the system handles patient health information across multiple tenants, **data
security, patient privacy, and strict cross-center isolation take precedence over feature
velocity** whenever they conflict.

## Core Principles

### I. Patient Data Security & Privacy (NON-NEGOTIABLE)

Protecting patient information is the first obligation of every change.

- All patient data MUST be encrypted in transit (TLS 1.2+) and at rest.
- Access to patient records MUST be authenticated and authorized by role; every read
  or write of patient data MUST be recorded in an immutable audit log.
- The system MUST follow least-privilege and data-minimization: collect and expose only
  the data required for the appointment workflow.
- Secrets (keys, tokens, DB credentials) MUST NOT be committed to source control and
  MUST be supplied via environment/secret management.
- No patient-identifying data may appear in logs, error messages, analytics, or
  third-party services without explicit justification recorded in the feature spec.

**Rationale**: The platform stores health-related personal data; a breach causes
irreversible harm to patients and the operator. Security is therefore a gate, not a
feature, and any violation blocks merge.

### II. Multi-Tenant Isolation (NON-NEGOTIABLE)

Each clinic center is an independent tenant, and one tenant's data MUST never leak to
another.

- Every center-owned record (users, patients, appointments, appointment requests,
  availability) MUST belong to exactly one center, and that ownership MUST be enforced
  on the server for every read and write — never trusted from the client.
- Non-super-admin users (center admin, doctor, reception) MUST be scoped to exactly one
  center; a user session MUST resolve to a single active center context.
- Only the platform super-admin role may operate across centers (provisioning,
  suspension); all such cross-center actions MUST be audited.
- Default-deny: any query or endpoint that cannot establish the caller's center scope
  MUST fail closed, returning no data.
- Tests MUST include cross-tenant access attempts proving one center cannot view,
  search, or mutate another center's data.

**Rationale**: The product onboards many independent clinics onto shared
infrastructure; a single isolation defect exposes one clinic's patients to another and
is as damaging as a breach. Isolation is a correctness and compliance gate.

### III. Web-First, Accessible & Localized Experience

The product is delivered as a web application used by clinic staff (platform super-admin,
center admin, doctor, reception). Patients have no login accounts in the MVP; all patient
interaction is staff-mediated.

- The UI MUST be responsive and function on current mobile and desktop browsers.
- Interactive flows (scheduling, rescheduling, cancellation, request handling) MUST be
  reachable by keyboard and meet WCAG 2.1 AA for color contrast and focus states.
- Every abbreviation shown in the UI MUST have a hover tooltip / accessible label.
- The primary UI language MUST be English. The product deploys to clinics in Egypt, so
  monetary values MUST be presented in Egyptian Pounds (EGP) and locale-dependent
  formatting (dates, numbers) MUST follow the active locale. Arabic / right-to-left (RTL)
  support is NOT required for the MVP and is deferred to a future version.

**Rationale**: Appointment scheduling must work reliably for a broad, non-technical
staff audience across devices; accessibility is a correctness requirement, not a polish
task. English-first keeps the MVP focused while EGP/locale formatting still fits the
Egyptian deployment.

### IV. Appointment Integrity & Prioritization

The scheduling engine is the heart of the product and MUST never corrupt the calendar.

- Booking MUST be atomic: the system MUST prevent double-booking of the same
  provider/resource/time slot under concurrent requests.
- The doctor→reception handoff MUST be explicit: doctors submit appointment requests,
  and only reception converts a request into a confirmed appointment by assigning an
  open slot. Doctors do not place patients directly onto the calendar.
- Appointment priority/urgency MUST be an explicit, auditable attribute that drives
  ordering and surfacing of pending requests — never an implicit side effect.
- Every state transition (requested → confirmed → rescheduled → cancelled → completed →
  no-show) MUST be validated against allowed transitions and recorded with a timestamp
  and the acting role/user.
- Bookings MUST respect each doctor's defined availability and time off; cancelled
  appointments MUST be retained in history (not hard-deleted) and their slot freed.
- Time handling MUST be timezone-aware and store canonical UTC.

**Rationale**: A scheduling system that double-books, silently reorders, or bypasses the
reception handoff loses user trust immediately; integrity and explicit prioritization
are core value.

### V. Test-First Quality Gates

Behavior is proven by tests before it is shipped.

- Each feature MUST include automated tests covering its acceptance criteria; security,
  tenant-isolation, and appointment-integrity logic MUST have tests before
  implementation is merged.
- Tests MUST fail before the implementation exists and pass after (red-green).
- Concurrency-sensitive booking paths MUST have tests that exercise contention, and
  isolation paths MUST have tests that exercise cross-tenant access attempts.
- CI MUST run the full test suite and block merge on failure.

**Rationale**: The cost of a scheduling, isolation, or security defect in production is
high; tests are the cheapest place to catch them and the contract for safe change.

### VI. MVP Simplicity (YAGNI)

Ship the smallest correct slice that delivers the scheduling workflow.

- Prefer the simplest design that satisfies the spec; defer multi-feature abstractions
  until a second concrete use case exists.
- Any added complexity (new service, new dependency, new datastore) MUST be justified
  in the plan's Complexity Tracking section against a rejected simpler alternative.
- Scope beyond appointment scheduling, the doctor→reception request workflow,
  prioritization, tenant isolation, and securing patient data is out of scope for the
  MVP unless explicitly added to a spec. External messaging (SMS/WhatsApp/email) and
  patient self-service are explicitly deferred; v1 notifications are in-app only.

**Rationale**: An MVP earns the right to grow; premature generality slows delivery and
enlarges the security and isolation surface area.

## Security & Compliance Requirements

- A data classification MUST accompany each new field: public, internal, or patient/PHI.
- Authentication and session management MUST follow current OWASP guidance; passwords
  MUST be hashed with a memory-hard algorithm (e.g., bcrypt/argon2). Sessions MUST carry
  and enforce the user's center scope (see Principle II).
- Input from clients MUST be validated server-side; the server is the source of truth
  for authorization and tenant-scope decisions.
- Dependencies MUST be tracked and scanned for known vulnerabilities; high-severity
  advisories MUST be triaged before release.
- Backups of patient data MUST be encrypted, and a documented retention/erasure policy
  MUST exist to honor patient data-deletion requests.
- The platform MUST comply with applicable Egyptian regulations for the deploying
  clinics, including the Personal Data Protection Law (PDPL) and Ministry of Health and
  Population (MoHP) / Dental Syndicate requirements where they govern patient data and
  clinic operations. Compliance-affecting choices MUST be recorded in the feature spec.

## Development Workflow & Quality Gates

- Every change lands via pull request; no direct commits to the default branch.
- Each PR MUST pass CI (tests, linting) and a review that explicitly verifies the
  Constitution Check items relevant to the change (security, tenant isolation,
  integrity, accessibility/localization).
- Feature work follows the spec → plan → tasks → implementation flow; the plan MUST
  include a Constitution Check section gated on Principles I–VI.
- Changes touching patient data, authentication, tenant isolation, or the booking engine
  REQUIRE at least one reviewer attestation that Principles I, II, and IV are upheld.

## Governance

This constitution supersedes other practices where they conflict. When a guideline and
this document disagree, this document wins.

- **Amendments**: Proposed via PR that edits this file, states the rationale, and bumps
  the version. Amendments touching Principle I (security), II (isolation), or IV
  (integrity) REQUIRE explicit operator approval before merge.
- **Versioning**: Semantic versioning. MAJOR = removal/redefinition of a principle or
  incompatible governance change; MINOR = new principle/section or materially expanded
  guidance; PATCH = clarifications and wording fixes.
- **Compliance review**: Reviewers MUST confirm PRs comply with the applicable
  principles. Unjustified complexity, unaddressed security gaps, or unproven tenant
  isolation block merge. Use the agent guidance file (CLAUDE.md) for runtime, day-to-day
  development guidance.

**Version**: 1.1.1 | **Ratified**: 2026-06-22 | **Last Amended**: 2026-06-22
