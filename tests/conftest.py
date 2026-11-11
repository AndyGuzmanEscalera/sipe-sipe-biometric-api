"""Fixtures compartidas. Ninguna prueba contacta el dispositivo fisico."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.services.biometric_reader import get_reader
from tests.fakes import FakeReader

TOKEN = "token-de-prueba-0123456789"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        biometric_host="127.0.0.1",
        biometric_port=4370,
        biometric_timeout=1,
        biometric_device_id="alcaldia-central",
        biometric_api_token=TOKEN,
        attendance_default_limit=500,
        attendance_max_limit=5000,
    )


@pytest.fixture
def fake_reader(settings: Settings) -> FakeReader:
    return FakeReader(settings)


@pytest.fixture
def client(settings: Settings, fake_reader: FakeReader):
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_reader] = lambda: fake_reader
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}
