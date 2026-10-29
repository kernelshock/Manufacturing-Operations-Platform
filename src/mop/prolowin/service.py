"""Prolowin staging, normalization, canonical assimilation and reconciliation."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.master_data.models import (
    Article,
    ArticleRevision,
    BOMComponent,
    BOMRevision,
    UnitOfMeasureAlias,
)
from mop.prolowin.models import (
    DataQualityIssue,
    ImportBatch,
    ProlowinCompleteSnapshot,
    ProlowinDirectRelation,
    ProlowinFlatRequirement,
    ProlowinStructureRow,
    ReconciliationItem,
    ReconciliationRun,
    SourceOperationState,
)
from mop.prolowin.schemas import (
    CompleteImportResult,
    DataQualityIssueRead,
    DirectImportResult,
    FlatRequirementRead,
    ImportBatchRead,
    NormalizedProjectionRead,
    ProlowinCompleteStructureImport,
    ProlowinDirectStructureImport,
    ReconciliationItemRead,
    ReconciliationRequest,
    ReconciliationResult,
    ReconciliationRunRead,
    SourceOperationStateRead,
)


KNOWN_OPERATION_CODES = {"010", "020", "025", "030", "040", "050", "FIN"}
MAPPING_VERSION = "g2.7-v1"


class ProlowinConflictError(ValueError):
    pass


class ProlowinRuleError(ValueError):
    pass


class ProlowinNotFoundError(LookupError):
    pass


class ProlowinService:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _sha256(payload: object) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _decimal_text(value: Decimal) -> str:
        return format(value, "f")

    def _existing_batch(
        self,
        source_system: str,
        source_sha256: str,
        parser_version: str,
    ) -> ImportBatch | None:
        return self.session.scalar(
            select(ImportBatch).where(
                ImportBatch.source_system == source_system,
                ImportBatch.source_sha256 == source_sha256,
                ImportBatch.parser_version == parser_version,
            )
        )

    def _new_batch(
        self,
        *,
        source_type: str,
        filename: str,
        source_sha256: str,
        exported_at: datetime | None,
        parser_version: str,
        imported_by: UUID | None,
    ) -> ImportBatch:
        batch = ImportBatch(
            source_system="PROLOWIN",
            source_type=source_type,
            source_filename=filename,
            source_sha256=source_sha256,
            exported_at=exported_at,
            parser_version=parser_version,
            mapping_version=MAPPING_VERSION,
            imported_by=imported_by,
            status="RECEIVED",
            accepted_rows=0,
            rejected_rows=0,
        )
        self.session.add(batch)
        self.session.flush()
        return batch

    def _issue(
        self,
        *,
        batch_id: UUID,
        entity_type: str,
        entity_key: str,
        rule_code: str,
        severity: str,
        message: str,
        source_row_id: UUID | None = None,
        source_value: str | None = None,
        suggested_action: str | None = None,
    ) -> DataQualityIssue:
        issue = DataQualityIssue(
            batch_id=batch_id,
            entity_type=entity_type,
            entity_key=entity_key,
            rule_code=rule_code,
            severity=severity,
            message=message,
            source_row_id=source_row_id,
            source_value=source_value,
            suggested_action=suggested_action,
            status="OPEN",
        )
        self.session.add(issue)
        return issue

    def _issues(self, batch_id: UUID) -> list[DataQualityIssue]:
        return list(
            self.session.scalars(
                select(DataQualityIssue)
                .where(DataQualityIssue.batch_id == batch_id)
                .order_by(
                    DataQualityIssue.severity.desc(),
                    DataQualityIssue.rule_code,
                    DataQualityIssue.entity_key,
                    DataQualityIssue.created_at,
                )
            ).all()
        )

    @staticmethod
    def _has_blocker(issues: list[DataQualityIssue]) -> bool:
        return any(
            issue.severity == "BLOCKER" and issue.status == "OPEN"
            for issue in issues
        )

    def _get_batch(self, batch_id: UUID) -> ImportBatch:
        batch = self.session.get(ImportBatch, batch_id)
        if batch is None:
            raise ProlowinNotFoundError("import batch not found")
        return batch

    def list_batches(
        self,
        source_type: str | None = None,
        status: str | None = None,
    ) -> list[ImportBatch]:
        query = select(ImportBatch)
        if source_type:
            query = query.where(ImportBatch.source_type == source_type)
        if status:
            query = query.where(ImportBatch.status == status)
        return list(
            self.session.scalars(
                query.order_by(ImportBatch.imported_at.desc())
            ).all()
        )

    def list_issues(
        self,
        batch_id: UUID,
        severity: str | None = None,
        status: str | None = None,
    ) -> list[DataQualityIssue]:
        self._get_batch(batch_id)
        query = select(DataQualityIssue).where(
            DataQualityIssue.batch_id == batch_id
        )
        if severity:
            query = query.where(DataQualityIssue.severity == severity)
        if status:
            query = query.where(DataQualityIssue.status == status)
        return list(
            self.session.scalars(
                query.order_by(
                    DataQualityIssue.created_at,
                    DataQualityIssue.rule_code,
                )
            ).all()
        )

    def _find_uom_alias(self, raw_value: str) -> UnitOfMeasureAlias | None:
        return self.session.scalar(
            select(UnitOfMeasureAlias).where(
                UnitOfMeasureAlias.source_system == "PROLOWIN",
                UnitOfMeasureAlias.raw_value == raw_value,
            )
        )

    def _ensure_uom_alias(
        self,
        *,
        batch_id: UUID,
        raw_value: str,
        entity_key: str,
    ) -> UnitOfMeasureAlias:
        alias = self._find_uom_alias(raw_value)
        if alias is None:
            alias = UnitOfMeasureAlias(
                source_system="PROLOWIN",
                raw_value=raw_value,
                uom_id=None,
                mapping_status="UNMAPPED",
                conversion_factor=None,
                approved_at=None,
                approved_by=None,
            )
            self.session.add(alias)
            self.session.flush()

        if alias.mapping_status != "MAPPED" or alias.uom_id is None:
            self._issue(
                batch_id=batch_id,
                entity_type="uom",
                entity_key=entity_key,
                rule_code="PLW_UOM_UNMAPPED",
                severity="WARNING",
                message=f"Prolowin UoM '{raw_value}' has no approved canonical mapping",
                source_value=raw_value,
                suggested_action="Map the raw UoM through the governed UoM alias table.",
            )
        return alias

    def _upsert_article(
        self,
        *,
        batch_id: UUID,
        code: str,
        description: str,
    ) -> Article:
        article = self.session.scalar(
            select(Article).where(
                Article.external_system == "PROLOWIN",
                Article.external_code == code,
            )
        )
        now = datetime.now(timezone.utc)
        if article is None:
            article = Article(
                external_system="PROLOWIN",
                external_code=code,
                canonical_description=description,
                article_kind="UNKNOWN",
                default_uom_id=None,
                active=True,
            )
            self.session.add(article)
            self.session.flush()
        else:
            article.last_seen_at = now
            if (
                description.strip()
                and article.canonical_description.strip()
                and article.canonical_description.strip() != description.strip()
            ):
                self._issue(
                    batch_id=batch_id,
                    entity_type="article",
                    entity_key=code,
                    rule_code="PLW_DESCRIPTION_CONFLICT",
                    severity="WARNING",
                    message="Source description differs from existing canonical description",
                    source_value=description,
                    suggested_action="Review the description without silently overwriting canonical text.",
                )

        if article.article_kind == "UNKNOWN":
            self._issue(
                batch_id=batch_id,
                entity_type="article",
                entity_key=code,
                rule_code="PLW_ARTICLE_KIND_UNKNOWN",
                severity="WARNING",
                message="Article kind remains UNKNOWN",
                suggested_action="Classify from approved source structure or mapping; do not infer from code prefix.",
            )
        return article

    @staticmethod
    def _complete_row_payload(row) -> dict:
        return {
            "row_no": row.row_no,
            "page": row.page,
            "article_code": row.article_code,
            "operation_code": row.operation_code,
            "description_raw": row.description_raw,
            "quantity": ProlowinService._decimal_text(row.quantity),
            "uom_raw": row.uom_raw,
        }

    def _complete_result(
        self,
        batch: ImportBatch,
        *,
        idempotent_replay: bool,
    ) -> CompleteImportResult:
        snapshot = self.session.scalar(
            select(ProlowinCompleteSnapshot).where(
                ProlowinCompleteSnapshot.batch_id == batch.id
            )
        )
        root_revision_id = None
        flat_count = 0
        operation_count = 0
        if snapshot is not None:
            flat_count = self.session.scalar(
                select(func.count(ProlowinFlatRequirement.id)).where(
                    ProlowinFlatRequirement.snapshot_id == snapshot.id
                )
            ) or 0
            operation_count = self.session.scalar(
                select(func.count(SourceOperationState.id)).where(
                    SourceOperationState.snapshot_id == snapshot.id
                )
            ) or 0
            root_article = self.session.scalar(
                select(Article).where(
                    Article.external_system == "PROLOWIN",
                    Article.external_code == snapshot.root_article_code,
                )
            )
            if root_article is not None:
                root_revision = self.session.scalar(
                    select(ArticleRevision).where(
                        ArticleRevision.article_id == root_article.id,
                        ArticleRevision.source_fingerprint
                        == snapshot.normalized_fingerprint,
                    )
                )
                if root_revision is not None:
                    root_revision_id = root_revision.id

        return CompleteImportResult(
            batch=ImportBatchRead.model_validate(batch),
            root_article_revision_id=root_revision_id,
            snapshot_id=snapshot.id if snapshot is not None else None,
            flat_requirements=int(flat_count),
            operation_states=int(operation_count),
            data_quality_issues=[
                DataQualityIssueRead.model_validate(issue)
                for issue in self._issues(batch.id)
            ],
            idempotent_replay=idempotent_replay,
        )

    def import_complete_structure(
        self,
        payload: ProlowinCompleteStructureImport,
        *,
        imported_by: UUID | None,
    ) -> CompleteImportResult:
        existing = self._existing_batch(
            payload.source_system,
            payload.source.sha256,
            payload.source.parser_version,
        )
        if existing is not None:
            if existing.source_type != "COMPLETE_ARTICLE_STRUCTURE":
                raise ProlowinConflictError(
                    "import identity already exists with a different source type"
                )
            return self._complete_result(
                existing, idempotent_replay=True
            )

        batch = self._new_batch(
            source_type="COMPLETE_ARTICLE_STRUCTURE",
            filename=payload.source.filename,
            source_sha256=payload.source.sha256,
            exported_at=payload.source.exported_at,
            parser_version=payload.source.parser_version,
            imported_by=imported_by,
        )

        staged_rows: list[ProlowinStructureRow] = []
        for row in payload.rows:
            raw_payload = self._complete_row_payload(row)
            row_hash = row.row_hash or self._sha256(raw_payload)
            staged = ProlowinStructureRow(
                batch_id=batch.id,
                root_article_code=payload.root_article.code,
                source_page=row.page,
                source_row_no=row.row_no,
                article_code=row.article_code,
                operation_code=row.operation_code,
                description_raw=row.description_raw,
                quantity=row.quantity,
                uom_raw=row.uom_raw,
                raw_payload=raw_payload,
                row_hash=row_hash,
            )
            self.session.add(staged)
            staged_rows.append(staged)

        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ProlowinConflictError(
                "duplicate source row identity in Prolowin batch"
            ) from exc

        batch.status = "PARSED"

        by_code: dict[str, list[ProlowinStructureRow]] = defaultdict(list)
        for row in staged_rows:
            by_code[row.article_code].append(row)

        for code, rows in by_code.items():
            fin_rows = [
                row for row in rows if row.operation_code == "FIN"
            ]
            if not fin_rows:
                self._issue(
                    batch_id=batch.id,
                    entity_type="article",
                    entity_key=code,
                    rule_code="PLW_FIN_MISSING",
                    severity="BLOCKER",
                    message="Complete-structure report requires exactly one FIN row per article code",
                    suggested_action="Correct parser/source extraction and re-import.",
                )
            elif len(fin_rows) > 1:
                for fin_row in fin_rows:
                    self._issue(
                        batch_id=batch.id,
                        entity_type="article",
                        entity_key=code,
                        rule_code="PLW_FIN_DUPLICATE",
                        severity="BLOCKER",
                        message="Multiple FIN rows found for one article code",
                        source_row_id=fin_row.id,
                        suggested_action="Correct parser/source extraction and re-import.",
                    )

            descriptions = {
                row.description_raw.strip()
                for row in rows
                if row.description_raw.strip()
            }
            if len(descriptions) > 1:
                self._issue(
                    batch_id=batch.id,
                    entity_type="article",
                    entity_key=code,
                    rule_code="PLW_DESCRIPTION_CONFLICT",
                    severity="WARNING",
                    message="Multiple source descriptions found for one article code",
                    source_value=" | ".join(sorted(descriptions)),
                    suggested_action="Review description provenance before changing canonical text.",
                )

            if len(fin_rows) == 1:
                fin_quantity = fin_rows[0].quantity
                for row in rows:
                    if (
                        row.operation_code != "FIN"
                        and row.quantity != fin_quantity
                    ):
                        self._issue(
                            batch_id=batch.id,
                            entity_type="operation_state",
                            entity_key=f"{code}:{row.operation_code}",
                            rule_code="PLW_OPERATION_QTY_DIFF",
                            severity="WARNING",
                            message="Non-FIN operation quantity differs from FIN projection quantity",
                            source_row_id=row.id,
                            source_value=self._decimal_text(row.quantity),
                            suggested_action="Review as routing evidence; do not add operation quantity to material demand.",
                        )

            for row in rows:
                if row.operation_code not in KNOWN_OPERATION_CODES:
                    self._issue(
                        batch_id=batch.id,
                        entity_type="operation_state",
                        entity_key=f"{code}:{row.operation_code}",
                        rule_code="PLW_OPERATION_SEQUENCE_UNKNOWN",
                        severity="WARNING",
                        message="Unknown Prolowin operation code",
                        source_row_id=row.id,
                        source_value=row.operation_code,
                        suggested_action="Map operation code before using it for routing reconstruction.",
                    )

        root_fin = [
            row
            for row in by_code.get(payload.root_article.code, [])
            if row.operation_code == "FIN"
        ]
        if len(root_fin) != 1:
            self._issue(
                batch_id=batch.id,
                entity_type="root_article",
                entity_key=payload.root_article.code,
                rule_code="PLW_ROOT_NOT_IDENTIFIED",
                severity="BLOCKER",
                message="Exactly one root FIN row is required",
                suggested_action="Verify root article code and complete-report extraction.",
            )

        self.session.flush()
        current_issues = self._issues(batch.id)
        if self._has_blocker(current_issues):
            batch.status = "REJECTED"
            batch.accepted_rows = 0
            batch.rejected_rows = len(staged_rows)
            self.session.commit()
            self.session.refresh(batch)
            return self._complete_result(
                batch, idempotent_replay=False
            )

        batch.status = "VALIDATED"

        normalized_payload = [
            {
                "article_code": row.article_code,
                "operation_code": row.operation_code,
                "description_raw": row.description_raw,
                "quantity": self._decimal_text(row.quantity),
                "uom_raw": row.uom_raw,
            }
            for row in sorted(
                staged_rows,
                key=lambda item: (
                    item.article_code,
                    item.operation_code,
                    item.source_row_no,
                ),
            )
        ]
        fingerprint = self._sha256(
            {
                "schema_version": payload.schema_version,
                "report_type": payload.report_type,
                "root_article_code": payload.root_article.code,
                "rows": normalized_payload,
            }
        )

        snapshot = ProlowinCompleteSnapshot(
            batch_id=batch.id,
            root_article_code=payload.root_article.code,
            root_quantity=payload.root_article.quantity,
            root_uom_raw=payload.root_article.uom_raw,
            report_timestamp=payload.source.exported_at,
            source_sha256=payload.source.sha256,
            normalized_fingerprint=fingerprint,
        )
        self.session.add(snapshot)
        self.session.flush()

        descriptions_by_code: dict[str, str] = {}
        for code, rows in by_code.items():
            fin = next(
                row for row in rows if row.operation_code == "FIN"
            )
            descriptions_by_code[code] = fin.description_raw
            self.session.add(
                ProlowinFlatRequirement(
                    snapshot_id=snapshot.id,
                    article_code=code,
                    quantity=fin.quantity,
                    uom_raw=fin.uom_raw,
                    source_fin_row_id=fin.id,
                    is_root=(code == payload.root_article.code),
                )
            )
            for row in rows:
                if row.operation_code != "FIN":
                    self.session.add(
                        SourceOperationState(
                            snapshot_id=snapshot.id,
                            article_code=code,
                            source_operation_code=row.operation_code,
                            source_description=row.description_raw,
                            quantity=row.quantity,
                            uom_raw=row.uom_raw,
                            source_row_id=row.id,
                        )
                    )

        seen_uoms = sorted({row.uom_raw for row in staged_rows})
        for raw_uom in seen_uoms:
            self._ensure_uom_alias(
                batch_id=batch.id,
                raw_value=raw_uom,
                entity_key=raw_uom,
            )

        articles: dict[str, Article] = {}
        for code in sorted(by_code):
            articles[code] = self._upsert_article(
                batch_id=batch.id,
                code=code,
                description=descriptions_by_code[code],
            )

        root_article = articles[payload.root_article.code]
        root_revision = self.session.scalar(
            select(ArticleRevision).where(
                ArticleRevision.article_id == root_article.id,
                ArticleRevision.source_fingerprint == fingerprint,
            )
        )
        if root_revision is None:
            root_revision = ArticleRevision(
                article_id=root_article.id,
                revision_label=None,
                source_fingerprint=fingerprint,
                valid_from=payload.source.exported_at
                or datetime.now(timezone.utc),
                valid_to=None,
                status="DRAFT",
                source_batch_id=batch.id,
                approved_at=None,
                approved_by=None,
            )
            self.session.add(root_revision)

        batch.status = "APPLIED"
        batch.accepted_rows = len(staged_rows)
        batch.rejected_rows = 0

        try:
            self.session.commit()
            self.session.refresh(batch)
        except IntegrityError as exc:
            self.session.rollback()
            raise ProlowinConflictError(
                "Prolowin complete-structure canonical application conflicted with existing data"
            ) from exc

        return self._complete_result(
            batch, idempotent_replay=False
        )

    def get_normalized_projection(
        self, batch_id: UUID
    ) -> NormalizedProjectionRead:
        batch = self._get_batch(batch_id)
        if batch.source_type != "COMPLETE_ARTICLE_STRUCTURE":
            raise ProlowinRuleError(
                "normalized FIN projection is available only for complete-structure batches"
            )
        snapshot = self.session.scalar(
            select(ProlowinCompleteSnapshot).where(
                ProlowinCompleteSnapshot.batch_id == batch_id
            )
        )
        if snapshot is None:
            raise ProlowinNotFoundError(
                "normalized projection not available for rejected/unapplied batch"
            )

        flat = list(
            self.session.scalars(
                select(ProlowinFlatRequirement)
                .where(ProlowinFlatRequirement.snapshot_id == snapshot.id)
                .order_by(ProlowinFlatRequirement.article_code)
            ).all()
        )
        operations = list(
            self.session.scalars(
                select(SourceOperationState)
                .where(SourceOperationState.snapshot_id == snapshot.id)
                .order_by(
                    SourceOperationState.article_code,
                    SourceOperationState.source_operation_code,
                    SourceOperationState.source_row_id,
                )
            ).all()
        )
        return NormalizedProjectionRead(
            flat_requirements=[
                FlatRequirementRead.model_validate(item) for item in flat
            ],
            operation_states=[
                SourceOperationStateRead.model_validate(item)
                for item in operations
            ],
        )

    @staticmethod
    def _direct_row_payload(row) -> dict:
        return {
            "row_no": row.row_no,
            "sequence_no": row.sequence_no,
            "parent_article_code": row.parent_article_code,
            "parent_description_raw": row.parent_description_raw,
            "child_article_code": row.child_article_code,
            "child_description_raw": row.child_description_raw,
            "quantity": ProlowinService._decimal_text(row.quantity),
            "uom_raw": row.uom_raw,
            "source_relation_key": row.source_relation_key,
        }

    def _direct_result(
        self,
        batch: ImportBatch,
        *,
        idempotent_replay: bool,
    ) -> DirectImportResult:
        revisions = list(
            self.session.scalars(
                select(ArticleRevision).where(
                    ArticleRevision.source_batch_id == batch.id
                )
            ).all()
        )
        boms = list(
            self.session.scalars(
                select(BOMRevision).where(
                    BOMRevision.source_batch_id == batch.id
                )
            ).all()
        )
        return DirectImportResult(
            batch=ImportBatchRead.model_validate(batch),
            candidate_article_revision_ids=[
                item.id for item in revisions
            ],
            candidate_bom_revision_ids=[item.id for item in boms],
            data_quality_issues=[
                DataQualityIssueRead.model_validate(issue)
                for issue in self._issues(batch.id)
            ],
            idempotent_replay=idempotent_replay,
        )

    def import_direct_structure(
        self,
        payload: ProlowinDirectStructureImport,
        *,
        imported_by: UUID | None,
    ) -> DirectImportResult:
        existing = self._existing_batch(
            payload.source_system,
            payload.source.sha256,
            payload.source.parser_version,
        )
        if existing is not None:
            if existing.source_type != "DIRECT_ARTICLE_STRUCTURE":
                raise ProlowinConflictError(
                    "import identity already exists with a different source type"
                )
            return self._direct_result(
                existing, idempotent_replay=True
            )

        batch = self._new_batch(
            source_type="DIRECT_ARTICLE_STRUCTURE",
            filename=payload.source.filename,
            source_sha256=payload.source.sha256,
            exported_at=payload.source.exported_at,
            parser_version=payload.source.parser_version,
            imported_by=imported_by,
        )

        staged: list[ProlowinDirectRelation] = []
        normalized_keys: set[str] = set()
        for relation in payload.relations:
            raw_payload = self._direct_row_payload(relation)
            row_hash = relation.row_hash or self._sha256(raw_payload)
            relation_key = relation.source_relation_key or self._sha256(
                {
                    "parent": relation.parent_article_code,
                    "child": relation.child_article_code,
                    "quantity": self._decimal_text(relation.quantity),
                    "uom_raw": relation.uom_raw,
                    "sequence_no": relation.sequence_no,
                }
            )
            if relation_key in normalized_keys:
                self._issue(
                    batch_id=batch.id,
                    entity_type="direct_relation",
                    entity_key=relation_key,
                    rule_code="PLW_DIRECT_RELATION_DUPLICATE",
                    severity="BLOCKER",
                    message="Duplicate normalized direct parent-child relation",
                    source_value=relation_key,
                    suggested_action="Remove duplicate source relation before canonical application.",
                )
            normalized_keys.add(relation_key)

            item = ProlowinDirectRelation(
                batch_id=batch.id,
                root_article_code=payload.root_article_code,
                source_row_no=relation.row_no,
                sequence_no=relation.sequence_no,
                parent_article_code=relation.parent_article_code,
                parent_description_raw=relation.parent_description_raw,
                child_article_code=relation.child_article_code,
                child_description_raw=relation.child_description_raw,
                quantity=relation.quantity,
                uom_raw=relation.uom_raw,
                source_relation_key=relation_key,
                raw_payload=raw_payload,
                row_hash=row_hash,
            )
            self.session.add(item)
            staged.append(item)

        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ProlowinConflictError(
                "duplicate direct-structure source row identity"
            ) from exc

        batch.status = "PARSED"

        adjacency: dict[str, set[str]] = defaultdict(set)
        for relation in staged:
            if relation.parent_article_code == relation.child_article_code:
                self._issue(
                    batch_id=batch.id,
                    entity_type="direct_relation",
                    entity_key=relation.source_relation_key,
                    rule_code="PLW_BOM_CYCLE",
                    severity="BLOCKER",
                    message="Direct relation contains a self-cycle",
                    source_row_id=relation.id,
                    suggested_action="Correct the source parent-child relation.",
                )
            adjacency[relation.parent_article_code].add(
                relation.child_article_code
            )

        if payload.root_article_code not in adjacency:
            self._issue(
                batch_id=batch.id,
                entity_type="root_article",
                entity_key=payload.root_article_code,
                rule_code="PLW_ROOT_NOT_IDENTIFIED",
                severity="BLOCKER",
                message="Direct structure root has no outgoing relation",
                suggested_action="Provide the direct structure for the declared root.",
            )

        visited: set[str] = set()
        visiting: set[str] = set()

        def walk(code: str) -> None:
            if code in visiting:
                self._issue(
                    batch_id=batch.id,
                    entity_type="direct_structure",
                    entity_key=code,
                    rule_code="PLW_BOM_CYCLE",
                    severity="BLOCKER",
                    message="Cycle detected in direct Prolowin structure",
                    suggested_action="Correct the direct parent-child source structure.",
                )
                return
            if code in visited:
                return
            visiting.add(code)
            for child in adjacency.get(code, set()):
                walk(child)
            visiting.remove(code)
            visited.add(code)

        walk(payload.root_article_code)

        all_codes = {
            relation.parent_article_code for relation in staged
        } | {
            relation.child_article_code for relation in staged
        }
        disconnected = sorted(all_codes - visited)
        for code in disconnected:
            self._issue(
                batch_id=batch.id,
                entity_type="direct_structure",
                entity_key=code,
                rule_code="PLW_DIRECT_DISCONNECTED",
                severity="BLOCKER",
                message="Article is not reachable from the declared direct-structure root",
                suggested_action="Split unrelated structures or correct the root/path.",
            )

        self.session.flush()
        current_issues = self._issues(batch.id)
        if self._has_blocker(current_issues):
            batch.status = "REJECTED"
            batch.accepted_rows = 0
            batch.rejected_rows = len(staged)
            self.session.commit()
            self.session.refresh(batch)
            return self._direct_result(
                batch, idempotent_replay=False
            )

        batch.status = "VALIDATED"

        for raw_uom in sorted({item.uom_raw for item in staged}):
            self._ensure_uom_alias(
                batch_id=batch.id,
                raw_value=raw_uom,
                entity_key=raw_uom,
            )

        descriptions: dict[str, str] = {}
        for relation in staged:
            if relation.parent_description_raw:
                descriptions.setdefault(
                    relation.parent_article_code,
                    relation.parent_description_raw,
                )
            if relation.child_description_raw:
                descriptions.setdefault(
                    relation.child_article_code,
                    relation.child_description_raw,
                )

        articles: dict[str, Article] = {}
        for code in sorted(all_codes):
            articles[code] = self._upsert_article(
                batch_id=batch.id,
                code=code,
                description=descriptions.get(code, code),
            )

        relations_by_parent: dict[str, list[ProlowinDirectRelation]] = defaultdict(list)
        for relation in staged:
            relations_by_parent[relation.parent_article_code].append(
                relation
            )

        revisions_by_code: dict[str, ArticleRevision] = {}
        fingerprints_by_code: dict[str, str] = {}
        now = payload.source.exported_at or datetime.now(timezone.utc)

        for parent_code in sorted(relations_by_parent):
            relations = sorted(
                relations_by_parent[parent_code],
                key=lambda item: (
                    item.sequence_no
                    if item.sequence_no is not None
                    else 2_147_483_647,
                    item.child_article_code,
                    item.source_relation_key,
                ),
            )
            fingerprint = self._sha256(
                [
                    {
                        "child_article_code": item.child_article_code,
                        "quantity": self._decimal_text(item.quantity),
                        "uom_raw": item.uom_raw,
                        "sequence_no": item.sequence_no,
                        "source_relation_key": item.source_relation_key,
                    }
                    for item in relations
                ]
            )
            fingerprints_by_code[parent_code] = fingerprint
            article = articles[parent_code]
            revision = self.session.scalar(
                select(ArticleRevision).where(
                    ArticleRevision.article_id == article.id,
                    ArticleRevision.source_fingerprint == fingerprint,
                )
            )
            if revision is None:
                revision = ArticleRevision(
                    article_id=article.id,
                    revision_label=None,
                    source_fingerprint=fingerprint,
                    valid_from=now,
                    valid_to=None,
                    status="DRAFT",
                    source_batch_id=batch.id,
                    approved_at=None,
                    approved_by=None,
                )
                self.session.add(revision)
                self.session.flush()
            revisions_by_code[parent_code] = revision

        for parent_code in sorted(relations_by_parent):
            parent_revision = revisions_by_code[parent_code]
            fingerprint = fingerprints_by_code[parent_code]
            bom = self.session.scalar(
                select(BOMRevision).where(
                    BOMRevision.parent_article_revision_id
                    == parent_revision.id,
                    BOMRevision.source_fingerprint == fingerprint,
                )
            )
            if bom is None:
                max_revision = self.session.scalar(
                    select(func.max(BOMRevision.revision_no)).where(
                        BOMRevision.parent_article_revision_id
                        == parent_revision.id
                    )
                )
                bom = BOMRevision(
                    parent_article_revision_id=parent_revision.id,
                    revision_no=int(max_revision or 0) + 1,
                    valid_from=now,
                    valid_to=None,
                    status="DRAFT",
                    source_system="PROLOWIN",
                    source_batch_id=batch.id,
                    source_fingerprint=fingerprint,
                )
                self.session.add(bom)
                self.session.flush()

                for relation in sorted(
                    relations_by_parent[parent_code],
                    key=lambda item: (
                        item.sequence_no
                        if item.sequence_no is not None
                        else 2_147_483_647,
                        item.child_article_code,
                        item.source_relation_key,
                    ),
                ):
                    alias = self._find_uom_alias(relation.uom_raw)
                    child_revision = revisions_by_code.get(
                        relation.child_article_code
                    )
                    self.session.add(
                        BOMComponent(
                            bom_revision_id=bom.id,
                            child_article_id=articles[
                                relation.child_article_code
                            ].id,
                            child_revision_id=(
                                child_revision.id
                                if child_revision is not None
                                else None
                            ),
                            quantity=relation.quantity,
                            source_uom_raw=relation.uom_raw,
                            uom_id=(
                                alias.uom_id
                                if alias is not None
                                and alias.mapping_status == "MAPPED"
                                else None
                            ),
                            sequence_no=relation.sequence_no,
                            source_relation_key=relation.source_relation_key,
                            scrap_factor=None,
                            effective_from=None,
                            effective_to=None,
                        )
                    )

        batch.status = "APPLIED"
        batch.accepted_rows = len(staged)
        batch.rejected_rows = 0

        try:
            self.session.commit()
            self.session.refresh(batch)
        except IntegrityError as exc:
            self.session.rollback()
            raise ProlowinConflictError(
                "direct Prolowin structure conflicted with canonical master data"
            ) from exc

        return self._direct_result(
            batch, idempotent_replay=False
        )

    def _candidate_child_bom(
        self,
        component: BOMComponent,
    ) -> BOMRevision | None:
        if component.child_revision_id is None:
            return None
        child_revision = self.session.get(
            ArticleRevision, component.child_revision_id
        )
        if child_revision is None:
            raise ProlowinNotFoundError(
                "child article revision not found during reconciliation"
            )
        candidates = list(
            self.session.scalars(
                select(BOMRevision).where(
                    BOMRevision.parent_article_revision_id
                    == child_revision.id,
                    BOMRevision.source_fingerprint
                    == child_revision.source_fingerprint,
                    BOMRevision.status.in_(
                        ("DRAFT", "ACTIVE", "SUPERSEDED")
                    ),
                )
            ).all()
        )
        if len(candidates) > 1:
            raise ProlowinRuleError(
                "multiple candidate BOMs found for pinned child revision"
            )
        return candidates[0] if candidates else None

    def _explode_candidate(
        self,
        root: BOMRevision,
    ) -> list[tuple[str, Decimal, UUID | None, str]]:
        root_revision = self.session.get(
            ArticleRevision, root.parent_article_revision_id
        )
        if root_revision is None:
            raise ProlowinNotFoundError(
                "root article revision not found"
            )
        root_article = self.session.get(Article, root_revision.article_id)
        if root_article is None:
            raise ProlowinNotFoundError("root article not found")

        lines: list[tuple[str, Decimal, UUID | None, str]] = []

        def walk(
            bom: BOMRevision,
            multiplier: Decimal,
            article_path: tuple[UUID, ...],
        ) -> None:
            components = list(
                self.session.scalars(
                    select(BOMComponent)
                    .where(BOMComponent.bom_revision_id == bom.id)
                    .order_by(
                        BOMComponent.sequence_no.asc().nullslast(),
                        BOMComponent.created_at,
                        BOMComponent.id,
                    )
                ).all()
            )
            for component in components:
                child = self.session.get(
                    Article, component.child_article_id
                )
                if child is None:
                    raise ProlowinNotFoundError(
                        "child article not found during reconciliation"
                    )
                if child.id in article_path:
                    raise ProlowinRuleError(
                        "BOM cycle detected during candidate reconciliation"
                    )
                scrap = (
                    Decimal("1") + component.scrap_factor
                    if component.scrap_factor is not None
                    else Decimal("1")
                )
                quantity = multiplier * component.quantity * scrap
                lines.append(
                    (
                        child.external_code,
                        quantity,
                        component.uom_id,
                        component.source_uom_raw,
                    )
                )
                child_bom = self._candidate_child_bom(component)
                if child_bom is not None:
                    walk(
                        child_bom,
                        quantity,
                        article_path + (child.id,),
                    )

        walk(root, Decimal("1"), (root_article.id,))
        return lines

    def _comparison_value(
        self,
        quantity: Decimal,
        raw_uom: str,
        explicit_uom_id: UUID | None = None,
    ) -> tuple[str, Decimal]:
        alias = self._find_uom_alias(raw_uom)
        if (
            alias is not None
            and alias.mapping_status == "MAPPED"
            and alias.uom_id is not None
        ):
            if (
                explicit_uom_id is not None
                and explicit_uom_id != alias.uom_id
            ):
                raise ProlowinRuleError(
                    "BOM component canonical UoM conflicts with governed Prolowin alias"
                )
            factor = alias.conversion_factor or Decimal("1")
            return f"UOM:{alias.uom_id}", quantity * factor
        return f"RAW:{raw_uom}", quantity

    def reconcile(
        self,
        request,
    ) -> ReconciliationResult:
        if not isinstance(request, ReconciliationRequest):
            request = ReconciliationRequest.model_validate(request)

        batch = self._get_batch(request.complete_batch_id)
        if batch.source_type != "COMPLETE_ARTICLE_STRUCTURE":
            raise ProlowinRuleError(
                "reconciliation requires a complete-structure batch"
            )
        snapshot = self.session.scalar(
            select(ProlowinCompleteSnapshot).where(
                ProlowinCompleteSnapshot.batch_id == batch.id
            )
        )
        if snapshot is None:
            raise ProlowinRuleError(
                "complete batch has no normalized FIN projection"
            )

        bom = self.session.get(BOMRevision, request.bom_revision_id)
        if bom is None:
            raise ProlowinNotFoundError("BOM revision not found")
        root_revision = self.session.get(
            ArticleRevision, bom.parent_article_revision_id
        )
        if root_revision is None:
            raise ProlowinNotFoundError(
                "root article revision not found"
            )
        root_article = self.session.get(
            Article, root_revision.article_id
        )
        if root_article is None:
            raise ProlowinNotFoundError("root article not found")

        source_batch_id = bom.source_batch_id
        blocker_batches = [batch.id]
        if source_batch_id is not None:
            blocker_batches.append(source_batch_id)

        blockers = list(
            self.session.scalars(
                select(DataQualityIssue).where(
                    DataQualityIssue.batch_id.in_(blocker_batches),
                    DataQualityIssue.severity == "BLOCKER",
                    DataQualityIssue.status == "OPEN",
                )
            ).all()
        )

        if snapshot.root_article_code != root_article.external_code:
            raise ProlowinRuleError(
                "complete FIN snapshot root does not match BOM root article"
            )

        if blockers:
            run = ReconciliationRun(
                batch_id=batch.id,
                root_article_revision_id=root_revision.id,
                bom_revision_id=bom.id,
                status="BLOCKED",
                tolerance=request.tolerance,
                compared_items=0,
                matching_items=0,
                mismatching_items=0,
            )
            self.session.add(run)
            self.session.commit()
            self.session.refresh(run)
            return ReconciliationResult(
                run=ReconciliationRunRead.model_validate(run),
                items=[],
            )

        source_requirements = list(
            self.session.scalars(
                select(ProlowinFlatRequirement).where(
                    ProlowinFlatRequirement.snapshot_id == snapshot.id,
                    ProlowinFlatRequirement.is_root.is_(False),
                )
            ).all()
        )

        source_map: dict[tuple[str, str], dict] = {}
        for requirement in source_requirements:
            comparison_uom, quantity = self._comparison_value(
                requirement.quantity,
                requirement.uom_raw,
            )
            key = (requirement.article_code, comparison_uom)
            current = source_map.setdefault(
                key,
                {
                    "quantity": Decimal("0"),
                    "raw_uom": requirement.uom_raw,
                },
            )
            current["quantity"] += quantity

        calculated_map: dict[tuple[str, str], dict] = {}
        for code, quantity, uom_id, raw_uom in self._explode_candidate(bom):
            comparison_uom, normalized_quantity = self._comparison_value(
                quantity,
                raw_uom,
                explicit_uom_id=uom_id,
            )
            key = (code, comparison_uom)
            current = calculated_map.setdefault(
                key,
                {
                    "quantity": Decimal("0"),
                    "raw_uom": raw_uom,
                },
            )
            current["quantity"] += normalized_quantity

        run = ReconciliationRun(
            batch_id=batch.id,
            root_article_revision_id=root_revision.id,
            bom_revision_id=bom.id,
            status="MISMATCH",
            tolerance=request.tolerance,
            compared_items=0,
            matching_items=0,
            mismatching_items=0,
        )
        self.session.add(run)
        self.session.flush()

        items: list[ReconciliationItem] = []
        matching = 0
        mismatching = 0
        for key in sorted(set(source_map) | set(calculated_map)):
            code, comparison_uom = key
            source = source_map.get(key)
            calculated = calculated_map.get(key)

            if source is None:
                result = "CALCULATED_ONLY"
                variance = None
                mismatching += 1
            elif calculated is None:
                result = "SOURCE_ONLY"
                variance = None
                mismatching += 1
            else:
                variance = (
                    calculated["quantity"] - source["quantity"]
                )
                if abs(variance) <= request.tolerance:
                    result = "MATCH"
                    matching += 1
                else:
                    result = "MISMATCH"
                    mismatching += 1

            item = ReconciliationItem(
                reconciliation_run_id=run.id,
                article_code=code,
                source_fin_quantity=(
                    source["quantity"] if source is not None else None
                ),
                source_uom_raw=(
                    source["raw_uom"] if source is not None else None
                ),
                calculated_quantity=(
                    calculated["quantity"]
                    if calculated is not None
                    else None
                ),
                calculated_uom_raw=(
                    calculated["raw_uom"]
                    if calculated is not None
                    else None
                ),
                comparison_uom=comparison_uom,
                variance=variance,
                result=result,
            )
            self.session.add(item)
            items.append(item)

        run.compared_items = len(items)
        run.matching_items = matching
        run.mismatching_items = mismatching

        if mismatching:
            run.status = "MISMATCH"
            self._issue(
                batch_id=batch.id,
                entity_type="reconciliation",
                entity_key=str(run.id),
                rule_code="PLW_RECONCILIATION_MISMATCH",
                severity="ERROR",
                message=f"{mismatching} reconciliation item(s) differ from the FIN projection",
                suggested_action="Review direct hierarchy, quantities and approved UoM mappings before publication.",
            )
        else:
            warning_count = self.session.scalar(
                select(func.count(DataQualityIssue.id)).where(
                    DataQualityIssue.batch_id.in_(blocker_batches),
                    DataQualityIssue.severity.in_(
                        ("WARNING", "ERROR")
                    ),
                    DataQualityIssue.status == "OPEN",
                )
            ) or 0
            run.status = (
                "MATCH_WITH_WARNINGS" if warning_count else "MATCH"
            )
            batch.status = "RECONCILED"
            if source_batch_id is not None:
                direct_batch = self.session.get(
                    ImportBatch, source_batch_id
                )
                if (
                    direct_batch is not None
                    and direct_batch.status == "APPLIED"
                ):
                    direct_batch.status = "RECONCILED"

        self.session.commit()
        self.session.refresh(run)
        for item in items:
            self.session.refresh(item)

        return ReconciliationResult(
            run=ReconciliationRunRead.model_validate(run),
            items=[
                ReconciliationItemRead.model_validate(item)
                for item in items
            ],
        )
