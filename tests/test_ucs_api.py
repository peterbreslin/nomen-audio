"""Tests for UCS API endpoints."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.ucs.engine import is_loaded, load_ucs

FULL_LIST = "data/UCS/UCS v8.2.1 Full List.xlsx"
TOP_LEVEL = "data/UCS/UCS v8.2.1 Top Level Categories.xlsx"


@pytest.fixture(scope="module", autouse=True)
def _load_ucs():
    if not is_loaded():
        load_ucs(FULL_LIST, TOP_LEVEL)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_categories(client):
    resp = await client.get("/ucs/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["categories"]) == 82
    first = data["categories"][0]
    assert "name" in first
    assert "subcategories" in first
    assert len(first["subcategories"]) > 0


@pytest.mark.asyncio
async def test_get_categories_has_explanations(client):
    resp = await client.get("/ucs/categories")
    data = resp.json()
    air = next(c for c in data["categories"] if c["name"] == "AIR")
    assert "explanation" in air
    assert len(air["explanation"]) > 0


@pytest.mark.asyncio
async def test_lookup_valid(client):
    resp = await client.get("/ucs/lookup/DOORWood")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cat_id"] == "DOORWood"
    assert data["category"] == "DOORS"
    assert data["subcategory"] == "WOOD"
    assert "synonyms" in data
    assert len(data["synonyms"]) > 0


@pytest.mark.asyncio
async def test_lookup_invalid(client):
    resp = await client.get("/ucs/lookup/INVALID")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_parse_ucs_filename(client):
    resp = await client.post(
        "/ucs/parse-filename",
        json={"filename": "DOORWood_Cabin Door Open Close_JDOE_MYGAME.wav"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_ucs_compliant"] is True
    assert data["cat_id"] == "DOORWood"
    assert data["category"] == "DOORS"


@pytest.mark.asyncio
async def test_parse_non_ucs_filename(client):
    resp = await client.post(
        "/ucs/parse-filename",
        json={"filename": "wooden_door_creak.wav"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_ucs_compliant"] is False
    assert data["fuzzy_matches"] is not None


@pytest.mark.asyncio
async def test_generate_filename(client):
    resp = await client.post(
        "/ucs/generate-filename",
        json={
            "cat_id": "DOORWood",
            "fx_name": "Cabin Door Open Close",
            "creator_id": "JDOE",
            "source_id": "MYGAME",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["filename"] == "DOORWood_Cabin Door Open Close_JDOE_MYGAME.wav"
