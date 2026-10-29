"""Versioned API router."""

from fastapi import APIRouter

from mop.api.v1.audit import router as audit_router
from mop.api.v1.auth import router as auth_router
from mop.api.v1.iam import router as iam_router
from mop.api.v1.meta import router as meta_router
from mop.api.v1.organization import router as organization_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(iam_router)
router.include_router(audit_router)
router.include_router(meta_router)
router.include_router(organization_router)
