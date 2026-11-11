"""Filtro, orden y paginacion de las marcaciones descargadas del dispositivo.

El equipo no soporta consultas por rango ni por usuario en el protocolo, asi que
el historico se descarga completo y se filtra en memoria. El resultado es
determinista: el mismo historico con los mismos filtros produce la misma pagina.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as DateType
from typing import Any, Sequence

logger = logging.getLogger("app.attendance")


@dataclass(frozen=True)
class AttendanceQuery:
    """Filtros validados de la consulta de asistencia."""

    date: DateType | None = None
    from_date: DateType | None = None
    to_date: DateType | None = None
    ci: str | None = None
    limit: int = 500
    offset: int = 0

    @property
    def start(self) -> DateType | None:
        return self.date or self.from_date

    @property
    def end(self) -> DateType | None:
        return self.date or self.to_date


@dataclass(frozen=True)
class AttendancePage:
    """Pagina de resultados con los totales del conjunto filtrado."""

    total: int
    offset: int
    limit: int
    records: list[dict[str, Any]]

    @property
    def count(self) -> int:
        return len(self.records)


def sort_key(record: dict[str, Any]) -> tuple[str, str, int, str]:
    """Orden ascendente estable: timestamp, user_id, uid y record_id."""
    uid = record.get("uid")
    return (
        str(record.get("timestamp") or ""),
        str(record.get("user_id") or ""),
        int(uid) if isinstance(uid, int) else 0,
        str(record.get("record_id") or ""),
    )


def matches(record: dict[str, Any], query: AttendanceQuery) -> bool:
    """Aplica los filtros de fecha y CI a una marcacion normalizada.

    El CI se compara como texto contra `user_id`; nunca se convierte a entero.
    """
    record_date = str(record.get("date") or "")
    if query.date is not None:
        if record_date != query.date.isoformat():
            return False
    else:
        if query.from_date is not None and record_date < query.from_date.isoformat():
            return False
        if query.to_date is not None and record_date > query.to_date.isoformat():
            return False
    if query.ci is not None:
        if str(record.get("user_id") or "").strip() != query.ci:
            return False
    return True


class AttendanceService:
    """Aplica filtros y paginacion sobre el historico descargado."""

    def __init__(self, reader: Any) -> None:
        self.reader = reader

    def query(self, query: AttendanceQuery) -> AttendancePage:
        downloaded = self.reader.attendance()
        filtered = [record for record in downloaded if matches(record, query)]
        filtered.sort(key=sort_key)
        total = len(filtered)
        page = filtered[query.offset : query.offset + query.limit]
        logger.info(
            "attendance_query device_id=%s date=%s from=%s to=%s ci=%s downloaded=%s filtered=%s returned=%s offset=%s limit=%s",
            getattr(self.reader.settings, "biometric_device_id", None),
            query.date,
            query.from_date,
            query.to_date,
            query.ci,
            len(downloaded),
            total,
            len(page),
            query.offset,
            query.limit,
        )
        return AttendancePage(total=total, offset=query.offset, limit=query.limit, records=page)

    def users(self) -> Sequence[dict[str, Any]]:
        return self.reader.users()
