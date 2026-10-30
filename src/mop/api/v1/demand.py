"""G3 Demand / Plan / Taquilla API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mop.audit.context import request_audit_context
from mop.audit.service import AuditService
from mop.demand.schemas import (
    ProductionPlanCreate,
    ProductionPlanNumberUpdate,
    ProductionPlanRead,
    ProductionPlanStatusUpdate,
    RoutingOverrideRequest,
    RoutingResolveRequest,
    TaquillaCreate,
    TaquillaProductLineCreate,
    TaquillaProductLineRead,
    TaquillaProductLineUpdate,
    TaquillaRead,
    TaquillaStatusUpdate,
    TaquillaTopologyUpdate,
)
from mop.demand.service import (
    DemandConflictError,
    DemandNotFoundError,
    DemandRuleError,
    DemandService,
)
from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.persistence.dependencies import get_session

router = APIRouter(prefix="/demand", tags=["demand"])


def service(session: Session = Depends(get_session)) -> DemandService:
    return DemandService(session)


def _translate(operation):
    try:
        return operation()
    except DemandNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DemandConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DemandRuleError as exc:
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


@router.post("/plans", response_model=ProductionPlanRead, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: ProductionPlanCreate,
    request: Request,
    app: DemandService = Depends(service),
    actor: User = Depends(require_global_permission("demand.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_plan(payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="demand.plan.create",
        object_type="production_plan",
        object_id=created.id,
        details={"plan_number": created.plan_number},
    )
    return created


@router.get("/plans", response_model=list[ProductionPlanRead])
def list_plans(
    plan_status: str | None = None,
    app: DemandService = Depends(service),
    _: User = Depends(require_global_permission("demand.read")),
):
    return app.list_plans(plan_status)


@router.patch("/plans/{plan_id}/number", response_model=ProductionPlanRead)
def update_plan_number(
    plan_id: UUID,
    payload: ProductionPlanNumberUpdate,
    request: Request,
    app: DemandService = Depends(service),
    actor: User = Depends(require_global_permission("demand.edit")),
    session: Session = Depends(get_session),
):
    previous = _translate(lambda: app.get_plan(plan_id)).plan_number
    updated = _translate(lambda: app.update_plan_number(plan_id, payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="demand.plan.number.update",
        object_type="production_plan",
        object_id=updated.id,
        details={"previous_plan_number": previous, "plan_number": updated.plan_number},
    )
    return updated


@router.post("/plans/{plan_id}/status", response_model=ProductionPlanRead)
def transition_plan(
    plan_id: UUID,
    payload: ProductionPlanStatusUpdate,
    request: Request,
    app: DemandService = Depends(service),
    actor: User = Depends(require_global_permission("demand.edit")),
    session: Session = Depends(get_session),
):
    previous = _translate(lambda: app.get_plan(plan_id)).status
    updated = _translate(lambda: app.transition_plan(plan_id, payload))
    if updated.status != previous:
        _audit(
            session=session,
            request=request,
            actor=actor,
            action="demand.plan.status.transition",
            object_type="production_plan",
            object_id=updated.id,
            details={"previous_status": previous, "status": updated.status},
        )
    return updated


@router.post(
    "/plans/{plan_id}/taquillas",
    response_model=TaquillaRead,
    status_code=status.HTTP_201_CREATED,
)
def create_taquilla(
    plan_id: UUID,
    payload: TaquillaCreate,
    request: Request,
    app: DemandService = Depends(service),
    actor: User = Depends(require_global_permission("demand.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.create_taquilla(plan_id, payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="demand.taquilla.create",
        object_type="taquilla",
        object_id=created.id,
        details={
            "plan_id": str(created.plan_id),
            "taquilla_code": created.taquilla_code,
            "sequence_no": created.sequence_no,
        },
    )
    return created


@router.get("/plans/{plan_id}/taquillas", response_model=list[TaquillaRead])
def list_taquillas(
    plan_id: UUID,
    app: DemandService = Depends(service),
    _: User = Depends(require_global_permission("demand.read")),
):
    return _translate(lambda: app.list_taquillas(plan_id))


@router.patch("/taquillas/{taquilla_id}/topology", response_model=TaquillaRead)
def update_taquilla_topology(
    taquilla_id: UUID,
    payload: TaquillaTopologyUpdate,
    request: Request,
    app: DemandService = Depends(service),
    actor: User = Depends(require_global_permission("demand.edit")),
    session: Session = Depends(get_session),
):
    previous = _translate(lambda: app.get_taquilla(taquilla_id)).vehicle_topology
    updated = _translate(lambda: app.update_taquilla_topology(taquilla_id, payload))
    if updated.vehicle_topology != previous:
        _audit(
            session=session,
            request=request,
            actor=actor,
            action="demand.taquilla.topology.update",
            object_type="taquilla",
            object_id=updated.id,
            details={
                "previous_vehicle_topology": previous,
                "vehicle_topology": updated.vehicle_topology,
            },
        )
    return updated


@router.post("/taquillas/{taquilla_id}/status", response_model=TaquillaRead)
def transition_taquilla(
    taquilla_id: UUID,
    payload: TaquillaStatusUpdate,
    request: Request,
    app: DemandService = Depends(service),
    actor: User = Depends(require_global_permission("demand.edit")),
    session: Session = Depends(get_session),
):
    previous = _translate(lambda: app.get_taquilla(taquilla_id)).status
    updated = _translate(lambda: app.transition_taquilla(taquilla_id, payload))
    if updated.status != previous:
        _audit(
            session=session,
            request=request,
            actor=actor,
            action="demand.taquilla.status.transition",
            object_type="taquilla",
            object_id=updated.id,
            details={"previous_status": previous, "status": updated.status},
        )
    return updated


@router.post(
    "/taquillas/{taquilla_id}/products",
    response_model=TaquillaProductLineRead,
    status_code=status.HTTP_201_CREATED,
)
def add_product_line(
    taquilla_id: UUID,
    payload: TaquillaProductLineCreate,
    request: Request,
    app: DemandService = Depends(service),
    actor: User = Depends(require_global_permission("demand.edit")),
    session: Session = Depends(get_session),
):
    created = _translate(lambda: app.add_product_line(taquilla_id, payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="demand.taquilla_product.create",
        object_type="taquilla_product_line",
        object_id=created.id,
        details={
            "taquilla_id": str(created.taquilla_id),
            "article_id": str(created.article_id),
            "sequence_no": created.sequence_no,
            "requested_quantity": str(created.requested_quantity),
            "source_line_key": created.source_line_key,
            "deck_position": created.deck_position,
            "source_document_key": created.source_document_key,
        },
    )
    return created


@router.get(
    "/taquillas/{taquilla_id}/products",
    response_model=list[TaquillaProductLineRead],
)
def list_product_lines(
    taquilla_id: UUID,
    app: DemandService = Depends(service),
    _: User = Depends(require_global_permission("demand.read")),
):
    return _translate(lambda: app.list_product_lines(taquilla_id))


@router.patch(
    "/taquilla-products/{line_id}",
    response_model=TaquillaProductLineRead,
)
def update_product_line(
    line_id: UUID,
    payload: TaquillaProductLineUpdate,
    request: Request,
    app: DemandService = Depends(service),
    actor: User = Depends(require_global_permission("demand.edit")),
    session: Session = Depends(get_session),
):
    before = _translate(lambda: app.get_product_line(line_id))
    previous_sequence = before.sequence_no
    previous_quantity = str(before.requested_quantity)
    previous_deck_position = before.deck_position
    previous_source_document_key = before.source_document_key
    updated = _translate(lambda: app.update_product_line(line_id, payload))
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="demand.taquilla_product.update",
        object_type="taquilla_product_line",
        object_id=updated.id,
        details={
            "taquilla_id": str(updated.taquilla_id),
            "article_id": str(updated.article_id),
            "previous_sequence_no": previous_sequence,
            "sequence_no": updated.sequence_no,
            "previous_requested_quantity": previous_quantity,
            "requested_quantity": str(updated.requested_quantity),
            "previous_deck_position": previous_deck_position,
            "deck_position": updated.deck_position,
            "previous_source_document_key": previous_source_document_key,
            "source_document_key": updated.source_document_key,
        },
    )
    return updated


@router.post(
    "/taquilla-products/{line_id}/routing/resolve",
    response_model=TaquillaProductLineRead,
)
def resolve_product_line_routing(
    line_id: UUID,
    payload: RoutingResolveRequest,
    request: Request,
    app: DemandService = Depends(service),
    actor: User = Depends(require_global_permission("demand.edit")),
    session: Session = Depends(get_session),
):
    previous = _translate(lambda: app.get_product_line(line_id))
    previous_routing_id = previous.routing_revision_id
    updated = _translate(
        lambda: app.resolve_product_line_routing(
            line_id, payload, bound_by=actor.id
        )
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="demand.taquilla_product.routing.resolve",
        object_type="taquilla_product_line",
        object_id=updated.id,
        details={
            "article_id": str(updated.article_id),
            "previous_routing_revision_id": (
                str(previous_routing_id) if previous_routing_id else None
            ),
            "routing_revision_id": str(updated.routing_revision_id),
            "routing_effective_at": updated.routing_effective_at.isoformat(),
            "routing_binding_mode": updated.routing_binding_mode,
        },
    )
    return updated


@router.post(
    "/taquilla-products/{line_id}/routing/override",
    response_model=TaquillaProductLineRead,
)
def override_product_line_routing(
    line_id: UUID,
    payload: RoutingOverrideRequest,
    request: Request,
    app: DemandService = Depends(service),
    actor: User = Depends(require_global_permission("demand.edit")),
    session: Session = Depends(get_session),
):
    previous = _translate(lambda: app.get_product_line(line_id))
    previous_routing_id = previous.routing_revision_id
    updated = _translate(
        lambda: app.override_product_line_routing(
            line_id, payload, bound_by=actor.id
        )
    )
    _audit(
        session=session,
        request=request,
        actor=actor,
        action="demand.taquilla_product.routing.override",
        object_type="taquilla_product_line",
        object_id=updated.id,
        details={
            "article_id": str(updated.article_id),
            "previous_routing_revision_id": (
                str(previous_routing_id) if previous_routing_id else None
            ),
            "routing_revision_id": str(updated.routing_revision_id),
            "routing_effective_at": updated.routing_effective_at.isoformat(),
            "routing_binding_mode": updated.routing_binding_mode,
            "routing_override_reason": updated.routing_override_reason,
        },
    )
    return updated
