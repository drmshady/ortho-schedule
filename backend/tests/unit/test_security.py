from src.core.security import hash_password, sign_payload, verify_password, verify_signed_payload


def test_verify_password_rejects_mismatch_and_malformed_hash() -> None:
    password_hash = hash_password("CorrectPassword123!")

    assert verify_password("CorrectPassword123!", password_hash) is True
    assert verify_password("WrongPassword123!", password_hash) is False
    assert verify_password("CorrectPassword123!", "not-an-argon2-hash") is False


def test_signed_payload_rejects_tampered_signature() -> None:
    token = sign_payload({"sid": "abc123"}, "test-secret")
    body, _signature = token.split(".", 1)

    assert verify_signed_payload(token, "test-secret") == {"sid": "abc123"}
    assert verify_signed_payload(f"{body}.tampered", "test-secret") is None
