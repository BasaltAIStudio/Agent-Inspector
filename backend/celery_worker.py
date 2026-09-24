"""
Celery worker for processing audit tasks asynchronously.
Uses Redis as the broker and backend.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict

from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agentinspector import Inspector
from agentinspector.adapters import get_adapter
from agentinspector.models import AgentConfig, AgentFramework

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agentinspector.db")
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

celery_app = Celery(
    "agentinspector",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_audit_task(self, audit_id: str, body: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        from backend.database import Audit, TaskQueue

        task = db.query(TaskQueue).filter(TaskQueue.audit_id == audit_id).first()
        if task:
            task.status = "running"
            task.started_at = datetime.utcnow()
            db.commit()

        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            return {"status": "error", "message": "Audit not found"}

        config = AgentConfig(
            agent_id=body["agent_id"],
            name=body["agent_name"],
            framework=AgentFramework(body["framework"]),
            endpoint=body.get("endpoint"),
            tools=body.get("tools") or [],
            expected_capabilities=body.get("expected_capabilities") or [],
            prohibited_actions=body.get("prohibited_actions") or [],
            system_prompt=body.get("system_prompt") or "",
            metadata={"model": "gpt-4o-mini"},
        )
        adapter = get_adapter(config)
        inspector = Inspector(framework=body["framework"])
        report = inspector.audit(adapter, config=config)
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
        audit.completed_at = datetime.utcnow()

        if task:
            task.status = "completed"
            task.finished_at = datetime.utcnow()

        db.commit()
        return {"status": "completed", "audit_id": audit_id}
    except Exception as e:
        db.rollback()
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if audit:
            audit.status = "failed"
            audit.completed_at = datetime.utcnow()
        task = db.query(TaskQueue).filter(TaskQueue.audit_id == audit_id).first()
        if task:
            task.status = "failed"
            task.error = str(e)
            task.finished_at = datetime.utcnow()
        db.commit()
        raise self.retry(exc=e)
    finally:
        db.close()
