import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.database import (
    Audit,
    Finding,
    TaskQueue,
    TestResult,
    get_db,
)
from backend.dependencies import verify_api_key_and_rate_limit
from backend.engines.webhook_queue import WebhookQueue
from sqlalchemy.orm import Session

router = APIRouter()


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


class AuditDetailResponse(AuditResponse):
    findings: List[dict] = []
    test_results: List[dict] = []


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


@router.post("/audit", response_model=AuditResponse)
async def create_audit(
    request: Request,
    body: AuditCreateRequest,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> AuditResponse:
    audit_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    audit_record = Audit(
        id=audit_id,
        agent_id=body.agent_id,
        agent_name=body.agent_name,
        framework=body.framework,
        status="queued",
        created_at=now,
    )
    db.add(audit_record)

    task_record = TaskQueue(
        id=task_id,
        audit_id=audit_id,
        status="pending",
        priority=body.priority,
        created_at=now,
    )
    db.add(task_record)
    db.commit()

    body_dict = body.model_dump()

    asyncio.get_running_loop().create_task(
        _run_audit_task(audit_id, task_id, body_dict, api_key, request.state.request_id)
    )

    return AuditResponse(
        audit_id=audit_id,
        agent_id=body.agent_id,
        agent_name=body.agent_name,
        status="queued",
        overall_score=0.0,
        report={},
        created_at=now,
        finished_at=None,
        webhook_url=body.webhook_url,
    )


@router.get("/audits", response_model=List[AuditResponse])
async def list_audits(
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50,
) -> List[AuditResponse]:
    query = db.query(Audit)
    if agent_id:
        query = query.filter(Audit.agent_id == agent_id)
    if status:
        query = query.filter(Audit.status == status)
    if start_date:
        query = query.filter(Audit.created_at >= start_date)
    if end_date:
        query = query.filter(Audit.created_at <= end_date)
    records = query.order_by(Audit.created_at.desc()).limit(min(limit, 200)).all()
    return [
        AuditResponse(
            audit_id=r.id,
            agent_id=r.agent_id,
            agent_name=r.agent_name,
            status=r.status,
            overall_score=r.overall_score or 0.0,
            report=json.loads(json.dumps(r.__dict__, default=str)),
            created_at=r.created_at,
            finished_at=r.completed_at,
            webhook_url=None,
        )
        for r in records
    ]


@router.get("/audits/{audit_id}", response_model=AuditDetailResponse)
async def get_audit(
    audit_id: str,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> AuditDetailResponse:
    record = db.query(Audit).filter(Audit.id == audit_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Audit not found")
    findings = db.query(Finding).filter(Finding.audit_id == audit_id).all()
    test_results = db.query(TestResult).filter(TestResult.audit_id == audit_id).all()
    return AuditDetailResponse(
        audit_id=record.id,
        agent_id=record.agent_id,
        agent_name=record.agent_name,
        status=record.status,
        overall_score=record.overall_score or 0.0,
        report=json.loads(json.dumps(record.__dict__, default=str)),
        created_at=record.created_at,
        finished_at=record.completed_at,
        webhook_url=None,
        findings=findings,
        test_results=test_results,
    )


@router.get("/audits/{audit_id}/tests", response_model=List[TestResultResponse])
async def get_audit_tests(
    audit_id: str,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> List[TestResultResponse]:
    tests = db.query(TestResult).filter(TestResult.audit_id == audit_id).all()
    return tests


@router.get("/audits/{audit_id}/findings", response_model=List[FindingResponse])
async def get_audit_findings(
    audit_id: str,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> List[FindingResponse]:
    findings = db.query(Finding).filter(Finding.audit_id == audit_id).all()
    return findings


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> TaskResponse:
    task = db.query(TaskQueue).filter(TaskQueue.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(
        task_id=task.id,
        audit_id=task.audit_id,
        status=task.status,
        priority=task.priority,
        retries=task.retries,
        error=task.error,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> dict:
    task = db.query(TaskQueue).filter(TaskQueue.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Task already {task.status}")
    import secrets
    token = secrets.token_urlsafe(32)
    task.cancellation_token = token
    task.status = "cancelling"
    db.commit()
    return {"task_id": task.id, "status": "cancelling", "cancellation_token": token}


@router.delete("/audits/{audit_id}")
async def delete_audit(
    audit_id: str,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> dict:
    audit = db.query(Audit).filter(Audit.id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    db.query(Finding).filter(Finding.audit_id == audit_id).delete()
    db.query(TestResult).filter(TestResult.audit_id == audit_id).delete()
    db.delete(audit)
    db.commit()
    return {"message": "Audit deleted", "audit_id": audit_id}


async def _run_audit_task(audit_id: str, task_id: str, body: Dict[str, Any], api_key: str, request_id: Optional[str] = None) -> None:
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        task = db.query(TaskQueue).filter(TaskQueue.id == task_id).first()
        if task:
            task.status = "running"
            task.started_at = datetime.now(timezone.utc)
            db.commit()

        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            import logging

            logger = logging.getLogger("agentinspector")
            logger.error("Audit %s not found during task execution", audit_id)
            return

        from agentinspector import Inspector
        from agentinspector.adapters import get_adapter
        from agentinspector.models import AgentConfig, AgentFramework

        config = AgentConfig(
            agent_id=body["agent_id"],
            name=body["agent_name"],
            framework=AgentFramework(body["framework"]),
            endpoint=body.get("endpoint"),
            tools=body.get("tools") or [],
            expected_capabilities=body.get("expected_capabilities") or [],
            prohibited_actions=body.get("prohibited_actions") or [],
            system_prompt=body.get("system_prompt") or "",
            metadata={"model": "gpt-4o-mini", "request_id": request_id},
        )
        adapter = get_adapter(config)
        inspector = Inspector(framework=body["framework"])

        if task and task.cancellation_token:
            task.status = "cancelled"
            task.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        try:
            report = await asyncio.wait_for(inspector.audit(adapter, config=config), timeout=300.0)
        except asyncio.TimeoutError:
            raise RuntimeError("Audit timed out after 300s")

        report_dict = json.loads(json.dumps(report.__dict__, default=str))

        audit.status = "completed"
        audit.overall_score = report.overall_score
        audit.reliability_score = report_dict.get("reliability_score")
        audit.security_score = report_dict.get("security_score")
        audit.tool_usage_score = report_dict.get("tool_usage_score")
        audit.hallucination_score = report_dict.get("hallucination_score")
        audit.privacy_score = report_dict.get("privacy_score")
        audit.cost_score = report_dict.get("cost_score")
        audit.latency_score = report_dict.get("latency_score")
        audit.instruction_following_score = report_dict.get("instruction_following_score")
        audit.human_escalation_score = report_dict.get("human_escalation_score")
        audit.test_count = report_dict.get("test_count", 0)
        audit.findings_count = report_dict.get("findings_count", 0)
        audit.completed_at = datetime.now(timezone.utc)

        if task:
            task.status = "completed"
            task.finished_at = datetime.now(timezone.utc)

        db.commit()

        if audit.webhook_url:
            WebhookQueue.enqueue(audit.webhook_url, {
                "event": "audit.completed",
                "audit_id": audit_id,
                "agent_id": body["agent_id"],
                "status": "completed",
                "overall_score": report.overall_score,
            }, db)
    except Exception as e:
        db.rollback()
        import logging
        import traceback

        logger = logging.getLogger("agentinspector")
        logger.error("Audit task failed for %s: %s", audit_id, traceback.format_exc())
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if audit:
            audit.status = "failed"
            audit.completed_at = datetime.now(timezone.utc)
        task = db.query(TaskQueue).filter(TaskQueue.audit_id == audit_id).first()
        if task:
            task.status = "failed"
            task.error = str(e)
            task.finished_at = datetime.now(timezone.utc)
        db.commit()

        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if audit and getattr(audit, "webhook_url", None):
            WebhookQueue.enqueue(audit.webhook_url, {
                "event": "audit.failed",
                "audit_id": audit_id,
                "error": str(e),
            }, db)
    finally:
        db.close()
