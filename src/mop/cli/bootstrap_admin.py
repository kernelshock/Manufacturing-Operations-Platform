"""Create the first local administrator without exposing a public registration route."""

import argparse
import getpass
import os

from sqlalchemy import select

from mop.config import get_settings
from mop.iam.models import Role, User
from mop.iam.schemas import RoleAssignmentCreate, UserCreate
from mop.iam.service import IdentityConflictError, IdentityService
from mop.persistence.database import DatabaseManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the initial MOP administrator")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--display-name", default="MOP Administrator")
    args = parser.parse_args()

    password = os.getenv("MOP_BOOTSTRAP_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Initial administrator password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("Passwords do not match")

    settings = get_settings()
    database = DatabaseManager(settings.database_url)
    try:
        with database.session() as session:
            service = IdentityService(session)
            existing = session.scalar(select(User).where(User.username == args.username.strip().lower()))
            if existing is not None:
                raise SystemExit("Administrator username already exists")
            admin_role = session.scalar(select(Role).where(Role.code == "ADMIN"))
            if admin_role is None:
                raise SystemExit("ADMIN role is missing; run Alembic migrations first")
            try:
                user = service.create_user(
                    UserCreate(
                        username=args.username,
                        display_name=args.display_name,
                        password=password,
                    )
                )
                service.assign_role(
                    user.id,
                    RoleAssignmentCreate(role_id=admin_role.id, scope_type="global"),
                )
            except IdentityConflictError as exc:
                raise SystemExit(str(exc)) from exc
            print(f"Administrator created: {user.username}")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
