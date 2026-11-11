"""Configuracion por variables de entorno.

Toda la configuracion del dispositivo, de la API y de la paginacion vive aqui.
Los secretos se guardan como SecretStr para que no aparezcan en logs ni en repr().
"""
from __future__ import annotations

import codecs
import ipaddress
from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TRANSPORTS = {"auto", "tcp", "udp"}


class Settings(BaseSettings):
    """Parametros de ejecucion leidos del entorno o del archivo .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "sipe-sipe-biometric-api"
    service_version: str = "1.0.0"
    app_env: str = "production"
    log_level: str = "INFO"
    enable_docs: bool = False

    biometric_host: str = "192.168.30.90"
    biometric_port: int = 4370
    biometric_password: SecretStr = SecretStr("0")
    biometric_timeout: float = 10.0
    biometric_device_id: str = "alcaldia-central"
    biometric_transport: str = "auto"
    biometric_encoding: str = "UTF-8"

    biometric_api_token: SecretStr = SecretStr("")

    attendance_default_limit: int = 500
    attendance_max_limit: int = 5000

    @field_validator("biometric_host")
    @classmethod
    def _validate_host(cls, value: str) -> str:
        host = value.strip()
        if not host:
            raise ValueError("BIOMETRIC_HOST no puede estar vacio.")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not host.replace(".", "").replace("-", "").isalnum():
                raise ValueError("BIOMETRIC_HOST debe ser una direccion IP o un nombre de host valido.")
        return host

    @field_validator("biometric_port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("BIOMETRIC_PORT debe estar entre 1 y 65535.")
        return value

    @field_validator("biometric_timeout")
    @classmethod
    def _validate_timeout(cls, value: float) -> float:
        if not 0 < value <= 300:
            raise ValueError("BIOMETRIC_TIMEOUT debe estar entre 0 y 300 segundos.")
        return value

    @field_validator("biometric_device_id")
    @classmethod
    def _validate_device_id(cls, value: str) -> str:
        device_id = value.strip()
        if not device_id:
            raise ValueError("BIOMETRIC_DEVICE_ID no puede estar vacio.")
        return device_id

    @field_validator("biometric_transport")
    @classmethod
    def _validate_transport(cls, value: str) -> str:
        transport = value.strip().lower()
        if transport not in TRANSPORTS:
            raise ValueError("BIOMETRIC_TRANSPORT debe ser auto, tcp o udp.")
        return transport

    @field_validator("biometric_encoding")
    @classmethod
    def _validate_encoding(cls, value: str) -> str:
        codecs.lookup(value)
        return value

    @field_validator("attendance_default_limit")
    @classmethod
    def _validate_default_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ATTENDANCE_DEFAULT_LIMIT debe ser al menos 1.")
        return value

    @field_validator("attendance_max_limit")
    @classmethod
    def _validate_max_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ATTENDANCE_MAX_LIMIT debe ser al menos 1.")
        return value

    @property
    def device_password(self) -> int:
        """Clave de comunicacion del dispositivo (numerica en equipos ZKTeco)."""
        raw = self.biometric_password.get_secret_value().strip()
        if not raw:
            return 0
        try:
            return int(raw)
        except ValueError:
            return 0

    @property
    def api_token(self) -> str:
        return self.biometric_api_token.get_secret_value().strip()

    def effective_limit(self, requested: int | None) -> int:
        """Resuelve el limite pedido contra los limites configurados."""
        if requested is None:
            return min(self.attendance_default_limit, self.attendance_max_limit)
        return min(requested, self.attendance_max_limit)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
