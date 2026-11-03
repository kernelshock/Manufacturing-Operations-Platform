"""G5.8 isolated CI role fixture. Never run against a non-test database."""
import json
import os
from uuid import uuid4

from mop.config import Settings
from mop.iam.authorization import AuthorizationService
from mop.iam.models import Role
from mop.iam.schemas import RoleAssignmentCreate, RoleCreate, UserCreate
from mop.iam.service import IdentityService
from mop.persistence.database import DatabaseManager
from sqlalchemy import select


def main():
    if os.environ.get("MOP_ENVIRONMENT") != "test":
        raise RuntimeError("RBAC acceptance accounts can only be created in test environment")
    password = os.environ["MOP_RBAC_TEST_PASSWORD"]
    suffix = uuid4().hex[:8]
    db = DatabaseManager(Settings(environment="test", _env_file=None).database_url)
    with db.session() as session:
        identity = IdentityService(session)
        auth = AuthorizationService(session)
        existing_admin = session.scalar(select(Role).where(Role.code == "ADMIN"))
        if existing_admin is None:
            raise RuntimeError("ADMIN role is missing")
        specs = {
            "operator": ["mes.read", "mes.edit"],
            "viewer": ["mes.read"],
            "unprivileged": [],
        }
        accounts = {}
        for kind, granted in specs.items():
            role = identity.create_role(RoleCreate(
                code=f"G58_{kind.upper()}_{suffix}",
                name=f"G5.8 isolated {kind}",
                description="Ephemeral RBAC acceptance only",
            ))
            for permission in granted:
                identity.grant_permission(role.id, permission)
            user = identity.create_user(UserCreate(
                username=f"g58-{kind}-{suffix}",
                display_name=f"G5.8 {kind}",
                password=password,
            ))
            identity.assign_role(user.id, RoleAssignmentCreate(
                role_id=role.id, scope_type="global",
            ))
            effective = set(auth.permission_codes(user.id))
            if effective != set(granted):
                raise RuntimeError(f"Unexpected {kind} effective permissions")
            accounts[kind] = {"username": user.username, "user_id": str(user.id)}
        print("MES_RBAC_USERS=" + json.dumps(accounts, sort_keys=True))


if __name__ == "__main__":
    main()
