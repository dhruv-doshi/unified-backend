import pytest
import uuid
import io
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import update
from PIL import Image

from src.infrastructure.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_image_bytes(width=100, height=100):
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


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


# ── test_get_analysis_not_found ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_analysis_not_found(client, db):
    token, _ = await _make_verified_user(client, db)
    random_id = uuid.uuid4()

    response = await client.get(
        f"/api/v1/analysis/{random_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


# ── test_get_analysis_forbidden ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_analysis_forbidden(client, db):
    # Create two users
    token_a, user_id_a = await _make_verified_user(client, db, "_a")
    token_b, user_id_b = await _make_verified_user(client, db, "_b")

    img_bytes = _make_image_bytes()

    # User A uploads an image
    with patch("src.domain.analysis.service.upload_bytes", side_effect=["https://cdn.example.com/original.jpg", "https://cdn.example.com/thumb.jpg"]):
        with patch("src.workers.analysis_tasks.analyze_image_task") as mock_task:
            mock_task.delay = MagicMock()
            with patch("src.api.v1.analysis.routes.check_daily_limit_ist", new_callable=AsyncMock):
                upload_resp = await client.post(
                    "/api/v1/analysis/upload",
                    files={"image": ("test.jpg", img_bytes, "image/jpeg")},
                    headers={"Authorization": f"Bearer {token_a}"},
                )
    assert upload_resp.status_code == 202, f"Upload failed: {upload_resp.json()}"
    analysis_id = upload_resp.json()["data"]["analysisId"]

    # User B tries to access user A's analysis
    response = await client.get(
        f"/api/v1/analysis/{analysis_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


# ── test_upload_and_get_analysis ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_and_get_analysis(client, db):
    token, user_id = await _make_verified_user(client, db)
    img_bytes = _make_image_bytes()

    with patch("src.domain.analysis.service.upload_bytes", side_effect=["https://cdn.example.com/original.jpg", "https://cdn.example.com/thumb.jpg"]):
        with patch("src.workers.analysis_tasks.analyze_image_task") as mock_task:
            mock_task.delay = MagicMock()
            with patch("src.api.v1.analysis.routes.check_daily_limit_ist", new_callable=AsyncMock):
                upload_resp = await client.post(
                    "/api/v1/analysis/upload",
                    files={"image": ("photo.jpg", img_bytes, "image/jpeg")},
                    headers={"Authorization": f"Bearer {token}"},
                )

    assert upload_resp.status_code == 202, f"Upload failed: {upload_resp.json()}"
    data = upload_resp.json()["data"]
    assert "analysisId" in data
    assert data["status"] == "processing"

    analysis_id = data["analysisId"]

    # GET the analysis
    get_resp = await client.get(
        f"/api/v1/analysis/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    analysis_data = get_resp.json()["data"]
    assert analysis_data["status"] == "processing"
    assert analysis_data["filename"] == "photo.jpg"
    assert str(analysis_id) == str(analysis_data["id"])


# ── test_upload_requires_auth ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_no_auth_analysis_full(client, db):
    img_bytes = _make_image_bytes()
    response = await client.post(
        "/api/v1/analysis/upload",
        files={"image": ("test.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 401


# ── test_upload_invalid_format ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_invalid_format(client, db):
    token, _ = await _make_verified_user(client, db)

    # Fake GIF bytes
    fake_gif = b"GIF89a" + b"\x00" * 100

    with patch("src.api.v1.analysis.routes.check_daily_limit_ist", new_callable=AsyncMock):
        response = await client.post(
            "/api/v1/analysis/upload",
            files={"image": ("test.gif", fake_gif, "image/gif")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 415
    assert response.json()["code"] == "UNSUPPORTED_FORMAT"


# ── test_get_analysis_owner_can_access ───────────────────────────────────────

@pytest.mark.asyncio
async def test_get_analysis_owner_can_access(client, db):
    token, user_id = await _make_verified_user(client, db)
    img_bytes = _make_image_bytes()

    with patch("src.domain.analysis.service.upload_bytes", side_effect=["https://cdn.example.com/img.jpg", "https://cdn.example.com/thumb.jpg"]):
        with patch("src.workers.analysis_tasks.analyze_image_task") as mock_task:
            mock_task.delay = MagicMock()
            with patch("src.api.v1.analysis.routes.check_daily_limit_ist", new_callable=AsyncMock):
                upload_resp = await client.post(
                    "/api/v1/analysis/upload",
                    files={"image": ("owner_test.jpg", img_bytes, "image/jpeg")},
                    headers={"Authorization": f"Bearer {token}"},
                )

    assert upload_resp.status_code == 202
    analysis_id = upload_resp.json()["data"]["analysisId"]

    get_resp = await client.get(
        f"/api/v1/analysis/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["success"] is True
