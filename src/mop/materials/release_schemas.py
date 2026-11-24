"""Input and canonical encoding for receipt release signatures."""

import base64
import binascii
import hashlib
import json
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, field_validator

from mop.planning.governance_source_contracts import ReleaseAuthority

Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class SigningKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    public_key_base64: str = Field(min_length=44, max_length=44)
    identity_reference: Reference


class InspectionPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    engineering_defined: StrictBool
    responsible_area_id: UUID | None = None
    criteria: list[Reference] = Field(min_length=1, max_length=50)

    @field_validator("criteria")
    @classmethod
    def unique_criteria(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("inspection criteria must be unique")
        return values


class ReleasePreparation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_id: UUID
    key_id: UUID
    authority: ReleaseAuthority
    decision_ref: Reference
    expected_revision: int = Field(ge=0, strict=True)
    quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    checks: dict[Reference, StrictBool] = Field(min_length=1, max_length=50)
    document_base64: str = Field(min_length=4, max_length=1398104)

    @field_validator("quantity", mode="before")
    @classmethod
    def exact_quantity(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("quantity must be an exact decimal string or integer")
        return value


class SignedReleaseCreate(ReleasePreparation):
    signature_base64: str = Field(min_length=88, max_length=88)


def decode_bytes(value: str, *, maximum: int) -> bytes:
    try:
        result = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid base64 evidence") from exc
    if not result or len(result) > maximum:
        raise ValueError("evidence exceeds the permitted size")
    return result


def release_payload(lot_id: UUID, actor_id: UUID, command: ReleasePreparation) -> tuple[bytes, bytes]:
    """Exact UTF-8 bytes signed by the client's private Ed25519 key."""
    document = decode_bytes(command.document_base64, maximum=1048576)
    payload = {
        "protocol": "faic-mop.receipt-release.v1",
        "lot_id": str(lot_id), "actor_id": str(actor_id),
        "policy_id": str(command.policy_id), "key_id": str(command.key_id),
        "authority": command.authority.value, "decision_ref": command.decision_ref,
        "expected_revision": command.expected_revision, "quantity": format(command.quantity, ".8f"),
        "checks": command.checks, "document_sha256": hashlib.sha256(document).hexdigest(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"), document
