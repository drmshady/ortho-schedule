# Feature Specification: Deploy Clinic Scheduling App to Production

**Feature Branch**: `002-deploy-app`  
**Created**: 2026-06-23  
**Status**: Draft  
**Input**: User description: "prepare app for deployment and guide me through deployment"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get the app live and reachable by clinic staff (Priority: P1)

As the platform operator, I want the clinic-scheduling app published to a real, internet-reachable
address over a secure connection so that reception staff, doctors, and admins at pilot centers can
log in and use it from their browsers instead of only running it on a developer machine.

**Why this priority**: Nothing else about deployment matters if staff cannot reach a working,
secure instance. This is the minimum viable outcome — a running production instance behind the
operator's own domain with HTTPS.

**Independent Test**: From a clean device outside the build environment, open the app's public URL,
confirm the connection is encrypted (valid certificate, no browser warning), log in as a seeded
center admin, and complete one real booking. Delivers value on its own: a usable live system.

**Acceptance Scenarios**:

1. **Given** the app has been deployed, **When** a staff member visits the public URL in a browser,
   **Then** the application loads over HTTPS with a valid certificate and no security warning.
2. **Given** a valid center-admin account exists, **When** they sign in and create an appointment,
   **Then** the appointment is saved and visible after a page reload.
3. **Given** two reception users try to book the same doctor for the same slot, **When** both submit,
   **Then** exactly one succeeds and the other receives a clear "slot taken" outcome (no double-booking).
4. **Given** a user from Center A is signed in, **When** they attempt to view Center B's data,
   **Then** the system denies access and reveals no Center B information.

---

### User Story 2 - Walk the operator through deployment step by step (Priority: P1)

As the operator (a clinician, not a full-time DevOps engineer), I want to be guided through each
deployment step interactively — provisioning the server, supplying secrets, pointing the domain,
starting the services, and verifying health — so that I can stand up production confidently and
repeat it later without guesswork.

**Why this priority**: The explicit request is to be *guided through* deployment. A correct artifact
that the operator cannot operate is a failure. The guidance and the deployable artifacts are equally
the deliverable.

**Independent Test**: Following only the written guide (no outside help), the operator provisions a
fresh server and brings the app to a healthy state, with each step including a verification check
that confirms success before moving on.

**Acceptance Scenarios**:

1. **Given** a fresh, empty server, **When** the operator follows the guide top to bottom,
   **Then** they reach a running, healthy deployment without needing undocumented steps.
2. **Given** any single deployment step, **When** the operator completes it, **Then** the guide
   provides a concrete check (a command, URL, or status) confirming that step succeeded before the
   next step begins.
3. **Given** a step fails, **When** the operator consults the guide, **Then** it describes the
   expected symptom and the corrective action for that failure.
4. **Given** secrets are required (database password, session/signing secret), **When** the operator
   configures them, **Then** the guide ensures they are supplied at runtime and never committed to
   version control.

---

### User Story 3 - Keep the live system healthy, recoverable, and updatable (Priority: P2)

As the operator, I want the production instance to be observable, backed up, and safely updatable so
that I can detect problems, recover patient/appointment data after a failure, and roll out new
versions without losing data or causing extended outages.

**Why this priority**: A pilot with real clinic data must survive a server failure and accept
updates. This protects the data and makes the deployment sustainable, but it builds on an
already-live system (Stories 1–2).

**Independent Test**: Trigger a database backup, simulate data loss by restoring into a fresh
instance, confirm appointments and accounts are intact, then deploy a new application version and
confirm existing data is preserved and the new version serves traffic.

**Acceptance Scenarios**:

1. **Given** the system is running, **When** the operator (or a schedule) runs a backup, **Then** an
   encrypted, restorable backup of the database is produced and its location is known.
2. **Given** a backup exists, **When** it is restored into a clean instance, **Then** all
   appointments, accounts, and audit records are present and correct.
3. **Given** a new application version is released, **When** the operator deploys it, **Then**
   existing data is preserved, schema changes are applied automatically, and downtime is brief and
   communicated.
4. **Given** the system is running, **When** the operator checks status, **Then** a health
   indicator reports whether the app and database are up.

---

### Edge Cases

- **Domain/DNS not yet propagated**: The guide must detect and explain the wait when the domain does
  not yet resolve to the server, and verify resolution before requesting a certificate.
- **Certificate issuance fails** (rate limit, DNS misconfig, port 80/443 blocked): The operator is
  told the likely cause and how to retry safely.
- **Missing or weak secret**: Startup must fail fast with a clear message rather than launching with
  an insecure default; no default credentials in production.
- **Database migration fails mid-deploy**: The deploy must not leave a half-upgraded, serving
  instance; the operator is told how to recover to the prior known-good state.
- **Server reboot / process crash**: Services must come back automatically after a reboot.
- **Backup restore onto a different machine**: Restore must work on a clean server, not only the
  original host.
- **First-run with empty database**: Initial schema and a bootstrap super-admin account must be
  created so the operator can log in immediately.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST be deployable to a single internet-reachable server and serve both the
  application interface and its data services as a self-contained unit started from a documented
  command.
- **FR-002**: The deployed application MUST be served exclusively over an encrypted (HTTPS)
  connection using the operator's own domain, with a valid, automatically-renewing certificate;
  unencrypted requests MUST be redirected to the encrypted endpoint.
- **FR-003**: All secrets (database credentials, session/signing secret) MUST be supplied at deploy
  time from configuration that is excluded from version control; the application MUST refuse to start
  with missing or placeholder secrets.
