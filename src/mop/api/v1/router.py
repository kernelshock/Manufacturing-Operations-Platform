"""Versioned API router."""

from fastapi import APIRouter

from mop.api.v1.meta import router as meta_router

router = APIRouter()
router.include_router(meta_router)
