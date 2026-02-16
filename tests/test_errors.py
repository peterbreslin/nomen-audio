"""Tests for AppError and global error handler."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.errors import AppError


def test_app_error_attributes():
    err = AppError("FILE_NOT_FOUND", 404, "File does not exist")
    assert err.code == "FILE_NOT_FOUND"
    assert err.status_code == 404
    assert err.detail == "File does not exist"
    assert str(err) == "File does not exist"


def test_app_error_handler_returns_json():
    """Verify that AppError raised in a handler returns structured JSON."""
    test_app = FastAPI()

    @test_app.exception_handler(AppError)
    async def handler(request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "code": exc.code},
        )

    @test_app.get("/test")
    def raise_error():
        raise AppError("FILE_NOT_FOUND", 404, "Not found")

    client = TestClient(test_app)
    resp = client.get("/test")
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "FILE_NOT_FOUND"
    assert data["error"] == "Not found"
