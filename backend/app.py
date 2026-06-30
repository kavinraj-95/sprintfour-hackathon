"""FastAPI application entrypoint.

Thin by design: it wires CORS, a single typed error handler, and the routers.
All business logic lives in services/ — never here. Detection layers will be
added as their own service modules and surfaced through routes; the wiring
stays visible in this one file.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from errors import AppError
from models.api import ErrorResponse
from routes import export, review, session

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


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """Render a domain error as the uniform ErrorResponse envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=exc.error, detail=exc.detail).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Turn FastAPI's request-validation errors into the same envelope."""
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error="validation_error",
            detail=str(exc.errors()),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Last line of defence: even an unexpected error is a typed envelope,
    never a bare 500 with a stack trace on the wire."""
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_error",
            detail="An unexpected error occurred.",
        ).model_dump(),
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe; also reports which detector seam is active."""
    return {"status": "ok", "detector": config.DETECTOR}


app.include_router(session.router)
app.include_router(export.router)
app.include_router(review.router)
