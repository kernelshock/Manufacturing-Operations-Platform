"""Scoped inspection policy, signing-key administration and signed release."""

import base64
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.api.v1.material_receipts import ReceiptDecisionRead
from mop.iam.authorization import PermissionDeniedError
from mop.iam.dependencies import get_current_user
from mop.iam.models import User
from mop.materials.receipt_disposition import ReceiptDispositionError
from mop.materials.release_models import ReceiptReleaseEvidence, ReceiptSignerKey, ReceiptSignerRevocation
from mop.materials.release_schemas import (
    InspectionPolicyCreate, Reference, ReleasePreparation, SignedReleaseCreate, SigningKeyCreate,
)
from mop.materials.release_service import ReceiptReleaseService
from mop.materials.service import MaterialsConflict, MaterialsNotFound, MaterialsRule
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/materials/release", tags=["material release"])
SessionDependency = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


class InspectionPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    lot_id: UUID
    revision: int
    engineering_defined: bool
    responsible_area_id: UUID | None
    criteria: list[str]
    configured_by: UUID
    configured_at: datetime


class RevokeKeyCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reference


def checked(session, operation, *, commit=False):
    try:
        result = operation()
        if commit:
            session.commit()
        return result
    except PermissionDeniedError as exc:
        session.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MaterialsNotFound as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (MaterialsConflict, IntegrityError) as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="conflicting receipt release evidence") from exc
    except (MaterialsRule, ReceiptDispositionError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/signer-keys", status_code=201)
def register_signer(command: SigningKeyCreate, session: SessionDependency, actor: CurrentUser):
    service = ReceiptReleaseService(session, actor)
    key = checked(session, lambda: service.register_key(command), commit=True)
    return {"id": str(key.id), "user_id": str(key.user_id),
            "public_key_base64": base64.b64encode(key.public_key).decode("ascii")}


@router.get("/signer-keys")
def own_signer_keys(session: SessionDependency, actor: CurrentUser):
    return [
        {"id": str(key.id), "public_key_base64": base64.b64encode(key.public_key).decode("ascii"),
         "revoked": session.get(ReceiptSignerRevocation, key.id) is not None}
        for key in session.scalars(select(ReceiptSignerKey).where(
            ReceiptSignerKey.user_id == actor.id,
        ).order_by(ReceiptSignerKey.registered_at, ReceiptSignerKey.id))
    ]


@router.post("/signer-keys/{key_id}/revoke")
def revoke_signer(key_id: UUID, command: RevokeKeyCommand, session: SessionDependency, actor: CurrentUser):
    checked(session, lambda: ReceiptReleaseService(session, actor).revoke_key(key_id, command.reason), commit=True)
    return {"key_id": str(key_id), "revoked": True}


@router.post("/lots/{lot_id}/inspection-policy", status_code=201, response_model=InspectionPolicyRead)
def configure_policy(lot_id: UUID, command: InspectionPolicyCreate, session: SessionDependency, actor: CurrentUser):
    return checked(session, lambda: ReceiptReleaseService(session, actor).configure(lot_id, command), commit=True)


@router.get("/lots/{lot_id}/inspection-policy", response_model=InspectionPolicyRead | None)
def current_policy(lot_id: UUID, session: SessionDependency, actor: CurrentUser):
    return checked(session, lambda: ReceiptReleaseService(session, actor).latest_policy(lot_id))


@router.post("/lots/{lot_id}/signing-payload")
def prepare_release(lot_id: UUID, command: ReleasePreparation, session: SessionDependency, actor: CurrentUser):
    result = checked(session, lambda: ReceiptReleaseService(session, actor).prepare(lot_id, command))
    return {"algorithm": "Ed25519", "encoding": "UTF-8", "payload": result[3].decode("utf-8")}


@router.post("/lots/{lot_id}/decisions", status_code=201, response_model=ReceiptDecisionRead)
def release_lot(lot_id: UUID, command: SignedReleaseCreate, session: SessionDependency, actor: CurrentUser):
    return checked(session, lambda: ReceiptReleaseService(session, actor).release(lot_id, command), commit=True)


@router.get("/lots/{lot_id}/decisions/{decision_id}/evidence")
def release_evidence(lot_id: UUID, decision_id: UUID, session: SessionDependency, actor: CurrentUser):
    def read():
        ReceiptReleaseService(session, actor).lot(lot_id)
        from mop.materials.receipt_models import MaterialReceiptDecision
        decision = session.get(MaterialReceiptDecision, decision_id)
        evidence = session.get(ReceiptReleaseEvidence, decision_id)
        if decision is None or decision.lot_id != lot_id or evidence is None:
            raise MaterialsNotFound("signed release evidence not found")
        key = session.get(ReceiptSignerKey, evidence.key_id)
        return {
            "public_key_base64": base64.b64encode(key.public_key).decode("ascii"),
            "signer_user_id": str(key.user_id),
            "key_revoked": session.get(ReceiptSignerRevocation, key.id) is not None,
            "decision_id": str(decision_id), "key_id": str(evidence.key_id),
            "policy_id": str(evidence.policy_id), "document_sha256": evidence.document_sha256,
            "document_base64": base64.b64encode(evidence.document).decode("ascii"),
            "signature_base64": base64.b64encode(evidence.signature).decode("ascii"),
            "payload": evidence.signed_payload.decode("utf-8"), "algorithm": "Ed25519",
        }
    return checked(session, read)
