"""G3 operational demand application service."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.demand.models import ProductionPlan, Taquilla, TaquillaProductLine
from mop.master_data.models import Article
from mop.demand.schemas import (
    ProductionPlanCreate,
    ProductionPlanNumberUpdate,
    ProductionPlanStatusUpdate,
    TaquillaCreate,
    TaquillaProductLineCreate,
    TaquillaProductLineUpdate,
    TaquillaStatusUpdate,
    TaquillaTopologyUpdate,
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
                vehicle_topology="SIMPLE",
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

    def update_taquilla_topology(
        self, taquilla_id: UUID, data: TaquillaTopologyUpdate
    ) -> Taquilla:
        taquilla = self._require_draft_taquilla(taquilla_id)
        if taquilla.vehicle_topology == data.vehicle_topology:
            return taquilla
        has_lines = self.session.scalar(
            select(TaquillaProductLine.id)
            .where(TaquillaProductLine.taquilla_id == taquilla.id)
            .limit(1)
        )
        if has_lines is not None:
            raise DemandRuleError(
                "vehicle topology must be declared before product composition"
            )
        taquilla.vehicle_topology = data.vehicle_topology
        return self._commit(taquilla)

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


    def _require_draft_taquilla(self, taquilla_id: UUID) -> Taquilla:
        taquilla = self.get_taquilla(taquilla_id)
        if taquilla.status != "DRAFT":
            raise DemandRuleError(
                "product composition can only be changed while taquilla is DRAFT"
            )
        return taquilla

    def add_product_line(
        self, taquilla_id: UUID, data: TaquillaProductLineCreate
    ) -> TaquillaProductLine:
        taquilla = self._require_draft_taquilla(taquilla_id)
        article = self.session.get(Article, data.article_id)
        if article is None:
            raise DemandNotFoundError("article not found")
        if article.article_kind != "FINISHED_PRODUCT" or not article.active:
            raise DemandRuleError(
                "taquilla product line requires an active FINISHED_PRODUCT article"
            )
        self._validate_deck_position(taquilla, data.deck_position)

        if data.source_line_key is not None:
            existing = self.session.scalar(
                select(TaquillaProductLine).where(
                    TaquillaProductLine.taquilla_id == taquilla.id,
                    TaquillaProductLine.source_line_key == data.source_line_key,
                )
            )
            if existing is not None:
                if (
                    existing.article_id == data.article_id
                    and existing.sequence_no == data.sequence_no
                    and existing.requested_quantity == data.requested_quantity
                    and existing.deck_position == data.deck_position
                    and existing.source_document_key == data.source_document_key
                ):
                    return existing
                raise DemandConflictError(
                    "source_line_key already identifies a different product line"
                )

        return self._commit(
            TaquillaProductLine(
                taquilla_id=taquilla.id,
                article_id=data.article_id,
                sequence_no=data.sequence_no,
                requested_quantity=data.requested_quantity,
                source_line_key=data.source_line_key,
                deck_position=data.deck_position,
                source_document_key=data.source_document_key,
            )
        )

    def list_product_lines(
        self, taquilla_id: UUID
    ) -> Sequence[TaquillaProductLine]:
        self.get_taquilla(taquilla_id)
        return self.session.scalars(
            select(TaquillaProductLine)
            .where(TaquillaProductLine.taquilla_id == taquilla_id)
            .order_by(
                TaquillaProductLine.sequence_no,
                TaquillaProductLine.id,
            )
        ).all()

    def get_product_line(self, line_id: UUID) -> TaquillaProductLine:
        line = self.session.get(TaquillaProductLine, line_id)
        if line is None:
            raise DemandNotFoundError("taquilla product line not found")
        return line

    def _validate_deck_position(
        self, taquilla: Taquilla, deck_position: str
    ) -> None:
        if taquilla.vehicle_topology == "SIMPLE" and deck_position != "SINGLE":
            raise DemandRuleError(
                "SIMPLE taquilla product lines must use SINGLE deck position"
            )
        if (
            taquilla.vehicle_topology == "DOUBLE_DECK"
            and deck_position not in {"UPPER", "LOWER"}
        ):
            raise DemandRuleError(
                "DOUBLE_DECK taquilla product lines require UPPER or LOWER deck position"
            )

    def update_product_line(
        self, line_id: UUID, data: TaquillaProductLineUpdate
    ) -> TaquillaProductLine:
        line = self.get_product_line(line_id)
        taquilla = self._require_draft_taquilla(line.taquilla_id)
        requested_deck = data.deck_position or line.deck_position
        self._validate_deck_position(taquilla, requested_deck)
        line.sequence_no = data.sequence_no
        line.requested_quantity = data.requested_quantity
        line.deck_position = requested_deck
        if "source_document_key" in data.model_fields_set:
            line.source_document_key = data.source_document_key
        return self._commit(line)
