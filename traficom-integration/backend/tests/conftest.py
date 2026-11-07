from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astrasync_api.app import build_openapi, create_app

CONTRACT_DIR = Path(__file__).resolve().parents[2] / "contract"
FIXTURES_DIR = CONTRACT_DIR / "fixtures"


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def openapi(app: FastAPI) -> dict:
    return build_openapi(app)
