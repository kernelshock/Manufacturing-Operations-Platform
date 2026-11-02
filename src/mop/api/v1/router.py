"""Versioned API router."""

from fastapi import APIRouter

from mop.api.v1.audit import router as audit_router
from mop.api.v1.aps import router as aps_router
from mop.api.v1.aps_expansion import router as aps_expansion_router
from mop.api.v1.aps_capacity import router as aps_capacity_router
from mop.api.v1.aps_schedule import router as aps_schedule_router
from mop.api.v1.aps_lifecycle import router as aps_lifecycle_router
from mop.api.v1.demand import router as demand_router
from mop.api.v1.auth import router as auth_router
from mop.api.v1.iam import router as iam_router
from mop.api.v1.master_data import router as master_data_router
from mop.api.v1.meta import router as meta_router
from mop.api.v1.organization import router as organization_router
from mop.api.v1.prolowin import router as prolowin_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(iam_router)
router.include_router(audit_router)
router.include_router(aps_router)
router.include_router(aps_expansion_router)
router.include_router(aps_capacity_router)
router.include_router(aps_schedule_router)
router.include_router(aps_lifecycle_router)
router.include_router(demand_router)
router.include_router(meta_router)
router.include_router(master_data_router)
router.include_router(prolowin_router)
router.include_router(organization_router)
