"""FastAPI application entrypoint.

Thin by design: it wires CORS, a single typed error handler, and the routers.
All business logic lives in services/ and detectors/ — never here.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from models.api import ErrorResponse

app = FastAPI(
    title="Conseal — Redaction Correction",
    description="Sam's review surface: surface the misses the tool left visible.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AppError(Exception):
    """Domain error carrying an HTTP status and a human-readable message.

    Services raise this instead of returning bare 500s; the handler below turns
    it into a typed ErrorResponse the frontend can render.
    """

    def __init__(self, status_code: int, error: str, detail: str | None = None):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(f"{error}: {detail}" if detail else error)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=exc.error, detail=exc.detail).model_dump(),
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe; also reports which detector seam is active."""
    return {"status": "ok", "detector": config.DETECTOR}


# Routers are included as they are built (session, export). Kept here so the
# wiring is visible in one place.
# from routes import session, export
# app.include_router(session.router)
# app.include_router(export.router)
