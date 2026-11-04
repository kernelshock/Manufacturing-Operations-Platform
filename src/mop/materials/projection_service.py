"""G6.7 — read-only, plant-isolated materials intelligence.

Only G6.3 yields theoretical demand; G6.2 physical postings derive on-hand;
G6.5 append-only allocation derives held stock; G6.4 explicit MES events derive
observed use. All domains retain independent provenance and no write occurs.
"""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from mop.core.models import Plant
from mop.demand.models import ProductionPlan
from mop.master_data.models import Article, UnitOfMeasure
from mop.materials.requirement_schemas import MaterialRequirementAggregate
from mop.materials.models import MaterialLocation, MaterialMovement, MaterialWarehouse
from mop.materials.reservation_models import MaterialReservationEvent
from mop.materials.consumption_models import MaterialConsumption
from mop.materials.requirements import MaterialRequirementsService
from mop.materials.projection_schemas import (
    MaterialItemProjection, MaterialLocationProjection, MaterialPlanOption,
    MaterialPlanOverview, MaterialPlantOption, MaterialPurchaseEvidenceLine,
    MaterialPurchaseEvidenceOverview,
)
from mop.materials.service import MaterialsNotFound, MaterialsRule
from mop.mes.models import ExecutionOperation
from mop.prolowin.procurement_models import ProcurementEvidenceEvent

ZERO = Decimal("0")


