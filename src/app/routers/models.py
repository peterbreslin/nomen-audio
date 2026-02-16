"""Model status endpoints."""

from pydantic import BaseModel

from fastapi import APIRouter

from app.ml import model_manager

router = APIRouter(prefix="/models", tags=["models"])


class ModelStatusResponse(BaseModel):
    """Response body for GET /models/status."""

    clap_loaded: bool
    clapcap_loaded: bool
    embeddings_ready: bool
    embeddings_count: int
    loading: bool
    error: str | None
    status_message: str


@router.get("/status", response_model=ModelStatusResponse)
def get_models_status() -> ModelStatusResponse:
    status = model_manager.get_status()
    return ModelStatusResponse(**status)
