"""T078: Comprehensive cross-tenant isolation (US4, Principle II NON-NEGOTIABLE).

A user authenticated into center A must never view, search, or act on center B's
patients, appointments, requests, or staff. Every cross-center reference resolves to
403/404/empty — never another center's data.
"""
from httpx import AsyncClient
from tests.helpers import seed_clinic


async def _login(client: AsyncClient, email: str, password: str) -> int:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.status_code


async def _two_clinics(database_url: str):
    clinic_a = await seed_clinic(database_url)
    clinic_b = await seed_clinic(
        database_url,
        name="Uptown Clinic",
        reception_email="reception-b@example.com",
        doctor_email="doctor-b@example.com",
        doctor2_email="doctor2-b@example.com",
        admin_email="admin-b@example.com",
    )
    return clinic_a, clinic_b


async def test_patients_are_not_visible_across_centers(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic_a, clinic_b = await _two_clinics(prepared_database)
    assert await _login(client, clinic_b.reception_email, clinic_b.reception_password) == 200

    # Center B's reception searching for Center A's patient (by name) finds nothing.
    resp = await client.get("/api/v1/patients", params={"q": "Jane"})
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert str(clinic_a.patient_id) not in ids


async def test_doctors_list_is_center_scoped(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic_a, clinic_b = await _two_clinics(prepared_database)
    assert await _login(client, clinic_b.reception_email, clinic_b.reception_password) == 200

    resp = await client.get("/api/v1/doctors")
    assert resp.status_code == 200
    doctor_ids = {d["id"] for d in resp.json()}
    assert str(clinic_a.doctor_id) not in doctor_ids
    assert str(clinic_b.doctor_id) in doctor_ids


async def test_cannot_book_against_another_centers_doctor(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic_a, clinic_b = await _two_clinics(prepared_database)
    assert await _login(client, clinic_b.reception_email, clinic_b.reception_password) == 200

    # Center B reception attempts to create a patient in B, then book it against A's doctor.
    created = await client.post(
        "/api/v1/patients", json={"full_name": "Cross Tenant", "phone": "01099999999"}
    )
    assert created.status_code == 201
    patient_id = created.json()["id"]

    resp = await client.post(
        "/api/v1/appointments",
        json={
            "patient_id": patient_id,
            "doctor_id": str(clinic_a.doctor_id),
            "starts_at": "2026-07-01T09:00:00Z",
            "duration_minutes": 30,
        },
    )
    assert resp.status_code in (403, 404, 422)


async def test_appointments_list_excludes_other_centers(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic_a, clinic_b = await _two_clinics(prepared_database)

    # Center A reception books a real appointment.
    assert await _login(client, clinic_a.reception_email, clinic_a.reception_password) == 200
    booked = await client.post(
        "/api/v1/appointments",
        json={
            "patient_id": str(clinic_a.patient_id),
            "doctor_id": str(clinic_a.doctor_id),
            "starts_at": "2026-07-01T09:00:00Z",
            "duration_minutes": 30,
        },
    )
    assert booked.status_code == 201
    appointment_id = booked.json()["id"]

    # Center B reception cannot see A's appointment, even querying A's doctor id.
    assert await _login(client, clinic_b.reception_email, clinic_b.reception_password) == 200
    resp = await client.get(
        "/api/v1/appointments", params={"doctor_id": str(clinic_a.doctor_id)}
    )
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        assert all(a["id"] != appointment_id for a in resp.json())


async def test_requests_are_not_visible_across_centers(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic_a, clinic_b = await _two_clinics(prepared_database)

    # Center A's doctor submits a request.
    assert await _login(client, clinic_a.doctor_email, clinic_a.reception_password) == 200
    created = await client.post(
        "/api/v1/requests",
        json={
            "patient_id": str(clinic_a.patient_id),
            "reason": "Follow-up",
            "urgency": "soon",
            "expected_duration_minutes": 30,
        },
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    # Center B's reception queue never shows A's request.
    assert await _login(client, clinic_b.reception_email, clinic_b.reception_password) == 200
    queue = await client.get("/api/v1/requests")
    assert queue.status_code == 200
    assert all(r["id"] != request_id for r in queue.json())


async def test_staff_are_not_visible_across_centers(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic_a, clinic_b = await _two_clinics(prepared_database)
    assert await _login(client, clinic_b.admin_email, clinic_b.reception_password) == 200

    resp = await client.get("/api/v1/users")
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert clinic_a.doctor_email not in emails
    assert clinic_a.admin_email not in emails

    # And editing A's user by id is rejected (resolves out-of-scope to 404).
    edit = await client.put(
        f"/api/v1/users/{clinic_a.doctor_id}", json={"is_active": False}
    )
    assert edit.status_code == 404
