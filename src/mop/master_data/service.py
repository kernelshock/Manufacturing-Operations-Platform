"""Application service for canonical Master Data."""

from collections.abc import Sequence
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.core.models import Area, Plant, Resource, WorkCenter
from mop.master_data.models import (
    Article,
    ArticleRevision,
    BOMComponent,
    BOMRevision,
    CalendarException,
    CalendarWeeklyWindow,
    ManufacturingCalendar,
    ProductConfiguration,
    ResourceAssignment,
    RoutingOperation,
    RoutingRevision,
    Supplier,
    SupplierArticle,
    SupplierSourceMapping,
    UnitOfMeasure,
    UnitOfMeasureAlias,
)
from mop.master_data.schemas import (
    ArticleCreate,
    ArticleRevisionCreate,
    BOMComponentCreate,
    BOMExplosionAggregate,
    BOMExplosionLine,
    BOMExplosionRead,
    BOMRevisionCreate,
    CalendarExceptionCreate,
    CalendarExceptionRead,
    CalendarResolutionRead,
    CalendarWeeklyWindowCreate,
    CalendarWeeklyWindowRead,
    ManufacturingCalendarCreate,
    ManufacturingCalendarRead,
    ResourceAssignmentCreate,
    ResourceAssignmentRead,
    RoutingDefinitionRead,
    RoutingOperationCreate,
    RoutingOperationDefinition,
    RoutingOperationRead,
    RoutingRevisionCreate,
    RoutingRevisionRead,
    ProductConfigurationCreate,
    SupplierArticleCreate,
    SupplierCreate,
    SupplierSourceMappingCreate,
    UnitOfMeasureAliasCreate,
    UnitOfMeasureCreate,
)


class MasterDataConflictError(ValueError):
    pass


class MasterDataRuleError(ValueError):
    pass


class MasterDataNotFoundError(LookupError):
    pass


