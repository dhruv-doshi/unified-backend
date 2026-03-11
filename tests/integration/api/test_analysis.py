import pytest
import io
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from PIL import Image


def _make_image_bytes():
    img = Image.new("RGB", (100, 100), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _get_verified_token(client) -> tuple[str, uuid.UUID]:
    """Register, verify, login — return (token, user_id)."""
    from src.infrastructure.models.user import User
    from src.core.dependencies import get_db
    from sqlalchemy import update

    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"name": "Eve", "email": f"eve_{uuid.uuid4()}@example.com", "password": "Password123!"},
        )
    assert resp.status_code == 201
    user_id = uuid.UUID(resp.json()["data"]["user"]["id"])

    # Directly verify user via DB
    async for db in get_db():
        await db.execute(update(User).where(User.id == user_id).values(is_verified=True))
        await db.commit()
        break

    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": resp.json()["data"]["user"]["email"], "password": "Password123!"},
    )
    token = login_resp.json()["data"]["accessToken"]
    return token, user_id


@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    img = _make_image_bytes()
    response = await client.post(
        "/api/v1/analysis/upload",
        files={"image": ("test.jpg", img, "image/jpeg")},
    )
    assert response.status_code == 401
