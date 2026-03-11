import pytest
import uuid
from unittest.mock import patch, AsyncMock
from sqlalchemy import update

from src.infrastructure.models.user import User


# ── Helper ────────────────────────────────────────────────────────────────────

async def _make_verified_user(client, db, email_suffix=""):
    """Register a user and mark them verified directly in the DB."""
    email = f"user_{uuid.uuid4().hex[:8]}{email_suffix}@test.com"
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json={
            "name": "Test User", "email": email, "password": "Password123!"
        })
    assert resp.status_code == 201
    user_id = uuid.UUID(resp.json()["data"]["user"]["id"])

    await db.execute(update(User).where(User.id == user_id).values(is_verified=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200, f"Login failed: {login.json()}"
    token = login.json()["data"]["accessToken"]
    return token, user_id


# ── test_get_profile ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_profile(client, db):
    token, user_id = await _make_verified_user(client, db)

    response = await client.get(
        "/api/v1/user/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    result = data["data"]
    assert "id" in result
    assert "name" in result
    assert "email" in result
    assert result["id"] == str(user_id)


# ── test_get_images_empty ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_images_empty(client, db):
    token, _ = await _make_verified_user(client, db)

    response = await client.get(
        "/api/v1/user/images",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["data"] == []
    assert data["data"]["total"] == 0


# ── test_delete_image_not_found ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_image_not_found(client, db):
    token, _ = await _make_verified_user(client, db)
    random_id = uuid.uuid4()

    response = await client.delete(
        f"/api/v1/user/images/{random_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


# ── test_profile_returns_correct_email ───────────────────────────────────────

@pytest.mark.asyncio
async def test_profile_returns_correct_email(client, db):
    email = f"profile_{uuid.uuid4().hex[:8]}@test.com"
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        resp = await client.post("/api/v1/auth/register", json={
            "name": "Profile User", "email": email, "password": "Password123!"
        })
    assert resp.status_code == 201
    user_id = uuid.UUID(resp.json()["data"]["user"]["id"])

    await db.execute(update(User).where(User.id == user_id).values(is_verified=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    token = login.json()["data"]["accessToken"]

    profile_resp = await client.get(
        "/api/v1/user/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile_resp.status_code == 200
    assert profile_resp.json()["data"]["email"] == email
    assert profile_resp.json()["data"]["name"] == "Profile User"


# ── test_images_pagination ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_images_pagination_params(client, db):
    token, _ = await _make_verified_user(client, db)

    response = await client.get(
        "/api/v1/user/images?page=1&limit=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["page"] == 1
    assert data["data"]["limit"] == 5


# ── test_profile_requires_auth ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_image_requires_auth(client, db):
    random_id = uuid.uuid4()
    response = await client.delete(f"/api/v1/user/images/{random_id}")
    assert response.status_code == 401