class MasterDataService:
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
            raise MasterDataConflictError("master-data identity already exists") from exc

    def create_uom(self, data: UnitOfMeasureCreate) -> UnitOfMeasure:
        return self._commit(UnitOfMeasure(**data.model_dump()))

    def list_uoms(self) -> Sequence[UnitOfMeasure]:
        return self.session.scalars(select(UnitOfMeasure).order_by(UnitOfMeasure.code)).all()

    def create_uom_alias(
        self,
        data: UnitOfMeasureAliasCreate,
        approved_by: UUID | None = None,
    ) -> UnitOfMeasureAlias:
        if data.uom_id is not None and self.session.get(UnitOfMeasure, data.uom_id) is None:
            raise MasterDataNotFoundError("unit of measure not found")
        payload = data.model_dump()
        if data.mapping_status == "MAPPED":
            payload["approved_at"] = datetime.now(timezone.utc)
            payload["approved_by"] = approved_by
        return self._commit(UnitOfMeasureAlias(**payload))

    def list_uom_aliases(
        self, source_system: str | None = None
    ) -> Sequence[UnitOfMeasureAlias]:
        query = select(UnitOfMeasureAlias)
        if source_system:
            query = query.where(UnitOfMeasureAlias.source_system == source_system.strip().upper())
        return self.session.scalars(
            query.order_by(UnitOfMeasureAlias.source_system, UnitOfMeasureAlias.raw_value)
        ).all()

    def create_article(self, data: ArticleCreate) -> Article:
        if data.default_uom_id is not None and self.session.get(UnitOfMeasure, data.default_uom_id) is None:
            raise MasterDataNotFoundError("default unit of measure not found")
        return self._commit(Article(**data.model_dump()))

    def list_articles(
        self,
        external_system: str | None = None,
        article_kind: str | None = None,
    ) -> Sequence[Article]:
        query = select(Article)
        if external_system:
            query = query.where(Article.external_system == external_system.strip().upper())
        if article_kind:
            query = query.where(Article.article_kind == article_kind)
        return self.session.scalars(
            query.order_by(Article.external_system, Article.external_code)
        ).all()

    def create_article_revision(
        self,
        article_id: UUID,
        data: ArticleRevisionCreate,
    ) -> ArticleRevision:
        if self.session.get(Article, article_id) is None:
            raise MasterDataNotFoundError("article not found")
        return self._commit(
            ArticleRevision(
                article_id=article_id,
                revision_label=data.revision_label,
                source_fingerprint=data.source_fingerprint,
                valid_from=data.valid_from or datetime.now(timezone.utc),
                valid_to=None,
                status="DRAFT",
                source_batch_id=data.source_batch_id,
                approved_at=None,
                approved_by=None,
            )
        )

    def list_article_revisions(self, article_id: UUID) -> Sequence[ArticleRevision]:
        if self.session.get(Article, article_id) is None:
            raise MasterDataNotFoundError("article not found")
        return self.session.scalars(
            select(ArticleRevision)
            .where(ArticleRevision.article_id == article_id)
            .order_by(ArticleRevision.valid_from.desc())
        ).all()

    def create_product_configuration(
        self,
        data: ProductConfigurationCreate,
    ) -> ProductConfiguration:
        article = self.session.get(Article, data.article_id)
        if article is None:
            raise MasterDataNotFoundError("article not found")
        if article.article_kind != "FINISHED_PRODUCT":
            raise MasterDataRuleError(
                "product configuration requires a FINISHED_PRODUCT article"
            )

        if data.width_uom_id is not None:
            width_uom = self.session.get(UnitOfMeasure, data.width_uom_id)
            if width_uom is None:
                raise MasterDataNotFoundError("width unit of measure not found")
            if (
                width_uom.dimension != "LENGTH"
                or not width_uom.canonical
                or not width_uom.active
            ):
                raise MasterDataRuleError(
                    "width unit must be an active canonical LENGTH unit"
                )

        return self._commit(ProductConfiguration(**data.model_dump()))

    def list_product_configurations(
        self,
        family_code: str | None = None,
        model_code: str | None = None,
        active: bool | None = None,
    ) -> Sequence[ProductConfiguration]:
        query = select(ProductConfiguration)
        if family_code:
            query = query.where(
                ProductConfiguration.family_code == family_code.strip().upper()
            )
        if model_code:
            query = query.where(
                ProductConfiguration.model_code == model_code.strip().upper()
            )
        if active is not None:
            query = query.where(ProductConfiguration.active == active)
        return self.session.scalars(
            query.order_by(
                ProductConfiguration.family_code,
                ProductConfiguration.model_code,
                ProductConfiguration.configuration_string,
            )
        ).all()

    def get_product_configuration(self, article_id: UUID) -> ProductConfiguration:
        if self.session.get(Article, article_id) is None:
            raise MasterDataNotFoundError("article not found")
        configuration = self.session.scalar(
            select(ProductConfiguration).where(
                ProductConfiguration.article_id == article_id
            )
        )
        if configuration is None:
            raise MasterDataNotFoundError("product configuration not found")
        return configuration

    def create_supplier(self, data: SupplierCreate) -> Supplier:
        return self._commit(Supplier(**data.model_dump()))

    def list_suppliers(
        self,
        supply_category: str | None = None,
        active: bool | None = None,
    ) -> Sequence[Supplier]:
        query = select(Supplier)
        if supply_category:
            query = query.where(Supplier.supply_category == supply_category)
        if active is not None:
            query = query.where(Supplier.active == active)
        return self.session.scalars(query.order_by(Supplier.code)).all()

    def create_supplier_source_mapping(
        self,
        data: SupplierSourceMappingCreate,
        approved_by: UUID | None = None,
    ) -> SupplierSourceMapping:
        if data.supplier_id is not None and self.session.get(Supplier, data.supplier_id) is None:
            raise MasterDataNotFoundError("supplier not found")

        payload = data.model_dump()
        if data.mapping_status == "MAPPED":
            payload["approved_at"] = datetime.now(timezone.utc)
            payload["approved_by"] = approved_by
        return self._commit(SupplierSourceMapping(**payload))

    def list_supplier_source_mappings(
        self,
        external_system: str | None = None,
        mapping_status: str | None = None,
    ) -> Sequence[SupplierSourceMapping]:
        query = select(SupplierSourceMapping)
        if external_system:
            query = query.where(
                SupplierSourceMapping.external_system == external_system.strip().upper()
            )
        if mapping_status:
            query = query.where(SupplierSourceMapping.mapping_status == mapping_status)
        return self.session.scalars(
            query.order_by(
                SupplierSourceMapping.external_system,
                SupplierSourceMapping.external_code,
            )
        ).all()

    def create_supplier_article(
        self,
        data: SupplierArticleCreate,
    ) -> SupplierArticle:
        if self.session.get(Supplier, data.supplier_id) is None:
            raise MasterDataNotFoundError("supplier not found")
        if self.session.get(Article, data.article_id) is None:
            raise MasterDataNotFoundError("article not found")

        if data.order_uom_id is not None:
            order_uom = self.session.get(UnitOfMeasure, data.order_uom_id)
            if order_uom is None:
                raise MasterDataNotFoundError("order unit of measure not found")
            if not order_uom.canonical or not order_uom.active:
                raise MasterDataRuleError(
                    "order unit must be an active canonical unit of measure"
                )

        return self._commit(SupplierArticle(**data.model_dump()))

    def list_supplier_articles(
        self,
        supplier_id: UUID | None = None,
        article_id: UUID | None = None,
        active: bool | None = None,
    ) -> Sequence[SupplierArticle]:
        query = select(SupplierArticle)
        if supplier_id is not None:
            query = query.where(SupplierArticle.supplier_id == supplier_id)
        if article_id is not None:
            query = query.where(SupplierArticle.article_id == article_id)
        if active is not None:
            query = query.where(SupplierArticle.active == active)
        return self.session.scalars(
            query.order_by(SupplierArticle.supplier_id, SupplierArticle.article_id)
        ).all()



    def create_bom_revision(self, data: BOMRevisionCreate) -> BOMRevision:
        parent_revision = self.session.get(
            ArticleRevision, data.parent_article_revision_id
        )
        if parent_revision is None:
            raise MasterDataNotFoundError("parent article revision not found")

        valid_from = data.valid_from or datetime.now(timezone.utc)
        if data.valid_to is not None and data.valid_to <= valid_from:
            raise MasterDataRuleError("valid_to must be later than valid_from")

        return self._commit(
            BOMRevision(
                parent_article_revision_id=data.parent_article_revision_id,
                revision_no=data.revision_no,
                valid_from=valid_from,
                valid_to=data.valid_to,
                status="DRAFT",
                source_system=data.source_system,
                source_batch_id=data.source_batch_id,
                source_fingerprint=data.source_fingerprint,
            )
        )

    def list_bom_revisions(
        self,
        parent_article_revision_id: UUID | None = None,
        status: str | None = None,
    ) -> Sequence[BOMRevision]:
        query = select(BOMRevision)
        if parent_article_revision_id is not None:
            query = query.where(
                BOMRevision.parent_article_revision_id
                == parent_article_revision_id
            )
        if status:
            query = query.where(BOMRevision.status == status)
        return self.session.scalars(
            query.order_by(
                BOMRevision.parent_article_revision_id,
                BOMRevision.revision_no,
            )
        ).all()

    def add_bom_component(
        self,
        bom_revision_id: UUID,
        data: BOMComponentCreate,
    ) -> BOMComponent:
        bom = self.session.get(BOMRevision, bom_revision_id)
        if bom is None:
            raise MasterDataNotFoundError("BOM revision not found")
        if bom.status != "DRAFT":
            raise MasterDataRuleError(
                "components can only be added to a DRAFT BOM revision"
            )

        parent_revision = self.session.get(
            ArticleRevision, bom.parent_article_revision_id
        )
        if parent_revision is None:
            raise MasterDataNotFoundError("parent article revision not found")

        child = self.session.get(Article, data.child_article_id)
        if child is None:
            raise MasterDataNotFoundError("child article not found")
        if child.id == parent_revision.article_id:
            raise MasterDataRuleError("BOM cannot directly contain its parent article")

        if data.child_revision_id is not None:
            child_revision = self.session.get(
                ArticleRevision, data.child_revision_id
            )
            if child_revision is None:
                raise MasterDataNotFoundError("child article revision not found")
            if child_revision.article_id != data.child_article_id:
                raise MasterDataRuleError(
                    "child_revision_id does not belong to child_article_id"
                )

        if data.uom_id is not None:
            uom = self.session.get(UnitOfMeasure, data.uom_id)
            if uom is None:
                raise MasterDataNotFoundError("component unit of measure not found")
            if not uom.canonical or not uom.active:
                raise MasterDataRuleError(
                    "component unit must be an active canonical unit of measure"
                )

        return self._commit(
            BOMComponent(
                bom_revision_id=bom_revision_id,
                **data.model_dump(),
            )
        )

    def list_bom_components(
        self,
        bom_revision_id: UUID,
    ) -> Sequence[BOMComponent]:
        if self.session.get(BOMRevision, bom_revision_id) is None:
            raise MasterDataNotFoundError("BOM revision not found")
        return self.session.scalars(
            select(BOMComponent)
            .where(BOMComponent.bom_revision_id == bom_revision_id)
            .order_by(
                BOMComponent.sequence_no.asc().nullslast(),
                BOMComponent.created_at,
                BOMComponent.id,
            )
        ).all()

    @staticmethod
    def _window_contains(
        valid_from: datetime,
        valid_to: datetime | None,
        at: datetime,
    ) -> bool:
        return valid_from <= at and (valid_to is None or at < valid_to)

    @staticmethod
    def _windows_overlap(
        first_from: datetime,
        first_to: datetime | None,
        second_from: datetime,
        second_to: datetime | None,
    ) -> bool:
        first_end = first_to or datetime.max.replace(tzinfo=timezone.utc)
        second_end = second_to or datetime.max.replace(tzinfo=timezone.utc)
        return first_from < second_end and second_from < first_end

    def _components_effective_at(
        self,
        bom_revision_id: UUID,
        at: datetime,
    ) -> list[BOMComponent]:
        components = self.session.scalars(
            select(BOMComponent)
            .where(BOMComponent.bom_revision_id == bom_revision_id)
            .order_by(
                BOMComponent.sequence_no.asc().nullslast(),
                BOMComponent.created_at,
                BOMComponent.id,
            )
        ).all()
        return [
            component
            for component in components
            if (
                component.effective_from is None
                or component.effective_from <= at
            )
            and (
                component.effective_to is None
                or at < component.effective_to
            )
        ]

    def _parent_article(self, bom: BOMRevision) -> Article:
        revision = self.session.get(
            ArticleRevision, bom.parent_article_revision_id
        )
        if revision is None:
            raise MasterDataNotFoundError("parent article revision not found")
        article = self.session.get(Article, revision.article_id)
        if article is None:
            raise MasterDataNotFoundError("parent article not found")
        return article

    def _effective_child_bom(
        self,
        *,
        child_article_id: UUID,
        child_revision_id: UUID | None,
        at: datetime,
    ) -> BOMRevision | None:
        query = select(BOMRevision).where(BOMRevision.status == "ACTIVE")
        if child_revision_id is not None:
            query = query.where(
                BOMRevision.parent_article_revision_id == child_revision_id
            )
        else:
            revision_ids = self.session.scalars(
                select(ArticleRevision.id).where(
                    ArticleRevision.article_id == child_article_id
                )
            ).all()
            if not revision_ids:
                return None
            query = query.where(
                BOMRevision.parent_article_revision_id.in_(revision_ids)
            )

        candidates = [
            bom
            for bom in self.session.scalars(query).all()
            if self._window_contains(bom.valid_from, bom.valid_to, at)
        ]
        if len(candidates) > 1:
            raise MasterDataRuleError(
                "multiple effective active BOM revisions found; "
                "pin child_revision_id to remove ambiguity"
            )
        return candidates[0] if candidates else None

    def _validate_cycle_from_bom(
        self,
        bom: BOMRevision,
        *,
        at: datetime,
        article_path: tuple[UUID, ...],
    ) -> None:
        parent_article = self._parent_article(bom)
        if parent_article.id in article_path:
            raise MasterDataRuleError("BOM cycle detected")

        next_path = article_path + (parent_article.id,)
        for component in self._components_effective_at(bom.id, at):
            if component.child_article_id in next_path:
                raise MasterDataRuleError("BOM cycle detected")
            child_bom = self._effective_child_bom(
                child_article_id=component.child_article_id,
                child_revision_id=component.child_revision_id,
                at=at,
            )
            if child_bom is not None:
                self._validate_cycle_from_bom(
                    child_bom,
                    at=at,
                    article_path=next_path,
                )

    def _assert_publishable(self, bom: BOMRevision, at: datetime) -> None:
        components = self._components_effective_at(bom.id, at)
        if not components:
            raise MasterDataRuleError(
                "BOM revision requires at least one effective component"
            )

        active_for_parent = self.session.scalars(
            select(BOMRevision).where(
                BOMRevision.parent_article_revision_id
                == bom.parent_article_revision_id,
                BOMRevision.status == "ACTIVE",
                BOMRevision.id != bom.id,
            )
        ).all()
        if any(
            self._windows_overlap(
                existing.valid_from,
                existing.valid_to,
                bom.valid_from,
                bom.valid_to,
            )
            for existing in active_for_parent
        ):
            raise MasterDataRuleError(
                "an overlapping ACTIVE BOM already exists for this article revision"
            )

        self._validate_cycle_from_bom(
            bom,
            at=at,
            article_path=(),
        )

    def publish_bom_revision(self, bom_revision_id: UUID) -> BOMRevision:
        bom = self.session.get(BOMRevision, bom_revision_id)
        if bom is None:
            raise MasterDataNotFoundError("BOM revision not found")
        if bom.status != "DRAFT":
            raise MasterDataRuleError("only a DRAFT BOM revision can be published")

        at = max(datetime.now(timezone.utc), bom.valid_from)
        self._assert_publishable(bom, at)
        bom.status = "ACTIVE"
        return self._commit(bom)

    def supersede_bom_revision(
        self,
        active_bom_revision_id: UUID,
        replacement_bom_revision_id: UUID,
        effective_at: datetime | None = None,
    ) -> tuple[BOMRevision, BOMRevision]:
        active = self.session.get(BOMRevision, active_bom_revision_id)
        replacement = self.session.get(BOMRevision, replacement_bom_revision_id)
        if active is None or replacement is None:
            raise MasterDataNotFoundError("BOM revision not found")
        if active.status != "ACTIVE":
            raise MasterDataRuleError("current BOM revision is not ACTIVE")
        if replacement.status != "DRAFT":
            raise MasterDataRuleError("replacement BOM revision must be DRAFT")

        active_parent = self._parent_article(active)
        replacement_parent = self._parent_article(replacement)
        if active_parent.id != replacement_parent.id:
            raise MasterDataRuleError(
                "replacement BOM must belong to the same parent article"
            )

        at = effective_at or datetime.now(timezone.utc)
        if at <= active.valid_from:
            raise MasterDataRuleError(
                "supersede effective_at must be later than current valid_from"
            )
        if replacement.valid_to is not None and replacement.valid_to <= at:
            raise MasterDataRuleError(
                "replacement valid_to must be later than supersede effective_at"
            )

        replacement.valid_from = at
        self._assert_publishable(replacement, at)

        active.valid_to = at
        active.status = "SUPERSEDED"
        replacement.status = "ACTIVE"

        try:
            self.session.add_all([active, replacement])
            self.session.commit()
            self.session.refresh(active)
            self.session.refresh(replacement)
        except IntegrityError as exc:
            self.session.rollback()
            raise MasterDataConflictError(
                "BOM supersede operation conflicts with existing master data"
            ) from exc
        return active, replacement

    def explode_bom(
        self,
        bom_revision_id: UUID,
        root_quantity: Decimal = Decimal("1"),
        effective_at: datetime | None = None,
    ) -> BOMExplosionRead:
        if root_quantity <= 0:
            raise MasterDataRuleError("root quantity must be greater than zero")

        root = self.session.get(BOMRevision, bom_revision_id)
        if root is None:
            raise MasterDataNotFoundError("BOM revision not found")
        if root.status != "ACTIVE":
            raise MasterDataRuleError("only an ACTIVE BOM revision can be exploded")

        at = effective_at or datetime.now(timezone.utc)
        if not self._window_contains(root.valid_from, root.valid_to, at):
            raise MasterDataRuleError(
                "BOM revision is not effective at the requested timestamp"
            )

        root_article = self._parent_article(root)
        lines: list[BOMExplosionLine] = []

        def walk(
            bom: BOMRevision,
            multiplier: Decimal,
            article_ids: list[UUID],
            article_codes: list[str],
            component_ids: list[UUID],
        ) -> None:
            for component in self._components_effective_at(bom.id, at):
                child = self.session.get(Article, component.child_article_id)
                if child is None:
                    raise MasterDataNotFoundError("child article not found")
                if child.id in article_ids:
                    raise MasterDataRuleError("BOM cycle detected during explosion")

                scrap_multiplier = (
                    Decimal("1") + component.scrap_factor
                    if component.scrap_factor is not None
                    else Decimal("1")
                )
                quantity = multiplier * component.quantity * scrap_multiplier

                child_bom = self._effective_child_bom(
                    child_article_id=component.child_article_id,
                    child_revision_id=component.child_revision_id,
                    at=at,
                )
                next_article_ids = [*article_ids, child.id]
                next_article_codes = [*article_codes, child.external_code]
                next_component_ids = [*component_ids, component.id]

                lines.append(
                    BOMExplosionLine(
                        component_id=component.id,
                        bom_revision_id=bom.id,
                        article_id=child.id,
                        article_code=child.external_code,
                        quantity=quantity,
                        uom_id=component.uom_id,
                        source_uom_raw=component.source_uom_raw,
                        depth=len(next_component_ids),
                        leaf=child_bom is None,
                        path_article_ids=next_article_ids,
                        path_article_codes=next_article_codes,
                        path_component_ids=next_component_ids,
                    )
                )

                if child_bom is not None:
                    walk(
                        child_bom,
                        quantity,
                        next_article_ids,
                        next_article_codes,
                        next_component_ids,
                    )

        walk(
            root,
            root_quantity,
            [root_article.id],
            [root_article.external_code],
            [],
        )

        aggregated: dict[
            tuple[UUID, UUID | None, str], BOMExplosionAggregate
        ] = {}
        for line in lines:
            key = (line.article_id, line.uom_id, line.source_uom_raw)
            existing = aggregated.get(key)
            if existing is None:
                aggregated[key] = BOMExplosionAggregate(
                    article_id=line.article_id,
                    article_code=line.article_code,
                    quantity=line.quantity,
                    uom_id=line.uom_id,
                    source_uom_raw=line.source_uom_raw,
                )
            else:
                existing.quantity += line.quantity

        return BOMExplosionRead(
            root_bom_revision_id=root.id,
            root_quantity=root_quantity,
            effective_at=at,
            paths=lines,
            aggregate=sorted(
                aggregated.values(),
                key=lambda item: (
                    item.article_code,
                    str(item.uom_id or ""),
                    item.source_uom_raw,
                ),
            ),
        )


    def create_routing_revision(
        self,
        data: RoutingRevisionCreate,
    ) -> RoutingRevision:
        if self.session.get(ArticleRevision, data.article_revision_id) is None:
            raise MasterDataNotFoundError("article revision not found")

        valid_from = data.valid_from or datetime.now(timezone.utc)
        if data.valid_to is not None and data.valid_to <= valid_from:
            raise MasterDataRuleError("valid_to must be later than valid_from")

        return self._commit(
            RoutingRevision(
                article_revision_id=data.article_revision_id,
                revision_no=data.revision_no,
                valid_from=valid_from,
                valid_to=data.valid_to,
                status="DRAFT",
                source_system=data.source_system,
                source_batch_id=data.source_batch_id,
                source_fingerprint=data.source_fingerprint,
            )
        )

    def list_routing_revisions(
        self,
        article_revision_id: UUID | None = None,
        status: str | None = None,
    ) -> Sequence[RoutingRevision]:
        query = select(RoutingRevision)
        if article_revision_id is not None:
            query = query.where(
                RoutingRevision.article_revision_id == article_revision_id
            )
        if status:
            query = query.where(RoutingRevision.status == status)
        return self.session.scalars(
            query.order_by(
                RoutingRevision.article_revision_id,
                RoutingRevision.revision_no,
            )
        ).all()

    def add_routing_operation(
        self,
        routing_revision_id: UUID,
        data: RoutingOperationCreate,
    ) -> RoutingOperation:
        routing = self.session.get(RoutingRevision, routing_revision_id)
        if routing is None:
            raise MasterDataNotFoundError("routing revision not found")
        if routing.status != "DRAFT":
            raise MasterDataRuleError(
                "operations can only be added to a DRAFT routing revision"
            )

        area_id = data.area_id
        work_center_id = data.work_center_id

        if area_id is not None:
            area = self.session.get(Area, area_id)
            if area is None:
                raise MasterDataNotFoundError("area not found")
            if not area.active:
                raise MasterDataRuleError("routing area must be active")

        if work_center_id is not None:
            work_center = self.session.get(WorkCenter, work_center_id)
            if work_center is None:
                raise MasterDataNotFoundError("work center not found")
            if not work_center.active:
                raise MasterDataRuleError("routing work center must be active")
            if area_id is None:
                area_id = work_center.area_id
            elif work_center.area_id != area_id:
                raise MasterDataRuleError(
                    "work center does not belong to routing area"
                )

        payload = data.model_dump()
        payload["area_id"] = area_id
        payload["work_center_id"] = work_center_id
        return self._commit(
            RoutingOperation(
                routing_revision_id=routing_revision_id,
                **payload,
            )
        )

    def list_routing_operations(
        self,
        routing_revision_id: UUID,
    ) -> Sequence[RoutingOperation]:
        if self.session.get(RoutingRevision, routing_revision_id) is None:
            raise MasterDataNotFoundError("routing revision not found")
        return self.session.scalars(
            select(RoutingOperation)
            .where(
                RoutingOperation.routing_revision_id == routing_revision_id
            )
            .order_by(RoutingOperation.sequence_no)
        ).all()

    def add_resource_assignment(
        self,
        routing_operation_id: UUID,
        data: ResourceAssignmentCreate,
    ) -> ResourceAssignment:
        operation = self.session.get(RoutingOperation, routing_operation_id)
        if operation is None:
            raise MasterDataNotFoundError("routing operation not found")

        routing = self.session.get(
            RoutingRevision, operation.routing_revision_id
        )
        if routing is None:
            raise MasterDataNotFoundError("routing revision not found")
        if routing.status != "DRAFT":
            raise MasterDataRuleError(
                "resources can only be assigned to a DRAFT routing revision"
            )
        if operation.completion_marker:
            raise MasterDataRuleError(
                "completion marker cannot have resource assignments"
            )

        resource = self.session.get(Resource, data.resource_id)
        if resource is None:
            raise MasterDataNotFoundError("resource not found")
        if not resource.active:
            raise MasterDataRuleError("routing resource must be active")

        work_center = self.session.get(
            WorkCenter, resource.work_center_id
        )
        if work_center is None:
            raise MasterDataNotFoundError("resource work center not found")
        if not work_center.active:
            raise MasterDataRuleError("resource work center must be active")

        if (
            operation.work_center_id is not None
            and operation.work_center_id != resource.work_center_id
        ):
            raise MasterDataRuleError(
                "resource does not belong to routing work center"
            )
        if (
            operation.area_id is not None
            and operation.area_id != work_center.area_id
        ):
            raise MasterDataRuleError(
                "resource does not belong to routing area"
            )

        if data.principal:
            existing_principal = self.session.scalar(
                select(ResourceAssignment).where(
                    ResourceAssignment.routing_operation_id
                    == routing_operation_id,
                    ResourceAssignment.principal.is_(True),
                )
            )
            if existing_principal is not None:
                raise MasterDataRuleError(
                    "routing operation already has a principal resource"
                )

        return self._commit(
            ResourceAssignment(
                routing_operation_id=routing_operation_id,
                **data.model_dump(),
            )
        )

    def list_resource_assignments(
        self,
        routing_operation_id: UUID,
    ) -> Sequence[ResourceAssignment]:
        if self.session.get(RoutingOperation, routing_operation_id) is None:
            raise MasterDataNotFoundError("routing operation not found")
        return self.session.scalars(
            select(ResourceAssignment)
            .where(
                ResourceAssignment.routing_operation_id
                == routing_operation_id
            )
            .order_by(
                ResourceAssignment.principal.desc(),
                ResourceAssignment.created_at,
                ResourceAssignment.id,
            )
        ).all()

    def _routing_parent_article(self, routing: RoutingRevision) -> Article:
        revision = self.session.get(
            ArticleRevision, routing.article_revision_id
        )
        if revision is None:
            raise MasterDataNotFoundError("article revision not found")
        article = self.session.get(Article, revision.article_id)
        if article is None:
            raise MasterDataNotFoundError("article not found")
        return article

    def _assert_routing_publishable(
        self,
        routing: RoutingRevision,
    ) -> None:
        operations = list(self.list_routing_operations(routing.id))
        active_operations = [operation for operation in operations if operation.active]
        if not active_operations:
            raise MasterDataRuleError(
                "routing revision requires at least one active operation"
            )

        completion_markers = [
            operation
            for operation in active_operations
            if operation.completion_marker
        ]
        if len(completion_markers) > 1:
            raise MasterDataRuleError(
                "routing revision cannot have multiple completion markers"
            )

        for operation in active_operations:
            if operation.completion_marker:
                continue

            assignments = list(
                self.list_resource_assignments(operation.id)
            )
            for assignment in assignments:
                resource = self.session.get(Resource, assignment.resource_id)
                if resource is None:
                    raise MasterDataNotFoundError("resource not found")
                if not resource.active:
                    raise MasterDataRuleError(
                        "routing resource must be active at publication"
                    )

            if operation.schedulable:
                if (
                    operation.work_center_id is None
                    and not assignments
                ):
                    raise MasterDataRuleError(
                        "schedulable operation requires a work center "
                        "or resource assignment"
                    )

        active_for_revision = self.session.scalars(
            select(RoutingRevision).where(
                RoutingRevision.article_revision_id
                == routing.article_revision_id,
                RoutingRevision.status == "ACTIVE",
                RoutingRevision.id != routing.id,
            )
        ).all()
        if any(
            self._windows_overlap(
                existing.valid_from,
                existing.valid_to,
                routing.valid_from,
                routing.valid_to,
            )
            for existing in active_for_revision
        ):
            raise MasterDataRuleError(
                "an overlapping ACTIVE routing already exists "
                "for this article revision"
            )

    def publish_routing_revision(
        self,
        routing_revision_id: UUID,
    ) -> RoutingRevision:
        routing = self.session.get(RoutingRevision, routing_revision_id)
        if routing is None:
            raise MasterDataNotFoundError("routing revision not found")
        if routing.status != "DRAFT":
            raise MasterDataRuleError(
                "only a DRAFT routing revision can be published"
            )

        self._assert_routing_publishable(routing)
        routing.status = "ACTIVE"
        return self._commit(routing)

    def supersede_routing_revision(
        self,
        active_routing_revision_id: UUID,
        replacement_routing_revision_id: UUID,
        effective_at: datetime | None = None,
    ) -> tuple[RoutingRevision, RoutingRevision]:
        active = self.session.get(
            RoutingRevision, active_routing_revision_id
        )
        replacement = self.session.get(
            RoutingRevision, replacement_routing_revision_id
        )
        if active is None or replacement is None:
            raise MasterDataNotFoundError("routing revision not found")
        if active.status != "ACTIVE":
            raise MasterDataRuleError("current routing revision is not ACTIVE")
        if replacement.status != "DRAFT":
            raise MasterDataRuleError(
                "replacement routing revision must be DRAFT"
            )

        active_parent = self._routing_parent_article(active)
        replacement_parent = self._routing_parent_article(replacement)
        if active_parent.id != replacement_parent.id:
            raise MasterDataRuleError(
                "replacement routing must belong to the same article"
            )

        at = effective_at or datetime.now(timezone.utc)
        if at <= active.valid_from:
            raise MasterDataRuleError(
                "supersede effective_at must be later than current valid_from"
            )
        if replacement.valid_to is not None and replacement.valid_to <= at:
            raise MasterDataRuleError(
                "replacement valid_to must be later than supersede effective_at"
            )

        replacement.valid_from = at
        self._assert_routing_publishable(replacement)

        active.valid_to = at
        active.status = "SUPERSEDED"
        replacement.status = "ACTIVE"

        try:
            self.session.add_all([active, replacement])
            self.session.commit()
            self.session.refresh(active)
            self.session.refresh(replacement)
        except IntegrityError as exc:
            self.session.rollback()
            raise MasterDataConflictError(
                "routing supersede operation conflicts with existing master data"
            ) from exc
        return active, replacement

    def get_effective_routing(
        self,
        article_revision_id: UUID,
        effective_at: datetime | None = None,
    ) -> RoutingRevision:
        if self.session.get(ArticleRevision, article_revision_id) is None:
            raise MasterDataNotFoundError("article revision not found")

        at = effective_at or datetime.now(timezone.utc)
        candidates = [
            routing
            for routing in self.session.scalars(
                select(RoutingRevision).where(
                    RoutingRevision.article_revision_id
                    == article_revision_id,
                    RoutingRevision.status == "ACTIVE",
                )
            ).all()
            if self._window_contains(
                routing.valid_from,
                routing.valid_to,
                at,
            )
        ]
        if not candidates:
            raise MasterDataNotFoundError(
                "effective routing revision not found"
            )
        if len(candidates) > 1:
            raise MasterDataRuleError(
                "multiple effective active routing revisions found"
            )
        return candidates[0]

    def get_routing_definition(
        self,
        routing_revision_id: UUID,
    ) -> RoutingDefinitionRead:
        routing = self.session.get(RoutingRevision, routing_revision_id)
        if routing is None:
            raise MasterDataNotFoundError("routing revision not found")

        definitions = []
        for operation in self.list_routing_operations(routing_revision_id):
            definitions.append(
                RoutingOperationDefinition(
                    operation=RoutingOperationRead.model_validate(operation),
                    resources=[
                        ResourceAssignmentRead.model_validate(assignment)
                        for assignment in self.list_resource_assignments(
                            operation.id
                        )
                    ],
                )
            )

        return RoutingDefinitionRead(
            routing=RoutingRevisionRead.model_validate(routing),
            operations=definitions,
        )


    @staticmethod
    def _calendar_target(
        calendar: ManufacturingCalendar,
    ) -> tuple[str, UUID]:
        if calendar.resource_id is not None:
            return "resource", calendar.resource_id
        if calendar.work_center_id is not None:
            return "work_center", calendar.work_center_id
        if calendar.area_id is not None:
            return "area", calendar.area_id
        if calendar.plant_id is not None:
            return "plant", calendar.plant_id
        raise MasterDataRuleError("calendar has no target")

    @staticmethod
    def _date_window_contains(
        valid_from: date,
        valid_to: date | None,
        at: date,
    ) -> bool:
        return valid_from <= at and (valid_to is None or at < valid_to)

    @staticmethod
    def _date_windows_overlap(
        first_from: date,
        first_to: date | None,
        second_from: date,
        second_to: date | None,
    ) -> bool:
        date_max = date.max
        return (
            first_from < (second_to or date_max)
            and second_from < (first_to or date_max)
        )

    def _validate_calendar_target(
        self,
        data: ManufacturingCalendarCreate,
    ) -> tuple[str, UUID]:
        if data.resource_id is not None:
            target = self.session.get(Resource, data.resource_id)
            if target is None:
                raise MasterDataNotFoundError("calendar resource not found")
            if not target.active:
                raise MasterDataRuleError("calendar resource must be active")
            return "resource", target.id

        if data.work_center_id is not None:
            target = self.session.get(WorkCenter, data.work_center_id)
            if target is None:
                raise MasterDataNotFoundError("calendar work center not found")
            if not target.active:
                raise MasterDataRuleError(
                    "calendar work center must be active"
                )
            return "work_center", target.id

        if data.area_id is not None:
            target = self.session.get(Area, data.area_id)
            if target is None:
                raise MasterDataNotFoundError("calendar area not found")
            if not target.active:
                raise MasterDataRuleError("calendar area must be active")
            return "area", target.id

        if data.plant_id is not None:
            target = self.session.get(Plant, data.plant_id)
            if target is None:
                raise MasterDataNotFoundError("calendar plant not found")
            if not target.active:
                raise MasterDataRuleError("calendar plant must be active")
            return "plant", target.id

        raise MasterDataRuleError("calendar target is required")

    def create_manufacturing_calendar(
        self,
        data: ManufacturingCalendarCreate,
    ) -> ManufacturingCalendar:
        target_scope, target_id = self._validate_calendar_target(data)

        existing_versions = self.session.scalars(
            select(ManufacturingCalendar).where(
                ManufacturingCalendar.code == data.code
            )
        ).all()
        for existing in existing_versions:
            existing_scope, existing_target_id = self._calendar_target(existing)
            if (
                existing_scope != target_scope
                or existing_target_id != target_id
            ):
                raise MasterDataRuleError(
                    "calendar code cannot change target across revisions"
                )
            if existing.timezone != data.timezone:
                raise MasterDataRuleError(
                    "calendar code cannot change timezone across revisions"
                )

        return self._commit(
            ManufacturingCalendar(
                **data.model_dump(),
                status="DRAFT",
            )
        )

    def list_manufacturing_calendars(
        self,
        code: str | None = None,
        status: str | None = None,
    ) -> Sequence[ManufacturingCalendar]:
        query = select(ManufacturingCalendar)
        if code:
            query = query.where(
                ManufacturingCalendar.code == code.strip().upper()
            )
        if status:
            query = query.where(
                ManufacturingCalendar.status == status
            )
        return self.session.scalars(
            query.order_by(
                ManufacturingCalendar.code,
                ManufacturingCalendar.revision_no,
            )
        ).all()

    @staticmethod
    def _weekly_ranges(
        weekday: int,
        start_minute: int,
        end_minute: int,
        spans_midnight: bool,
    ) -> list[tuple[int, int]]:
        start = weekday * 1440 + start_minute
        if not spans_midnight:
            return [(start, weekday * 1440 + end_minute)]

        end = (weekday + 1) * 1440 + end_minute
        week_minutes = 7 * 1440
        if end <= week_minutes:
            return [(start, end)]
        return [(start, week_minutes), (0, end - week_minutes)]

    @classmethod
    def _weekly_windows_overlap(
        cls,
        first: CalendarWeeklyWindowCreate,
        second: CalendarWeeklyWindow,
    ) -> bool:
        first_ranges = cls._weekly_ranges(
            first.weekday,
            first.start_minute,
            first.end_minute,
            first.spans_midnight,
        )
        second_ranges = cls._weekly_ranges(
            second.weekday,
            second.start_minute,
            second.end_minute,
            second.spans_midnight,
        )
        return any(
            first_start < second_end and second_start < first_end
            for first_start, first_end in first_ranges
            for second_start, second_end in second_ranges
        )

    def add_calendar_weekly_window(
        self,
        calendar_id: UUID,
        data: CalendarWeeklyWindowCreate,
    ) -> CalendarWeeklyWindow:
        calendar = self.session.get(ManufacturingCalendar, calendar_id)
        if calendar is None:
            raise MasterDataNotFoundError(
                "manufacturing calendar not found"
            )
        if calendar.status != "DRAFT":
            raise MasterDataRuleError(
                "weekly windows can only be added to a DRAFT calendar"
            )

        existing = self.session.scalars(
            select(CalendarWeeklyWindow).where(
                CalendarWeeklyWindow.calendar_id == calendar_id,
                CalendarWeeklyWindow.active.is_(True),
            )
        ).all()
        if data.active and any(
            self._weekly_windows_overlap(data, window)
            for window in existing
        ):
            raise MasterDataRuleError(
                "calendar weekly windows cannot overlap"
            )

        return self._commit(
            CalendarWeeklyWindow(
                calendar_id=calendar_id,
                **data.model_dump(),
            )
        )

    def list_calendar_weekly_windows(
        self,
        calendar_id: UUID,
    ) -> Sequence[CalendarWeeklyWindow]:
        if self.session.get(ManufacturingCalendar, calendar_id) is None:
            raise MasterDataNotFoundError(
                "manufacturing calendar not found"
            )
        return self.session.scalars(
            select(CalendarWeeklyWindow)
            .where(CalendarWeeklyWindow.calendar_id == calendar_id)
            .order_by(
                CalendarWeeklyWindow.weekday,
                CalendarWeeklyWindow.start_minute,
            )
        ).all()

    @staticmethod
    def _exception_interval(
        exception: CalendarException | CalendarExceptionCreate,
    ) -> tuple[int, int]:
        if exception.start_minute is None:
            return 0, 1440
        assert exception.end_minute is not None
        return exception.start_minute, exception.end_minute

    def add_calendar_exception(
        self,
        calendar_id: UUID,
        data: CalendarExceptionCreate,
    ) -> CalendarException:
        calendar = self.session.get(ManufacturingCalendar, calendar_id)
        if calendar is None:
            raise MasterDataNotFoundError(
                "manufacturing calendar not found"
            )
        if calendar.status != "DRAFT":
            raise MasterDataRuleError(
                "exceptions can only be added to a DRAFT calendar"
            )

        existing = self.session.scalars(
            select(CalendarException).where(
                CalendarException.calendar_id == calendar_id,
                CalendarException.local_date == data.local_date,
                CalendarException.active.is_(True),
            )
        ).all()
        new_start, new_end = self._exception_interval(data)
        if data.active and any(
            (
                new_start < self._exception_interval(item)[1]
                and self._exception_interval(item)[0] < new_end
            )
            for item in existing
        ):
            raise MasterDataRuleError(
                "calendar exceptions cannot overlap on the same local date"
            )

        return self._commit(
            CalendarException(
                calendar_id=calendar_id,
                **data.model_dump(),
            )
        )

    def list_calendar_exceptions(
        self,
        calendar_id: UUID,
    ) -> Sequence[CalendarException]:
        if self.session.get(ManufacturingCalendar, calendar_id) is None:
            raise MasterDataNotFoundError(
                "manufacturing calendar not found"
            )
        return self.session.scalars(
            select(CalendarException)
            .where(CalendarException.calendar_id == calendar_id)
            .order_by(
                CalendarException.local_date,
                CalendarException.start_minute.asc().nullsfirst(),
            )
        ).all()

    def _assert_calendar_publishable(
        self,
        calendar: ManufacturingCalendar,
        ignore_calendar_id: UUID | None = None,
    ) -> None:
        windows = self.session.scalars(
            select(CalendarWeeklyWindow).where(
                CalendarWeeklyWindow.calendar_id == calendar.id,
                CalendarWeeklyWindow.active.is_(True),
            )
        ).all()
        exceptions = self.session.scalars(
            select(CalendarException).where(
                CalendarException.calendar_id == calendar.id,
                CalendarException.active.is_(True),
            )
        ).all()
        if not windows and not exceptions:
            raise MasterDataRuleError(
                "manufacturing calendar requires at least one availability rule"
            )

        target_scope, target_id = self._calendar_target(calendar)
        active_calendars = self.session.scalars(
            select(ManufacturingCalendar).where(
                ManufacturingCalendar.status == "ACTIVE",
                ManufacturingCalendar.id != calendar.id,
            )
        ).all()
        for existing in active_calendars:
            if existing.id == ignore_calendar_id:
                continue
            existing_scope, existing_target_id = self._calendar_target(existing)
            if (
                existing_scope == target_scope
                and existing_target_id == target_id
                and self._date_windows_overlap(
                    existing.valid_from,
                    existing.valid_to,
                    calendar.valid_from,
                    calendar.valid_to,
                )
            ):
                raise MasterDataRuleError(
                    "an overlapping ACTIVE calendar already exists "
                    "for this target"
                )

    def publish_manufacturing_calendar(
        self,
        calendar_id: UUID,
    ) -> ManufacturingCalendar:
        calendar = self.session.get(ManufacturingCalendar, calendar_id)
        if calendar is None:
            raise MasterDataNotFoundError(
                "manufacturing calendar not found"
            )
        if calendar.status != "DRAFT":
            raise MasterDataRuleError(
                "only a DRAFT calendar can be published"
            )
        self._assert_calendar_publishable(calendar)
        calendar.status = "ACTIVE"
        return self._commit(calendar)

    def supersede_manufacturing_calendar(
        self,
        active_calendar_id: UUID,
        replacement_calendar_id: UUID,
        effective_on: date,
    ) -> tuple[ManufacturingCalendar, ManufacturingCalendar]:
        active = self.session.get(
            ManufacturingCalendar, active_calendar_id
        )
        replacement = self.session.get(
            ManufacturingCalendar, replacement_calendar_id
        )
        if active is None or replacement is None:
            raise MasterDataNotFoundError(
                "manufacturing calendar not found"
            )
        if active.status != "ACTIVE":
            raise MasterDataRuleError(
                "current manufacturing calendar is not ACTIVE"
            )
        if replacement.status != "DRAFT":
            raise MasterDataRuleError(
                "replacement manufacturing calendar must be DRAFT"
            )
        if active.code != replacement.code:
            raise MasterDataRuleError(
                "replacement calendar must use the same calendar code"
            )
        if self._calendar_target(active) != self._calendar_target(replacement):
            raise MasterDataRuleError(
                "replacement calendar must use the same target"
            )
        if active.timezone != replacement.timezone:
            raise MasterDataRuleError(
                "replacement calendar must use the same timezone"
            )
        if effective_on <= active.valid_from:
            raise MasterDataRuleError(
                "effective_on must be later than current valid_from"
            )
        if (
            replacement.valid_to is not None
            and replacement.valid_to <= effective_on
        ):
            raise MasterDataRuleError(
                "replacement valid_to must be later than effective_on"
            )

        replacement.valid_from = effective_on
        self._assert_calendar_publishable(
            replacement,
            ignore_calendar_id=active.id,
        )

        active.valid_to = effective_on
        active.status = "SUPERSEDED"
        replacement.status = "ACTIVE"

        try:
            self.session.add_all([active, replacement])
            self.session.commit()
            self.session.refresh(active)
            self.session.refresh(replacement)
        except IntegrityError as exc:
            self.session.rollback()
            raise MasterDataConflictError(
                "calendar supersede operation conflicts with existing master data"
            ) from exc
        return active, replacement

    def _calendar_hierarchy(
        self,
        *,
        plant_id: UUID | None = None,
        area_id: UUID | None = None,
        work_center_id: UUID | None = None,
        resource_id: UUID | None = None,
    ) -> list[tuple[str, UUID]]:
        if sum(
            value is not None
            for value in (
                plant_id,
                area_id,
                work_center_id,
                resource_id,
            )
        ) != 1:
            raise MasterDataRuleError(
                "exactly one calendar-resolution target is required"
            )

        if resource_id is not None:
            resource = self.session.get(Resource, resource_id)
            if resource is None:
                raise MasterDataNotFoundError("resource not found")
            work_center = self.session.get(
                WorkCenter, resource.work_center_id
            )
            if work_center is None:
                raise MasterDataNotFoundError("work center not found")
            area = self.session.get(Area, work_center.area_id)
            if area is None:
                raise MasterDataNotFoundError("area not found")
            return [
                ("resource", resource.id),
                ("work_center", work_center.id),
                ("area", area.id),
                ("plant", area.plant_id),
            ]

        if work_center_id is not None:
            work_center = self.session.get(WorkCenter, work_center_id)
            if work_center is None:
                raise MasterDataNotFoundError("work center not found")
            area = self.session.get(Area, work_center.area_id)
            if area is None:
                raise MasterDataNotFoundError("area not found")
            return [
                ("work_center", work_center.id),
                ("area", area.id),
                ("plant", area.plant_id),
            ]

        if area_id is not None:
            area = self.session.get(Area, area_id)
            if area is None:
                raise MasterDataNotFoundError("area not found")
            return [
                ("area", area.id),
                ("plant", area.plant_id),
            ]

        assert plant_id is not None
        if self.session.get(Plant, plant_id) is None:
            raise MasterDataNotFoundError("plant not found")
        return [("plant", plant_id)]

    @staticmethod
    def _calendar_matches_target(
        calendar: ManufacturingCalendar,
        scope: str,
        target_id: UUID,
    ) -> bool:
        calendar_scope, calendar_target_id = (
            MasterDataService._calendar_target(calendar)
        )
        return calendar_scope == scope and calendar_target_id == target_id

    def _effective_calendar_for_hierarchy(
        self,
        hierarchy: list[tuple[str, UUID]],
        at: datetime,
    ) -> ManufacturingCalendar:
        candidates = self.session.scalars(
            select(ManufacturingCalendar).where(
                ManufacturingCalendar.status.in_(("ACTIVE", "SUPERSEDED"))
            )
        ).all()

        for scope, target_id in hierarchy:
            matches = []
            for calendar in candidates:
                if not self._calendar_matches_target(
                    calendar, scope, target_id
                ):
                    continue
                local_date = at.astimezone(
                    ZoneInfo(calendar.timezone)
                ).date()
                if self._date_window_contains(
                    calendar.valid_from,
                    calendar.valid_to,
                    local_date,
                ):
                    matches.append(calendar)

            if len(matches) > 1:
                raise MasterDataRuleError(
                    "multiple effective published calendars found for target"
                )
            if matches:
                return matches[0]

        raise MasterDataNotFoundError(
            "effective manufacturing calendar not found"
        )

    @staticmethod
    def _weekly_window_matches(
        window: CalendarWeeklyWindow,
        local_at: datetime,
    ) -> bool:
        seconds = (
            local_at.hour * 3600
            + local_at.minute * 60
            + local_at.second
        )
        start_seconds = window.start_minute * 60
        end_seconds = window.end_minute * 60
        weekday = local_at.weekday()

        if not window.spans_midnight:
            return (
                window.weekday == weekday
                and start_seconds <= seconds < end_seconds
            )

        if window.weekday == weekday and seconds >= start_seconds:
            return True
        next_weekday = (window.weekday + 1) % 7
        return next_weekday == weekday and seconds < end_seconds

    def resolve_calendar_availability(
        self,
        *,
        at: datetime,
        plant_id: UUID | None = None,
        area_id: UUID | None = None,
        work_center_id: UUID | None = None,
        resource_id: UUID | None = None,
    ) -> CalendarResolutionRead:
        if at.tzinfo is None or at.utcoffset() is None:
            raise MasterDataRuleError(
                "calendar resolution timestamp must be timezone-aware"
            )

        hierarchy = self._calendar_hierarchy(
            plant_id=plant_id,
            area_id=area_id,
            work_center_id=work_center_id,
            resource_id=resource_id,
        )
        calendar = self._effective_calendar_for_hierarchy(
            hierarchy,
            at,
        )
        target_scope, target_id = self._calendar_target(calendar)
        local_at = at.astimezone(ZoneInfo(calendar.timezone))
        minute_of_day = local_at.hour * 60 + local_at.minute

        exceptions = self.session.scalars(
            select(CalendarException).where(
                CalendarException.calendar_id == calendar.id,
                CalendarException.local_date == local_at.date(),
                CalendarException.active.is_(True),
            )
        ).all()
        matching_exceptions = []
        for exception in exceptions:
            start_minute, end_minute = self._exception_interval(exception)
            if start_minute <= minute_of_day < end_minute:
                matching_exceptions.append(exception)

        if len(matching_exceptions) > 1:
            raise MasterDataRuleError(
                "multiple calendar exceptions match requested timestamp"
            )
        if matching_exceptions:
            exception = matching_exceptions[0]
            if exception.exception_kind == "CLOSED":
                return CalendarResolutionRead(
                    calendar_id=calendar.id,
                    calendar_code=calendar.code,
                    calendar_revision_no=calendar.revision_no,
                    target_scope=target_scope,
                    target_id=target_id,
                    timezone=calendar.timezone,
                    at=at,
                    local_at=local_at,
                    available=False,
                    capacity_factor=Decimal("0"),
                    source="EXCEPTION_CLOSED",
                    exception_id=exception.id,
                )
            assert exception.capacity_factor is not None
            return CalendarResolutionRead(
                calendar_id=calendar.id,
                calendar_code=calendar.code,
                calendar_revision_no=calendar.revision_no,
                target_scope=target_scope,
                target_id=target_id,
                timezone=calendar.timezone,
                at=at,
                local_at=local_at,
                available=True,
                capacity_factor=exception.capacity_factor,
                source="EXCEPTION_OVERRIDE",
                exception_id=exception.id,
            )

        windows = self.session.scalars(
            select(CalendarWeeklyWindow).where(
                CalendarWeeklyWindow.calendar_id == calendar.id,
                CalendarWeeklyWindow.active.is_(True),
            )
        ).all()
        matching_windows = [
            window
            for window in windows
            if self._weekly_window_matches(window, local_at)
        ]
        if len(matching_windows) > 1:
            raise MasterDataRuleError(
                "multiple calendar weekly windows match requested timestamp"
            )
        if matching_windows:
            window = matching_windows[0]
            return CalendarResolutionRead(
                calendar_id=calendar.id,
                calendar_code=calendar.code,
                calendar_revision_no=calendar.revision_no,
                target_scope=target_scope,
                target_id=target_id,
                timezone=calendar.timezone,
                at=at,
                local_at=local_at,
                available=True,
                capacity_factor=window.capacity_factor,
                source="WEEKLY_WINDOW",
                weekly_window_id=window.id,
            )

        return CalendarResolutionRead(
            calendar_id=calendar.id,
            calendar_code=calendar.code,
            calendar_revision_no=calendar.revision_no,
            target_scope=target_scope,
            target_id=target_id,
            timezone=calendar.timezone,
            at=at,
            local_at=local_at,
            available=False,
            capacity_factor=Decimal("0"),
            source="NO_WINDOW",
        )
