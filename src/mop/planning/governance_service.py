"""Internal transaction boundary for trusted G7.6 governance commands.

Callers own commit and must authenticate the actor, resolve the permitted role
at the case's plant, and verify evidence before using this service.
"""

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from json import dumps
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from mop.audit.models import AuditEntry
from mop.iam.models import User
from mop.planning.governance import (
    DecisionKind,
    ExceptionCase,
    GovernanceEvent,
    GovernanceProjection,
    GovernanceRole,
    replay_governance,
)
from mop.planning.governance_models import GovernanceCaseRecord, GovernanceEventRecord


class GovernanceConflict(ValueError):
    """The case revision or retry key conflicts with a committed command."""


class GovernanceCaseNotFound(LookupError):
    """There is no case with the specified identifier."""


_CASE = TypeAdapter(ExceptionCase)
_CASE_COLUMNS = frozenset({"case_id", "plant_id", "article_id", "uom_id", "creator_id", "created_at"})


class GovernanceService:
    def __init__(self, session: Session):
        self.session = session

    def submit(
        self, case: ExceptionCase, *, actor: User, role: GovernanceRole, reason: str,
        idempotency_key: str, request_id: str | None = None, source_ip: str | None = None,
    ) -> GovernanceProjection:
        """Persist the verified case and its first event in the same transaction."""
        return self._apply(
            case.case_id, DecisionKind.SUBMIT, actor=actor, role=role, reason=reason,
            expected_revision=0, idempotency_key=idempotency_key, evidence_refs=(),
            request_id=request_id, source_ip=source_ip, new_case=case,
        )

    def transition(
        self, case_id: UUID, kind: DecisionKind, *, actor: User, role: GovernanceRole,
        reason: str, expected_revision: int, idempotency_key: str,
        evidence_refs: tuple[str, ...] = (), request_id: str | None = None,
        source_ip: str | None = None,
    ) -> GovernanceProjection:
        if kind == DecisionKind.SUBMIT:
            raise ValueError("use submit to create and submit a case")
        return self._apply(
            case_id, kind, actor=actor, role=role, reason=reason,
            expected_revision=expected_revision, idempotency_key=idempotency_key,
            evidence_refs=evidence_refs, request_id=request_id, source_ip=source_ip,
        )

    def get(self, case_id: UUID) -> GovernanceProjection:
        record = self.session.get(GovernanceCaseRecord, case_id)
        if record is None:
            raise GovernanceCaseNotFound(case_id)
        return replay_governance(self._case(record), self._events(case_id))

    def _apply(
        self, case_id: UUID, kind: DecisionKind, *, actor: User, role: GovernanceRole,
        reason: str, expected_revision: int, idempotency_key: str,
        evidence_refs: tuple[str, ...], request_id: str | None, source_ip: str | None,
        new_case: ExceptionCase | None = None,
    ) -> GovernanceProjection:
        if not idempotency_key.strip() or len(idempotency_key) > 128:
            raise ValueError("idempotency key must contain 1 to 128 characters")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected revision must be a nonnegative integer")

        case_payload = _CASE.dump_python(new_case, mode="json") if new_case is not None else None
        if case_payload is not None:
            # The capture timestamp belongs to the first accepted submission.
            case_payload.pop("created_at")
        command = [str(case_id), kind, role, reason, expected_revision, evidence_refs, case_payload]
        digest = sha256(dumps(command, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

        with self.session.begin_nested():
            # Take locks in the same order for every command, even across cases.
            self._lock(f"actor:{actor.id}:{idempotency_key}")
            self._lock(f"case:{case_id}")
            existing = self.session.scalar(select(GovernanceEventRecord).where(
                GovernanceEventRecord.actor_id == actor.id,
                GovernanceEventRecord.idempotency_key == idempotency_key,
            ))
            if existing is not None:
                if existing.request_digest != digest:
                    raise GovernanceConflict("idempotency key already has a different command")
                record = self.session.get(GovernanceCaseRecord, case_id)
                return replay_governance(self._case(record), self._events(case_id, existing.revision))

            record = self.session.scalar(select(GovernanceCaseRecord).where(
                GovernanceCaseRecord.id == case_id,
            ).with_for_update())
            if new_case is not None:
                if record is not None:
                    raise GovernanceConflict("case already exists")
                case, events = new_case, ()
            else:
                if record is None:
                    raise GovernanceCaseNotFound(case_id)
                case, events = self._case(record), self._events(case_id)
            if len(events) != expected_revision:
                raise GovernanceConflict("case revision has changed")

            event = GovernanceEvent(
                case_id=case_id, revision=expected_revision + 1, kind=kind,
                actor_id=actor.id, actor_role=role, recorded_at=datetime.now(timezone.utc),
                reason=reason, evidence_refs=evidence_refs,
            )
            projection = replay_governance(case, (*events, event))
            if new_case is not None:
                self.session.add(GovernanceCaseRecord(
                    id=case_id, plant_id=case.plant_id, article_id=case.article_id,
                    uom_id=case.uom_id, creator_id=case.creator_id, created_at=case.created_at,
                    snapshot=_CASE.dump_python(case, mode="json", exclude=_CASE_COLUMNS),
                ))
            audit_id = uuid4()
            self.session.add(AuditEntry(
                id=audit_id, actor_user_id=actor.id, actor_username=actor.username,
                occurred_at=event.recorded_at, action=f"planning.governance.{kind.value.lower()}",
                object_type="GovernanceCase", object_id=str(case_id), outcome="success",
                scope_type="plant", scope_id=case.plant_id, request_id=request_id, source_ip=source_ip,
                details={"revision": event.revision, "status": projection.status,
                         "actor_role": role, "reason": reason, "evidence_refs": list(evidence_refs)},
            ))
            self.session.flush()
            values = asdict(event)
            values["evidence_refs"] = list(evidence_refs)
            self.session.add(GovernanceEventRecord(
                **values, idempotency_key=idempotency_key,
                request_digest=digest, audit_entry_id=audit_id,
            ))
            self.session.flush()
            return projection

    def _lock(self, key: str) -> None:
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": "mop.g7.governance:" + key},
        )

    @staticmethod
    def _case(record: GovernanceCaseRecord) -> ExceptionCase:
        return _CASE.validate_python({
            **record.snapshot, "case_id": record.id, "plant_id": record.plant_id,
            "article_id": record.article_id, "uom_id": record.uom_id,
            "creator_id": record.creator_id, "created_at": record.created_at,
        })

    def _events(self, case_id: UUID, through_revision: int | None = None) -> tuple[GovernanceEvent, ...]:
        query = select(GovernanceEventRecord).where(GovernanceEventRecord.case_id == case_id)
        if through_revision is not None:
            query = query.where(GovernanceEventRecord.revision <= through_revision)
        return tuple(
            GovernanceEvent(
                case_id=row.case_id, revision=row.revision, kind=DecisionKind(row.kind),
                actor_id=row.actor_id, actor_role=GovernanceRole(row.actor_role),
                recorded_at=row.recorded_at, reason=row.reason, evidence_refs=tuple(row.evidence_refs),
            )
            for row in self.session.scalars(query.order_by(GovernanceEventRecord.revision))
        )
