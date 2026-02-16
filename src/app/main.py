"""NomenAudio FastAPI sidecar — entry point."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import paths
from app.db import repository
from app.errors import AppError
from app.ml import model_manager
from app.routers import analysis as analysis_router
from app.routers import files
from app.routers import models as models_router
from app.routers import settings as settings_router
from app.routers import ucs as ucs_router
from app.services.settings import load_settings
from app.ucs.engine import load_ucs

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_ucs(paths.get_ucs_full_list(), paths.get_ucs_top_level())
    load_settings()
    await repository.connect(paths.get_db_path())
    model_manager.start_loading()
    yield
    await repository.close()


app = FastAPI(title="NomenAudio", version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files.router)
app.include_router(analysis_router.router)
app.include_router(models_router.router)
app.include_router(ucs_router.router)
app.include_router(settings_router.router)


@app.exception_handler(AppError)
async def app_error_handler(request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "code": exc.code},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}


if __name__ == "__main__":
    # Prefer running via `python -m app` (__main__.py prints PORT before
    # heavy imports).  This fallback is kept for convenience / tests.
    import socket as _sock

    with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as _s:
        _s.bind(("127.0.0.1", 0))
        _port = _s.getsockname()[1]
    print(f"PORT={_port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=_port, log_level="warning")
