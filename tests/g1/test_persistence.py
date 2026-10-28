import os

import pytest
from sqlalchemy.exc import SQLAlchemyError

from fastapi.testclient import TestClient

from mop.application import create_app
from mop.config import Settings
from mop.persistence.database import DatabaseManager


class ReadyDatabase:
    def check_connection(self) -> None:
        return None

    def dispose(self) -> None:
        return None


class UnavailableDatabase:
    def check_connection(self) -> None:
        raise SQLAlchemyError("database unavailable")

    def dispose(self) -> None:
        return None


def test_database_manager_can_probe_a_sqlalchemy_database() -> None:
    database = DatabaseManager("sqlite+pysqlite:///:memory:")
    try:
        database.check_connection()
    finally:
        database.dispose()


def test_readiness_reports_database_ok() -> None:
    settings = Settings(environment="test", _env_file=None)
    client = TestClient(create_app(settings, database=ReadyDatabase()))

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"] == {
        "application": "ok",
        "database": "ok",
    }


def test_readiness_fails_closed_when_database_is_unavailable() -> None:
    settings = Settings(environment="test", _env_file=None)
    client = TestClient(create_app(settings, database=UnavailableDatabase()))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"] == {
        "application": "ok",
        "database": "unavailable",
    }


@pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)
def test_postgresql_integration_connection() -> None:
    settings = Settings(environment="test", _env_file=None)
    database = DatabaseManager(settings.database_url)
    try:
        assert database.engine.dialect.name == "postgresql"
        database.check_connection()
    finally:
        database.dispose()
