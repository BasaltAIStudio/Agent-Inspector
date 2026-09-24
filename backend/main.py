"""

import os
LITE_MODE = os.getenv("AGENT_INSPECTOR_LITE", "false").lower() == "true"

if LITE_MODE:
    print("🚀 Running in LITE MODE: Using SQLite, skipping Celery/Redis.")
    # Override database connection to local sqlite
    # Disable Celery task dispatching, use sync execution instead

Production-grade FastAPI backend with task queue, webhooks, rate limiting, and observability.
Uses in-process asyncio task execution. Celery support deferred to future release.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import traceback
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from sqlalchemy import create_engine, Column, String, Float, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

from backend.database import get_db, Base, engine, SessionLocal, Agent, Audit, Finding, TestResult, TaskQueue, APIKeyRecord, init_db, AdminAuditLog, SecretVault
from backend.monitoring import Monitor, TrendTracker, Alert

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(message)s",
)
logger = logging.getLogger("agentinspector")


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["traceback"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


for handler in logging.root.handlers:
    handler.setFormatter(StructuredFormatter())


class RateLimiter:
    def __init__(self):
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._window = 60.0

    def is_allowed(self, key: str, limit: int) -> bool:
        now = time.time()
        self._requests[key] = [t for t in self._requests[key] if now - t < self._window]
        if len(self._requests[key]) >= limit:
            return False
        self._requests[key].append(now)
        return True


rate_limiter = RateLimiter()


class WebhookNotifier:
    @staticmethod
    async def send(url: str, payload: Dict[str, Any]) -> None:
        if not url:
            return
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json=payload)
        except Exception:
            pass


ADMIN_SCOPES = {"admin"}
AUDIT_SCOPES = {"audit:read", "audit:write"}
AGENT_SCOPES = {"agent:read", "agent:write"}


def _has_scope(requested_scopes: Optional[str], required: str) -> bool:
    if not requested_scopes:
        return False
    requested = {s.strip() for s in requested_scopes.split(",") if s.strip()}
    return required in requested


def _get_key_record(api_key: str, db: Session) -> Optional[APIKeyRecord]:
    record = db.query(APIKeyRecord).filter(APIKeyRecord.key == api_key, APIKeyRecord.revoked == False).first()
    return record


def _enforce_scope(record: APIKeyRecord, required_scope: str) -> None:
    scopes = {s.strip() for s in record.scopes.split(",") if s.strip()}
    if required_scope not in scopes and "admin" not in scopes:
        raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")


def _log_admin_action(db: Session, action: str, actor_key: Optional[str], resource_type: Optional[str], resource_id: Optional[str], ip_address: Optional[str], user_agent: Optional[str], success: bool = True, error: Optional[str] = None) -> None:
    log = AdminAuditLog(
        action=action,
        actor_key=actor_key,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        error=error,
    )
    db.add(log)
    db.commit()


def _set_secret(db: Session, name: str, value: str) -> None:
    existing = _get_secret(db, name)
    if existing:
        secret = db.query(SecretVault).filter(SecretVault.name == name).first()
        if secret:
            secret.value = value
            db.add(secret)
            db.commit()
            return
    secret = SecretVault(name=name, value=value)
    db.add(secret)
    db.commit()


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


def _build_scope_spec(raw_scopes: Optional[str]) -> str:
    return raw_scopes or "audit:read,audit:write,agent:read"


def _current_scope_set(raw_scopes: str) -> set:
    return {s.strip() for s in raw_scopes.split(",") if s.strip()}


async def verify_api_key_and_rate_limit(request: Request, db: Session = Depends(get_db), required_scope: Optional[str] = None) -> str:
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    record = _get_key_record(api_key, db)
    if not record:
        raise HTTPException(status_code=403, detail="Invalid API key")
    if record.expires_at and record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="API key expired")
    if not rate_limiter.is_allowed(api_key, record.rate_limit):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    record.last_used_at = datetime.now(timezone.utc)
    db.add(record)
    db.commit()
    if required_scope:
        _enforce_scope(record, required_scope)
    return api_key


async def verify_admin_api_key(request: Request, db: Session = Depends(get_db)) -> str:
    api_key = await verify_api_key_and_rate_limit(request, db)
    record = _get_key_record(api_key, db)
    _enforce_scope(record, "admin")
    return api_key


app = FastAPI(
    title="AgentInspector API",
    description="Automated QA + security + reliability + cost + compliance testing for AI agents.",
    version="0.5.0",
)


@app.on_event("startup")
async def startup_event():
    init_db()


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
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
                    raise HTTPException(status_code=403, detail="Invalid request signature")
            finally:
                session.close()
    return await call_next(request)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0
    logger.info("request", extra={"path": request.url.path, "status_code": response.status_code, "duration_ms": duration_ms})
    return response


cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins] if cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from backend.routers import agents as agents_router
from backend.routers import audits as audits_router
from backend.routers import admin as admin_router
from backend.routers import monitoring as monitoring_router
from backend.routers import keys as keys_router
from backend.routers import demo as demo_router

API_PREFIX = "/api/v1"

app.include_router(agents_router.router, prefix=API_PREFIX)
app.include_router(audits_router.router, prefix=API_PREFIX)
app.include_router(admin_router.router, prefix=API_PREFIX)
app.include_router(monitoring_router.router, prefix=API_PREFIX)
app.include_router(keys_router.router, prefix=API_PREFIX)
app.include_router(demo_router.router, prefix=API_PREFIX)


class AuditCreateRequest(BaseModel):
    agent_id: str
    agent_name: str
    framework: str = "rest_api"
    endpoint: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    expected_capabilities: Optional[List[str]] = None
    prohibited_actions: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    webhook_url: Optional[str] = None
    priority: int = Field(default=0, ge=0, le=10)

    model_config = ConfigDict(str_strip_whitespace=True)


class AgentCreateRequest(BaseModel):
    name: str
    description: str
    agent_type: str = "custom"
    endpoint: Optional[str] = None
    api_key: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    agent_type: str
    endpoint: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditResponse(BaseModel):
    audit_id: str
    agent_id: str
    agent_name: str
    status: str
    overall_score: float
    report: Dict[str, Any]
    created_at: datetime
    finished_at: Optional[datetime] = None
    webhook_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TaskResponse(BaseModel):
    task_id: str
    audit_id: str
    status: str
    priority: int
    retries: int
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TestResultResponse(BaseModel):
    id: str
    audit_id: str
    test_name: str
    category: str
    status: str
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    latency_ms: float
    cost: float
    tokens_used: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FindingResponse(BaseModel):
    id: str
    audit_id: str
    category: str
    severity: str
    title: str
    description: str
    evidence: str
    remediation: str
    reproducibility: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditDetailResponse(AuditResponse):
    findings: List[FindingResponse] = []
    test_results: List[TestResultResponse] = []


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: Optional[str] = None
    sentence_model: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_status = "sqlite"
    try:
        from backend.database import SessionLocal
        session = SessionLocal()
        session.execute("SELECT 1")
        session.close()
        db_status = os.getenv("DATABASE_URL", "sqlite").split("://")[0]
    except Exception:
        db_status = "error"
    redis_status = None
    try:
        import redis as redislib
        r = redislib.Redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"))
        r.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "unreachable"
    return HealthResponse(
        status="healthy",
        version="0.5.0",
        database=db_status,
        redis=redis_status,
        sentence_model=os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2"),
    )


@app.get(f"{API_PREFIX}/dashboard", response_model=Dict[str, Any])
async def dashboard(api_key: str = Depends(verify_api_key_and_rate_limit), db: Session = Depends(get_db)) -> Dict[str, Any]:
    total_audits = db.query(Audit).count()
    total_agents = db.query(Agent).count()
    total_findings = db.query(Finding).count()
    completed_audits = db.query(Audit).filter(Audit.status == "completed").count()
    failed_audits = db.query(Audit).filter(Audit.status == "failed").count()
    return {
        "status": "operational",
        "total_audits": total_audits,
        "total_agents": total_agents,
        "total_findings": total_findings,
        "completed_audits": completed_audits,
        "failed_audits": failed_audits,
        "success_rate": (completed_audits / total_audits) if total_audits else 0.0,
    }


@app.get(f"{API_PREFIX}/metrics", response_model=Dict[str, Any])
async def metrics_endpoint(api_key: str = Depends(verify_api_key_and_rate_limit), db: Session = Depends(get_db)) -> Dict[str, Any]:
    total_audits = db.query(Audit).count()
    total_agents = db.query(Agent).count()
    total_findings = db.query(Finding).count()
    total_tasks = db.query(TaskQueue).count()
    completed_audits = db.query(Audit).filter(Audit.status == "completed").count()
    failed_audits = db.query(Audit).filter(Audit.status == "failed").count()
    return {
        "total_audits": total_audits,
        "total_agents": total_agents,
        "total_findings": total_findings,
        "total_tasks": total_tasks,
        "completed_audits": completed_audits,
        "failed_audits": failed_audits,
        "success_rate": (completed_audits / total_audits) if total_audits else 0.0,
    }


@app.post(f"{API_PREFIX}/admin/scheduler/run")
async def trigger_scheduler_run(
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db=Depends(get_db),
) -> dict:
    import asyncio

    from backend.scheduler import scheduler

    asyncio.get_running_loop().create_task(scheduler.run_once())
    try:
        _log_admin_action(
            db,
            "scheduler.manual_run",
            admin_key,
            "scheduler",
            None,
            request.client.host if request and request.client else None,
            request.headers.get("user-agent") if request else None,
            success=True,
        )
    except Exception:
        pass
    return {"status": "triggered", "message": "Scheduler run started in background"}


@app.get(f"{API_PREFIX}/admin/webhooks/dead-letter")
async def list_dead_letter_webhooks(
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db=Depends(get_db),
    limit: int = 100,
) -> list:
    from backend.engines.webhook_queue import WebhookQueue

    deliveries = WebhookQueue.get_dead_letter(db, limit=min(limit, 500))
    _log_admin_action(
        db,
        "webhooks.dlq.read",
        admin_key,
        "webhook_delivery",
        None,
        request.client.host if request and request.client else None,
        request.headers.get("user-agent") if request else None,
        success=True,
    )
    return [
        {
            "id": d.id,
            "webhook_url": d.webhook_url,
            "payload": d.payload,
            "status": d.status,
            "retry_count": d.retry_count,
            "failed_at": d.failed_at.isoformat() if d.failed_at else None,
            "created_at": d.created_at.isoformat(),
            "last_error": d.last_error,
        }
        for d in deliveries
    ]


@app.post(f"{API_PREFIX}/admin/webhooks/dead-letter/{{delivery_id}}/retry")
async def retry_dead_letter_webhook(
    delivery_id: str,
    admin_key: str = Depends(verify_admin_api_key),
    request: Request = None,
    db=Depends(get_db),
) -> dict:
    from backend.database import WebhookDelivery

    delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Webhook delivery not found")
    if delivery.status != "dead_letter":
        raise HTTPException(status_code=400, detail="Delivery is not in dead-letter queue")
    delivery.status = "pending"
    delivery.retry_count = 0
    from datetime import datetime, timezone

    delivery.next_retry_at = datetime.now(timezone.utc)
    delivery.failed_at = None
    delivery.last_error = None
    db.add(delivery)
    _log_admin_action(
        db,
        "webhooks.dlq.retry",
        admin_key,
        "webhook_delivery",
        delivery_id,
        request.client.host if request and request.client else None,
        request.headers.get("user-agent") if request else None,
        success=True,
    )
    db.commit()
    return {"message": "Webhook re-queued for delivery", "delivery_id": delivery_id}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning("HTTPException %s: %s", exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    logger.error("Validation error: %s", exc.errors())
    return JSONResponse(
        status_code=422,
        content={"error": "Validation failed", "details": exc.errors(), "status_code": 422},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500},
    )
