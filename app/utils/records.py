"""Normalizacion de registros y usuarios a un formato estable.

El nucleo de `record_id` conserva la misma tupla de identidad que ya fue validada
en el proyecto de correspondencia (device_id, user_id, timestamp, status, punch).
El campo `uid` se excluye a proposito: pyzk lo documenta como "not really used
any more" y su valor no es estable entre la lectura de historico y otros flujos,
por lo que incluirlo romperia la determinismo del identificador.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

RECORD_ID_FIELDS = ("device_id", "user_id", "timestamp", "status", "punch")


def build_record_id(
    device_id: str,
    user_id: str,
    timestamp: str,
    status: Any,
    punch: Any,
) -> str:
    """SHA-256 determinista sobre la identidad estable de una marcacion."""
    identity = [device_id, user_id, timestamp, status, punch]
    payload = json.dumps(identity, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_attendance(item: Any, device_id: str) -> dict[str, Any]:
    """Convierte un Attendance de pyzk en el contrato JSON de la API."""
    timestamp = item.timestamp
    timestamp_iso = timestamp.isoformat(timespec="seconds")
    user_id = str(item.user_id)
    status = _optional_int(getattr(item, "status", None))
    punch = _optional_int(getattr(item, "punch", None))
    record = {
        "device_id": device_id,
        "uid": _optional_int(getattr(item, "uid", None)),
        "user_id": user_id,
        "timestamp": timestamp_iso,
        "date": timestamp.date().isoformat(),
        "time": timestamp.time().isoformat(timespec="seconds"),
        "status": status,
        "punch": punch,
    }
    record["record_id"] = build_record_id(
        record["device_id"],
        record["user_id"],
        record["timestamp"],
        record["status"],
        record["punch"],
    )
    return record


def normalize_user(item: Any) -> dict[str, Any]:
    """Convierte un User de pyzk al contrato JSON de la API.

    Nunca se serializa password, tarjetas ni plantillas biometricas.
    """
    uid = _optional_int(getattr(item, "uid", None))
    raw_user_id = getattr(item, "user_id", None)
    user_id = str(raw_user_id) if raw_user_id not in (None, "") else ""
    raw_name = getattr(item, "name", None)
    name = str(raw_name) if raw_name not in (None, "") else None
    return {"uid": uid, "user_id": user_id, "name": name}
