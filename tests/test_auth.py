"""Pruebas de la autenticacion por token Bearer."""
from __future__ import annotations

from tests.conftest import TOKEN


def test_token_ausente_responde_401(client):
    response = client.get("/attendance")
    assert response.status_code == 401
    assert "detail" in response.json()


def test_token_incorrecto_responde_401(client):
    response = client.get("/attendance", headers={"Authorization": "Bearer token-errado"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Token de acceso invalido"


def test_esquema_distinto_responde_401(client):
    response = client.get("/attendance", headers={"Authorization": f"Basic {TOKEN}"})
    assert response.status_code == 401


def test_token_por_query_string_no_se_acepta(client):
    response = client.get(f"/attendance?token={TOKEN}")
    assert response.status_code == 401


def test_token_por_query_string_con_nombre_api_token_no_se_acepta(client):
    response = client.get(f"/attendance?api_token={TOKEN}")
    assert response.status_code == 401


def test_token_valido_permite_consultar(client, auth_headers):
    response = client.get("/attendance", headers=auth_headers)
    assert response.status_code == 200


def test_token_valido_es_case_insensitive_en_el_esquema(client):
    response = client.get("/attendance", headers={"Authorization": f"bearer {TOKEN}"})
    assert response.status_code == 200


def test_todas_las_rutas_menos_health_exigen_token(client):
    for path in ("/device", "/users", "/attendance"):
        assert client.get(path).status_code == 401


def test_el_token_no_aparece_en_las_respuestas_de_error(client):
    body = client.get("/attendance", headers={"Authorization": "Bearer token-errado-secreto"}).text
    assert "token-errado-secreto" not in body
