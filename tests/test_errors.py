"""Pruebas del mapeo de errores del dispositivo a codigos HTTP."""
from __future__ import annotations

from app.utils.errors import (
    BiometricAuthError,
    BiometricConnectionError,
    BiometricTimeoutError,
)


def test_error_de_conexion_responde_502(client, auth_headers, fake_reader):
    def fallar():
        raise BiometricConnectionError("detalle interno del operador")

    fake_reader.attendance = fallar
    response = client.get("/attendance", headers=auth_headers)
    assert response.status_code == 502
    assert response.json() == {"detail": "No fue posible conectar con el dispositivo biometrico"}


def test_timeout_responde_504(client, auth_headers, fake_reader):
    def fallar():
        raise BiometricTimeoutError("el equipo no respondio")

    fake_reader.attendance = fallar
    response = client.get("/attendance", headers=auth_headers)
    assert response.status_code == 504
    assert "tiempo limite" in response.json()["detail"]


def test_error_de_autenticacion_responde_502(client, auth_headers, fake_reader):
    def fallar():
        raise BiometricAuthError("clave rechazada")

    fake_reader.attendance = fallar
    response = client.get("/attendance", headers=auth_headers)
    assert response.status_code == 502


def test_el_error_no_expone_detalles_internos(client, auth_headers, fake_reader):
    def fallar():
        raise BiometricConnectionError("host=192.168.30.90 clave=1234 puerto=4370")

    fake_reader.attendance = fallar
    cuerpo = client.get("/attendance", headers=auth_headers).text
    assert "192.168.30.90" not in cuerpo
    assert "1234" not in cuerpo
    assert "Traceback" not in cuerpo


def test_users_con_error_de_dispositivo_responde_502(client, auth_headers, fake_reader):
    def fallar():
        raise BiometricConnectionError("sin dispositivo")

    fake_reader.users = fallar
    assert client.get("/users", headers=auth_headers).status_code == 502


def test_device_con_error_de_dispositivo_responde_502(client, auth_headers, fake_reader):
    def fallar():
        raise BiometricConnectionError("sin dispositivo")

    fake_reader.device_info = fallar
    assert client.get("/device", headers=auth_headers).status_code == 502
