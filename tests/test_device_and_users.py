"""Pruebas de /users y /device."""
from __future__ import annotations


def test_users_normalizados(client, auth_headers):
    response = client.get("/users", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == "alcaldia-central"
    assert body["total"] == 3
    assert body["users"][0] == {"uid": 1, "user_id": "4458643", "name": "JUAN PEREZ"}


def test_user_id_se_devuelve_como_texto(client, auth_headers):
    body = client.get("/users", headers=auth_headers).json()
    for usuario in body["users"]:
        assert isinstance(usuario["user_id"], str)


def test_usuario_sin_nombre_devuelve_null(client, auth_headers):
    body = client.get("/users", headers=auth_headers).json()
    sin_nombre = [usuario for usuario in body["users"] if usuario["user_id"] == "4458644"]
    assert sin_nombre and sin_nombre[0]["name"] is None


def test_users_no_expone_credenciales(client, auth_headers):
    cuerpo = client.get("/users", headers=auth_headers).text
    assert "clave-de-equipo" not in cuerpo
    assert "password" not in cuerpo


def test_device_expone_la_informacion_disponible(client, auth_headers):
    response = client.get("/device", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == "alcaldia-central"
    assert body["connected"] is True
    assert body["serial_number"] == "SN-0001"
    assert body["firmware_version"] == "Ver 6.60 Apr 22 2019"
    assert body["platform"] == "ZMM720_TFT"
    assert body["device_name"] == "uFace802 Plus"


def test_device_omite_los_campos_no_disponibles(client, auth_headers, fake_reader):
    fake_reader.device_info = lambda: {"platform": "ZMM720_TFT", "transport": "TCP"}
    body = client.get("/device", headers=auth_headers).json()
    assert body["platform"] == "ZMM720_TFT"
    assert "serial_number" not in body
    assert "firmware_version" not in body
