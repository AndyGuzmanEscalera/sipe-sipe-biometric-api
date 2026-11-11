"""Adaptador de solo lectura para equipos ZKTeco compatibles (pyzk==0.9).

El nucleo de conexion (`_BoundedZK`, `Reader.session`, sondas TCP/ICMP) fue
reutilizado del lector ya validado del proyecto de correspondencia
(`backend/app/modules/rrhh/reader/connection.py`) y se conserva sin reescribir
el protocolo. Solo se adapto la capa de configuracion, los nombres y el
mapeo de errores.

Garantias de esta capa:
  * toda conexion se cierra con `disconnect()` en un `finally`;
  * nunca se envia un comando de escritura al dispositivo;
  * no se conecta al importar el modulo.
"""
from __future__ import annotations

import logging
import platform
import socket
import subprocess
import warnings
from contextlib import contextmanager
from functools import lru_cache
from struct import unpack
from typing import Any, Iterator

from zk import ZK, const

from app.config import Settings, get_settings
from app.utils.errors import (
    BiometricAuthError,
    BiometricConnectionError,
    BiometricError,
    BiometricProtocolError,
    BiometricTimeoutError,
)
from app.utils.records import normalize_attendance, normalize_user

logger = logging.getLogger("app.biometric")

READ_ONLY_COMMANDS = frozenset(
    {
        const.CMD_CONNECT,
        const.CMD_AUTH,
        const.CMD_EXIT,
        const.CMD_GET_TIME,
        const.CMD_GET_VERSION,
        const.CMD_OPTIONS_RRQ,
        const.CMD_GET_FREE_SIZES,
        const.CMD_FREE_DATA,
        1503,
        1504,
    }
)


def explain_error(exc: BaseException) -> str:
    """Traduce una excepcion del driver a un mensaje operativo en espanol."""
    text = str(exc).lower()
    if "unauth" in text or "auth" in text:
        return "Autenticacion rechazada: comprueba la clave de comunicacion configurada."
    if "timed out" in text or "timeout" in text:
        return "Sin respuesta dentro del tiempo limite: red, firewall, transporte o protocolo incompatible."
    if "refused" in text or "10061" in text:
        return "Conexion rechazada: puerto TCP cerrado o servicio no disponible."
    if "invalid" in text or "unpack" in text or "supported" in text:
        return "Respuesta no interpretable por pyzk: posible protocolo o formato incompatible."
    return "No se pudo completar la consulta: revisa red, clave, firmware y compatibilidad del protocolo."


def classify_error(exc: BaseException) -> type[BiometricError]:
    """Selecciona la excepcion de dominio segun la causa del fallo.

    Reconoce tanto el texto original del driver como los mensajes operativos
    ya traducidos, de modo que la clasificacion no depende del idioma de origen.
    """
    text = str(exc).lower()
    if "unauth" in text or "auth" in text or "autenticacion rechazada" in text:
        return BiometricAuthError
    if "timed out" in text or "timeout" in text or "tiempo limite" in text:
        return BiometricTimeoutError
    if "invalid" in text or "unpack" in text or "not supported" in text:
        return BiometricProtocolError
    return BiometricConnectionError


