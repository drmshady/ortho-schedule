from httpx import AsyncClient
from tests.helpers import seed_clinic


async def _login_reception(client: AsyncClient, clinic) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": clinic.reception_email, "password": clinic.reception_password},
    )
    assert resp.status_code == 200


async def test_search_patients_returns_center_patients(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login_reception(client, clinic)

    resp = await client.get("/api/v1/patients", params={"q": "Jane"})

    assert resp.status_code == 200
    names = [p["full_name"] for p in resp.json()]
    assert "Jane Doe" in names


async def test_create_patient_succeeds(client: AsyncClient, prepared_database: str) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login_reception(client, clinic)

    resp = await client.post(
        "/api/v1/patients",
        json={"full_name": "Omar Hassan", "phone": "01222333444"},
    )

    assert resp.status_code == 201
    assert resp.json()["full_name"] == "Omar Hassan"


async def test_create_patient_duplicate_returns_409_then_confirm_succeeds(
    client: AsyncClient, prepared_database: str
) -> None:
    clinic = await seed_clinic(prepared_database)
    await _login_reception(client, clinic)

    duplicate = {"full_name": "Jane Doe", "phone": "01000000000"}
    conflict = await client.post("/api/v1/patients", json=duplicate)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "possible_duplicate"
    assert len(conflict.json()["candidates"]) >= 1

    confirmed = await client.post(
        "/api/v1/patients", json={**duplicate, "confirm_possible_duplicate": True}
    )
    assert confirmed.status_code == 201
