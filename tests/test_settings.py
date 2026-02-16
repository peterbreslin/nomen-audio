"""Tests for settings service and API."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.settings import (
    get_settings,
    load_settings,
    update_settings,
    validate_custom_field_tags,
    CustomFieldDef,
)


@pytest.fixture(autouse=True)
def _fresh_settings(tmp_path):
    """Reset settings to defaults using a temp file before each test."""
    path = tmp_path / "settings.json"
    load_settings(str(path))


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestSettingsService:
    def test_defaults(self):
        s = get_settings()
        assert s.creator_id == ""
        assert s.source_id == ""
        assert s.rename_on_save_default is True
        assert s.custom_fields == []
        assert s.llm_api_key is None
        assert s.version == 1

    def test_save_reload(self, tmp_path):
        path = tmp_path / "settings.json"
        load_settings(str(path))
        update_settings({"creator_id": "ABC", "source_id": "XYZ"})
        # Reload from disk
        load_settings(str(path))
        s = get_settings()
        assert s.creator_id == "ABC"
        assert s.source_id == "XYZ"

    def test_partial_update(self):
        update_settings({"creator_id": "NEW"})
        s = get_settings()
        assert s.creator_id == "NEW"
        assert s.source_id == ""  # unchanged

    def test_missing_file_loads_defaults(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        load_settings(str(path))
        s = get_settings()
        assert s.creator_id == ""

    def test_version_persisted_on_save(self, tmp_path):
        """Version field survives save → reload cycle."""
        path = tmp_path / "settings.json"
        load_settings(str(path))
        update_settings({"creator_id": "X"})
        load_settings(str(path))
        assert get_settings().version == 1

    def test_version_defaults_when_missing(self, tmp_path):
        """Loading a settings file without version field defaults to 1."""
        import json

        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"creator_id": "OLD"}))
        load_settings(str(path))
        assert get_settings().version == 1


class TestTagValidation:
    def test_valid_tag(self):
        fields = [CustomFieldDef(tag="RECORDIST", label="Recordist")]
        validate_custom_field_tags(fields)  # should not raise

    def test_lowercase_rejected(self):
        fields = [CustomFieldDef(tag="myTag", label="Test")]
        with pytest.raises(ValueError, match="myTag"):
            validate_custom_field_tags(fields)

    def test_too_long_rejected(self):
        fields = [CustomFieldDef(tag="A" * 33, label="Test")]
        with pytest.raises(ValueError, match="33"):
            validate_custom_field_tags(fields)

    def test_builtin_clash_rejected(self):
        fields = [CustomFieldDef(tag="CATEGORY", label="Test")]
        with pytest.raises(ValueError, match="CATEGORY"):
            validate_custom_field_tags(fields)

    def test_embedder_clash_rejected(self):
        fields = [CustomFieldDef(tag="EMBEDDER", label="Test")]
        with pytest.raises(ValueError, match="EMBEDDER"):
            validate_custom_field_tags(fields)


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_settings_defaults(client):
    resp = await client.get("/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["creator_id"] == ""
    assert data["rename_on_save_default"] is True


@pytest.mark.asyncio
async def test_put_settings_partial(client):
    resp = await client.put("/settings", json={"creator_id": "TESTER"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["creator_id"] == "TESTER"
    assert data["source_id"] == ""  # unchanged


@pytest.mark.asyncio
async def test_put_settings_invalid_tag(client):
    resp = await client.put(
        "/settings",
        json={"custom_fields": [{"tag": "lowercase", "label": "Bad"}]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_key_masking(client):
    await client.put("/settings", json={"llm_api_key": "sk-secret-key"})
    resp = await client.get("/settings")
    data = resp.json()
    assert data["llm_api_key"] == "configured"


@pytest.mark.asyncio
async def test_api_key_null_when_unset(client):
    resp = await client.get("/settings")
    data = resp.json()
    assert data["llm_api_key"] is None


@pytest.mark.asyncio
async def test_put_settings_invalid_type_422(client):
    """Sending wrong type (e.g., rename_on_save_default as string) returns 422."""
    resp = await client.put(
        "/settings",
        json={"rename_on_save_default": "not_a_bool"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_settings_unknown_field_ignored(client):
    """Unknown fields are silently ignored, partial update still works."""
    resp = await client.put(
        "/settings",
        json={"creator_id": "VALID", "bogus_field": 999},
    )
    assert resp.status_code == 200
    assert resp.json()["creator_id"] == "VALID"