def tcp_probe(host: str, port: int, timeout: float) -> tuple[bool, str, OSError | None]:
    """Comprueba que el puerto TCP responde sin abrir una sesion del protocolo."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "Puerto TCP accesible; esto todavia no confirma compatibilidad ZKTeco.", None
    except OSError as exc:
        return False, explain_error(exc), exc


def ping_probe(host: str, timeout: float) -> str:
    """Prueba ICMP opcional; su resultado no confirma compatibilidad del protocolo."""
    windows = platform.system() == "Windows"
    args = (
        ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
        if windows
        else ["ping", "-c", "1", "-W", str(max(1, int(timeout))), host]
    )
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout + 2, check=False)
        return "Responde a ICMP." if result.returncode == 0 else "Sin respuesta ICMP (puede estar bloqueado)."
    except (OSError, subprocess.TimeoutExpired):
        return "Prueba ICMP no disponible o agoto su tiempo."


class ReadOnlyZK(ZK):
    """ZK de pyzk==0.9 limitado a comandos de lectura.

    El bloqueo es real: cualquier comando fuera de la lista blanca se rechaza
    antes de salir a la red, incluyendo altas/bajas de usuarios, limpieza de
    asistencia, reinicio del equipo y descarga de plantillas biometricas.
    """

    def _ZK__recieve_raw_data(self, size: int) -> bytes:
        chunks: list[bytes] = []
        while size > 0:
            chunk = self._ZK__sock.recv(size)
            if not chunk:
                raise BiometricConnectionError(
                    "El equipo cerro la conexion durante la descarga; respuesta incompleta."
                )
            chunks.append(chunk)
            size -= len(chunk)
        return b"".join(chunks)

    def _ZK__send_command(self, command: int, command_string: bytes = b"", response_size: int = 8):
        if command not in READ_ONLY_COMMANDS:
            raise BiometricConnectionError("Comando bloqueado por la politica de solo lectura.")
        if command == 1503:
            _, requested, function, _ = unpack("<bhii", command_string)
            if not (
                requested == const.CMD_ATTLOG_RRQ
                or (requested == const.CMD_USERTEMP_RRQ and function == const.FCT_USER)
            ):
                raise BiometricConnectionError(
                    "Solo se permiten usuarios y asistencias; plantillas bloqueadas."
                )
        return super()._ZK__send_command(command, command_string, response_size)

    def _ZK__create_socket(self) -> None:
        # pyzk reemplaza el socket inicial sin cerrarlo.
        self._ZK__sock.close()
        super()._ZK__create_socket()

    def close_socket(self) -> None:
        self._ZK__sock.close()


class BiometricReader:
    """Fachada de lectura del dispositivo biometrico."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.last_transport: str | None = None

    @contextmanager
    def session(self, transport: str | None = None) -> Iterator[Any]:
        """Abre una sesion de lectura y la cierra siempre, incluso ante errores."""
        settings = self.settings
        mode = (transport or settings.biometric_transport).lower()
        modes = ("tcp", "udp") if mode == "auto" else (mode,)
        errors: list[str] = []
        failure: BaseException | None = None
        client: ReadOnlyZK | None = None
        connection: Any = None

        for candidate in modes:
            if candidate == "tcp":
                reachable, message, probe_error = tcp_probe(
                    settings.biometric_host, settings.biometric_port, settings.biometric_timeout
                )
                if not reachable:
                    errors.append("TCP: " + message)
                    if failure is None:
                        failure = probe_error
                    continue
            client = ReadOnlyZK(
                settings.biometric_host,
                port=settings.biometric_port,
                timeout=settings.biometric_timeout,
                password=settings.device_password,
                force_udp=candidate == "udp",
                ommit_ping=True,
                encoding=settings.biometric_encoding,
            )
            # El sondeo TCP ya se hizo con el timeout configurado; se evita el
            # timeout fijo de 10s que aplica pyzk en su propio helper.
            client.helper.test_tcp = lambda: 0
            try:
                connection = client.connect()
                self.last_transport = candidate.upper()
                logger.info(
                    "device_connected device_id=%s transport=%s host=%s port=%s",
                    settings.biometric_device_id,
                    candidate.upper(),
                    settings.biometric_host,
                    settings.biometric_port,
                )
                break
            except BaseException as exc:
                client.close_socket()
                if not isinstance(exc, Exception):
                    raise
                errors.append(candidate.upper() + ": " + explain_error(exc))
                if failure is None:
                    failure = exc
                if "auth" in str(exc).lower():
                    break  # No repetir autenticacion en otro transporte.

        if connection is None:
            detail = " / ".join(errors) or "No fue posible abrir una sesion con el dispositivo."
            error_type = classify_error(failure) if failure is not None else BiometricConnectionError
            logger.warning("device_connection_failed device_id=%s detail=%s", settings.biometric_device_id, detail)
            raise error_type(detail)

        try:
            yield connection
        except BiometricError:
            raise
        except Exception as exc:
            detail = explain_error(exc)
            logger.warning("device_read_failed device_id=%s detail=%s", settings.biometric_device_id, detail)
            raise classify_error(exc)(detail) from exc
        finally:
            try:
                connection.disconnect()
            except Exception:
                warnings.warn("No se confirmo el cierre de la sesion; se cerro el socket local.")
            finally:
                if client is not None:
                    client.close_socket()

    def device_info(self) -> dict[str, Any]:
        """Informacion del equipo disponible en modo lectura."""
        info: dict[str, Any] = {}
        with self.session() as connection:
            for key, method in (
                ("device_name", "get_device_name"),
                ("serial_number", "get_serialnumber"),
                ("firmware_version", "get_firmware_version"),
                ("platform", "get_platform"),
            ):
                try:
                    value = getattr(connection, method)()
                except Exception as exc:
                    logger.info(
                        "device_field_unavailable field=%s detail=%s", key, explain_error(exc)
                    )
                    continue
                if value is None:
                    continue
                text = str(value).strip()
                if not text:
                    continue
                info[key] = text
            info["transport"] = self.last_transport
        return info

    def users(self) -> list[dict[str, Any]]:
        """Usuarios registrados en el dispositivo."""
        with self.session() as connection:
            return [normalize_user(user) for user in connection.get_users()]

    def attendance(self) -> list[dict[str, Any]]:
        """Historico completo de marcaciones reportado por el dispositivo.

        El equipo no permite filtrar por rango ni por usuario en el protocolo,
        por lo que se descarga el historico y el filtrado ocurre en memoria.
        """
        device_id = self.settings.biometric_device_id
        with self.session() as connection:
            records = [normalize_attendance(item, device_id) for item in connection.get_attendance()]
        logger.info("device_records_read device_id=%s records=%s", device_id, len(records))
        return records


@lru_cache(maxsize=1)
def get_reader() -> BiometricReader:
    """Instancia compartida del lector; no abre conexiones hasta usarla."""
    return BiometricReader(get_settings())
