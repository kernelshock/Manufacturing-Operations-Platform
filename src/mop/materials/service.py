"""G6.2 — transactional operational stock ledger, not ERP accounting inventory."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.audit.models import AuditEntry
from mop.core.models import Plant
from mop.master_data.models import Article, UnitOfMeasure
from mop.materials.models import MaterialLocation, MaterialMovement, MaterialWarehouse
from mop.materials.schemas import (
    BalanceRead, LocationCreate, MovementCreate, MovementReverse, WarehouseCreate,
)
from mop.materials.quantity import decimal_quantity


class MaterialsNotFound(LookupError):
    pass


class MaterialsConflict(ValueError):
    pass


class MaterialsRule(ValueError):
    pass


class MaterialsService:
    def __init__(self, session: Session):
        self.session = session

    def _advisory_lock(self, key: str) -> None:
        # PostgreSQL transaction-scoped lock: all writers for one key are serialized.
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "mop.g6:" + key},
        )

    def _commit(self, entity):
        try:
            self.session.commit()
            self.session.refresh(entity)
            return entity
        except IntegrityError as exc:
            self.session.rollback()
            raise MaterialsConflict("conflicting inventory identity or evidence") from exc

    def _audit(self, actor_id: UUID, actor_username: str, action: str, entity) -> None:
        self.session.add(AuditEntry(
            actor_user_id=actor_id, actor_username=actor_username, action=action,
            object_type=type(entity).__name__, object_id=str(entity.id), outcome="success",
            details={"source_system": getattr(entity, "source_system", None),
                     "source_reference": getattr(entity, "source_reference", None)},
        ))

    def warehouse(self, data: WarehouseCreate, actor_id: UUID, username: str) -> MaterialWarehouse:
        plant = self.session.get(Plant, data.plant_id)
        if plant is None or not plant.active:
            raise MaterialsRule("active plant is required")
        entity = MaterialWarehouse(plant_id=data.plant_id, code=data.code, name=data.name.strip())
        self.session.add(entity)
        self.session.flush()
        self._audit(actor_id, username, "materials.warehouse.create", entity)
        return self._commit(entity)

    def location(self, data: LocationCreate, actor_id: UUID, username: str) -> MaterialLocation:
        wh = self.session.get(MaterialWarehouse, data.warehouse_id)
        if wh is None or not wh.active:
            raise MaterialsRule("active warehouse is required")
        entity = MaterialLocation(warehouse_id=data.warehouse_id, code=data.code, name=data.name.strip())
        self.session.add(entity)
        self.session.flush()
        self._audit(actor_id, username, "materials.location.create", entity)
        return self._commit(entity)

    def list_warehouses(self, plant_id: UUID | None = None):
        stmt = select(MaterialWarehouse)
        if plant_id is not None:
            stmt = stmt.where(MaterialWarehouse.plant_id == plant_id)
        return self.session.scalars(stmt.order_by(MaterialWarehouse.code)).all()

    def list_locations(self, warehouse_id: UUID | None = None):
        stmt = select(MaterialLocation)
        if warehouse_id is not None:
            stmt = stmt.where(MaterialLocation.warehouse_id == warehouse_id)
        return self.session.scalars(stmt.order_by(MaterialLocation.code)).all()

    def balance(self, article_id: UUID, location_id: UUID) -> BalanceRead:
        row = self.session.execute(
            select(func.count(MaterialMovement.id), func.coalesce(func.sum(MaterialMovement.signed_quantity), 0))
            .where(MaterialMovement.article_id == article_id, MaterialMovement.location_id == location_id)
        ).one()
        count, amount = row
        unit_id = self.session.scalar(select(MaterialMovement.uom_id).where(
            MaterialMovement.article_id == article_id, MaterialMovement.location_id == location_id
        ).limit(1)) if count else None
        return BalanceRead(article_id=article_id, location_id=location_id,
                           uom_id=unit_id if count else None,
                           initialized=bool(count), on_hand=Decimal(amount) if count else None)

    def list_movements(self, article_id: UUID, location_id: UUID):
        return self.session.scalars(
            select(MaterialMovement).where(
                MaterialMovement.article_id == article_id,
                MaterialMovement.location_id == location_id,
            ).order_by(MaterialMovement.posted_at, MaterialMovement.id)
        ).all()

    def _check_dimensions(self, article_id: UUID, location_id: UUID, uom_id: UUID):
        article = self.session.get(Article, article_id)
        location = self.session.get(MaterialLocation, location_id)
        warehouse = self.session.get(MaterialWarehouse, location.warehouse_id) if location else None
        uom = self.session.get(UnitOfMeasure, uom_id)
        if article is None or not article.active:
            raise MaterialsRule("active canonical article required")
        if location is None or not location.active or warehouse is None or not warehouse.active:
            raise MaterialsRule("active location and warehouse required")
        if uom is None or not uom.active or article.default_uom_id != uom_id:
            raise MaterialsRule("article canonical UoM is required; no implicit conversion")
        prior = self.balance(article_id, location_id)
        if prior.initialized and prior.uom_id != uom_id:
            raise MaterialsRule("ledger UoM mismatch")
        return prior

    def _store(self, entity: MaterialMovement, actor_id: UUID, username: str):
        self.session.add(entity)
        self.session.flush()
        self._audit(actor_id, username, "materials.movement.post", entity)
        return self._commit(entity)

    def post(self, data: MovementCreate, actor_id: UUID, username: str):
        from mop.materials.schemas import PostingResult
        qty = decimal_quantity(data.quantity, allow_zero=data.kind == "OPENING_ZERO")
        if qty > Decimal("9999999999999999.99999999"):
            raise MaterialsRule("stock quantity exceeds Numeric(24,8)")
        if data.kind == "OPENING_ZERO" and qty != 0:
            raise MaterialsRule("zero opening must contain exactly zero")
        self._advisory_lock(f"source:{data.source_system}:{data.idempotency_key}")
        existing = self.session.scalar(select(MaterialMovement).where(
            MaterialMovement.source_system == data.source_system,
            MaterialMovement.idempotency_key == data.idempotency_key,
        ))
        if existing is not None:
            if (existing.article_id, existing.location_id, existing.uom_id, existing.kind,
                existing.quantity, existing.source_reference) != (
                data.article_id, data.location_id, data.uom_id, data.kind,
                qty, data.source_reference
            ) or (data.occurred_at is not None and existing.occurred_at != data.occurred_at):
                raise MaterialsConflict("idempotency key reused with different inventory evidence")
            self.session.rollback()
            return PostingResult(movement=existing, idempotent_replay=True)

        self._advisory_lock(f"balance:{data.article_id}:{data.location_id}")
        current = self._check_dimensions(data.article_id, data.location_id, data.uom_id)
        if data.kind.startswith("OPENING") and current.initialized:
            raise MaterialsRule("opening balance can be posted only once per material/location")
        if data.kind in ("ISSUE", "ADJUSTMENT_OUT") and not current.initialized:
            raise MaterialsRule("cannot issue from UNKNOWN stock")
        sign = -1 if data.kind in ("ISSUE", "ADJUSTMENT_OUT") else 1
        signed = qty * sign
        if current.initialized and (current.on_hand or Decimal("0")) + signed < 0:
            raise MaterialsRule("insufficient stock; negative stock is not authorized")
        entity = MaterialMovement(
            article_id=data.article_id, location_id=data.location_id, uom_id=data.uom_id,
            kind=data.kind, quantity=qty, signed_quantity=signed,
            source_system=data.source_system, source_reference=data.source_reference,
            idempotency_key=data.idempotency_key,
            occurred_at=data.occurred_at or datetime.now(timezone.utc), posted_by=actor_id,
        )
        self._store(entity, actor_id, username)
        return PostingResult(movement=entity, idempotent_replay=False)

    def reverse(self, movement_id: UUID, data: MovementReverse, actor_id: UUID, username: str):
        from mop.materials.schemas import PostingResult
        self._advisory_lock(f"source:{data.source_system}:{data.idempotency_key}")
        existing = self.session.scalar(select(MaterialMovement).where(
            MaterialMovement.source_system == data.source_system,
            MaterialMovement.idempotency_key == data.idempotency_key,
        ))
        if existing is not None:
            if existing.kind != "REVERSAL" or existing.reversal_of_id != movement_id or existing.source_reference != data.source_reference:
                raise MaterialsConflict("reversal idempotency conflict")
            self.session.rollback()
            return PostingResult(movement=existing, idempotent_replay=True)
        original = self.session.get(MaterialMovement, movement_id)
        if original is None:
            raise MaterialsNotFound("movement not found")
        if original.kind in ("REVERSAL", "OPENING_ZERO"):
            raise MaterialsRule("cannot reverse a reversal")
        self._advisory_lock(f"balance:{original.article_id}:{original.location_id}")
        if self.session.scalar(select(MaterialMovement.id).where(MaterialMovement.reversal_of_id == movement_id)):
            raise MaterialsConflict("movement already reversed")
        current = self.balance(original.article_id, original.location_id)
        signed = -original.signed_quantity
        if current.on_hand is None or current.on_hand + signed < 0:
            raise MaterialsRule("reversal would create negative stock")
        entity = MaterialMovement(
            article_id=original.article_id, location_id=original.location_id,
            uom_id=original.uom_id, kind="REVERSAL", quantity=original.quantity,
            signed_quantity=signed, source_system=data.source_system.strip(),
            source_reference=data.source_reference.strip(),
            idempotency_key=data.idempotency_key.strip(),
            reversal_of_id=original.id, occurred_at=datetime.now(timezone.utc),
            posted_by=actor_id,
        )
        self._store(entity, actor_id, username)
        return PostingResult(movement=entity, idempotent_replay=False)
