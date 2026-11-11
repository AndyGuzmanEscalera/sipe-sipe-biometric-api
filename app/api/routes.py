"""Rutas HTTP de solo lectura.

Solo se expone GET. No existe ninguna ruta POST/PUT/PATCH/DELETE en esta API.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.schemas import (
    AttendanceFilters,
    AttendanceQueryParams,
    AttendanceResponse,
    BiometricUser,
    DeviceResponse,
    HealthResponse,
    UsersResponse,
    first_error_message,
    to_query,
)
from app.security.auth import require_api_token
from app.services.attendance_service import AttendanceService
from app.services.biometric_reader import BiometricReader, get_reader

logger = logging.getLogger("app.api")

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Estado del servicio (no requiere token ni dispositivo)",
)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.service_version,
    )


@router.get(
    "/device",
    response_model=DeviceResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(require_api_token)],
    tags=["device"],
    summary="Informacion disponible del dispositivo biometrico",
)
def device(
    reader: Annotated[BiometricReader, Depends(get_reader)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeviceResponse:
    info: dict[str, Any] = reader.device_info()
    return DeviceResponse(
        device_id=settings.biometric_device_id,
        connected=True,
        **info,
    )


@router.get(
    "/users",
    response_model=UsersResponse,
    dependencies=[Depends(require_api_token)],
    tags=["device"],
    summary="Usuarios registrados en el dispositivo",
)
def users(
    reader: Annotated[BiometricReader, Depends(get_reader)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UsersResponse:
    items = reader.users()
    return UsersResponse(
        device_id=settings.biometric_device_id,
        total=len(items),
        users=[BiometricUser(**item) for item in items],
    )


@router.get(
    "/attendance",
    response_model=AttendanceResponse,
    dependencies=[Depends(require_api_token)],
    tags=["attendance"],
    summary="Marcaciones del dispositivo con filtros opcionales",
)
def attendance(
    reader: Annotated[BiometricReader, Depends(get_reader)],
    settings: Annotated[Settings, Depends(get_settings)],
    date_: Annotated[date | None, Query(alias="date")] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    ci: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AttendanceResponse:
    try:
        params = AttendanceQueryParams(date=date_, from_=from_, to=to, ci=ci)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=first_error_message(exc),
        ) from exc

    if limit is not None and limit > settings.attendance_max_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'limit' supera el maximo permitido ({settings.attendance_max_limit}).",
        )

    query = to_query(params, settings.effective_limit(limit), offset)
    page = AttendanceService(reader).query(query)
    return AttendanceResponse(
        device_id=settings.biometric_device_id,
        filters=AttendanceFilters(
            date=params.date,
            from_=params.from_,
            to=params.to,
            ci=params.ci,
        ),
        total=page.total,
        offset=page.offset,
        limit=page.limit,
        count=page.count,
        records=page.records,
    )
