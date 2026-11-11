"""Contratos JSON de la API.

`status` y `punch` se devuelven con su valor original del dispositivo: no se
traducen a entrada/salida/retorno/descanso sin confirmacion institucional.
"""
from __future__ import annotations

from datetime import date as DateType

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.attendance_service import AttendanceQuery


class HealthResponse(BaseModel):
    """Estado del servicio; no requiere token ni dispositivo."""

    status: str = "ok"
    service: str
    version: str


class DeviceResponse(BaseModel):
    """Informacion disponible del dispositivo en modo lectura."""

    model_config = ConfigDict(populate_by_name=True)

    device_id: str
    connected: bool = True
    device_name: str | None = None
    serial_number: str | None = None
    firmware_version: str | None = None
    platform: str | None = None
    transport: str | None = None


class BiometricUser(BaseModel):
    """Usuario registrado en el dispositivo."""

    uid: int | None = None
    user_id: str
    name: str | None = None


class UsersResponse(BaseModel):
    """Lista de usuarios del dispositivo."""

    device_id: str
    total: int
    users: list[BiometricUser]


class AttendanceRecord(BaseModel):
    """Marcacion normalizada."""

    device_id: str
    uid: int | None = None
    user_id: str
    timestamp: str
    date: str
    time: str
    status: int | None = None
    punch: int | None = None
    record_id: str


class AttendanceFilters(BaseModel):
    """Filtros aplicados, tal como fueron interpretados."""

    model_config = ConfigDict(populate_by_name=True)

    date: DateType | None = None
    from_: DateType | None = Field(default=None, validation_alias="from", serialization_alias="from")
    to: DateType | None = None
    ci: str | None = None


class AttendanceResponse(BaseModel):
    """Pagina de marcaciones con los totales del conjunto filtrado."""

    device_id: str
    filters: AttendanceFilters
    total: int
    offset: int
    limit: int
    count: int
    records: list[AttendanceRecord]


class AttendanceQueryParams(BaseModel):
    """Filtros de entrada con validacion de combinaciones.

    Reglas:
      * `date` no puede usarse junto con `from`/`to`;
      * `from` y `to` se usan siempre juntos;
      * `from` no puede ser posterior a `to`;
      * `ci` se trata siempre como texto.
    """

    model_config = ConfigDict(populate_by_name=True)

    date: DateType | None = None
    from_: DateType | None = Field(default=None, validation_alias="from")
    to: DateType | None = None
    ci: str | None = None

    @model_validator(mode="after")
    def _validate_filters(self) -> "AttendanceQueryParams":
        if self.date is not None and (self.from_ is not None or self.to is not None):
            raise ValueError("'date' no puede usarse junto con 'from' o 'to'.")
        if (self.from_ is None) != (self.to is None):
            raise ValueError("'from' y 'to' deben usarse juntos.")
        if self.from_ is not None and self.to is not None and self.from_ > self.to:
            raise ValueError("'from' no puede ser posterior a 'to'.")
        if self.ci is not None:
            cleaned = self.ci.strip()
            if not cleaned:
                raise ValueError("'ci' no puede estar vacio.")
            self.ci = cleaned
        return self


def first_error_message(exc: Exception) -> str:
    """Extrae el primer mensaje de error de una validacion de Pydantic."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        for error in errors():
            message = error.get("msg", "")
            return message.replace("Value error, ", "").strip()
    return str(exc)


def to_query(params: AttendanceQueryParams, limit: int, offset: int) -> AttendanceQuery:
    """Construye el query interno del servicio de asistencia."""
    return AttendanceQuery(
        date=params.date,
        from_date=params.from_,
        to_date=params.to,
        ci=params.ci,
        limit=limit,
        offset=offset,
    )
