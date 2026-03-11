import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_register(client):
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Alice", "email": "alice@example.com", "password": "Password123!"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "accessToken" in data["data"]
    assert data["data"]["user"]["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        await client.post(
            "/api/v1/auth/register",
            json={"name": "Bob", "email": "bob@example.com", "password": "Password123!"},
        )
        response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Bob2", "email": "bob@example.com", "password": "Password123!"},
        )
    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_EXISTS"


@pytest.mark.asyncio
async def test_login_unverified(client):
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        await client.post(
            "/api/v1/auth/register",
            json={"name": "Carol", "email": "carol@example.com", "password": "Password123!"},
        )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "Password123!"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "EMAIL_NOT_VERIFIED"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        await client.post(
            "/api/v1/auth/register",
            json={"name": "Dave", "email": "dave@example.com", "password": "Password123!"},
        )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "dave@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_forgot_password_silent(client):
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
