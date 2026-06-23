# Quickstart: Clinic Patient Scheduling

How to run the stack locally and walk through the core loop. Aligns with the plan's structure
(`backend/`, `frontend/`, `e2e/`) and research decisions.

## Prerequisites

- Python 3.12, Node 20+, Docker (for PostgreSQL).
- PostgreSQL 16 with the `btree_gist` extension (provided by the official image).

## 1. Start the database

```bash
docker run --name clinic-db -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=clinic \
  -p 5432:5432 -d postgres:16
```

The first migration enables the extension and creates the booking exclusion constraint:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE appointment
  ADD CONSTRAINT no_double_booking
  EXCLUDE USING gist (doctor_id WITH =, period WITH &&) WHERE (status = 'scheduled');
```

## 2. Backend

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/clinic
export SESSION_SECRET=dev-only-change-me
alembic upgrade head
# Seed a super-admin (one-off script)
python -m src.scripts.seed_superadmin --email super@platform.test --password 'ChangeMe123!'
uvicorn src.main:app --reload --port 8000
```

API is at `http://localhost:8000/api/v1`; OpenAPI docs at `/docs`.

## 3. Frontend

```bash
cd frontend
npm install
npm run gen:api          # regenerates the typed client from ../specs/.../contracts/openapi.yaml
npm run dev              # http://localhost:5173 (proxies /api to :8000)
```

## 4. Walk the core loop (maps to acceptance scenarios)

1. **Super-admin provisions a center** (US4): log in as super-admin → create a center
   (name, `Africa/Cairo`, grid 15) with a first admin email + temp password.
2. **Center admin sets up staff** (US3): log in as that admin (forced password change on first
   login) → create a `doctor` and a `reception` account, each with a temp password.
3. **Doctor sets availability** (FR-012): log in as the doctor (change password) → add a weekly
   template (e.g., Mon 09:00–13:00) and optionally a date exception (block a holiday).
4. **Reception books a walk-in** (US1): log in as reception (change password) → register/find a
   patient → open the doctor's day → pick an open slot → confirm. Verify it appears on the
   doctor schedule and the center day view. Try booking the same slot again → blocked with
   `double_booking`.
5. **Doctor → reception handoff** (US2): log in as doctor → submit an appointment request
   (patient, reason, urgency, expected duration) → log in as reception → see it in the pending
   queue (urgent/overdue highlighted) → fulfill it into a slot. Verify the request shows
   `fulfilled`, an appointment exists, and the doctor gets an in-app notification.

## 5. Tests (Constitution Principle V)

```bash
# Backend: contract + integration (incl. concurrency & cross-tenant isolation) against real Postgres
cd backend && pytest

# Frontend component/integration
cd frontend && npm test

# End-to-end across roles
cd e2e && npx playwright test
```

The suites that gate merge specifically include: double-booking under contention, cross-tenant
access attempts returning 403/empty, forced-first-login password change, and the
doctor→reception fulfill/decline flow (see `contracts/README.md`).

## Key environment variables

| Var | Purpose |
|-----|---------|
| `DATABASE_URL` | Postgres DSN (async psycopg) |
| `SESSION_SECRET` | Signs session cookies — supply via secret manager in prod (Principle I) |
| `COOKIE_SECURE` | `true` in prod (HTTPS only) |

> Production deployment must terminate TLS 1.2+, enable Postgres at-rest encryption and
> encrypted backups, and supply all secrets via a secret manager — never committed (Principle
> I). PHI fields (see data-model.md) must never appear in logs.
