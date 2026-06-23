# Feature Specification: Clinic Patient Scheduling

**Feature Branch**: `001-clinic-scheduling`  
**Created**: 2026-06-22  
**Status**: Draft  
**Input**: User description: "web app for schedule patient between doctor and reciption doctors and reciption should have seperate accounts and thier should be addmin for each center"

## Clarifications

### Session 2026-06-22

- Q: How should bookable appointment times be defined for a doctor? → A: Fixed base grid (e.g., 15-min units) with each appointment spanning one or more units to honor its expected duration (fixed-grid slots, variable length).
- Q: How should a doctor's working hours / availability be defined? → A: A recurring weekly template plus date-specific exceptions (time off, holidays, extra hours).
- Q: When a center admin creates a staff account, how does that person get their login credentials? → A: Admin sets an initial/temporary password shared out-of-band; user is forced to change it on first login (no email/SMS in v1).
- Q: What scale should v1 be designed for? → A: Small pilot — up to ~10 centers, ~50 concurrent users, low-thousands of appointments/month.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reception schedules patient appointments (Priority: P1)

A reception staff member at a center registers a patient (or finds an existing one) and books an appointment into a doctor's calendar at an available time slot. The booked appointment immediately appears on the doctor's schedule and on the center's daily view.

**Why this priority**: This is the core value of the product — getting a patient onto a doctor's calendar. Without it, nothing else matters. A center could run its front desk on this alone.

**Independent Test**: Log in as reception, create/find a patient, select a doctor and an open slot, confirm the booking, and verify it appears on both the reception calendar and the doctor's schedule. Delivers a working booking system on its own.

**Acceptance Scenarios**:

1. **Given** a reception user viewing a doctor's calendar with open slots, **When** they select an open slot and assign a registered patient, **Then** an appointment is created and shown on that doctor's schedule for that time.
2. **Given** an existing appointment, **When** reception reschedules it to a different open slot, **Then** the appointment moves and the original slot becomes available again.
3. **Given** an existing appointment, **When** reception cancels it, **Then** the slot becomes available and the appointment is marked cancelled (not deleted from history).
4. **Given** a slot that is already booked, **When** reception attempts to book another patient into the same doctor/time, **Then** the system prevents the double-booking and explains why.

---

### User Story 2 - Doctor sends an appointment request to reception (Priority: P1)

A doctor (e.g., during or after a consultation) decides a patient needs a follow-up or a new appointment and sends an appointment request to the center's reception. Reception receives the request in a queue, picks a concrete time slot, and confirms it — turning the request into a scheduled appointment.

**Why this priority**: This is the explicit "schedule patient between doctor and reception" handoff the product is built around. It is the second half of the core loop and distinguishes this product from a plain calendar.

**Independent Test**: Log in as a doctor, create an appointment request for a patient with desired details (urgency, preferred timeframe, notes); log in as reception, see the request in the pending queue, assign a slot, and confirm. Verify the request becomes a scheduled appointment and is removed from the pending queue.

**Acceptance Scenarios**:

1. **Given** a doctor with a patient in front of them, **When** the doctor submits an appointment request with patient, reason, and preferred timeframe, **Then** the request appears in reception's pending-requests queue for that center.
2. **Given** a pending request, **When** reception assigns an open slot and confirms, **Then** the request becomes a fixed (confirmed) appointment on the doctor's calendar, the request is marked fulfilled, and the doctor can see the confirmed time.
3. **Given** a pending request, **When** reception declines it with a reason (e.g., no availability), **Then** the doctor is notified in-app of the decline and reason.
4. **Given** a pending request older than its preferred timeframe, **When** reception views the queue, **Then** overdue/urgent requests are visually distinguished.

---

### User Story 3 - Center admin manages staff accounts (Priority: P2)

A center admin creates and manages the accounts for their center's doctors and reception staff, sets each person's role, and deactivates accounts when staff leave. Each staff member has their own separate login.

**Why this priority**: Required for a center to operate with more than one hard-coded user and to keep roles separated, but a single-center pilot could begin with pre-provisioned accounts, so it ranks just below the core booking loop.

**Independent Test**: Log in as a center admin, create a doctor account and a reception account, verify each can log in with their own credentials and sees only role-appropriate screens, then deactivate one and verify they can no longer log in.

**Acceptance Scenarios**:

1. **Given** a center admin, **When** they create a new staff member with a role (doctor or reception), **Then** that person receives credentials and can log in with access scoped to that role.
2. **Given** an active staff account, **When** the admin deactivates it, **Then** that user can no longer log in but their historical records (appointments, requests) remain intact.
3. **Given** a center admin, **When** they view their staff list, **Then** they see only staff belonging to their own center and no one from other centers.
4. **Given** a doctor account, **When** the admin sets the doctor's working hours/availability, **Then** reception can only book that doctor within those hours.

