"""Pruebas de normalizacion, record_id determinista y orden."""
from __future__ import annotations

from datetime import datetime

from zk.attendance import Attendance
from zk.user import User

from app.utils.records import build_record_id, normalize_attendance, normalize_user


def test_normalizacion_de_marcacion():
    item = Attendance("4458643", datetime(2026, 11, 11, 7, 55, 20), 0, 1, 1234)
    record = normalize_attendance(item, "alcaldia-central")
    assert record == {
        "device_id": "alcaldia-central",
        "uid": 1234,
        "user_id": "4458643",
        "timestamp": "2026-11-11T07:55:20",
        "date": "2026-11-11",
        "time": "07:55:20",
        "status": 0,
        "punch": 1,
        "record_id": record["record_id"],
    }
    assert len(record["record_id"]) == 64


def test_el_user_id_siempre_es_texto():
    item = Attendance(4458643, datetime(2026, 11, 11, 7, 55, 20), 0, 1, 1)
    record = normalize_attendance(item, "alcaldia-central")
    assert record["user_id"] == "4458643"
    assert isinstance(record["user_id"], str)


def test_status_y_punch_se_conservan_sin_interpretar():
    item = Attendance("4458643", datetime(2026, 11, 11, 7, 55, 20), 4, 2, 1)
    record = normalize_attendance(item, "alcaldia-central")
    assert record["status"] == 4
    assert record["punch"] == 2
    assert "entrada" not in record
    assert "salida" not in record


def test_record_id_es_determinista():
    item = Attendance("4458643", datetime(2026, 11, 11, 7, 55, 20), 0, 1, 1234)
    primero = normalize_attendance(item, "alcaldia-central")
    segundo = normalize_attendance(item, "alcaldia-central")
    assert primero["record_id"] == segundo["record_id"]


def test_record_id_cambia_con_el_dispositivo():
    item = Attendance("4458643", datetime(2026, 11, 11, 7, 55, 20), 0, 1, 1234)
    uno = normalize_attendance(item, "alcaldia-central")
    otro = normalize_attendance(item, "alcaldia-central-2")
    assert uno["record_id"] != otro["record_id"]


def test_record_id_no_depende_del_uid_del_registro():
    """El uid no es estable en pyzk y no debe alterar la identidad de la marcacion."""
    base = Attendance("4458643", datetime(2026, 11, 11, 7, 55, 20), 0, 1, 1234)
    otro_uid = Attendance("4458643", datetime(2026, 11, 11, 7, 55, 20), 0, 1, 4321)
    assert (
        normalize_attendance(base, "alcaldia-central")["record_id"]
        == normalize_attendance(otro_uid, "alcaldia-central")["record_id"]
    )


def test_record_id_es_un_sha256_hexadecimal():
    valor = build_record_id("alcaldia-central", "4458643", "2026-11-11T07:55:20", 0, 1)
    assert len(valor) == 64
    assert all(caracter in "0123456789abcdef" for caracter in valor)


def test_normalizacion_de_usuario():
    item = User(1, "JUAN PEREZ", 14, "clave-secreta", "1", "4458643", 12345)
    usuario = normalize_user(item)
    assert usuario == {"uid": 1, "user_id": "4458643", "name": "JUAN PEREZ"}


def test_usuario_sin_nombre_usa_null():
    item = User(2, "", 14, "clave-secreta", "1", "4458644", 0)
    usuario = normalize_user(item)
    assert usuario["name"] is None
    assert usuario["user_id"] == "4458644"


def test_el_usuario_no_expone_password_ni_tarjeta():
    item = User(1, "JUAN PEREZ", 14, "clave-secreta", "1", "4458643", 12345)
    usuario = normalize_user(item)
    assert "password" not in usuario
    assert "card" not in usuario
    assert "privilege" not in usuario
    assert "clave-secreta" not in str(usuario)
