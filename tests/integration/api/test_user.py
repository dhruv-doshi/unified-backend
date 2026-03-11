import pytest
from unittest.mock import patch, AsyncMock
import uuid


@pytest.mark.asyncio
async def test_profile_requires_auth(client):
    response = await client.get("/api/v1/user/profile")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_images_requires_auth(client):
    response = await client.get("/api/v1/user/images")
    assert response.status_code == 401
