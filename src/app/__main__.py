"""Entry point for ``python -m app`` — prints PORT before heavy imports."""

import socket


def _find_open_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


port = _find_open_port()
print(f"PORT={port}", flush=True)

import uvicorn  # noqa: E402

from app import paths  # noqa: E402
from app.main import app  # noqa: E402

paths.init()

uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