- **FR-004**: The deployment MUST initialize the database schema automatically on first run and apply
  any pending schema migrations on each subsequent deploy, without manual SQL.
- **FR-005**: The deployment MUST create an initial administrative account (or document a one-time
  bootstrap step) so the operator can sign in immediately after go-live.
- **FR-006**: The system MUST expose a health status for the application and the database that the
  operator can check to confirm the deployment is up.
- **FR-007**: Application and database services MUST restart automatically after a crash or server
  reboot.
- **FR-008**: The deployment MUST provide a repeatable way to produce an encrypted, restorable backup
  of all persistent data, and a documented procedure to restore it onto a clean instance.
- **FR-009**: The system MUST provide a documented update procedure that deploys a new application
  version while preserving existing data and applying schema migrations.
- **FR-010**: The deployment MUST preserve every production behavior gate defined for the app: no
  double-booking under concurrency, per-center data isolation (default-deny), audit logging of
  patient-data access, and absence of patient identifiers from logs and error output.
- **FR-011**: A step-by-step deployment guide MUST exist that an operator with general computer
  literacy (not specialized DevOps experience) can follow end-to-end, where each step includes a
  verification check and common-failure remedies.
- **FR-012**: The deployment MUST be reproducible: following the same guide and configuration on a
  fresh server MUST yield an equivalent running system.
- **FR-013**: Application logs MUST be accessible to the operator for troubleshooting, and MUST NOT
  contain patient identifiers or secrets.
- **FR-014**: The deployment MUST allow configuration of environment-specific values (domain,
  timezone defaults, etc.) without changing application code.
- **FR-015**: The system MUST present a clear, non-technical error/maintenance page when the
  application is unavailable, rather than exposing internal error details to end users.

### Key Entities *(include if feature involves data)*

- **Deployment environment**: The target server and its runtime — the network address, the operator's
  domain, the encrypted endpoint, and the set of running services (application, data store).
- **Configuration & secrets**: The environment-specific values and protected credentials required to
  run in production, kept out of version control and injected at deploy time.
- **Backup artifact**: A restorable, encrypted copy of all persistent data, with a known location and
  creation time, used to recover after failure.
- **Release/version**: A deployable build of the application that can be rolled out and, conceptually,
  rolled back; deploying a release may carry schema migrations.
- **Deployment guide / runbook**: The ordered, verifiable set of operator instructions covering
  provisioning, configuration, go-live, verification, backup/restore, and updates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time operator can take a fresh server to a healthy, publicly reachable,
  HTTPS-secured production instance in under 60 minutes by following the guide alone.
- **SC-002**: 100% of deployment steps in the guide include a verification check the operator can run
  to confirm success before proceeding.
- **SC-003**: From a device outside the build environment, staff can load the live app over HTTPS with
  a valid certificate (zero browser security warnings) and complete a booking on the first attempt.
- **SC-004**: A simulated server failure followed by a restore from backup recovers 100% of
  appointments, accounts, and audit records with zero data loss within 30 minutes.
- **SC-005**: Deploying a new application version preserves all existing data, applies pending schema
  changes automatically, and results in less than 5 minutes of user-visible downtime.
- **SC-006**: The production instance enforces every behavior gate verifiable in production —
  concurrent double-booking attempts never both succeed, and cross-center access attempts are denied
  100% of the time.
- **SC-007**: No secret or patient identifier appears in committed files, application logs, or
  end-user error output (verified by inspection).
- **SC-008**: After an unplanned server reboot, the application returns to a healthy serving state
  automatically with no operator action.

## Assumptions

- **Hosting model**: Deployment targets a single managed Linux virtual server running the application
  and its database together via containers (Docker Compose). Managed-PaaS, multi-node cloud, and
  Kubernetes models are out of scope for this go-live.
- **Domain & TLS**: The operator already owns a domain and can edit its DNS; certificates are issued
  and renewed automatically (Let's Encrypt-style) for that domain.
- **Delivery style**: Deployment is delivered as prepared configuration/scripts plus a step-by-step
  guide that the operator runs interactively; full unattended CI/CD auto-deploy is out of scope for
  this go-live (may follow later).
- **Compliance posture**: A pilot/baseline security posture is targeted — TLS in transit, encryption
  at rest where supported, audit logging, encrypted backups, and the existing constitution gates.
  Formal HIPAA/GDPR certification, BAAs/DPAs, and strict data-residency programs are deferred until
  after pilot validation.
- **Scale**: Pilot scale per the existing plan — roughly 10 centers, ~50 concurrent users, and
  low-thousands of appointments per month; a single server is sufficient.
- **Operator profile**: The operator is computer-literate but not a specialist DevOps engineer; the
  guide assumes no prior container-orchestration experience.
- **Application readiness**: The application from feature `001-clinic-scheduling` is functionally
  complete and passing its tests; this feature concerns making it deployable and operable, not adding
  scheduling features.
- **Notifications**: In-app notifications only; no external email/SMS infrastructure is provisioned as
  part of deployment.
- **Data residency**: Region selection for the server is left to the operator's preference/cost; no
  specific jurisdiction is mandated at pilot stage.

## Dependencies

- A registered domain name with editable DNS controlled by the operator.
- A provisioned Linux virtual server (or an account with a provider where one can be created) with
  inbound HTTP/HTTPS access.
- The completed, test-passing application from feature `001-clinic-scheduling`.
- Operator access to create the server, set DNS records, and store secrets securely.
