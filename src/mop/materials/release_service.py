"""Authenticated receipt release with detached Ed25519 signatures."""

from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from mop.audit.models import AuditEntry
from mop.core.models import Area
from mop.iam.authorization import AuthorizationService, PermissionDeniedError
from mop.iam.models import User
from mop.materials.models import MaterialLocation, MaterialWarehouse
from mop.materials.receipt_disposition import LotAction, LotBucket
from mop.materials.receipt_models import MaterialReceiptDecision, MaterialReceiptLot
from mop.materials.receipt_service import ReceiptService
from mop.materials.release_models import (
    ReceiptInspectionPolicy, ReceiptReleaseEvidence, ReceiptSignerKey, ReceiptSignerRevocation,
)
from mop.materials.release_schemas import decode_bytes, release_payload
from mop.materials.service import MaterialsConflict, MaterialsNotFound, MaterialsRule
from mop.planning.governance_source_contracts import ReleaseAuthority


class ReceiptReleaseService:
    def __init__(self, session: Session, actor: User):
        self.session = session
        self.actor = actor
        self.auth = AuthorizationService(session)
        self.receipts = ReceiptService(session)

    def lot(self, lot_id):
        lot = self.session.get(MaterialReceiptLot, lot_id)
        plant_id = self.session.scalar(
            select(MaterialWarehouse.plant_id)
            .join(MaterialLocation, MaterialLocation.warehouse_id == MaterialWarehouse.id)
            .where(MaterialLocation.id == lot.location_id)
        ) if lot is not None else None
        if lot is None or plant_id is None or not self.auth.allowed(
            self.actor.id, "materials.receipt.read", "plant", plant_id,
        ):
            raise MaterialsNotFound("receipt lot not found")
        return lot, plant_id

    def register_key(self, command):
        self.auth.require(self.actor.id, "admin.users")
        user = self.session.get(User, command.user_id)
        if user is None or not user.enabled:
            raise MaterialsRule("enabled signer identity is required")
        key_bytes = decode_bytes(command.public_key_base64, maximum=32)
        Ed25519PublicKey.from_public_bytes(key_bytes)
        key = ReceiptSignerKey(
            id=uuid4(), user_id=user.id, public_key=key_bytes,
            identity_reference=command.identity_reference, registered_by=self.actor.id,
            registered_at=datetime.now(timezone.utc),
        )
        self.session.add(key)
        self.audit("materials.signer.register", str(key.id), {"user_id": str(user.id)})
        self.session.flush()
        return key

    def revoke_key(self, key_id, reason):
        self.auth.require(self.actor.id, "admin.users")
        key = self.session.scalar(select(ReceiptSignerKey).where(
            ReceiptSignerKey.id == key_id,
        ).with_for_update())
        if key is None:
            raise MaterialsNotFound("signing key not found")
        existing = self.session.get(ReceiptSignerRevocation, key_id)
        if existing is not None:
            return existing
        record = ReceiptSignerRevocation(
            key_id=key_id, actor_id=self.actor.id, reason=reason,
            revoked_at=datetime.now(timezone.utc),
        )
        self.session.add(record)
        self.audit("materials.signer.revoke", str(key_id), {"reason": reason})
        self.session.flush()
        return record

    def latest_policy(self, lot_id):
        self.lot(lot_id)
        return self.session.scalar(select(ReceiptInspectionPolicy).where(
            ReceiptInspectionPolicy.lot_id == lot_id,
        ).order_by(ReceiptInspectionPolicy.revision.desc()).limit(1))

    def configure(self, lot_id, command):
        lot, plant_id = self.lot(lot_id)
        self.auth.require(self.actor.id, "materials.release.configure", "plant", plant_id)
        self.receipts.stock._advisory_lock(f"balance:{lot.article_id}:{lot.location_id}")
        current = self.latest_policy(lot_id)
        if (current.revision if current is not None else 0) != command.expected_revision:
            raise MaterialsConflict("inspection policy revision has changed")
        area = self.session.get(Area, command.responsible_area_id) if command.responsible_area_id else None
        if command.responsible_area_id is not None and (area is None or area.plant_id != plant_id):
            raise MaterialsRule("responsible area must belong to the receipt plant")
        if not command.engineering_defined and area is None:
            raise MaterialsRule("non-engineering material requires a responsible area")
        policy = ReceiptInspectionPolicy(
            id=uuid4(), lot_id=lot_id, revision=command.expected_revision + 1,
            engineering_defined=command.engineering_defined,
            responsible_area_id=command.responsible_area_id, criteria=command.criteria,
            configured_by=self.actor.id, configured_at=datetime.now(timezone.utc),
        )
        self.session.add(policy)
        self.audit("materials.inspection.configure", str(policy.id), {"lot_id": str(lot_id)}, plant_id)
        self.session.flush()
        return policy

    def _authority(self, policy, plant_id, authority):
        if policy.engineering_defined:
            if authority not in (ReleaseAuthority.ENGINEERING, ReleaseAuthority.LABORATORY):
                raise PermissionDeniedError("Engineering or Laboratory release required")
            capability = "engineering" if authority == ReleaseAuthority.ENGINEERING else "laboratory"
            self.auth.require(self.actor.id, f"materials.release.{capability}", "plant", plant_id)
        else:
            if authority != ReleaseAuthority.AREA_LEADER:
                raise PermissionDeniedError("responsible area leader release required")
            self.auth.require(self.actor.id, "materials.release.area", "area", policy.responsible_area_id)

    def prepare(self, lot_id, command):
        key = self.session.scalar(select(ReceiptSignerKey).where(
            ReceiptSignerKey.id == command.key_id,
        ).with_for_update())
        lot, plant_id = self.lot(lot_id)
        self.receipts.stock._advisory_lock(f"balance:{lot.article_id}:{lot.location_id}")
        policy = self.latest_policy(lot_id)
        if policy is None or policy.id != command.policy_id:
            raise MaterialsConflict("current inspection policy is required")
        self._authority(policy, plant_id, command.authority)
        if set(command.checks) != set(policy.criteria) or not all(command.checks.values()):
            raise MaterialsRule("every configured inspection criterion must pass")
        if key is None or key.user_id != self.actor.id:
            raise PermissionDeniedError("signing key must belong to the authenticated user")
        if self.session.get(ReceiptSignerRevocation, key.id) is not None:
            raise PermissionDeniedError("signing key is revoked")
        payload, document = release_payload(lot_id, self.actor.id, command)
        return lot, policy, key, payload, document, plant_id

    def release(self, lot_id, command):
        # Key lock precedes stock lock for consistency with key revocation.
        self.session.scalar(select(ReceiptSignerKey).where(
            ReceiptSignerKey.id == command.key_id,
        ).with_for_update())
        lot, plant_id = self.lot(lot_id)
        self.receipts.stock._advisory_lock(f"balance:{lot.article_id}:{lot.location_id}")
        payload, document = release_payload(lot_id, self.actor.id, command)
        existing = self.session.scalar(select(MaterialReceiptDecision).where(
            MaterialReceiptDecision.lot_id == lot_id,
            MaterialReceiptDecision.decision_ref == command.decision_ref,
        ))
        signature = decode_bytes(command.signature_base64, maximum=64)
        if existing is not None:
            evidence = self.session.get(ReceiptReleaseEvidence, existing.id)
            if evidence is None or evidence.signed_payload != payload or evidence.signature != signature:
                raise MaterialsConflict("release reference already has different signed evidence")
            return existing

        lot, policy, key, payload, document, plant_id = self.prepare(lot_id, command)
        try:
            Ed25519PublicKey.from_public_bytes(key.public_key).verify(signature, payload)
        except InvalidSignature as exc:
            raise MaterialsRule("release signature verification failed") from exc
        decision = self.receipts.decide(
            lot_id, action=LotAction.RELEASE, source=LotBucket.QUARANTINE,
            quantity=command.quantity, decision_ref=command.decision_ref,
            expected_revision=command.expected_revision, actor_id=self.actor.id,
            username=self.actor.username, verified_release_quantity=command.quantity,
        )
        self.session.add(ReceiptReleaseEvidence(
            decision_id=decision.id, policy_id=policy.id, key_id=key.id, document=document,
            document_sha256=sha256(document).hexdigest(), signature=signature, signed_payload=payload,
        ))
        self.audit("materials.release.signature_verified", str(decision.id), {
            "document_sha256": sha256(document).hexdigest(), "key_id": str(key.id),
            "policy_id": str(policy.id), "authority": command.authority.value,
        }, plant_id)
        self.session.flush()
        return decision

    def audit(self, action, object_id, details, plant_id=None):
        self.session.add(AuditEntry(
            actor_user_id=self.actor.id, actor_username=self.actor.username,
            action=action, object_type="ReceiptRelease", object_id=object_id, outcome="success",
            scope_type="plant" if plant_id is not None else "global", scope_id=plant_id,
            details=details,
        ))
