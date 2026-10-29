"""Application service for canonical Master Data."""

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.master_data.models import (
    Article,
    ArticleRevision,
    BOMComponent,
    BOMRevision,
    ProductConfiguration,
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
