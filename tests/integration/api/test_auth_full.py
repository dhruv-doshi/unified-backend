import pytest
import uuid
from unittest.mock import patch, AsyncMock
from sqlalchemy import select

from src.infrastructure.models.auth import EmailVerification, PasswordReset
from src.infrastructure.models.user import User


# ── Helper ────────────────────────────────────────────────────────────────────

async def _register_user(client, email=None, password="Password123!", name="Test User"):
    """Register a user and return (response, email)."""
    if email is None:
        email = f"user_{uuid.uuid4().hex[:8]}@test.com"
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json={
            "name": name, "email": email, "password": password,
        })
    return resp, email


# ── test_verify_email_success ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_email_success(client, db):
    resp, email = await _register_user(client)
    assert resp.status_code == 201
    user_id = uuid.UUID(resp.json()["data"]["user"]["id"])

    # Fetch the verification token from DB
    result = await db.execute(
        select(EmailVerification).where(EmailVerification.user_id == user_id)
    )
    verification = result.scalar_one()

    verify_resp = await client.post("/api/v1/auth/verify-email", json={"token": verification.token})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["success"] is True


# ── test_verify_email_invalid_token ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_email_invalid_token(client, db):
    response = await client.post("/api/v1/auth/verify-email", json={"token": "bogus-token-xyz"})
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


# ── test_reset_password_flow ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_password_flow(client, db):
    email = f"reset_{uuid.uuid4().hex[:8]}@test.com"

    # Register
    resp, _ = await _register_user(client, email=email)
    assert resp.status_code == 201
    user_id = uuid.UUID(resp.json()["data"]["user"]["id"])

    # Verify email directly in DB
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    user.is_verified = True
    await db.commit()

    # Call forgot-password (mock email sending)
    with patch("src.domain.auth.service.send_password_reset_email", new_callable=AsyncMock):
        forgot_resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_resp.status_code == 200

    # Fetch the reset token from DB
    reset_result = await db.execute(
        select(PasswordReset).where(PasswordReset.user_id == user_id)
    )
    reset = reset_result.scalar_one()

    # Reset password
    new_password = "NewPassword456!"
    reset_resp = await client.post("/api/v1/auth/reset-password", json={
        "token": reset.token,
        "password": new_password,
    })
    assert reset_resp.status_code == 200
    assert reset_resp.json()["success"] is True

    # Verify login works with new password
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": new_password,
    })
    assert login_resp.status_code == 200
    assert "accessToken" in login_resp.json()["data"]

    # Old password should no longer work
    old_login_resp = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Password123!",
    })
    assert old_login_resp.status_code == 401


# ── test_register_password_too_short ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_password_too_short(client, db):
    response = await client.post("/api/v1/auth/register", json={
        "name": "Test User",
        "email": "short@test.com",
        "password": "abc",
    })
    assert response.status_code == 422


# ── test_register_empty_name ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_empty_name(client, db):
    response = await client.post("/api/v1/auth/register", json={
        "name": "",
        "email": "emptyname@test.com",
        "password": "Password123!",
    })
    assert response.status_code == 422


# ── test_reset_password_invalid_token ────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_password_invalid_token(client, db):
    response = await client.post("/api/v1/auth/reset-password", json={
        "token": "invalid-reset-token",
        "password": "NewPassword123!",
    })
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


# ── test_verify_email_already_used ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_email_already_used(client, db):
    resp, email = await _register_user(client)
    assert resp.status_code == 201
    user_id = uuid.UUID(resp.json()["data"]["user"]["id"])

    result = await db.execute(
        select(EmailVerification).where(EmailVerification.user_id == user_id)
    )
    verification = result.scalar_one()
    token = verification.token

    # First verify should succeed
    first = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert first.status_code == 200

    # Second verify with same token should fail (token already used)
    second = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert second.status_code == 401
    assert second.json()["code"] == "TOKEN_INVALID"