class MaterialProjectionService:
    def __init__(self, session: Session):
        self.session = session
        self.requirements = MaterialRequirementsService(session)

    def plants(self, search: str | None = None, limit: int = 500):
        stmt = select(Plant).where(Plant.active.is_(True))
        if search:
            stmt = stmt.where(Plant.code.ilike(f"%{search}%"))
        values = self.session.scalars(stmt.order_by(Plant.code).limit(limit)).all()
        return [MaterialPlantOption(id=p.id, code=p.code, name=p.name) for p in values]

    def plans(self, search: str | None = None, limit: int = 500):
        stmt = select(ProductionPlan).where(ProductionPlan.status != "CANCELLED")
        if search:
            stmt = stmt.where(ProductionPlan.plan_number.ilike(f"%{search}%"))
        values = self.session.scalars(stmt.order_by(ProductionPlan.plan_number).limit(limit)).all()
        return [MaterialPlanOption(id=p.id, plan_number=p.plan_number, status=p.status)
                for p in values]

    def overview(self, plan_id: UUID, plant_id: UUID, effective_at: datetime):
        if effective_at.tzinfo is None or effective_at.utcoffset() is None:
            raise MaterialsRule("effective_at requires an explicit timezone")
        plant = self.session.get(Plant, plant_id)
        if plant is None:
            raise MaterialsNotFound("selected plant not found")
        if not plant.active:
            raise MaterialsRule("selected plant inactive; choose an active plant")
        projection = self.requirements.project(plan_id, effective_at)
        requirements = list(projection.aggregate)
        taquilla_ids = list({path.taquilla_id for path in projection.paths})
        rows = self.session.execute(
            select(MaterialLocation, MaterialWarehouse.code)
            .join(MaterialWarehouse, MaterialWarehouse.id == MaterialLocation.warehouse_id)
            .where(MaterialWarehouse.plant_id == plant.id,
                   MaterialWarehouse.active.is_(True), MaterialLocation.active.is_(True))
            .order_by(MaterialWarehouse.code, MaterialLocation.code)
        ).all()
        locations = [(loc, wh_code) for loc, wh_code in rows]
        location_ids = [loc.id for loc, _ in locations]

        # MES consumption may use substitutes or unplanned articles. Keep those
        # visible rather than silently discarding recorded real material use.
        consumption: dict[tuple[UUID, UUID], Decimal] = defaultdict(lambda: ZERO)
        if location_ids:
            observed = self.session.execute(
                select(
                    MaterialConsumption.article_id, MaterialConsumption.uom_id,
                    func.sum(case(
                        (MaterialConsumption.kind == "CONSUME", MaterialConsumption.quantity),
                        else_=-MaterialConsumption.quantity,
                    )),
                )
                .join(ExecutionOperation, ExecutionOperation.id == MaterialConsumption.execution_operation_id)
                .where(
                    ExecutionOperation.plan_id == plan_id,
                    MaterialConsumption.location_id.in_(location_ids),
                )
                .group_by(MaterialConsumption.article_id, MaterialConsumption.uom_id)
            ).all()
            consumption = {(a, u): Decimal(q) for a, u, q in observed}
        expected_keys = {(r.material_article_id, r.uom_id) for r in requirements}
        for (article_id, uom_id), observed_qty in consumption.items():
            if (article_id, uom_id) in expected_keys:
                continue
            article = self.session.get(Article, article_id)
            uom = self.session.get(UnitOfMeasure, uom_id)
            if article is None or uom is None:
                raise MaterialsRule("measured material lacks canonical article/UoM")
            requirements.append(MaterialRequirementAggregate(
                material_article_id=article_id, material_article_code=article.external_code,
                uom_id=uom_id, uom_code=uom.code, theoretical_quantity=ZERO,
            ))
        requirements.sort(key=lambda item: (item.material_article_code, item.uom_code))
        article_ids = list({item.material_article_id for item in requirements})

        # Only stock belonging to the selected plant can satisfy its projection.
        quantities: dict[tuple[UUID, UUID], Decimal] = {}
        holds: dict[tuple[UUID, UUID], Decimal] = defaultdict(lambda: ZERO)
        plan_holds: dict[tuple[UUID, UUID], Decimal] = defaultdict(lambda: ZERO)
        if article_ids and location_ids:
            inventory = self.session.execute(
                select(MaterialMovement.article_id, MaterialMovement.location_id,
                       func.sum(MaterialMovement.signed_quantity))
                .where(MaterialMovement.article_id.in_(article_ids),
                       MaterialMovement.location_id.in_(location_ids))
                .group_by(MaterialMovement.article_id, MaterialMovement.location_id)
            ).all()
            quantities = {(a, loc): Decimal(q) for a, loc, q in inventory}

            hold_rows = self.session.execute(
                select(
                    MaterialReservationEvent.article_id, MaterialReservationEvent.location_id,
                    func.sum(MaterialReservationEvent.signed_quantity),
                    func.sum(case(
                        (MaterialReservationEvent.taquilla_id.in_(taquilla_ids),
                         MaterialReservationEvent.signed_quantity),
                        else_=ZERO,
                    )),
                ).where(MaterialReservationEvent.article_id.in_(article_ids),
                        MaterialReservationEvent.location_id.in_(location_ids))
                .group_by(MaterialReservationEvent.article_id, MaterialReservationEvent.location_id)
            ).all()
            for article, location, total, selected in hold_rows:
                holds[(article, location)] = Decimal(total)
                plan_holds[(article, location)] = Decimal(selected)


        # The presentation reports a gross exposure only; measured use is already
        # reflected in physical stock and may cover a different production horizon.
        paths_by_material = defaultdict(list)
        for path in projection.paths:
            paths_by_material[(path.material_article_id, path.uom_id)].append(path)

        items: list[MaterialItemProjection] = []
        for req in requirements:
            article = self.session.get(Article, req.material_article_id)
            if article is None:
                raise MaterialsRule("BOM article no longer exists")
            location_lines = []
            total_held = ZERO
            total_plan_held = ZERO
            physical_total = ZERO
            all_initialized = bool(locations)
            for location, warehouse_code in locations:
                key = (req.material_article_id, location.id)
                current = quantities.get(key)
                is_known = current is not None
                if not is_known:
                    all_initialized = False
                else:
                    physical_total += current
                held = holds[key]
                total_held += held
                total_plan_held += plan_holds[key]
                location_lines.append(MaterialLocationProjection(
                    location_id=location.id, warehouse_code=warehouse_code,
                    location_code=location.code, location_name=location.name,
                    on_hand=current, held=held,
                    unallocated=current - held if current is not None else None,
                    state="KNOWN" if is_known else "UNKNOWN",
                ))

            on_hand = physical_total if all_initialized else None
            unallocated = on_hand - total_held if on_hand is not None else None
            gross_gap = (max(ZERO, req.theoretical_quantity - total_plan_held -
                             max(ZERO, unallocated))
                         if unallocated is not None else None)
            # No measured MES event means zero recorded consumption, not unknown physical stock.
            # The query above produces a plain dict, so indexing would raise KeyError.
            measured = consumption.get((req.material_article_id, req.uom_id), ZERO)
            paths = paths_by_material[(req.material_article_id, req.uom_id)]
            warnings = []
            if not paths:
                warnings.append("MEASURED_MATERIAL_NOT_IN_EFFECTIVE_BOM")
            if not all_initialized:
                warnings.append("UNKNOWN_STOCK_IN_AT_LEAST_ONE_ACTIVE_LOCATION")
            if any(p.taquilla_status != "COMPLETED" for p in paths):
                warnings.append("THEORETICAL_AND_MEASURED_ARE_DIFFERENT_LIFECYCLE_BASES")
            warnings.append("QUALITY_RELEASE_AND_INBOUND_SUPPLY_NOT_INFERRED")
            items.append(MaterialItemProjection(
                source_basis="BOM" if paths else "MEASURED_WITHOUT_BOM",
                article_id=req.material_article_id,
                article_code=req.material_article_code,
                article_description=article.canonical_description,
                uom_id=req.uom_id, uom_code=req.uom_code,
                theoretical_plan_quantity=req.theoretical_quantity,
                actual_net_measured_consumption=measured,
                theoretical_minus_measured=req.theoretical_quantity - measured,
                physical_on_hand=on_hand,
                reserved_all_plans=total_held,
                reserved_this_plan=total_plan_held,
                unallocated_physical=unallocated,
                provisional_gross_gap=gross_gap,
                stock_state="KNOWN" if all_initialized else "UNKNOWN",
                location_breakdown=location_lines,
                distinct_taquillas=len({p.taquilla_id for p in paths}),
                source_path_count=len(paths),
                bom_revision_ids=sorted({p.bom_revision_id for p in paths}, key=str),
                warnings=warnings,
            ))
        return MaterialPlanOverview(
            plan_id=plan_id, plan_number=projection.plan_number,
            plan_status=projection.plan_status,
            plant_id=plant.id, plant_code=plant.code,
            effective_at=effective_at, generated_at=datetime.now(timezone.utc),
            source_taquillas=len(taquilla_ids),
            excluded_cancelled_taquillas=projection.excluded_cancelled_taquillas,
            material_count=len(items),
            bom_material_count=len(projection.aggregate),
            unplanned_consumption_materials=sum(not paths_by_material[(i.article_id, i.uom_id)] for i in items),
            unknown_stock_materials=sum(item.stock_state == "UNKNOWN" for item in items),
            indicative_gap_materials=sum(
                item.provisional_gross_gap is not None and item.provisional_gross_gap > ZERO
                for item in items
            ),
            items=items,
            warnings=[
                "GROSS_SHORTFALL_IS_NOT_AN_ATP_OR_PURCHASING_RECOMMENDATION",
                "MEASURED_CONSUMPTION_IS_ALREADY_REFLECTED_IN_PHYSICAL_STOCK",
                "PROLOWIN_MANUAL_HISTORY_IS_PARTIAL_AND_DOES_NOT_ADD_STOCK",
                "QUANTITIES_CANNOT_BE_SUMMED_ACROSS_DIFFERENT_UNITS",
                "LOCATION_STOCK_MUST_BE_INITIALIZED_EXPLICITLY",
                "BOM_REVISIONS_AND_PLAN_SCOPE_ARE_SNAPSHOT_AT_EFFECTIVE_AT",
            ],
        )

    def purchase_evidence(self, plan_id: UUID, effective_at: datetime):
        demand = self.requirements.project(plan_id, effective_at)
        article_ids = [item.material_article_id for item in demand.aggregate]
        evidence = []
        if article_ids:
            evidence = self.session.scalars(
                select(ProcurementEvidenceEvent).where(
                    ProcurementEvidenceEvent.mapped_article_id.in_(article_ids),
                    ProcurementEvidenceEvent.review_status == "VERIFIED",
                )
                .order_by(ProcurementEvidenceEvent.event_date, ProcurementEvidenceEvent.id)
            ).all()
        grouped = defaultdict(list)
        for event in evidence:
            grouped[event.mapped_article_id].append(event)
        items = []
        for required in demand.aggregate:
            events = grouped[required.material_article_id]
            items.append(MaterialPurchaseEvidenceLine(
                article_id=required.material_article_id,
                article_code=required.material_article_code,
                verified_order_lines=len({
                    (event.po_number, event.line_number) for event in events if event.kind == "ORDER"
                }),
                verified_receipt_events=sum(e.kind == "RECEIPT" for e in events),
                verified_claims=sum(e.kind == "CLAIM" for e in events),
                verified_escalations=sum(e.kind == "ESCALATION" for e in events),
                latest_verified_event_at=max((e.event_date for e in events), default=None),
                original_promise_dates=sorted({
                    e.original_promise_date for e in events
                    if e.kind == "ORDER" and e.original_promise_date is not None
                }),
                revised_promise_dates=sorted({
                    e.revised_promise_date for e in events
                    if e.kind == "RESCHEDULE" and e.revised_promise_date is not None
                }),
            ))
        return MaterialPurchaseEvidenceOverview(
            plan_id=plan_id, effective_at=effective_at, items=items,
        )
