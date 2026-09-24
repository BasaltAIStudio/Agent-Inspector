import hashlib
import hmac
import os
import secrets
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.database import SecretVault, SessionLocal, get_db
from backend.dependencies import rate_limiter


class WebhookNotifier:
    @staticmethod
    async def send(url: str, payload: Dict[str, Any], db: Session = None) -> None:
        if not url:
            return
        from backend.engines.webhook_queue import WebhookQueue

        if db is None:
            local_db = SessionLocal()
            close_db = True
        else:
            local_db = db
            close_db = False
        try:
            WebhookQueue.enqueue(url, payload, local_db)
        finally:
            if close_db:
                local_db.close()


async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


async def request_signing_middleware(request: Request, call_next):
    if os.getenv("REQUIRE_REQUEST_SIGNING", "").lower() in {"1", "true", "yes"}:
        secret_name = request.headers.get("X-Signature-Secret")
        signature = request.headers.get("X-Signature")
        if secret_name and signature:
            from backend.database import SessionLocal

            session = SessionLocal()
            try:
                secret = _get_secret(session, secret_name)
                if not secret or not _verify_signature(secret, request.url.path, signature):
                    from fastapi import HTTPException

                    raise HTTPException(status_code=403, detail="Invalid request signature")
            finally:
                session.close()
    return await call_next(request)


async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0
    import logging

    logger = logging.getLogger("agentinspector")
    logger.info("request", extra={"path": request.url.path, "status_code": response.status_code, "duration_ms": duration_ms})
    return response


def register_middleware(app):
    app.add_middleware(request_id_middleware)
    app.add_middleware(request_signing_middleware)
    app.add_middleware(metrics_middleware)

    cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins] if cors_origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _get_secret(db: Session, name: str) -> Optional[str]:
    record = db.query(SecretVault).filter(SecretVault.name == name).first()
    if not record:
        return None
    return record.value


def _sign_payload(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _verify_signature(secret: str, payload: str, signature: str) -> bool:
    expected = _sign_payload(secret, payload)
    return hmac.compare_digest(expected, signature)
