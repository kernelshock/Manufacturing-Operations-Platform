"""Identity lifecycle and RBAC assignment services."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.core.models import Area, Organization, Plant
from mop.iam.models import Permission, Role, RolePermission, User, UserRoleAssignment
from mop.iam.schemas import RoleAssignmentCreate, RoleCreate, UserCreate
from mop.iam.security import hash_password, verify_password


class IdentityConflictError(ValueError):
    pass


class IdentityNotFoundError(LookupError):
    pass


class IdentityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _commit(self, entity):
        try:
            self.session.add(entity)
            self.session.commit()
            self.session.refresh(entity)
            return entity
        except IntegrityError as exc:
            self.session.rollback()
            raise IdentityConflictError("identity record already exists") from exc

    def create_user(self, data: UserCreate) -> User:
        return self._commit(
            User(
                username=data.username,
                display_name=data.display_name.strip(),
                password_hash=hash_password(data.password),
                enabled=data.enabled,
            )
        )

    def create_role(self, data: RoleCreate) -> Role:
        return self._commit(
            Role(
                code=data.code,
                name=data.name.strip(),
                description=data.description,
                active=True,
                system=False,
            )
        )

    def list_users(self):
        return self.session.scalars(select(User).order_by(User.username)).all()

    def list_roles(self):
        return self.session.scalars(select(Role).order_by(Role.code)).all()

    def list_permissions(self):
        return self.session.scalars(select(Permission).order_by(Permission.code)).all()

    def authenticate(self, username: str, password: str) -> User | None:
        normalized = username.strip().lower()
        user = self.session.scalar(select(User).where(User.username == normalized))
        if user is None or not user.enabled:
            return None
        if not verify_password(password, user.password_hash):
            return None
        user.last_login_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(user)
        return user

    def grant_permission(self, role_id: UUID, permission_code: str) -> RolePermission:
        role = self.session.get(Role, role_id)
        if role is None:
            raise IdentityNotFoundError("role not found")
        permission = self.session.scalar(select(Permission).where(Permission.code == permission_code))
        if permission is None:
            raise IdentityNotFoundError("permission not found")
        existing = self.session.get(RolePermission, (role.id, permission.id))
        if existing is not None:
            return existing
        return self._commit(RolePermission(role_id=role.id, permission_id=permission.id))

    def assign_role(self, user_id: UUID, data: RoleAssignmentCreate) -> UserRoleAssignment:
        user = self.session.get(User, user_id)
        if user is None:
            raise IdentityNotFoundError("user not found")
        role = self.session.get(Role, data.role_id)
        if role is None or not role.active:
            raise IdentityNotFoundError("role not found")
        self._validate_scope(data.scope_type, data.scope_id)
        return self._commit(
            UserRoleAssignment(
                user_id=user.id,
                role_id=role.id,
                scope_type=data.scope_type,
                scope_id=data.scope_id,
            )
        )

    def _validate_scope(self, scope_type: str, scope_id: UUID | None) -> None:
        if scope_type == "global":
            return
        model = {
            "organization": Organization,
            "plant": Plant,
            "area": Area,
        }[scope_type]
        if self.session.get(model, scope_id) is None:
            raise IdentityNotFoundError(f"{scope_type} scope not found")
