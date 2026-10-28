"""Server-side capability and organizational-scope authorization."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from mop.core.models import Area, Plant, WorkCenter
from mop.iam.models import Permission, Role, RolePermission, UserRoleAssignment


class PermissionDeniedError(PermissionError):
    pass


class AuthorizationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def permission_codes(self, user_id: UUID) -> list[str]:
        statement = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user_id,
                Role.active.is_(True),
            )
            .distinct()
            .order_by(Permission.code)
        )
        return list(self.session.scalars(statement).all())

    def require(
        self,
        user_id: UUID,
        permission_code: str,
        target_scope_type: str = "global",
        target_scope_id: UUID | None = None,
    ) -> None:
        if not self.allowed(user_id, permission_code, target_scope_type, target_scope_id):
            raise PermissionDeniedError(permission_code)

    def allowed(
        self,
        user_id: UUID,
        permission_code: str,
        target_scope_type: str = "global",
        target_scope_id: UUID | None = None,
    ) -> bool:
        statement = (
            select(UserRoleAssignment)
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                UserRoleAssignment.user_id == user_id,
                Role.active.is_(True),
                Permission.code == permission_code,
            )
        )
        assignments = self.session.scalars(statement).all()

        if any(item.scope_type == "global" for item in assignments):
            return True
        if target_scope_type == "global":
            return False

        lineage = self._lineage(target_scope_type, target_scope_id)
        if lineage is None:
            return False

        return any(
            assignment.scope_type in lineage
            and assignment.scope_id == lineage[assignment.scope_type]
            for assignment in assignments
        )

    def _lineage(self, scope_type: str, scope_id: UUID | None) -> dict[str, UUID] | None:
        if scope_id is None:
            return None
        if scope_type == "organization":
            return {"organization": scope_id}
        if scope_type == "plant":
            plant = self.session.get(Plant, scope_id)
            if plant is None:
                return None
            return {"organization": plant.organization_id, "plant": plant.id}
        if scope_type == "area":
            area = self.session.get(Area, scope_id)
            if area is None:
                return None
            plant = self.session.get(Plant, area.plant_id)
            if plant is None:
                return None
            return {
                "organization": plant.organization_id,
                "plant": plant.id,
                "area": area.id,
            }
        if scope_type == "work_center":
            work_center = self.session.get(WorkCenter, scope_id)
            if work_center is None:
                return None
            area = self.session.get(Area, work_center.area_id)
            if area is None:
                return None
            plant = self.session.get(Plant, area.plant_id)
            if plant is None:
                return None
            return {
                "organization": plant.organization_id,
                "plant": plant.id,
                "area": area.id,
            }
        return None
