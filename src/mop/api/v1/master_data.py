"""Canonical Master Data API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.master_data.schemas import (
    ArticleCreate,
    ArticleRead,
    ArticleRevisionCreate,
    ArticleRevisionRead,
    UnitOfMeasureAliasCreate,
    UnitOfMeasureAliasRead,
    UnitOfMeasureCreate,
    UnitOfMeasureRead,
)
from mop.master_data.service import (
    MasterDataConflictError,
    MasterDataNotFoundError,
    MasterDataService,
)
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/master-data", tags=["master-data"])


def service(session: Session = Depends(get_session)) -> MasterDataService:
    return MasterDataService(session)


def _translate(operation):
    try:
        return operation()
    except MasterDataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MasterDataConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


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


@router.post("/uoms", response_model=UnitOfMeasureRead, status_code=status.HTTP_201_CREATED)
def create_uom(
    payload: UnitOfMeasureCreate,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_uom(payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.uom.create",
        object_type="unit_of_measure",
        object_id=created.id,
        details={"code": created.code},
    )
    return created


@router.get("/uoms", response_model=list[UnitOfMeasureRead])
def list_uoms(
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return app.list_uoms()


@router.post(
    "/uom-aliases",
    response_model=UnitOfMeasureAliasRead,
    status_code=status.HTTP_201_CREATED,
)
def create_uom_alias(
    payload: UnitOfMeasureAliasCreate,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_uom_alias(payload, approved_by=actor.id))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.uom_alias.create",
        object_type="unit_of_measure_alias",
        object_id=created.id,
        details={
            "source_system": created.source_system,
            "raw_value": created.raw_value,
            "mapping_status": created.mapping_status,
        },
    )
    return created


@router.get("/uom-aliases", response_model=list[UnitOfMeasureAliasRead])
def list_uom_aliases(
    source_system: str | None = None,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return app.list_uom_aliases(source_system)


@router.post("/articles", response_model=ArticleRead, status_code=status.HTTP_201_CREATED)
def create_article(
    payload: ArticleCreate,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_article(payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.article.create",
        object_type="article",
        object_id=created.id,
        details={
            "external_system": created.external_system,
            "external_code": created.external_code,
            "article_kind": created.article_kind,
        },
    )
    return created


@router.get("/articles", response_model=list[ArticleRead])
def list_articles(
    external_system: str | None = None,
    article_kind: str | None = None,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return app.list_articles(external_system, article_kind)


@router.post(
    "/articles/{article_id}/revisions",
    response_model=ArticleRevisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_article_revision(
    article_id: UUID,
    payload: ArticleRevisionCreate,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_article_revision(article_id, payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.article_revision.create",
        object_type="article_revision",
        object_id=created.id,
        details={
            "article_id": str(article_id),
            "source_fingerprint": created.source_fingerprint,
            "status": created.status,
        },
    )
    return created


@router.get(
    "/articles/{article_id}/revisions",
    response_model=list[ArticleRevisionRead],
)
def list_article_revisions(
    article_id: UUID,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return _translate(lambda: app.list_article_revisions(article_id))
