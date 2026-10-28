"""Request context extraction for audit records."""

from uuid import uuid4

from fastapi import Request


def request_audit_context(request: Request) -> dict[str, str | None]:
    request_id = request.headers.get("x-request-id") or str(uuid4())
    source_ip = request.client.host if request.client is not None else None
    return {"request_id": request_id, "source_ip": source_ip}
