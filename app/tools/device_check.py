"""Diagnostico de solo lectura del dispositivo biometrico.

Uso manual (no se ejecuta automaticamente):

    python -m app.tools.device_check

Muestra informacion basica del equipo, el numero de usuarios y el numero de
marcaciones descargadas. No modifica nada en el dispositivo.
"""
from __future__ import annotations

import json
import logging
import sys

from app.config import get_settings
from app.services.biometric_reader import BiometricReader, ping_probe, tcp_probe
from app.utils.errors import BiometricError


def collect(settings) -> dict:
    """Reune el informe de diagnostico sin escribir nada en el dispositivo."""
    reader = BiometricReader(settings)
    report: dict = {
        "device_id": settings.biometric_device_id,
        "host": settings.biometric_host,
        "port": settings.biometric_port,
        "read_only": True,
    }
    reachable, message, _ = tcp_probe(
        settings.biometric_host, settings.biometric_port, settings.biometric_timeout
    )
    report["tcp_port"] = message
    report["icmp"] = ping_probe(settings.biometric_host, settings.biometric_timeout)

    report["device"] = reader.device_info()
    report["users_count"] = len(reader.users())
    report["records_count"] = len(reader.attendance())
    report["transport"] = reader.last_transport
    return report


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    settings = get_settings()
    try:
        report = collect(settings)
    except BiometricError as exc:
        print(f"No fue posible completar el diagnostico: {exc.public_message}", file=sys.stderr)
        print(f"Detalle operador: {exc.operator_detail}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
