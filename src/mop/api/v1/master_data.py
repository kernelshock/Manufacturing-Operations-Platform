"""Canonical Master Data API."""

from datetime import datetime
from decimal import Decimal
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
    BOMComponentCreate,
    BOMComponentRead,
    BOMExplosionRead,
    BOMRevisionCreate,
    BOMRevisionRead,
    BOMSupersedeRequest,
    ProductConfigurationCreate,
    ProductConfigurationRead,
    SupplierArticleCreate,
    SupplierArticleRead,
    SupplierCreate,
    SupplierRead,
    SupplierSourceMappingCreate,
    SupplierSourceMappingRead,
    UnitOfMeasureAliasCreate,
    UnitOfMeasureAliasRead,
    UnitOfMeasureCreate,
    UnitOfMeasureRead,
)
from mop.master_data.service import (
    MasterDataConflictError,
    MasterDataNotFoundError,
    MasterDataRuleError,
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
    except MasterDataRuleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
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


@router.post(
    "/product-configurations",
    response_model=ProductConfigurationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_product_configuration(
    payload: ProductConfigurationCreate,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_product_configuration(payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.product_configuration.create",
        object_type="product_configuration",
        object_id=created.id,
        details={
            "article_id": str(created.article_id),
            "family_code": created.family_code,
            "model_code": created.model_code,
            "product_class": created.product_class,
        },
    )
    return created


@router.get(
    "/product-configurations",
    response_model=list[ProductConfigurationRead],
)
def list_product_configurations(
    family_code: str | None = None,
    model_code: str | None = None,
    active: bool | None = None,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return app.list_product_configurations(family_code, model_code, active)


@router.get(
    "/articles/{article_id}/product-configuration",
    response_model=ProductConfigurationRead,
)
def get_product_configuration(
    article_id: UUID,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return _translate(lambda: app.get_product_configuration(article_id))


@router.post(
    "/suppliers",
    response_model=SupplierRead,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier(
    payload: SupplierCreate,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_supplier(payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.supplier.create",
        object_type="supplier",
        object_id=created.id,
        details={
            "code": created.code,
            "legal_name": created.legal_name,
            "supply_category": created.supply_category,
        },
    )
    return created


@router.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(
    supply_category: str | None = None,
    active: bool | None = None,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return app.list_suppliers(supply_category, active)


@router.post(
    "/supplier-source-mappings",
    response_model=SupplierSourceMappingRead,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_source_mapping(
    payload: SupplierSourceMappingCreate,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(
        lambda: app.create_supplier_source_mapping(payload, approved_by=actor.id)
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.supplier_source_mapping.create",
        object_type="supplier_source_mapping",
        object_id=created.id,
        details={
            "supplier_id": str(created.supplier_id) if created.supplier_id else None,
            "external_system": created.external_system,
            "external_code": created.external_code,
            "mapping_status": created.mapping_status,
        },
    )
    return created


@router.get(
    "/supplier-source-mappings",
    response_model=list[SupplierSourceMappingRead],
)
def list_supplier_source_mappings(
    external_system: str | None = None,
    mapping_status: str | None = None,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return app.list_supplier_source_mappings(external_system, mapping_status)


@router.post(
    "/supplier-articles",
    response_model=SupplierArticleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_article(
    payload: SupplierArticleCreate,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_supplier_article(payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.supplier_article.create",
        object_type="supplier_article",
        object_id=created.id,
        details={
            "supplier_id": str(created.supplier_id),
            "article_id": str(created.article_id),
            "preferred": created.preferred,
            "lead_time_days": created.lead_time_days,
        },
    )
    return created


@router.get("/supplier-articles", response_model=list[SupplierArticleRead])
def list_supplier_articles(
    supplier_id: UUID | None = None,
    article_id: UUID | None = None,
    active: bool | None = None,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return app.list_supplier_articles(supplier_id, article_id, active)



@router.post(
    "/bom-revisions",
    response_model=BOMRevisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_bom_revision(
    payload: BOMRevisionCreate,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_bom_revision(payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.bom_revision.create",
        object_type="bom_revision",
        object_id=created.id,
        details={
            "parent_article_revision_id": str(created.parent_article_revision_id),
            "revision_no": created.revision_no,
            "source_system": created.source_system,
            "source_fingerprint": created.source_fingerprint,
            "status": created.status,
        },
    )
    return created


@router.get("/bom-revisions", response_model=list[BOMRevisionRead])
def list_bom_revisions(
    parent_article_revision_id: UUID | None = None,
    status_filter: str | None = None,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return app.list_bom_revisions(parent_article_revision_id, status_filter)


@router.post(
    "/bom-revisions/{bom_revision_id}/components",
    response_model=BOMComponentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_bom_component(
    bom_revision_id: UUID,
    payload: BOMComponentCreate,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.add_bom_component(bom_revision_id, payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.bom_component.create",
        object_type="bom_component",
        object_id=created.id,
        details={
            "bom_revision_id": str(created.bom_revision_id),
            "child_article_id": str(created.child_article_id),
            "child_revision_id": (
                str(created.child_revision_id) if created.child_revision_id else None
            ),
            "quantity": str(created.quantity),
            "source_uom_raw": created.source_uom_raw,
        },
    )
    return created


@router.get(
    "/bom-revisions/{bom_revision_id}/components",
    response_model=list[BOMComponentRead],
)
def list_bom_components(
    bom_revision_id: UUID,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return _translate(lambda: app.list_bom_components(bom_revision_id))


@router.post(
    "/bom-revisions/{bom_revision_id}/publish",
    response_model=BOMRevisionRead,
)
def publish_bom_revision(
    bom_revision_id: UUID,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    published = _translate(lambda: app.publish_bom_revision(bom_revision_id))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.bom_revision.publish",
        object_type="bom_revision",
        object_id=published.id,
        details={
            "parent_article_revision_id": str(
                published.parent_article_revision_id
            ),
            "revision_no": published.revision_no,
            "status": published.status,
        },
    )
    return published


@router.post(
    "/bom-revisions/{bom_revision_id}/supersede",
    response_model=BOMRevisionRead,
)
def supersede_bom_revision(
    bom_revision_id: UUID,
    payload: BOMSupersedeRequest,
    request: Request,
    app: MasterDataService = Depends(service),
    actor: User = Depends(require_global_permission("masterdata.edit")),
    session: Session = Depends(get_session),
):
    current, replacement = _translate(
        lambda: app.supersede_bom_revision(
            bom_revision_id,
            payload.replacement_bom_revision_id,
            payload.effective_at,
        )
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="masterdata.bom_revision.supersede",
        object_type="bom_revision",
        object_id=current.id,
        details={
            "replacement_bom_revision_id": str(replacement.id),
            "effective_at": replacement.valid_from.isoformat(),
        },
    )
    return replacement


@router.get(
    "/bom-revisions/{bom_revision_id}/explode",
    response_model=BOMExplosionRead,
)
def explode_bom(
    bom_revision_id: UUID,
    quantity: Decimal = Decimal("1"),
    effective_at: datetime | None = None,
    app: MasterDataService = Depends(service),
    _: User = Depends(require_global_permission("masterdata.read")),
):
    return _translate(
        lambda: app.explode_bom(
            bom_revision_id,
            root_quantity=quantity,
            effective_at=effective_at,
        )
    )