---

### User Story 4 - Platform super-admin provisions centers (Priority: P2)

A platform super-admin creates a new center, configures its basic profile, and creates that center's first admin account. Each center is isolated from every other center.

**Why this priority**: Enables onboarding multiple centers (the multi-center requirement), but the first center can be seeded manually, so it follows the core operational stories.

**Independent Test**: Log in as super-admin, create a center, assign its first admin, then verify that admin can log in and manage only their own center while being unable to see any other center's data.

**Acceptance Scenarios**:

1. **Given** a super-admin, **When** they create a center and assign an admin, **Then** that center exists and its admin can log in and manage it.
2. **Given** two centers each with their own data, **When** any non-super-admin user from one center is logged in, **Then** they cannot view, search, or access any data belonging to the other center.
3. **Given** a super-admin, **When** they suspend a center, **Then** all of that center's users are blocked from logging in until it is reactivated.

---

### Edge Cases

- What happens when reception tries to book a patient with a doctor who is on leave or outside working hours? → Booking is blocked with an explanation.
- What happens when two reception users try to book the same slot at the same moment? → Only one booking succeeds; the other is told the slot was just taken.
- What happens when a patient has overlapping appointments with two different doctors at the same time? → System warns of the patient time conflict before confirming.
- How does the system handle a doctor's appointment request for a patient who is later found to be a duplicate record? → Patient records can be merged without losing appointment history (merge may be deferred; at minimum duplicates are detectable by name + phone).
- What happens to pending requests and future appointments when a doctor account is deactivated? → Future appointments are flagged for reception to reassign or cancel; pending requests are surfaced for handling.
- How does the system handle a no-show? → Reception can mark an appointment as "no-show", distinct from "cancelled" and "completed".
- What happens when a center is suspended mid-day with appointments on the books? → Existing records are preserved; users simply cannot log in until reactivated.

## Requirements *(mandatory)*

### Functional Requirements

#### Accounts, Roles & Access

- **FR-001**: System MUST support four distinct roles: platform super-admin, center admin, doctor, and reception, each with its own separate login credentials.
- **FR-002**: System MUST scope every center admin, doctor, and reception user to exactly one center and prevent them from accessing any other center's data.
- **FR-003**: System MUST allow a platform super-admin to create, configure, suspend, and reactivate centers, and to create each center's first admin account.
- **FR-004**: System MUST allow a center admin to create, edit, deactivate, and reactivate doctor and reception accounts within their own center only.
- **FR-004a**: When creating a staff account, the admin MUST set an initial/temporary password (shared with the user out-of-band, since there is no email/SMS in v1), and the system MUST force the user to set a new password on first login.
- **FR-005**: System MUST present each user only the screens and actions permitted by their role (e.g., reception cannot manage staff accounts; doctors cannot finalize bookings).
- **FR-006**: System MUST preserve historical records (appointments, requests, patient data) when a user account is deactivated.
- **FR-007**: System MUST authenticate users via email/username and password, with sessions scoped to a single center per login.

#### Patients

- **FR-008**: Reception MUST be able to register a new patient and search/find existing patients within their center.
- **FR-009**: System MUST store, at minimum, patient name, phone number, and any clinic-relevant identifiers per patient.
- **FR-010**: System MUST help detect likely duplicate patients (e.g., matching name and phone) during registration.
- **FR-011**: Patients MUST NOT have login accounts in this version (all patient interaction is mediated by staff).

#### Doctor Availability

- **FR-012**: System MUST allow a doctor's working hours/availability to be defined (by the doctor and/or center admin) per center as a recurring weekly template plus date-specific exceptions (time off, holidays, or extra/changed hours that override the template for given dates).
- **FR-013**: System MUST prevent booking a doctor outside their defined availability or during marked time off.

#### Appointment Requests (Doctor → Reception)

- **FR-014**: Doctors MUST be able to submit an appointment request for a patient that carries the details reception needs to book it, including at minimum: the patient, reason/visit type, preferred timeframe, urgency, expected duration, and free-text notes.
- **FR-015**: System MUST place doctor-submitted requests into a pending-requests queue visible to reception for that center.
- **FR-016**: Reception MUST be able to fulfill a doctor's request by marking it as a fixed (confirmed) appointment — assigning a specific doctor, date, and open time slot — or decline it with a reason. Only reception can turn a request into a fixed appointment.
- **FR-017**: System MUST notify the requesting doctor in-app when their request is fulfilled or declined.
- **FR-018**: System MUST visually distinguish urgent or overdue requests in the reception queue.

#### Scheduling

