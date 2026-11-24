"""Plant-scoped intake and queries for material receipt lots."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.api.v1.materials import checked
from mop.iam.authorization import AuthorizationService
from mop.iam.dependencies import get_current_user
from mop.iam.models import User
from mop.materials.models import MaterialLocation, MaterialWarehouse
from mop.materials.quantity import MaterialQuantityError
from mop.materials.receipt_disposition import LotAction, LotBucket
from mop.materials.receipt_models import MaterialReceiptDecision, MaterialReceiptLot
from mop.materials.receipt_service import ReceiptService
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/materials/receipt-lots", tags=["material receipts"])
SessionDependency = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class ReceiptLotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_line_ref: Reference
    lot_ref: Reference
    article_id: UUID
    location_id: UUID
    uom_id: UUID
    purchase_order_evidence_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=8)

    @field_validator("quantity", mode="before")
    @classmethod
    def exact_quantity(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("quantity must be an exact decimal string or integer")
        return value


class ReceiptLotRead(BaseModel):
    id: UUID
    plant_id: UUID
    receipt_line_ref: str
    lot_ref: str
    article_id: UUID
    location_id: UUID
    uom_id: UUID
    purchase_order_evidence_id: UUID | None
    received_quantity: Decimal
    physical: Decimal
    quarantine: Decimal
    available: Decimal
    nonconforming: Decimal

    @field_serializer("received_quantity", "physical", "quarantine", "available", "nonconforming", when_used="json")
    def serialize_quantity(self, quantity: Decimal) -> str:
        return format(quantity, ".8f")


def _location_plant(session: Session, location_id: UUID) -> UUID | None:
    return session.scalar(
        select(MaterialWarehouse.plant_id)
        .join(MaterialLocation, MaterialLocation.warehouse_id == MaterialWarehouse.id)
        .where(MaterialLocation.id == location_id)
    )


def _read(service: ReceiptService, lot: MaterialReceiptLot, plant_id: UUID) -> ReceiptLotRead:
    balances = service.balances(lot.id)
    return ReceiptLotRead(
        id=lot.id, plant_id=plant_id, receipt_line_ref=lot.receipt_line_ref,
        lot_ref=lot.lot_ref, article_id=lot.article_id, location_id=lot.location_id,
        uom_id=lot.uom_id, purchase_order_evidence_id=lot.purchase_order_evidence_id,
        received_quantity=lot.quantity, physical=balances.physical,
        quarantine=balances.quarantine, available=balances.available,
        nonconforming=balances.nonconforming,
    )


@router.post("", status_code=201, response_model=ReceiptLotRead)
def receive_lot(command: ReceiptLotCreate, session: SessionDependency, actor: CurrentUser):
    plant_id = _location_plant(session, command.location_id)
    if plant_id is None or not AuthorizationService(session).allowed(
        actor.id, "materials.receipt.receive", "plant", plant_id,
    ):
        raise HTTPException(status_code=404, detail="receipt location not found")
    if command.purchase_order_evidence_id is not None and not AuthorizationService(session).allowed(
        actor.id, "prolowin.procurement.read",
    ):
        raise HTTPException(status_code=403, detail="purchase evidence permission required")
    service = ReceiptService(session)
    try:
        lot = checked(lambda: service.receive(
            **command.model_dump(), actor_id=actor.id, username=actor.username,
        ))
        result = _read(service, lot, plant_id)
        session.commit()
        return result
    except MaterialQuantityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="conflicting receipt evidence") from exc


@router.get("/{lot_id}", response_model=ReceiptLotRead)
def get_lot(lot_id: UUID, session: SessionDependency, actor: CurrentUser):
    lot = session.get(MaterialReceiptLot, lot_id)
    plant_id = _location_plant(session, lot.location_id) if lot is not None else None
    if lot is None or plant_id is None or not AuthorizationService(session).allowed(
        actor.id, "materials.receipt.read", "plant", plant_id,
    ):
        raise HTTPException(status_code=404, detail="receipt lot not found")
    return _read(ReceiptService(session), lot, plant_id)


class ReceiptDecisionRead(BaseModel):
    """Persisted decision evidence in its original sequence."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lot_id: UUID
    revision: int
    action: LotAction
    source: LotBucket
    decision_ref: str
    quantity: Decimal
    verified_release_quantity: Decimal | None
    movement_id: UUID | None
    actor_id: UUID
    occurred_at: datetime

    @field_serializer("quantity", "verified_release_quantity", when_used="json")
    def serialize_quantity(self, quantity: Decimal | None) -> str | None:
        return format(quantity, ".8f") if quantity is not None else None


@router.get("/{lot_id}/decisions", response_model=list[ReceiptDecisionRead])
def get_lot_decisions(lot_id: UUID, session: SessionDependency, actor: CurrentUser):
    lot = session.get(MaterialReceiptLot, lot_id)
    plant_id = _location_plant(session, lot.location_id) if lot is not None else None
    if lot is None or plant_id is None or not AuthorizationService(session).allowed(
        actor.id, "materials.receipt.read", "plant", plant_id,
    ):
        raise HTTPException(status_code=404, detail="receipt lot not found")
    return list(session.scalars(
        select(MaterialReceiptDecision)
        .where(MaterialReceiptDecision.lot_id == lot_id)
        .order_by(MaterialReceiptDecision.revision)
    ))
