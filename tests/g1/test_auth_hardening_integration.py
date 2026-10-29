import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mop.application import create_app
from mop.config import Settings
from mop.iam.models import User
from mop.iam.schemas import UserCreate
from mop.iam.service import IdentityService
from mop.persistence.database import DatabaseManager


pytestmark = pytest.mark.skipif(
    "MOP_DATABASE_URL" not in os.environ,
    reason="requires an explicit PostgreSQL integration database",
)


def test_login_lockout_persists_and_resets_after_expiry() -> None:
    settings = Settings(
        environment="test",
        login_max_failures=3,
        login_lockout_minutes=1,
        _env_file=None,
    )
    database = DatabaseManager(settings.database_url)
    suffix = uuid4().hex[:8].lower()
    username = f"lockout-{suffix}"
    password = "Mop-Lockout-Integration-2026!"

    with database.session() as session:
        IdentityService(session).create_user(
            UserCreate(
                username=username,
                display_name="Lockout Test",
                password=password,
            )
        )

    with TestClient(create_app(settings, database=database)) as client:
        for _ in range(3):
            response = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": "wrong-password"},
            )
            assert response.status_code == 401

        correct_while_locked = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert correct_while_locked.status_code == 401

        with database.session() as session:
            user = session.scalar(select(User).where(User.username == username))
            assert user is not None
            assert user.failed_login_count == 3
            assert user.locked_until is not None
            user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            session.commit()

        after_expiry = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert after_expiry.status_code == 200
        assert after_expiry.headers["cache-control"] == "no-store"

        with database.session() as session:
            user = session.scalar(select(User).where(User.username == username))
            assert user is not None
            assert user.failed_login_count == 0
            assert user.locked_until is None
