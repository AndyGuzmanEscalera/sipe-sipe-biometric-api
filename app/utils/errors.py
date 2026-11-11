"""Errores de dominio y su mapeo a codigos HTTP.

El detalle publico nunca incluye excepciones crudas del driver: el texto
operativo queda en los logs y el cliente recibe un mensaje estable.
"""
from __future__ import annotations


class BiometricError(Exception):
    """Error controlado al hablar con el dispositivo biometrico."""

    status_code: int = 502
    public_message: str = "No fue posible conectar con el dispositivo biometrico"

    def __init__(self, operator_detail: str = "") -> None:
        detail = operator_detail or self.public_message
        super().__init__(detail)
        self.operator_detail = detail


class BiometricConnectionError(BiometricError):
    """El dispositivo no acepta conexiones o responde de forma inesperada."""

    status_code = 502
    public_message = "No fue posible conectar con el dispositivo biometrico"


class BiometricTimeoutError(BiometricError):
    """El dispositivo no respondio dentro del tiempo limite configurado."""

    status_code = 504
    public_message = "El dispositivo biometrico no respondio dentro del tiempo limite configurado"


class BiometricAuthError(BiometricError):
    """El dispositivo rechazo la clave de comunicacion configurada."""

    status_code = 502
    public_message = "El dispositivo biometrico rechazo la autenticacion configurada"


class BiometricProtocolError(BiometricError):
    """La respuesta del dispositivo no es interpretable por pyzk."""

    status_code = 502
    public_message = "El dispositivo biometrico respondio con un formato no compatible"


class BiometricDependencyError(BiometricError):
    """La dependencia de lectura (pyzk) no esta disponible en el servidor."""

    status_code = 503
    public_message = "El servicio de lectura biométrica no esta disponible en este servidor"
