"""Tests for the models status API endpoint."""

from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import repository
from app.main import app


@pytest_asyncio.fixture
async def client():
    await repository.connect(":memory:")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    await repository.close()


# ---------------------------------------------------------------------------
# GET /models/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_models_status_ready(client):
    mock_status = {
        "clap_loaded": True,
        "clapcap_loaded": False,
        "embeddings_ready": True,
        "embeddings_count": 4500,
        "loading": False,
        "error": None,
        "status_message": "Models ready",
    }
    with patch("app.routers.models.model_manager.get_status", return_value=mock_status):
        resp = await client.get("/models/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["clap_loaded"] is True
    assert data["embeddings_ready"] is True
    assert data["embeddings_count"] == 4500
    assert data["status_message"] == "Models ready"


@pytest.mark.asyncio
async def test_models_status_loading(client):
    mock_status = {
        "clap_loaded": False,
        "clapcap_loaded": False,
        "embeddings_ready": False,
        "embeddings_count": 0,
        "loading": True,
        "error": None,
        "status_message": "Loading CLAP model...",
    }
    with patch("app.routers.models.model_manager.get_status", return_value=mock_status):
        resp = await client.get("/models/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["loading"] is True
    assert data["clap_loaded"] is False


@pytest.mark.asyncio
async def test_models_status_error(client):
    mock_status = {
        "clap_loaded": False,
        "clapcap_loaded": False,
        "embeddings_ready": False,
        "embeddings_count": 0,
        "loading": False,
        "error": "Failed to download model",
        "status_message": "Error: Failed to download model",
    }
    with patch("app.routers.models.model_manager.get_status", return_value=mock_status):
        resp = await client.get("/models/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] == "Failed to download model"
