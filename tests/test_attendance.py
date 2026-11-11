"""Pruebas de /attendance: filtros, paginacion y orden."""
from __future__ import annotations

import pytest

MARKERS = ("timestamp", "user_id", "date", "time", "status", "punch", "uid", "device_id", "record_id")


def test_fecha_exacta(client, auth_headers):
    response = client.get("/attendance", params={"date": "2026-11-11"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["count"] == 3
    assert body["offset"] == 0
    assert body["limit"] == 500
    assert body["filters"]["date"] == "2026-11-11"
    assert body["filters"]["from"] is None
    assert body["filters"]["to"] is None
    assert all(record["date"] == "2026-11-11" for record in body["records"])


def test_rango_de_fechas(client, auth_headers):
    response = client.get(
        "/attendance",
        params={"from": "2026-11-01", "to": "2026-11-11"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["count"] == 5
    assert body["filters"]["from"] == "2026-11-01"
    assert body["filters"]["to"] == "2026-11-11"
    assert body["filters"]["date"] is None
    assert {record["date"] for record in body["records"]} <= {
        "2026-11-01",
        "2026-11-05",
        "2026-11-11",
    }


def test_rango_invertido_responde_400(client, auth_headers):
    response = client.get(
        "/attendance",
        params={"from": "2026-11-11", "to": "2026-11-01"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "from" in response.json()["detail"]


def test_filtrar_por_ci(client, auth_headers):
    response = client.get("/attendance", params={"ci": "4458643"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["count"] == 3
    assert body["filters"]["ci"] == "4458643"
    assert all(record["user_id"] == "4458643" for record in body["records"])


def test_filtrar_por_ci_con_fecha(client, auth_headers):
    response = client.get(
        "/attendance",
        params={"ci": "4458643", "date": "2026-11-11"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["count"] == 2
    assert all(record["user_id"] == "4458643" for record in body["records"])
    assert all(record["date"] == "2026-11-11" for record in body["records"])


def test_filtrar_por_ci_con_rango(client, auth_headers):
    response = client.get(
        "/attendance",
        params={"ci": "4458643", "from": "2026-11-01", "to": "2026-11-11"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["count"] == 3
    assert all(record["user_id"] == "4458643" for record in body["records"])


def test_limit(client, auth_headers):
    response = client.get("/attendance", params={"limit": 2}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    assert body["count"] == 2
    assert body["limit"] == 2


def test_offset(client, auth_headers):
    response = client.get("/attendance", params={"offset": 4, "limit": 5}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    assert body["offset"] == 4
    assert body["count"] == 2


def test_offset_fuera_de_rango_devuelve_pagina_vacia(client, auth_headers):
    response = client.get("/attendance", params={"offset": 99}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    assert body["count"] == 0
    assert body["records"] == []


def test_limit_supera_el_maximo_configurado_responde_400(client, auth_headers):
    response = client.get("/attendance", params={"limit": 5001}, headers=auth_headers)
    assert response.status_code == 400
    assert "5000" in response.json()["detail"]


def test_limit_igual_al_maximo_configurado_es_valido(client, auth_headers):
    response = client.get("/attendance", params={"limit": 5000}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["limit"] == 5000


def test_offset_negativo_responde_422(client, auth_headers):
    response = client.get("/attendance", params={"offset": -1}, headers=auth_headers)
    assert response.status_code == 422


def test_limit_cero_responde_422(client, auth_headers):
    response = client.get("/attendance", params={"limit": 0}, headers=auth_headers)
    assert response.status_code == 422


def test_fecha_invalida_responde_422(client, auth_headers):
    response = client.get("/attendance", params={"date": "2026-13-45"}, headers=auth_headers)
    assert response.status_code == 422


def test_fecha_con_rango_responde_400(client, auth_headers):
    response = client.get(
        "/attendance",
        params={"date": "2026-11-11", "from": "2026-11-01", "to": "2026-11-11"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "date" in response.json()["detail"]


def test_from_sin_to_responde_400(client, auth_headers):
    response = client.get("/attendance", params={"from": "2026-11-01"}, headers=auth_headers)
    assert response.status_code == 400


def test_to_sin_from_responde_400(client, auth_headers):
    response = client.get("/attendance", params={"to": "2026-11-11"}, headers=auth_headers)
    assert response.status_code == 400


def test_ci_vacio_responde_422(client, auth_headers):
    response = client.get("/attendance", params={"ci": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_ci_se_trata_como_texto_y_no_como_numero(client, auth_headers):
    response = client.get("/attendance", params={"ci": "007"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["records"][0]["user_id"] == "007"


def test_orden_ascendente_y_determinista(client, auth_headers):
    response = client.get("/attendance", params={"date": "2026-11-11"}, headers=auth_headers)
    body = response.json()
    marcas = [record["timestamp"] for record in body["records"]]
    assert marcas == sorted(marcas)
    assert marcas == ["2026-11-11T07:55:20", "2026-11-11T08:05:00", "2026-11-11T09:10:05"]


def test_el_orden_no_depende_del_orden_de_descarga(client, auth_headers):
    primera = client.get("/attendance", headers=auth_headers).json()
    segunda = client.get("/attendance", headers=auth_headers).json()
    assert [r["record_id"] for r in primera["records"]] == [r["record_id"] for r in segunda["records"]]


def test_los_registros_tienen_el_contrato_minimo(client, auth_headers):
    body = client.get("/attendance", headers=auth_headers).json()
    for record in body["records"]:
        assert set(MARKERS).issubset(record.keys())
        assert record["device_id"] == "alcaldia-central"
        assert isinstance(record["user_id"], str)
        assert isinstance(record["record_id"], str)
        assert len(record["record_id"]) == 64


def test_la_api_es_solo_lectura(client, auth_headers):
    for metodo in ("post", "put", "patch", "delete"):
        respuesta = getattr(client, metodo)("/attendance", headers=auth_headers)
        assert respuesta.status_code == 405


@pytest.mark.parametrize("ruta", ["/attendance", "/users", "/device"])
def test_no_existen_metodos_de_escritura_en_ninguna_ruta(client, auth_headers, ruta):
    for metodo in ("post", "put", "patch", "delete"):
        assert getattr(client, metodo)(ruta, headers=auth_headers).status_code == 405
