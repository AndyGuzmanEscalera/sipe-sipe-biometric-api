"""Autenticacion por token Bearer.

El token llega unicamente en la cabecera `Authorization`. No se acepta por query
string y la comparacion es de tiempo constante. El token nunca se escribe en los
logs ni en las respuestas de error.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

logger = logging.getLogger("app.security")

bearer_scheme = HTTPBearer(auto_error=False, description="Token de acceso de la API")


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    """Exige `Authorization: Bearer <token>` con el token configurado."""
    if not settings.api_token:
        logger.error("api_token_missing_configuracion=BIOMETRIC_API_TOKEN")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La API no tiene un token de acceso configurado",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el encabezado Authorization con el token Bearer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    provided = credentials.credentials or ""
    if not secrets.compare_digest(provided.encode("utf-8"), settings.api_token.encode("utf-8")):
        logger.warning("api_token_rechazado")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso invalido",
            headers={"WWW-Authenticate": "Bearer"},
        )
