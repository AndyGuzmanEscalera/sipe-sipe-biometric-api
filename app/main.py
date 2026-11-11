"""Punto de entrada de la API de lectura biométrica.

- No se conecta al dispositivo al importar el modulo.
- Todas las rutas salvo `GET /health` exigen `Authorization: Bearer <token>`.
- Los errores del dispositivo se traducen a codigos HTTP estables.
"""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.config import get_settings
from app.utils.errors import BiometricError

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Registra endpoint, estado y duracion de cada peticion."""

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "http_request method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response


app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
    description=(
        "Gateway de solo lectura para dispositivos biometricos ZKTeco. "
        "Hardware -> lectura -> normalizacion -> filtros -> JSON."
    ),
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

app.add_middleware(RequestLoggingMiddleware)
app.include_router(router)


@app.exception_handler(BiometricError)
async def biometric_error_handler(request: Request, exc: BiometricError) -> JSONResponse:
    """Mapea errores del dispositivo a codigos HTTP sin exponer detalle interno."""
    logger.warning(
        "biometric_error path=%s status=%s detail=%s",
        request.url.path,
        exc.status_code,
        exc.operator_detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.public_message})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Evita que un fallo interno devuelva trazas al cliente."""
    logger.exception("unhandled_error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno inesperado"},
    )
