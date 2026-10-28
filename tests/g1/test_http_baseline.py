from fastapi.testclient import TestClient

from mop.application import create_app
from mop.config import Settings


class ReadyDatabase:
    def check_connection(self) -> None:
        return None

    def dispose(self) -> None:
        return None


def client() -> TestClient:
    settings = Settings(environment="test", _env_file=None)
    return TestClient(create_app(settings, database=ReadyDatabase()))


def test_liveness_endpoint() -> None:
    response = client().get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Manufacturing Operations Platform",
        "environment": "test",
    }


def test_readiness_endpoint_includes_database_status() -> None:
    response = client().get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"] == {
        "application": "ok",
        "database": "ok",
    }


def test_versioned_api_metadata() -> None:
    response = client().get("/api/v1/meta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Manufacturing Operations Platform"
    assert payload["version"] == "2.0.0.dev1"
    assert payload["environment"] == "test"
    assert payload["api_prefix"] == "/api/v1"


def test_openapi_contains_versioned_and_health_endpoints() -> None:
    response = client().get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert "/api/v1/meta" in paths
