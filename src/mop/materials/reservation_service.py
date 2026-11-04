"""G6.5: governed allocation of physical stock to G3 taquillas.

HOLD/RELEASE are append-only accounting of commitments, not stock movements.
Concurrent physical issues and commitments serialize on the G6.2 balance lock.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.audit.models import AuditEntry
from mop.demand.models import ProductionPlan, Taquilla
from mop.materials.models import MaterialMovement
from mop.materials.reservation_models import MaterialReservationEvent
from mop.materials.reservation_schemas import (
    LocationAvailability, ReservationCreate, ReservationEventRead,
    ReservationRelease, ReservationResult, TaquillaCoverage,
)
from mop.materials.requirements import MaterialRequirementsService
from mop.materials.service import MaterialsConflict, MaterialsNotFound, MaterialsRule, MaterialsService


def reserved_quantity(session: Session, article_id: UUID, location_id: UUID | None = None,
                      taquilla_id: UUID | None = None) -> Decimal:
    """Signed HOLD minus RELEASE (no mutable cached reservation total)."""
    stmt = select(func.coalesce(func.sum(MaterialReservationEvent.signed_quantity), 0)).where(
        MaterialReservationEvent.article_id == article_id
    )
    if location_id is not None:
        stmt = stmt.where(MaterialReservationEvent.location_id == location_id)
    if taquilla_id is not None:
        stmt = stmt.where(MaterialReservationEvent.taquilla_id == taquilla_id)
    return Decimal(session.scalar(stmt))


class ReservationService:
    def __init__(self, session: Session):
        self.session = session
        self.materials = MaterialsService(session)
        self.requirements = MaterialRequirementsService(session)

    def _existing(self, key: str) -> MaterialReservationEvent | None:
        return self.session.scalar(
            select(MaterialReservationEvent).where(MaterialReservationEvent.idempotency_key == key)
        )

    def _result(self, event: MaterialReservationEvent, replay: bool) -> ReservationResult:
        return ReservationResult(reservation=ReservationEventRead.model_validate(event),
                                 idempotent_replay=replay)

    def _commit(self, event: MaterialReservationEvent, actor: UUID, username: str) -> ReservationResult:
        self.session.add(event)
        self.session.add(AuditEntry(
            actor_user_id=actor, actor_username=username,
            action="materials.reservation.hold" if event.kind == "HOLD" else "materials.reservation.release",
            object_type="MaterialReservationEvent", object_id=str(event.id), outcome="success",
            details={
                "plan_id": str(event.plan_id), "taquilla_id": str(event.taquilla_id),
                "article_id": str(event.article_id), "location_id": str(event.location_id),
                "quantity": str(event.quantity), "source_reference": event.source_reference,
                "release_of_id": str(event.release_of_id) if event.release_of_id else None,
            },
        ))
        try:
            self.session.commit()
            self.session.refresh(event)
        except IntegrityError as exc:
            self.session.rollback()
            raise MaterialsConflict("duplicate or conflicting reservation evidence") from exc
        return self._result(event, False)

    def availability(self, article_id: UUID, location_id: UUID) -> LocationAvailability:
        stock = self.materials.balance(article_id, location_id)
        held = reserved_quantity(self.session, article_id, location_id)
        return LocationAvailability(
            article_id=article_id, location_id=location_id, uom_id=stock.uom_id,
            on_hand=stock.on_hand, reserved=held,
            unallocated_on_hand=stock.on_hand - held if stock.on_hand is not None else None,
        )

    def coverage(self, taquilla_id: UUID, article_id: UUID, location_id: UUID,
                 effective_at: datetime) -> TaquillaCoverage:
        projection = self.requirements.project_taquilla(taquilla_id, effective_at)
        requirement = next(
            (item for item in projection.aggregate if item.material_article_id == article_id), None
        )
        if requirement is None:
            raise MaterialsRule("article is not a terminal material of the effective taquilla BOM")
        stock = self.availability(article_id, location_id)
        if stock.uom_id is not None and stock.uom_id != requirement.uom_id:
            raise MaterialsRule("stock UoM does not match canonical BOM material")
        for_taquilla = reserved_quantity(self.session, article_id, taquilla_id=taquilla_id)
        # Theoretical requirement minus confirmed holds and unallocated physical quantity.
        shortage = (max(Decimal("0"), requirement.theoretical_quantity - for_taquilla
                        - max(Decimal("0"), stock.unallocated_on_hand))
                    if stock.unallocated_on_hand is not None else None)
        return TaquillaCoverage(
            plan_id=projection.plan_id, taquilla_id=taquilla_id,
            article_id=article_id, uom_id=requirement.uom_id,
            bom_effective_at=effective_at,
            theoretical_required=requirement.theoretical_quantity,
            held_for_taquilla=for_taquilla,
            unallocated_on_hand=stock.unallocated_on_hand,
            shortage=shortage,
            stock_state="KNOWN" if stock.on_hand is not None else "UNKNOWN",
        )

    def events(self, taquilla_id: UUID):
        return self.session.scalars(
            select(MaterialReservationEvent)
            .where(MaterialReservationEvent.taquilla_id == taquilla_id)
            .order_by(MaterialReservationEvent.recorded_at, MaterialReservationEvent.id)
        ).all()

    def hold(self, data: ReservationCreate, actor: UUID, username: str) -> ReservationResult:
        self.materials._advisory_lock(f"reservation:source:{data.idempotency_key}")
        existing = self._existing(data.idempotency_key)
        if existing:
            if (
                existing.kind != "HOLD" or existing.taquilla_id != data.taquilla_id
                or existing.article_id != data.article_id
                or existing.location_id != data.location_id or existing.uom_id != data.uom_id
                or existing.quantity != data.quantity
                or existing.bom_effective_at != data.bom_effective_at
                or existing.source_reference != data.source_reference
            ):
                raise MaterialsConflict("idempotency key reused with different reservation evidence")
            self.session.rollback()
            return self._result(existing, True)

        # Different locations of the same taquilla share a global demand budget.
        self.materials._advisory_lock(f"reservation:demand:{data.taquilla_id}:{data.article_id}")
        taquilla = self.session.get(Taquilla, data.taquilla_id)
        if not taquilla:
            raise MaterialsNotFound("taquilla not found")
        plan = self.session.get(ProductionPlan, taquilla.plan_id)
        if plan is None or plan.status == "CANCELLED" or taquilla.status == "CANCELLED":
            raise MaterialsRule("cancelled plan or taquilla cannot receive a new reservation")
        projection = self.requirements.project_taquilla(taquilla.id, data.bom_effective_at)
        requirement = next(
            (item for item in projection.aggregate if item.material_article_id == data.article_id),
            None,
        )
        if requirement is None or requirement.uom_id != data.uom_id:
            raise MaterialsRule("reservation article and UoM must match effective terminal BOM material")
        already = reserved_quantity(self.session, data.article_id, taquilla_id=taquilla.id)
        if already + data.quantity > requirement.theoretical_quantity:
            raise MaterialsRule("reservation exceeds effective taquilla material demand")

        self.materials._advisory_lock(f"balance:{data.article_id}:{data.location_id}")
        stock = self.materials._check_dimensions(data.article_id, data.location_id, data.uom_id)
        held = reserved_quantity(self.session, data.article_id, data.location_id)
        if stock.on_hand is None:
            raise MaterialsRule("cannot reserve from UNKNOWN stock")
        if data.quantity > stock.on_hand - held:
            raise MaterialsRule("insufficient unallocated physical stock to reserve")
        event = MaterialReservationEvent(
            id=uuid4(), kind="HOLD", plan_id=plan.id, taquilla_id=taquilla.id,
            article_id=data.article_id, location_id=data.location_id, uom_id=data.uom_id,
            quantity=data.quantity, signed_quantity=data.quantity,
            bom_effective_at=data.bom_effective_at, idempotency_key=data.idempotency_key,
            source_reference=data.source_reference, recorded_by=actor,
        )
        return self._commit(event, actor, username)

    def release(self, hold_id: UUID, data: ReservationRelease,
                actor: UUID, username: str) -> ReservationResult:
        self.materials._advisory_lock(f"reservation:source:{data.idempotency_key}")
        existing = self._existing(data.idempotency_key)
        if existing:
            if (
                existing.kind != "RELEASE" or existing.release_of_id != hold_id
                or existing.quantity != data.quantity
                or existing.source_reference != data.source_reference
                or existing.reason_code != data.reason_code
            ):
                raise MaterialsConflict("idempotency key reused with different release evidence")
            self.session.rollback()
            return self._result(existing, True)
        original = self.session.get(MaterialReservationEvent, hold_id)
        if original is None:
            raise MaterialsNotFound("reservation not found")
        if original.kind != "HOLD":
            raise MaterialsRule("cannot release a release event")
        self.materials._advisory_lock(f"balance:{original.article_id}:{original.location_id}")
        released = Decimal(self.session.scalar(
            select(func.coalesce(func.sum(MaterialReservationEvent.quantity), 0))
            .where(MaterialReservationEvent.release_of_id == original.id)
        ))
        if data.quantity > original.quantity - released:
            raise MaterialsConflict("release exceeds remaining held quantity")
        event = MaterialReservationEvent(
            id=uuid4(), kind="RELEASE", plan_id=original.plan_id,
            taquilla_id=original.taquilla_id, article_id=original.article_id,
            location_id=original.location_id, uom_id=original.uom_id,
            quantity=data.quantity, signed_quantity=-data.quantity,
            bom_effective_at=original.bom_effective_at,
            idempotency_key=data.idempotency_key, source_reference=data.source_reference,
            reason_code=data.reason_code, release_of_id=original.id, recorded_by=actor,
        )
        return self._commit(event, actor, username)
