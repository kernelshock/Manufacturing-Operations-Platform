"""G3 operational demand application service."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.demand.models import ProductionPlan, Taquilla
from mop.demand.schemas import (
    ProductionPlanCreate,
    ProductionPlanNumberUpdate,
    ProductionPlanStatusUpdate,
    TaquillaCreate,
    TaquillaStatusUpdate,
)


class DemandConflictError(ValueError):
    pass


class DemandRuleError(ValueError):
    pass


class DemandNotFoundError(LookupError):
    pass


_PLAN_TRANSITIONS = {
    "DRAFT": {"OPEN", "CANCELLED"},
    "OPEN": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}

_TAQUILLA_TRANSITIONS = {
    "DRAFT": {"READY", "CANCELLED"},
    "READY": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


class DemandService:
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
            raise DemandConflictError("demand identity already exists") from exc

    def create_plan(self, data: ProductionPlanCreate) -> ProductionPlan:
        return self._commit(
            ProductionPlan(
                plan_number=data.plan_number,
                description=data.description,
                status="DRAFT",
            )
        )

    def list_plans(self, status: str | None = None) -> Sequence[ProductionPlan]:
        query = select(ProductionPlan)
        if status is not None:
            query = query.where(ProductionPlan.status == status)
        return self.session.scalars(
            query.order_by(ProductionPlan.created_at.desc(), ProductionPlan.plan_number)
        ).all()

    def get_plan(self, plan_id: UUID) -> ProductionPlan:
        plan = self.session.get(ProductionPlan, plan_id)
        if plan is None:
            raise DemandNotFoundError("production plan not found")
        return plan

    def update_plan_number(
        self, plan_id: UUID, data: ProductionPlanNumberUpdate
    ) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        if plan.status in {"COMPLETED", "CANCELLED"}:
            raise DemandRuleError("terminal production plan number is immutable")
        plan.plan_number = data.plan_number
        return self._commit(plan)

    def transition_plan(
        self, plan_id: UUID, data: ProductionPlanStatusUpdate
    ) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        if data.status == plan.status:
            return plan
        if data.status not in _PLAN_TRANSITIONS[plan.status]:
            raise DemandRuleError(
                f"production plan transition {plan.status} -> {data.status} is not allowed"
            )
        plan.status = data.status
        return self._commit(plan)

    def create_taquilla(self, plan_id: UUID, data: TaquillaCreate) -> Taquilla:
        plan = self.get_plan(plan_id)
        if plan.status in {"COMPLETED", "CANCELLED"}:
            raise DemandRuleError("cannot add taquillas to a terminal production plan")
        return self._commit(
            Taquilla(
                plan_id=plan.id,
                taquilla_code=data.taquilla_code,
                sequence_no=data.sequence_no,
                description=data.description,
                status="DRAFT",
            )
        )

    def list_taquillas(self, plan_id: UUID) -> Sequence[Taquilla]:
        self.get_plan(plan_id)
        return self.session.scalars(
            select(Taquilla)
            .where(Taquilla.plan_id == plan_id)
            .order_by(Taquilla.sequence_no, Taquilla.taquilla_code)
        ).all()

    def get_taquilla(self, taquilla_id: UUID) -> Taquilla:
        taquilla = self.session.get(Taquilla, taquilla_id)
        if taquilla is None:
            raise DemandNotFoundError("taquilla not found")
        return taquilla

    def transition_taquilla(
        self, taquilla_id: UUID, data: TaquillaStatusUpdate
    ) -> Taquilla:
        taquilla = self.get_taquilla(taquilla_id)
        if data.status == taquilla.status:
            return taquilla
        if data.status not in _TAQUILLA_TRANSITIONS[taquilla.status]:
            raise DemandRuleError(
                f"taquilla transition {taquilla.status} -> {data.status} is not allowed"
            )
        taquilla.status = data.status
        return self._commit(taquilla)
