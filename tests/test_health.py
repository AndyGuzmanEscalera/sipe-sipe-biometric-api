"""Pruebas de /health: no requiere token ni dispositivo."""
from __future__ import annotations

from tests.conftest import TOKEN


def test_health_responde_ok_sin_token(client, fake_reader):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "sipe-sipe-biometric-api"
    assert "version" in body


def test_health_no_contacta_el_dispositivo(client, fake_reader):
    client.get("/health")
    assert fake_reader.attendance_calls == 0
    assert fake_reader.users_calls == 0
    assert fake_reader.device_info_calls == 0


def test_health_ignora_un_token_invalido(client):
    response = client.get("/health", headers={"Authorization": "Bearer invalido"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_token_no_se_expone_en_el_health(client):
    assert TOKEN not in client.get("/health").text
