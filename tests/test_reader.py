"""Pruebas de la capa pyzk simulada.

No se abre ninguna conexion: la clase `ReadOnlyZK` (heredada de pyzk) se
reemplaza por un doble para verificar el control de errores, el cierre
garantizado de la sesion y el bloqueo de comandos de escritura.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from app.config import Settings
from app.services.biometric_reader import (
    READ_ONLY_COMMANDS,
    BiometricReader,
    ReadOnlyZK,
)
from app.utils.errors import (
    BiometricAuthError,
    BiometricConnectionError,
    BiometricError,
    BiometricTimeoutError,
)


def make_reader(**kwargs) -> BiometricReader:
    parametros = {
        "biometric_host": "127.0.0.1",
        "biometric_port": 4370,
        "biometric_timeout": 1,
        "biometric_transport": "tcp",
        "biometric_device_id": "alcaldia-central",
    }
    parametros.update(kwargs)
    settings = Settings(**parametros)
    return BiometricReader(settings)


def patch_client(client):
    return patch("app.services.biometric_reader.ReadOnlyZK", return_value=client)


def patch_probe():
    return patch(
        "app.services.biometric_reader.tcp_probe",
        return_value=(True, "Puerto TCP accesible", None),
    )


def test_no_se_conecta_al_importar_los_modulos():
    with patch("app.services.biometric_reader.ReadOnlyZK") as factory:
        reader = make_reader()
        assert isinstance(reader, BiometricReader)
        assert factory.call_count == 0


def test_conexion_fallida_reporta_error_de_conexion():
    client = Mock()
    client.connect.side_effect = OSError("Connection refused")
    with patch_client(client), patch_probe():
        with pytest.raises(BiometricConnectionError):
            with make_reader().session():
                pass
    client.close_socket.assert_called_once()


def test_timeout_reporta_error_de_tiempo_limite():
    client = Mock()
    client.connect.side_effect = TimeoutError("timed out")
    with patch_client(client), patch_probe():
        with pytest.raises(BiometricTimeoutError):
            with make_reader().session():
                pass


def test_autenticacion_rechazada_no_reintenta_otro_transporte():
    client = Mock()
    client.connect.side_effect = RuntimeError("Unauthenticated")
    with patch_client(client) as factory, patch_probe():
        with pytest.raises(BiometricAuthError):
            with make_reader(biometric_transport="auto").session():
                pass
    assert factory.call_count == 1


def test_desconexion_se_garantiza_aunque_la_lectura_falle():
    client = Mock()
    client.connect.return_value = client
    client.get_attendance.side_effect = RuntimeError("fallo de lectura")
    with patch_client(client), patch_probe():
        with pytest.raises(BiometricError):
            with make_reader().session() as connection:
                connection.get_attendance()
    client.disconnect.assert_called_once()
    client.close_socket.assert_called_once()


def test_desconexion_se_garantiza_en_el_camino_feliz():
    client = Mock()
    client.connect.return_value = client
    with patch_client(client), patch_probe():
        with make_reader().session() as connection:
            assert connection is client
    client.disconnect.assert_called_once()
    client.close_socket.assert_called_once()


def test_el_error_de_lectura_no_expone_detalle_interno():
    client = Mock()
    client.connect.return_value = client
    client.get_attendance.side_effect = RuntimeError("secreto interno del driver")
    with patch_client(client), patch_probe():
        with pytest.raises(BiometricError) as error:
            with make_reader().session() as connection:
                connection.get_attendance()
    assert "secreto interno del driver" not in error.value.public_message


def test_la_politica_bloquea_comandos_de_escritura():
    cliente = ReadOnlyZK("127.0.0.1", ommit_ping=True)
    try:
        for metodo in (
            cliente.disable_device,
            cliente.enable_device,
            cliente.restart,
            cliente.clear_attendance,
            cliente.clear_data,
            cliente.set_user,
            lambda: cliente.set_time(datetime(2026, 1, 1)),
        ):
            with pytest.raises(BiometricError):
                metodo()
    finally:
        cliente.close_socket()


def test_los_comandos_peligrosos_no_estan_en_la_lista_blanca():
    from zk import const

    for comando in (
        const.CMD_USER_WRQ,
        const.CMD_USERTEMP_WRQ,
        const.CMD_DELETE_USER,
        const.CMD_DELETE_USERTEMP,
        const.CMD_CLEAR_ATTLOG,
        const.CMD_CLEAR_DATA,
        const.CMD_DISABLEDEVICE,
        const.CMD_ENABLEDEVICE,
        const.CMD_RESTART,
        const.CMD_SET_TIME,
        const.CMD_OPTIONS_WRQ,
        const.CMD_UNLOCK,
    ):
        assert comando not in READ_ONLY_COMMANDS


def test_el_transporte_registrado_se_expone():
    client = Mock()
    client.connect.return_value = client
    with patch_client(client), patch_probe():
        reader = make_reader()
        with reader.session():
            pass
        assert reader.last_transport == "TCP"
