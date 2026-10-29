"""Application service for canonical Master Data."""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.master_data.models import (
    Article,
    ArticleRevision,
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

