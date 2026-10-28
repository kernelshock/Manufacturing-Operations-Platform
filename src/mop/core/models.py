"""Core organizational persistence models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mop.persistence.base import Base


class Organization(Base):
    __tablename__ = "core_organization"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    plants: Mapped[list["Plant"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class Plant(Base):
    __tablename__ = "core_plant"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_core_plant_org_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("core_organization.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="plants")
    areas: Mapped[list["Area"]] = relationship(back_populates="plant", cascade="all, delete-orphan")


class Area(Base):
    __tablename__ = "core_area"
    __table_args__ = (UniqueConstraint("plant_id", "code", name="uq_core_area_plant_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plant_id: Mapped[UUID] = mapped_column(ForeignKey("core_plant.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    plant: Mapped[Plant] = relationship(back_populates="areas")
    work_centers: Mapped[list["WorkCenter"]] = relationship(back_populates="area", cascade="all, delete-orphan")


class WorkCenter(Base):
    __tablename__ = "core_work_center"
    __table_args__ = (UniqueConstraint("area_id", "code", name="uq_core_work_center_area_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    area_id: Mapped[UUID] = mapped_column(ForeignKey("core_area.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    area: Mapped[Area] = relationship(back_populates="work_centers")
    resources: Mapped[list["Resource"]] = relationship(back_populates="work_center", cascade="all, delete-orphan")


class Resource(Base):
    __tablename__ = "core_resource"
    __table_args__ = (UniqueConstraint("work_center_id", "code", name="uq_core_resource_wc_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    work_center_id: Mapped[UUID] = mapped_column(ForeignKey("core_work_center.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, default="generic")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    work_center: Mapped[WorkCenter] = relationship(back_populates="resources")
