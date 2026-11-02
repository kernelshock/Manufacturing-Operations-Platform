"""G3 operational demand application service."""

from collections.abc import Sequence
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.demand.models import (
    ProductionPlan,
    Taquilla,
    TaquillaAssimilationBatch,
    TaquillaAssimilationDocument,
    TaquillaAssimilationIssue,
    TaquillaAssimilationLine,
    TaquillaProductLine,
)
from mop.master_data.models import Article, ArticleRevision, RoutingRevision
from mop.demand.schemas import (
    DemandCancellationRequest,
    HistoricalCompletionRequest,
    ProductionPlanCreate,
    ProductionPlanNumberUpdate,
    ProductionPlanStatusUpdate,
    RoutingOverrideRequest,
    RoutingResolveRequest,
    TaquillaAssimilationRequest,
    TaquillaAssimilationResult,
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
    "DRAFT": {"OPEN"},
    "OPEN": {"COMPLETED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}

_TAQUILLA_TRANSITIONS = {
    "DRAFT": {"READY"},
    "READY": {"COMPLETED"},
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
        if data.status == "COMPLETED":
            taquillas = list(self.list_taquillas(plan.id))
            if not taquillas:
                raise DemandRuleError("production plan cannot complete without taquillas")
            if any(item.status not in {"COMPLETED", "CANCELLED"} for item in taquillas):
                raise DemandRuleError("all taquillas must be completed or cancelled before plan completion")
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


    @staticmethod
    def _routing_window_contains(
        routing: RoutingRevision, effective_at: datetime
    ) -> bool:
        return (
            routing.valid_from <= effective_at
            and (routing.valid_to is None or effective_at < routing.valid_to)
        )

    def _routing_for_product_line(
        self,
        line: TaquillaProductLine,
        routing_revision_id: UUID,
        effective_at: datetime,
    ) -> RoutingRevision:
        routing = self.session.get(RoutingRevision, routing_revision_id)
        if routing is None:
            raise DemandNotFoundError("routing revision not found")
        revision = self.session.get(ArticleRevision, routing.article_revision_id)
        if revision is None:
            raise DemandNotFoundError("routing article revision not found")
        if revision.article_id != line.article_id:
            raise DemandRuleError(
                "routing revision does not belong to the product line article"
            )
        if routing.status != "ACTIVE":
            raise DemandRuleError("routing revision must be ACTIVE")
        if not self._routing_window_contains(routing, effective_at):
            raise DemandRuleError(
                "routing revision is not effective at the requested time"
            )
        return routing

    def _apply_routing_binding(
        self,
        line: TaquillaProductLine,
        routing: RoutingRevision,
        *,
        mode: str,
        effective_at: datetime,
        bound_by: UUID,
        override_reason: str | None,
    ) -> TaquillaProductLine:
        line.routing_revision_id = routing.id
        line.routing_binding_mode = mode
        line.routing_effective_at = effective_at
        line.routing_override_reason = override_reason
        line.routing_bound_at = datetime.now(timezone.utc)
        line.routing_bound_by = bound_by
        return self._commit(line)

    def resolve_product_line_routing(
        self,
        line_id: UUID,
        data: RoutingResolveRequest,
        *,
        bound_by: UUID,
    ) -> TaquillaProductLine:
        line = self.get_product_line(line_id)
        self._require_draft_taquilla(line.taquilla_id)
        at = data.effective_at or datetime.now(timezone.utc)

        candidates = []
        for routing, revision in self.session.execute(
            select(RoutingRevision, ArticleRevision)
            .join(
                ArticleRevision,
                RoutingRevision.article_revision_id == ArticleRevision.id,
            )
            .where(
                ArticleRevision.article_id == line.article_id,
                RoutingRevision.status == "ACTIVE",
            )
        ).all():
            if self._routing_window_contains(routing, at):
                candidates.append(routing)

        if not candidates:
            raise DemandNotFoundError(
                "effective routing revision for product line not found"
            )
        if len(candidates) > 1:
            raise DemandRuleError(
                "multiple effective active routing revisions found for product line"
            )

        return self._apply_routing_binding(
            line,
            candidates[0],
            mode="RESOLVED",
            effective_at=at,
            bound_by=bound_by,
            override_reason=None,
        )

    def override_product_line_routing(
        self,
        line_id: UUID,
        data: RoutingOverrideRequest,
        *,
        bound_by: UUID,
    ) -> TaquillaProductLine:
        line = self.get_product_line(line_id)
        self._require_draft_taquilla(line.taquilla_id)
        at = data.effective_at or datetime.now(timezone.utc)
        routing = self._routing_for_product_line(
            line, data.routing_revision_id, at
        )
        return self._apply_routing_binding(
            line,
            routing,
            mode="OVERRIDE",
            effective_at=at,
            bound_by=bound_by,
            override_reason=data.reason,
        )


    def historical_complete_plan(
        self,
        plan_id: UUID,
        data: HistoricalCompletionRequest,
        *,
        actor_id: UUID,
    ) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        if plan.status in {"COMPLETED", "CANCELLED"}:
            raise DemandRuleError(
                "historical completion requires a non-terminal production plan"
            )
        taquillas = list(self.list_taquillas(plan_id))
        if not taquillas:
            raise DemandRuleError(
                "historical completion requires at least one taquilla"
            )
        if any(item.status == "COMPLETED" for item in taquillas):
            raise DemandRuleError(
                "historical completion cannot overwrite an already completed taquilla"
            )

        at = datetime.now(timezone.utc)
        for item in taquillas:
            if item.status == "CANCELLED":
                continue
            item.status = "COMPLETED"
            item.historical_completion_classification = data.classification
            item.historical_completion_note = data.note
            item.historical_completed_at = at
            item.historical_completed_by = actor_id
            self.session.add(item)

        plan.status = "COMPLETED"
        plan.historical_completion_classification = data.classification
        plan.historical_completion_note = data.note
        plan.historical_completed_at = at
        plan.historical_completed_by = actor_id
        self.session.add(plan)
        try:
            self.session.commit()
            self.session.refresh(plan)
            return plan
        except IntegrityError as exc:
            self.session.rollback()
            raise DemandConflictError(
                "historical completion conflicts with demand state"
            ) from exc

    def cancel_taquilla(
        self,
        taquilla_id: UUID,
        data: DemandCancellationRequest,
        *,
        actor_id: UUID,
    ) -> Taquilla:
        taquilla = self.get_taquilla(taquilla_id)
        if taquilla.status in {"COMPLETED", "CANCELLED"}:
            raise DemandRuleError(
                "only a non-terminal taquilla can be cancelled"
            )
        taquilla.status = "CANCELLED"
        taquilla.cancellation_reason = data.reason
        taquilla.cancelled_at = datetime.now(timezone.utc)
        taquilla.cancelled_by = actor_id
        return self._commit(taquilla)

    def cancel_plan(
        self,
        plan_id: UUID,
        data: DemandCancellationRequest,
        *,
        actor_id: UUID,
    ) -> ProductionPlan:
        plan = self.get_plan(plan_id)
        if plan.status in {"COMPLETED", "CANCELLED"}:
            raise DemandRuleError(
                "only a non-terminal production plan can be cancelled"
            )
        taquillas = list(self.list_taquillas(plan_id))
        if any(item.status == "COMPLETED" for item in taquillas):
            raise DemandRuleError(
                "production plan with completed taquillas cannot be cancelled"
            )

        at = datetime.now(timezone.utc)
        for item in taquillas:
            if item.status == "CANCELLED":
                continue
            item.status = "CANCELLED"
            item.cancellation_reason = data.reason
            item.cancelled_at = at
            item.cancelled_by = actor_id
            self.session.add(item)

        plan.status = "CANCELLED"
        plan.cancellation_reason = data.reason
        plan.cancelled_at = at
        plan.cancelled_by = actor_id
        self.session.add(plan)
        try:
            self.session.commit()
            self.session.refresh(plan)
            return plan
        except IntegrityError as exc:
            self.session.rollback()
            raise DemandConflictError(
                "production plan cancellation conflicts with demand state"
            ) from exc

    def delete_draft_taquilla(self, taquilla_id: UUID) -> Taquilla:
        taquilla = self.get_taquilla(taquilla_id)
        plan = self.get_plan(taquilla.plan_id)
        if plan.status in {"COMPLETED", "CANCELLED"}:
            raise DemandRuleError(
                "cannot delete taquilla from a terminal production plan"
            )
        if taquilla.status != "DRAFT":
            raise DemandRuleError(
                "only a DRAFT taquilla can be hard-deleted"
            )
        has_lines = self.session.scalar(
            select(TaquillaProductLine.id)
            .where(TaquillaProductLine.taquilla_id == taquilla.id)
            .limit(1)
        )
        if has_lines is not None:
            raise DemandRuleError(
                "taquilla with dependent product composition must be cancelled, not deleted"
            )
        self.session.delete(taquilla)
        self.session.commit()
        return taquilla


    @staticmethod
    def _assimilation_fingerprint(
        data: TaquillaAssimilationRequest,
    ) -> str:
        canonical = json.dumps(
            data.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def list_assimilation_batches(
        self,
        status: str | None = None,
    ) -> Sequence[TaquillaAssimilationBatch]:
        query = select(TaquillaAssimilationBatch)
        if status is not None:
            query = query.where(TaquillaAssimilationBatch.status == status)
        return self.session.scalars(
            query.order_by(
                TaquillaAssimilationBatch.imported_at.desc(),
                TaquillaAssimilationBatch.id,
            )
        ).all()

    def list_assimilation_issues(
        self,
        batch_id: UUID,
    ) -> Sequence[TaquillaAssimilationIssue]:
        if self.session.get(TaquillaAssimilationBatch, batch_id) is None:
            raise DemandNotFoundError("assimilation batch not found")
        return self.session.scalars(
            select(TaquillaAssimilationIssue)
            .where(TaquillaAssimilationIssue.batch_id == batch_id)
            .order_by(
                TaquillaAssimilationIssue.created_at,
                TaquillaAssimilationIssue.id,
            )
        ).all()

    def _assimilation_result(
        self,
        batch: TaquillaAssimilationBatch,
        *,
        idempotent_replay: bool,
    ) -> TaquillaAssimilationResult:
        issues = list(self.list_assimilation_issues(batch.id))
        return TaquillaAssimilationResult(
            batch=batch,
            issues=issues,
            target_taquilla_id=batch.target_taquilla_id,
            idempotent_replay=idempotent_replay,
        )

    def import_taquilla(
        self,
        data: TaquillaAssimilationRequest,
        *,
        imported_by: UUID,
    ) -> TaquillaAssimilationResult:
        fingerprint = self._assimilation_fingerprint(data)
        source_system = data.source_system.strip().upper()

        existing = self.session.scalar(
            select(TaquillaAssimilationBatch).where(
                TaquillaAssimilationBatch.source_system == source_system,
                TaquillaAssimilationBatch.payload_fingerprint == fingerprint,
                TaquillaAssimilationBatch.parser_version
                == data.parser_version,
            )
        )
        if existing is not None:
            return self._assimilation_result(
                existing,
                idempotent_replay=True,
            )

        plan = self.get_plan(data.plan_id)
        if plan.status in {"COMPLETED", "CANCELLED"}:
            raise DemandRuleError(
                "cannot assimilate a taquilla into a terminal production plan"
            )

        batch = TaquillaAssimilationBatch(
            plan_id=plan.id,
            source_system=source_system,
            parser_version=data.parser_version,
            mapping_version=data.mapping_version,
            payload_fingerprint=fingerprint,
            taquilla_code=data.taquilla_code,
            sequence_no=data.sequence_no,
            vehicle_topology=data.vehicle_topology,
            status="RECEIVED",
            accepted_lines=0,
            rejected_lines=0,
            imported_by=imported_by,
        )
        self.session.add(batch)
        self.session.flush()

        document_by_key: dict[str, TaquillaAssimilationDocument] = {}
        issues: list[TaquillaAssimilationIssue] = []

        for source_document in data.documents:
            document = TaquillaAssimilationDocument(
                batch_id=batch.id,
                source_document_key=source_document.source_document_key,
                source_filename=source_document.filename,
                source_sha256=source_document.sha256,
                exported_at=source_document.exported_at,
            )
            self.session.add(document)
            self.session.flush()
            document_by_key[source_document.source_document_key] = document

            prior_document = self.session.scalar(
                select(TaquillaAssimilationDocument)
                .join(
                    TaquillaAssimilationBatch,
                    TaquillaAssimilationDocument.batch_id
                    == TaquillaAssimilationBatch.id,
                )
                .where(
                    TaquillaAssimilationDocument.source_sha256
                    == source_document.sha256,
                    TaquillaAssimilationBatch.source_system == source_system,
                    TaquillaAssimilationBatch.id != batch.id,
                )
                .limit(1)
            )
            if prior_document is not None:
                issues.append(
                    TaquillaAssimilationIssue(
                        batch_id=batch.id,
                        rule_code="TAQ_SOURCE_DOCUMENT_REUSED",
                        severity="BLOCKER",
                        message=(
                            "source document already belongs to another "
                            "assimilation batch"
                        ),
                        source_document_key=source_document.source_document_key,
                    )
                )

        duplicate_code = self.session.scalar(
            select(Taquilla).where(
                Taquilla.taquilla_code == data.taquilla_code
            )
        )
        if duplicate_code is not None:
            issues.append(
                TaquillaAssimilationIssue(
                    batch_id=batch.id,
                    rule_code="TAQ_DUPLICATE_CODE",
                    severity="BLOCKER",
                    message="taquilla code already exists",
                )
            )

        duplicate_sequence = self.session.scalar(
            select(Taquilla).where(
                Taquilla.plan_id == plan.id,
                Taquilla.sequence_no == data.sequence_no,
            )
        )
        if duplicate_sequence is not None:
            issues.append(
                TaquillaAssimilationIssue(
                    batch_id=batch.id,
                    rule_code="TAQ_DUPLICATE_PLAN_SEQUENCE",
                    severity="BLOCKER",
                    message="taquilla sequence already exists in production plan",
                )
            )

        staged_lines: list[TaquillaAssimilationLine] = []
        accepted_lines = 0
        rejected_lines = 0

        for source_line in data.lines:
            article_system = (
                source_line.article_source_system or source_system
            ).strip().upper()
            article = self.session.scalar(
                select(Article).where(
                    Article.external_system == article_system,
                    Article.external_code == source_line.article_code,
                )
            )

            line_issue: TaquillaAssimilationIssue | None = None
            if article is None:
                line_issue = TaquillaAssimilationIssue(
                    batch_id=batch.id,
                    rule_code="TAQ_PRODUCT_UNMAPPED",
                    severity="BLOCKER",
                    message=(
                        "source product does not resolve to an exact G2 Article"
                    ),
                    source_document_key=source_line.source_document_key,
                    source_line_key=source_line.source_line_key,
                )
            elif article.article_kind != "FINISHED_PRODUCT" or not article.active:
                line_issue = TaquillaAssimilationIssue(
                    batch_id=batch.id,
                    rule_code="TAQ_PRODUCT_NOT_ACTIVE_FINISHED",
                    severity="BLOCKER",
                    message=(
                        "resolved Article must be active FINISHED_PRODUCT"
                    ),
                    source_document_key=source_line.source_document_key,
                    source_line_key=source_line.source_line_key,
                )

            staged = TaquillaAssimilationLine(
                batch_id=batch.id,
                document_id=document_by_key[
                    source_line.source_document_key
                ].id,
                source_line_key=source_line.source_line_key,
                source_article_system=article_system,
                source_article_code=source_line.article_code,
                resolved_article_id=article.id if article is not None else None,
                requested_quantity=source_line.requested_quantity,
                deck_position=source_line.deck_position,
            )
            self.session.add(staged)
            staged_lines.append(staged)

            if line_issue is None:
                accepted_lines += 1
            else:
                rejected_lines += 1
                issues.append(line_issue)

        batch.accepted_lines = accepted_lines
        batch.rejected_lines = rejected_lines
        batch.status = (
            "REVIEW_REQUIRED"
            if any(issue.severity == "BLOCKER" for issue in issues)
            else "VALIDATED"
        )
        self.session.add_all(issues)
        self.session.add(batch)
        try:
            self.session.commit()
            self.session.refresh(batch)
        except IntegrityError as exc:
            self.session.rollback()
            raise DemandConflictError(
                "assimilation staging conflicts with existing source evidence"
            ) from exc

        if batch.status != "VALIDATED":
            return self._assimilation_result(
                batch,
                idempotent_replay=False,
            )

        try:
            target = Taquilla(
                plan_id=plan.id,
                taquilla_code=data.taquilla_code,
                sequence_no=data.sequence_no,
                description=None,
                vehicle_topology=data.vehicle_topology,
                status="DRAFT",
            )
            self.session.add(target)
            self.session.flush()

            reloaded_lines = self.session.scalars(
                select(TaquillaAssimilationLine)
                .where(TaquillaAssimilationLine.batch_id == batch.id)
                .order_by(TaquillaAssimilationLine.id)
            ).all()
            line_by_source_key = {
                line.source_line_key: line for line in reloaded_lines
            }

            for sequence_no, source_line in enumerate(data.lines, start=1):
                staged = line_by_source_key[source_line.source_line_key]
                product_line = TaquillaProductLine(
                    taquilla_id=target.id,
                    article_id=staged.resolved_article_id,
                    sequence_no=sequence_no,
                    requested_quantity=staged.requested_quantity,
                    source_line_key=staged.source_line_key,
                    deck_position=staged.deck_position,
                    source_document_key=source_line.source_document_key,
                )
                self.session.add(product_line)
                self.session.flush()
                staged.target_product_line_id = product_line.id
                self.session.add(staged)

            batch.target_taquilla_id = target.id
            batch.status = "APPLIED"
            self.session.add(batch)
            self.session.commit()
            self.session.refresh(batch)
        except IntegrityError:
            self.session.rollback()
            batch = self.session.get(TaquillaAssimilationBatch, batch.id)
            if batch is None:
                raise DemandConflictError(
                    "assimilation batch disappeared during apply"
                )
            batch.status = "REVIEW_REQUIRED"
            self.session.add(
                TaquillaAssimilationIssue(
                    batch_id=batch.id,
                    rule_code="TAQ_APPLY_CONFLICT",
                    severity="BLOCKER",
                    message=(
                        "validated source could not be applied because target "
                        "demand now conflicts with another record"
                    ),
                )
            )
            self.session.add(batch)
            self.session.commit()
            self.session.refresh(batch)

        return self._assimilation_result(
            batch,
            idempotent_replay=False,
        )
