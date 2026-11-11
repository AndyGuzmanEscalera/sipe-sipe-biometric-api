"""Doble de prueba para la capa de dispositivo.

No se abre ninguna conexion real: el protocolo pyzk esta simulado y las
marcaciones usan las clases reales de pyzk (`zk.attendance.Attendance` y
`zk.user.User`) para que las pruebas validen el contrato exacto del driver.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from zk.attendance import Attendance
from zk.user import User

from app.utils.records import normalize_attendance, normalize_user

ATTENDANCE_ROWS = [
    ("4458643", datetime(2026, 11, 11, 9, 10, 5), 1, 1, 1),
    ("4458643", datetime(2026, 11, 1, 8, 0, 0), 0, 1, 1),
    ("4458644", datetime(2026, 11, 11, 8, 5, 0), 0, 1, 2),
    ("4458643", datetime(2026, 11, 11, 7, 55, 20), 0, 1, 1),
    ("007", datetime(2026, 11, 5, 12, 0, 0), 0, 1, 3),
    ("4458644", datetime(2026, 10, 31, 8, 5, 0), 0, 1, 2),
]

USER_ROWS = [
    (1, "JUAN PEREZ", "4458643"),
    (2, "", "4458644"),
    (3, "ANA LOPEZ", "007"),
]

DEVICE_INFO = {
    "device_name": "uFace802 Plus",
    "serial_number": "SN-0001",
    "firmware_version": "Ver 6.60 Apr 22 2019",
    "platform": "ZMM720_TFT",
    "transport": "TCP",
}


def build_attendance() -> list[Attendance]:
    return [Attendance(user_id, moment, status, punch, uid) for user_id, moment, status, punch, uid in ATTENDANCE_ROWS]


def build_users() -> list[User]:
    return [User(uid, name, 14, "clave-de-equipo", "1", user_id, 0) for uid, name, user_id in USER_ROWS]


class FakeReader:
    """Sustituye a BiometricReader sin tocar la red."""

    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self.last_transport = "TCP"
        self.attendance_calls = 0
        self.users_calls = 0
        self.device_info_calls = 0

    def attendance(self) -> list[dict[str, Any]]:
        self.attendance_calls += 1
        device_id = self.settings.biometric_device_id
        return [normalize_attendance(item, device_id) for item in build_attendance()]

    def users(self) -> list[dict[str, Any]]:
        self.users_calls += 1
        return [normalize_user(item) for item in build_users()]

    def device_info(self) -> dict[str, Any]:
        self.device_info_calls += 1
        return dict(DEVICE_INFO)
