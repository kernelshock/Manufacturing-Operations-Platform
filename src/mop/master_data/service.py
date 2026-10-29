"""Application service for canonical Master Data."""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mop.master_data.models import Article, ArticleRevision, UnitOfMeasure, UnitOfMeasureAlias
from mop.master_data.schemas import (
    ArticleCreate,
    ArticleRevisionCreate,
    UnitOfMeasureAliasCreate,
    UnitOfMeasureCreate,
)


class MasterDataConflictError(ValueError):
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
