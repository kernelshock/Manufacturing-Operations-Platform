"""G6.3 projected material needs from authoritative G3 demand and G2 published BOM.

This module runs SELECT-only queries and delegates all recursive expansion, scrap,
effectivity and cycle protection to G2 MasterDataService. No stock posting,
reservation or MES quantity inference occurs here.
"""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from mop.demand.models import ProductionPlan, Taquilla, TaquillaProductLine
from mop.master_data.models import Article, ArticleRevision, BOMRevision, UnitOfMeasure
from mop.master_data.service import MasterDataRuleError, MasterDataService
from mop.materials.requirement_schemas import (
    MaterialDemandProjection, MaterialRequirementAggregate, MaterialRequirementPath,
)
from mop.materials.service import MaterialsNotFound, MaterialsRule


class MaterialRequirementsService:
    def __init__(self, session: Session):
        self.session = session
        self.master = MasterDataService(session)

    def _root_bom(self, article_id: UUID, at: datetime) -> BOMRevision:
        candidates = self.session.scalars(
            select(BOMRevision)
            .join(ArticleRevision, ArticleRevision.id == BOMRevision.parent_article_revision_id)
            .where(
                ArticleRevision.article_id == article_id,
                BOMRevision.status == "ACTIVE",
                BOMRevision.valid_from <= at,
                or_(BOMRevision.valid_to.is_(None), BOMRevision.valid_to > at),
            )
            .order_by(BOMRevision.id)
        ).all()
        if len(candidates) != 1:
            if not candidates:
                raise MaterialsRule(
                    f"no effective ACTIVE BOM for product article {article_id} at {at.isoformat()}"
                )
            raise MaterialsRule(
                f"ambiguous ACTIVE BOM revisions for article {article_id}; explicit G2 reconciliation required"
            )
        return candidates[0]

    def project(
        self,
        plan_id: UUID,
        effective_at: datetime,
        *,
        taquilla_id: UUID | None = None,
    ) -> MaterialDemandProjection:
        if effective_at.tzinfo is None or effective_at.utcoffset() is None:
            raise MaterialsRule("effective_at must include an explicit timezone offset")

        plan = self.session.get(ProductionPlan, plan_id)
        if plan is None:
            raise MaterialsNotFound("production plan not found")
        if plan.status == "CANCELLED":
            raise MaterialsRule("cancelled production plan cannot create material demand")

        stmt = select(Taquilla).where(Taquilla.plan_id == plan_id)
        if taquilla_id is not None:
            stmt = stmt.where(Taquilla.id == taquilla_id)
        taquillas = self.session.scalars(
            stmt.order_by(Taquilla.sequence_no, Taquilla.id)
        ).all()
        if taquilla_id is not None and not taquillas:
            raise MaterialsNotFound("taquilla not found in production plan")
        if taquilla_id is not None and taquillas[0].status == "CANCELLED":
            raise MaterialsRule("cancelled taquilla cannot create material demand")

        excluded = [taquilla.id for taquilla in taquillas if taquilla.status == "CANCELLED"]
        active = [taquilla for taquilla in taquillas if taquilla.status != "CANCELLED"]
        if not active:
            raise MaterialsRule("no non-cancelled taquillas in requested scope")

        paths: list[MaterialRequirementPath] = []
        totals: dict[tuple[UUID, UUID], Decimal] = defaultdict(Decimal)
        material_codes: dict[tuple[UUID, UUID], tuple[str, str]] = {}
        line_count = 0

        for taquilla in active:
            product_lines = self.session.scalars(
                select(TaquillaProductLine)
                .where(TaquillaProductLine.taquilla_id == taquilla.id)
                .order_by(TaquillaProductLine.sequence_no, TaquillaProductLine.id)
            ).all()
            if not product_lines:
                raise MaterialsRule(
                    f"taquilla {taquilla.taquilla_code} has no product lines; projection would be incomplete"
                )
            for product_line in product_lines:
                line_count += 1
                product = self.session.get(Article, product_line.article_id)
                if product is None or not product.active:
                    raise MaterialsRule("production line references inactive or missing article")
                bom = self._root_bom(product.id, effective_at)
                try:
                    exploded = self.master.explode_bom(
                        bom.id, root_quantity=product_line.requested_quantity,
                        effective_at=effective_at,
                    )
                except MasterDataRuleError as exc:
                    raise MaterialsRule(str(exc)) from exc
                leaves = [item for item in exploded.paths if item.leaf]
                if not leaves:
                    raise MaterialsRule(
                        f"published BOM {bom.id} has no effective terminal materials"
                    )

                for leaf in leaves:
                    material = self.session.get(Article, leaf.article_id)
                    if material is None or not material.active:
                        raise MaterialsRule("BOM references inactive or unknown terminal article")
                    if material.article_kind not in ("PURCHASED", "CONSUMABLE"):
                        raise MaterialsRule(
                            f"terminal article {material.external_code} is {material.article_kind}, "
                            "not an explicitly purchased/consumable material; complete its BOM"
                        )
                    if leaf.uom_id is None or material.default_uom_id != leaf.uom_id:
                        raise MaterialsRule(
                            f"material {material.external_code} lacks matching canonical component UoM"
                        )
                    uom = self.session.get(UnitOfMeasure, leaf.uom_id)
                    if uom is None or not uom.active or not uom.canonical:
                        raise MaterialsRule("component UoM must be active and canonical")
                    if not leaf.quantity.is_finite() or leaf.quantity <= 0:
                        raise MaterialsRule("invalid BOM explosion quantity")
                    key = (leaf.article_id, leaf.uom_id)
                    paths.append(MaterialRequirementPath(
                        plan_id=plan.id, plan_number=plan.plan_number,
                        taquilla_id=taquilla.id, taquilla_code=taquilla.taquilla_code,
                        taquilla_status=taquilla.status,
                        product_line_id=product_line.id,
                        product_sequence_no=product_line.sequence_no,
                        deck_position=product_line.deck_position,
                        product_article_id=product.id,
                        product_article_code=product.external_code,
                        product_quantity=product_line.requested_quantity,
                        bom_revision_id=bom.id,
                        component_id=leaf.component_id,
                        component_bom_revision_id=leaf.bom_revision_id,
                        path_component_ids=leaf.path_component_ids,
                        path_article_ids=leaf.path_article_ids,
                        material_article_id=material.id,
                        material_article_code=material.external_code,
                        uom_id=uom.id, uom_code=uom.code,
                        theoretical_quantity=leaf.quantity,
                    ))
                    totals[key] += leaf.quantity
                    material_codes[key] = (material.external_code, uom.code)

        aggregate = [
            MaterialRequirementAggregate(
                material_article_id=article_id,
                material_article_code=material_codes[(article_id, uom_id)][0],
                uom_id=uom_id,
                uom_code=material_codes[(article_id, uom_id)][1],
                theoretical_quantity=quantity,
            )
            for (article_id, uom_id), quantity in sorted(
                totals.items(), key=lambda pair: (
                    material_codes[pair[0]][0], material_codes[pair[0]][1], str(pair[0][0])
                )
            )
        ]
        return MaterialDemandProjection(
            scope="TAQUILLA" if taquilla_id else "PLAN",
            scope_id=taquilla_id or plan.id,
            plan_id=plan.id, plan_number=plan.plan_number,
            plan_status=plan.status, effective_at=effective_at,
            excluded_cancelled_taquillas=excluded, source_product_lines=line_count,
            paths=paths, aggregate=aggregate,
        )

    def project_taquilla(self, taquilla_id: UUID, effective_at: datetime) -> MaterialDemandProjection:
        taquilla = self.session.get(Taquilla, taquilla_id)
        if taquilla is None:
            raise MaterialsNotFound("taquilla not found")
        return self.project(taquilla.plan_id, effective_at, taquilla_id=taquilla.id)