- **FR-019**: Reception MUST be able to create, reschedule, and cancel appointments by selecting a doctor, an open time slot, and a patient — including direct bookings (e.g., walk-ins) that do NOT originate from a doctor's request.
- **FR-019a**: System MUST model bookable time as a fixed base grid (configurable per center/doctor, e.g., 15-minute units); each appointment occupies one or more contiguous units sufficient to cover its expected duration, and the schedule must be validated and displayed against this grid.
- **FR-020**: System MUST prevent double-booking the same doctor for overlapping times (i.e., any overlap of the units an appointment occupies).
- **FR-021**: System MUST warn when a patient would have two overlapping appointments.
- **FR-022**: System MUST support appointment statuses including at least: scheduled, completed, cancelled, and no-show.
- **FR-023**: System MUST provide a daily/weekly schedule view per doctor and a center-wide day view for reception.
- **FR-024**: Doctors MUST be able to view their own upcoming and past appointments.
- **FR-025**: System MUST keep a cancelled appointment in history rather than permanently deleting it, and free its slot for rebooking.

#### Notifications

- **FR-026**: System MUST deliver request and appointment updates to relevant staff via in-app notifications only (no SMS/email/WhatsApp in this version).

### Key Entities *(include if feature involves data)*

- **Center**: A clinic/practice that is the unit of tenancy and isolation. Has a profile, a status (active/suspended), staff, patients, and appointments. All non-super-admin data belongs to exactly one center.
- **User**: A person with login credentials and one role (super-admin, center admin, doctor, or reception). Non-super-admin users belong to one center.
- **Doctor (profile)**: A user with role doctor; additionally has working hours/availability and a schedule of appointments.
- **Patient**: A person receiving care, registered and managed by staff; no login. Belongs to one center; has identifying/contact details.
- **Appointment Request**: A doctor-originated request to schedule a patient, with reason, preferred timeframe/urgency, and a state (pending, fulfilled, declined). Belongs to one center; references a doctor and a patient.
- **Appointment**: A confirmed booking linking a patient, a doctor, a start time, and a duration spanning one or more contiguous base-grid units, plus a status (scheduled, completed, cancelled, no-show). Belongs to one center; may originate from a request or a direct reception booking.
- **Availability/Schedule**: A doctor's bookable working hours within a center, expressed as a recurring weekly template plus date-specific exceptions (time off, holidays, extra/changed hours), against which appointments are validated. Time is divided into a fixed base grid (e.g., 15-minute units) used for booking and conflict detection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reception user can book a new appointment (find/create patient → pick slot → confirm) in under 90 seconds.
- **SC-002**: A doctor can submit an appointment request to reception in under 30 seconds.
- **SC-003**: 100% of attempts to double-book a doctor or violate availability are prevented.
- **SC-004**: 100% of one center's operational data (patients, appointments, requests, staff) is inaccessible to users of any other center.
- **SC-005**: 95% of pending doctor requests are actioned (fulfilled or declined) by reception within the same business day in a piloting center.
- **SC-006**: Reception can locate an existing patient by name or phone in under 10 seconds.
- **SC-007**: A center admin can create a fully working staff account (able to log in with correct role access) in under 2 minutes.

## Assumptions

- **Multi-tenant, super-admin onboarding**: Centers and their first admin are provisioned by a platform super-admin; centers cannot self-register in this version. Aligns with the multi-tenant model used across the operator's other products.
- **Doctor→reception handoff is the booking origination model**: Doctors do not place patients directly onto the calendar; they send requests and reception performs the actual scheduling. Reception may also create walk-in/direct bookings.
- **No patient self-service**: Patients have no accounts and cannot book online in v1; all interaction is staff-mediated.
- **In-app notifications only**: No SMS, WhatsApp, or email integration in v1.
- **Scheduling-only scope**: The app does the appointment-scheduling workflow only (staff accounts, patients, doctor→reception requests, calendars). Billing, clinical records/charting, inventory, and other clinic-management features are out of scope for v1.
- **Language**: The primary UI language is English. Arabic / right-to-left (RTL) support is deferred to a future version.
- **Egypt context**: The deploying clinics operate in Egypt; EGP currency, locale formatting, and local privacy/health regulations (PDPL, MoHP, Dental Syndicate) are expected to apply where relevant (to be detailed in planning). Mobile-responsive web is desirable; native mobile apps are out of scope for v1.
- **Single time zone per center**: Each center operates in one local time zone.
- **One active session scope per login**: A user logs into one center context at a time, consistent with strict tenant isolation.
- **Standard web app expectations**: Session-based authentication, user-friendly error messages, and standard web performance are assumed unless otherwise specified.
- **v1 scale (pilot)**: The system is designed for a small pilot — up to ~10 centers, ~50 concurrent users, and low-thousands of appointments per month — not as a hard cap but as the sizing target for architecture decisions.
