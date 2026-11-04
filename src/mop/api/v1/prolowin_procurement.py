"""Legacy Prolowin procurement evidence: no ERP API or OCR required."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from mop.iam.dependencies import require_global_permission
from mop.iam.models import User
from mop.persistence.dependencies import get_session
from mop.prolowin.procurement_schemas import (
    CaptureRead, ManualCaptureCreate, EvidenceCreate, EvidenceRead,
    EvidenceReview, OrderLineSummary,
)
from mop.prolowin.procurement_service import (
    EvidenceConflict, EvidenceNotFound, EvidenceRule, ProcurementEvidenceService,
)

router = APIRouter(prefix="/prolowin/procurement", tags=["prolowin-procurement"])


def service(db: Session = Depends(get_session)):
    return ProcurementEvidenceService(db)


def checked(callback):
    try:
        return callback()
    except EvidenceNotFound as e:
        raise HTTPException(404, detail=str(e)) from e
    except EvidenceConflict as e:
        raise HTTPException(409, detail=str(e)) from e
    except EvidenceRule as e:
        raise HTTPException(422, detail=str(e)) from e


@router.post("/captures/manual", response_model=CaptureRead, status_code=201)
def manual(payload: ManualCaptureCreate, svc: ProcurementEvidenceService = Depends(service),
           actor: User = Depends(require_global_permission("prolowin.procurement.capture"))):
    return checked(lambda: svc.manual_capture(payload, actor.id, actor.username))


@router.post("/captures/screenshots", response_model=CaptureRead, status_code=201)
async def screenshot(request: Request,
                     x_evidence_label: str = Header(..., min_length=1, max_length=150),
                     svc: ProcurementEvidenceService = Depends(service),
                     actor: User = Depends(require_global_permission("prolowin.procurement.capture"))):
    content_type = request.headers.get("content-type", "").split(";")[0].strip()
    if content_type not in ("image/png", "image/jpeg"):
        raise HTTPException(422, detail="only image/png or image/jpeg screenshots")
    # Enforce the cap DURING ingestion, not after buffering untrusted input.
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 4 * 1024 * 1024:
            raise HTTPException(413, detail="maximum screenshot size 4 MiB")
    return checked(lambda: svc.screenshot(bytes(content), content_type, x_evidence_label,
                                          actor.id, actor.username))


@router.get("/captures/{capture_id}", response_model=CaptureRead)
def get_capture(capture_id: UUID, svc: ProcurementEvidenceService = Depends(service),
                _: User = Depends(require_global_permission("prolowin.procurement.read"))):
    return checked(lambda: svc.capture(capture_id))


@router.get("/captures/{capture_id}/image")
def view_evidence(capture_id: UUID, svc: ProcurementEvidenceService = Depends(service),
                  _: User = Depends(require_global_permission("prolowin.procurement.read"))):
    cap = checked(lambda: svc.capture(capture_id))
    if cap.source_type != "SCREENSHOT" or not cap.image_bytes:
        raise HTTPException(404, detail="no screenshot for this capture")
    return Response(content=cap.image_bytes, media_type=cap.image_mime,
                    headers={"Cache-Control": "no-store",
                             "Content-Disposition": "attachment; filename=source-evidence.bin",
                             "X-Content-Type-Options": "nosniff"})


@router.post("/events", response_model=EvidenceRead, status_code=201)
def transcribe(payload: EvidenceCreate, svc: ProcurementEvidenceService = Depends(service),
               actor: User = Depends(require_global_permission("prolowin.procurement.capture"))):
    return checked(lambda: svc.record(payload, actor.id, actor.username))


@router.get("/events", response_model=list[EvidenceRead])
def list_evidence(po_number: str | None = None, status: str | None = None,
                  svc: ProcurementEvidenceService = Depends(service),
                  _: User = Depends(require_global_permission("prolowin.procurement.read"))):
    if status and status not in {"PENDING", "VERIFIED", "REJECTED"}:
        raise HTTPException(422, detail="invalid evidence status")
    return svc.list_events(po_number=po_number, status=status)


@router.post("/events/{event_id}/review", response_model=EvidenceRead)
def review(event_id: UUID, payload: EvidenceReview,
           svc: ProcurementEvidenceService = Depends(service),
           actor: User = Depends(require_global_permission("prolowin.procurement.verify"))):
    return checked(lambda: svc.verify(event_id, payload, actor.id, actor.username))


@router.get("/orders/{po_number}/lines/{line_number}", response_model=OrderLineSummary)
def order_summary(po_number: str, line_number: int, as_of: datetime,
                  svc: ProcurementEvidenceService = Depends(service),
                  _: User = Depends(require_global_permission("prolowin.procurement.read"))):
    return checked(lambda: svc.summary(po_number, line_number, as_of))
