"""G6.4 explicit MES material-use evidence, atomic with stock movement and audit."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.audit.models import AuditEntry
from mop.master_data.models import Article
from mop.materials.consumption_models import MaterialConsumption
from mop.materials.consumption_schemas import (
    ConsumptionCreate, ConsumptionRead, ConsumptionResult, ConsumptionReverse,
)
from mop.materials.models import MaterialMovement
from mop.materials.service import (
    MaterialsConflict, MaterialsNotFound, MaterialsRule, MaterialsService,
)
from mop.mes.models import ExecutionDispatch, ExecutionOperation


CONSUMPTION_SOURCE = "MOP_G6_CONSUMPTION"


class MaterialConsumptionService:
    """Explicit inventory ISSUE plus measured consumption in one transaction.

    Neither MES START/COMPLETE nor G6.3 theoretical BOM demand calls this service.
    An external stock ISSUE cannot be mistaken for a measured MES consumption.
    """

    def __init__(self, session: Session):
        self.session = session
        self.materials = MaterialsService(session)

    def _operation(self, operation_id: UUID) -> ExecutionOperation:
        operation = self.session.get(ExecutionOperation, operation_id)
        if operation is None:
            raise MaterialsNotFound("MES execution operation not found")
        return operation

    def list(self, operation_id: UUID) -> list[MaterialConsumption]:
        self._operation(operation_id)
        return list(self.session.scalars(
            select(MaterialConsumption)
            .where(MaterialConsumption.execution_operation_id == operation_id)
            .order_by(MaterialConsumption.created_at, MaterialConsumption.id)
        ).all())

    @staticmethod
    def _result(item: MaterialConsumption, replay: bool) -> ConsumptionResult:
        return ConsumptionResult(
            consumption=ConsumptionRead.model_validate(item),
            idempotent_replay=replay,
        )

    def _existing(self, key: str) -> MaterialConsumption | None:
        return self.session.scalar(
            select(MaterialConsumption).where(MaterialConsumption.idempotency_key == key)
        )

    def _commit(self, item: MaterialConsumption) -> ConsumptionResult:
        try:
            self.session.commit()
            self.session.refresh(item)
            return self._result(item, False)
        except IntegrityError as exc:
            self.session.rollback()
            raise MaterialsConflict("consumption evidence was already posted") from exc

    def _audit(self, item: MaterialConsumption, actor_id: UUID, username: str) -> None:
        self.session.add(AuditEntry(
            actor_user_id=actor_id,
            actor_username=username,
            action="materials.consumption.record" if item.kind == "CONSUME"
                   else "materials.consumption.reverse",
            object_type="MaterialConsumption",
            object_id=str(item.id),
            outcome="success",
            details={
                "execution_operation_id": str(item.execution_operation_id),
                "stock_movement_id": str(item.stock_movement_id),
                "article_id": str(item.article_id),
                "location_id": str(item.location_id),
                "quantity": str(item.quantity),
                "evidence_reference": item.evidence_reference,
                "reversal_of_id": str(item.reversal_of_id) if item.reversal_of_id else None,
                "reason_code": item.reason_code,
            },
        ))

    def record(
        self, operation_id: UUID, data: ConsumptionCreate, actor_id: UUID, username: str
    ) -> ConsumptionResult:
        self.materials._advisory_lock(f"source:{CONSUMPTION_SOURCE}:{data.idempotency_key}")
        existing = self._existing(data.idempotency_key)
        if existing is not None:
            if (
                existing.kind != "CONSUME"
                or existing.execution_operation_id != operation_id
                or existing.article_id != data.article_id
                or existing.location_id != data.location_id
                or existing.uom_id != data.uom_id
                or existing.quantity != data.quantity
                or existing.evidence_reference != data.evidence_reference
                or existing.observed_at != data.observed_at
            ):
                raise MaterialsConflict("idempotency key already has different consumption evidence")
            self.session.rollback()
            return self._result(existing, True)

        # Lock the actual MES operation: its START/COMPLETE lifecycle is the authority.
        operation = self.session.scalar(
            select(ExecutionOperation).where(ExecutionOperation.id == operation_id).with_for_update()
        )
        if operation is None:
            raise MaterialsNotFound("MES execution operation not found")
        dispatch = self.session.get(ExecutionDispatch, operation.dispatch_id)
        if dispatch is None or dispatch.status != "RELEASED":
            raise MaterialsRule("consumption requires a RELEASED MES dispatch")
        if operation.status not in {"RUNNING", "PAUSED", "COMPLETED"} or operation.actual_start is None:
            raise MaterialsRule("consumption requires an operation that has actually started")
        if data.observed_at < operation.actual_start:
            raise MaterialsRule("material usage cannot predate MES operation start")
        if operation.actual_finish is not None and data.observed_at > operation.actual_finish:
            raise MaterialsRule("material usage cannot postdate MES operation finish")
        if data.observed_at > datetime.now(timezone.utc):
            raise MaterialsRule("future material usage is not actual consumption")

        article = self.session.get(Article, data.article_id)
        if article is None or not article.active or article.article_kind not in {
            "PURCHASED", "CONSUMABLE", "MANUFACTURED"
        }:
            raise MaterialsRule("actual consumption requires an active purchased, consumable or manufactured input")

        # This lock is shared with every G6 stock posting and reversal.
        self.materials._advisory_lock(f"balance:{data.article_id}:{data.location_id}")
        balance = self.materials._check_dimensions(data.article_id, data.location_id, data.uom_id)
        if not balance.initialized or balance.on_hand is None:
            raise MaterialsRule("cannot consume material from UNKNOWN inventory")
        if balance.on_hand < data.quantity:
            raise MaterialsRule("insufficient physical stock for measured consumption")
        from mop.materials.reservation_service import reserved_quantity
        reserved = reserved_quantity(self.session, data.article_id, data.location_id)
        if balance.on_hand - reserved < data.quantity:
            raise MaterialsRule("material is reserved for a taquilla; release allocation before consumption")

        # Reserved source namespace prevents bypass of MES consumption bookkeeping.
        if self.session.scalar(select(MaterialMovement.id).where(
            MaterialMovement.source_system == CONSUMPTION_SOURCE,
            MaterialMovement.idempotency_key == data.idempotency_key,
        )) is not None:
            raise MaterialsConflict("stock evidence already exists without matching consumption record")

        movement = MaterialMovement(
            id=uuid4(), article_id=data.article_id, location_id=data.location_id,
            uom_id=data.uom_id, kind="ISSUE", quantity=data.quantity,
            signed_quantity=-data.quantity, source_system=CONSUMPTION_SOURCE,
            source_reference=data.evidence_reference, idempotency_key=data.idempotency_key,
            occurred_at=data.observed_at, posted_by=actor_id,
        )
        item = MaterialConsumption(
            id=uuid4(), kind="CONSUME", execution_operation_id=operation.id,
            article_id=data.article_id, location_id=data.location_id,
            uom_id=data.uom_id, quantity=data.quantity,
            stock_movement_id=movement.id,
            idempotency_key=data.idempotency_key,
            evidence_reference=data.evidence_reference,
            observed_at=data.observed_at, recorded_by=actor_id,
        )
        # The consumption FK references an already-inserted movement. Flush under
        # the SAME uncommitted transaction so SQLAlchemy cannot reorder its INSERT.
        self.session.add(movement)
        self.session.flush()
        self.session.add(item)
        self.materials._audit(actor_id, username, "materials.movement.post", movement)
        self._audit(item, actor_id, username)
        return self._commit(item)

    def reverse(
        self, consumption_id: UUID, data: ConsumptionReverse,
        actor_id: UUID, username: str,
    ) -> ConsumptionResult:
        self.materials._advisory_lock(f"source:{CONSUMPTION_SOURCE}:{data.idempotency_key}")
        existing = self._existing(data.idempotency_key)
        if existing is not None:
            if (existing.kind != "REVERSE" or existing.reversal_of_id != consumption_id
                or existing.evidence_reference != data.evidence_reference
                or existing.reason_code != data.reason_code
                or existing.observed_at != data.observed_at):
                raise MaterialsConflict("reversal idempotency key has conflicting evidence")
            self.session.rollback()
            return self._result(existing, True)

        original = self.session.get(MaterialConsumption, consumption_id)
        if original is None:
            raise MaterialsNotFound("consumption not found")
        if original.kind != "CONSUME":
            raise MaterialsRule("cannot reverse a reversal event")
        self.materials._advisory_lock(f"balance:{original.article_id}:{original.location_id}")
        if self.session.scalar(select(MaterialConsumption.id).where(
            MaterialConsumption.reversal_of_id == consumption_id
        )) is not None:
            raise MaterialsConflict("consumption already reversed")

        if data.observed_at < original.observed_at:
            raise MaterialsRule("reversal cannot precede its original consumption")
        if data.observed_at > datetime.now(timezone.utc):
            raise MaterialsRule("future correction event is not allowed")

        movement = MaterialMovement(
            id=uuid4(), article_id=original.article_id,
            location_id=original.location_id, uom_id=original.uom_id,
            kind="REVERSAL", quantity=original.quantity,
            signed_quantity=original.quantity,
            source_system=CONSUMPTION_SOURCE,
            source_reference=data.evidence_reference,
            idempotency_key=data.idempotency_key,
            reversal_of_id=original.stock_movement_id,
            occurred_at=data.observed_at, posted_by=actor_id,
        )
        item = MaterialConsumption(
            id=uuid4(), kind="REVERSE",
            execution_operation_id=original.execution_operation_id,
            article_id=original.article_id, location_id=original.location_id,
            uom_id=original.uom_id, quantity=original.quantity,
            stock_movement_id=movement.id,
            idempotency_key=data.idempotency_key,
            evidence_reference=data.evidence_reference,
            reversal_of_id=original.id,
            reason_code=data.reason_code,
            observed_at=data.observed_at, recorded_by=actor_id,
        )
        # The consumption FK references an already-inserted movement. Flush under
        # the SAME uncommitted transaction so SQLAlchemy cannot reorder its INSERT.
        self.session.add(movement)
        self.session.flush()
        self.session.add(item)
        self.materials._audit(actor_id, username, "materials.movement.post", movement)
        self._audit(item, actor_id, username)
        return self._commit(item)
