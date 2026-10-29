"""Prolowin integration API under the Master Data boundary."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.persistence.dependencies import get_session
from mop.prolowin.schemas import (
    CompleteImportResult,
    DataQualityIssueRead,
    DirectImportResult,
    ImportBatchRead,
    NormalizedProjectionRead,
    ProlowinCompleteStructureImport,
    ProlowinDirectStructureImport,
    ReconciliationRequest,
    ReconciliationResult,
)
from mop.prolowin.service import (
    ProlowinConflictError,
    ProlowinNotFoundError,
    ProlowinRuleError,
    ProlowinService,
)

router = APIRouter(
    prefix="/master-data/prolowin",
    tags=["master-data-prolowin"],
)


def service(session: Session = Depends(get_session)) -> ProlowinService:
    return ProlowinService(session)


def _translate(operation):
    try:
        return operation()
    except ProlowinNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ProlowinConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ProlowinRuleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


def _audit(
    *,
    session: Session,
    request: Request,
    actor: User,
    action: str,
    object_type: str,
    object_id: UUID,
    details: dict | None = None,
) -> None:
    AuditService(session).record(
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        outcome="success",
        actor_user_id=actor.id,
        actor_username=actor.username,
        details=details,
        **request_audit_context(request),
    )


@router.post(
    "/complete-structures/import",
    response_model=CompleteImportResult,
    status_code=status.HTTP_201_CREATED,
)
def import_complete_structure(
    payload: ProlowinCompleteStructureImport,
    request: Request,
    app: ProlowinService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    result = _translate(
        lambda: app.import_complete_structure(
            payload, imported_by=actor.id
        )
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.prolowin.complete_structure.import",
        object_type="import_batch",
        object_id=result.batch.id,
        details={
            "status": result.batch.status,
            "source_sha256": result.batch.source_sha256,
            "parser_version": result.batch.parser_version,
            "idempotent_replay": result.idempotent_replay,
        },
    )
    return result


@router.post(
    "/direct-structures/import",
    response_model=DirectImportResult,
    status_code=status.HTTP_201_CREATED,
)
def import_direct_structure(
    payload: ProlowinDirectStructureImport,
    request: Request,
    app: ProlowinService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    result = _translate(
        lambda: app.import_direct_structure(
            payload, imported_by=actor.id
        )
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.prolowin.direct_structure.import",
        object_type="import_batch",
        object_id=result.batch.id,
        details={
            "status": result.batch.status,
            "candidate_article_revisions": len(
                result.candidate_article_revision_ids
            ),
            "candidate_bom_revisions": len(
                result.candidate_bom_revision_ids
            ),
            "idempotent_replay": result.idempotent_replay,
        },
    )
    return result


@router.get(
    "/import-batches",
    response_model=list[ImportBatchRead],
)
def list_import_batches(
    source_type: str | None = None,
    status_filter: str | None = None,
    app: ProlowinService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return app.list_batches(source_type, status_filter)


@router.get(
    "/import-batches/{batch_id}/issues",
    response_model=list[DataQualityIssueRead],
)
def list_data_quality_issues(
    batch_id: UUID,
    severity: str | None = None,
    status_filter: str | None = None,
    app: ProlowinService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return _translate(
        lambda: app.list_issues(batch_id, severity, status_filter)
    )


@router.get(
    "/import-batches/{batch_id}/projection",
    response_model=NormalizedProjectionRead,
)
def get_normalized_projection(
    batch_id: UUID,
    app: ProlowinService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return _translate(
        lambda: app.get_normalized_projection(batch_id)
    )


@router.post(
    "/reconciliations",
    response_model=ReconciliationResult,
    status_code=status.HTTP_201_CREATED,
)
def reconcile(
    payload: ReconciliationRequest,
    request: Request,
    app: ProlowinService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    result = _translate(lambda: app.reconcile(payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.prolowin.reconcile",
        object_type="reconciliation_run",
        object_id=result.run.id,
        details={
            "status": result.run.status,
            "complete_batch_id": str(result.run.batch_id),
            "bom_revision_id": str(result.run.bom_revision_id),
            "compared_items": result.run.compared_items,
            "mismatching_items": result.run.mismatching_items,
        },
    )
    return result
