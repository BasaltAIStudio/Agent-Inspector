"""
Continuous monitoring, alerting, and trend tracking for AgentInspector.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import Audit, Finding, TestResult

logger = logging.getLogger("agentinspector.monitoring")


class Alert:
    def __init__(self, alert_type: str, message: str, severity: str, audit_id: Optional[str] = None):
        self.alert_type = alert_type
        self.message = message
        self.severity = severity
        self.audit_id = audit_id
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_type": self.alert_type,
            "message": self.message,
            "severity": self.severity,
            "audit_id": self.audit_id,
            "created_at": self.created_at.isoformat(),
        }


class Monitor:
    def __init__(self, db: Session):
        self.db = db
        self.alerts: List[Alert] = []

    def check_score_drop(self, agent_id: str, window_hours: int = 24, threshold: float = 20.0) -> List[Alert]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        audits = (
            self.db.query(Audit)
            .filter(Audit.agent_id == agent_id, Audit.created_at >= cutoff, Audit.status == "completed")
            .order_by(Audit.created_at.desc())
            .all()
        )
        if len(audits) < 2:
            return []
        recent = audits[0].overall_score or 0.0
        previous = audits[1].overall_score or 0.0
        if recent < previous - threshold:
            alert = Alert(
                alert_type="score_drop",
                message=f"Score dropped from {previous:.1f} to {recent:.1f} in last {window_hours}h",
                severity="high",
                audit_id=audits[0].id,
            )
            self.alerts.append(alert)
            return [alert]
        return []

    def check_failure_spike(self, agent_id: str, window_hours: int = 24, failure_rate_threshold: float = 0.3) -> List[Alert]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        audits = (
            self.db.query(Audit)
            .filter(Audit.agent_id == agent_id, Audit.created_at >= cutoff, Audit.status == "completed")
            .all()
        )
        if not audits:
            return []
        audit_ids = [a.id for a in audits]
        total = self.db.query(func.count(TestResult.id)).filter(TestResult.audit_id.in_(audit_ids)).scalar() or 0
        failed = (
            self.db.query(func.count(TestResult.id))
            .filter(TestResult.audit_id.in_(audit_ids), TestResult.status == "fail")
            .scalar()
            or 0
        )
        if total == 0:
            return []
        rate = failed / total
        if rate >= failure_rate_threshold:
            alert = Alert(
                alert_type="failure_spike",
                message=f"Failure rate {rate*100:.1f}% exceeds {failure_rate_threshold*100:.1f}% threshold",
                severity="medium",
                audit_id=audits[-1].id,
            )
            self.alerts.append(alert)
            return [alert]
        return []

    def check_critical_findings(self, agent_id: str, window_hours: int = 24) -> List[Alert]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        audits = (
            self.db.query(Audit)
            .filter(Audit.agent_id == agent_id, Audit.created_at >= cutoff, Audit.status == "completed")
            .all()
        )
        if not audits:
            return []
        audit_ids = [a.id for a in audits]
        criticals = (
            self.db.query(func.count(Finding.id))
            .filter(Finding.audit_id.in_(audit_ids), Finding.severity == "critical")
            .scalar()
            or 0
        )
        if criticals > 0:
            alert = Alert(
                alert_type="critical_findings",
                message=f"{criticals} critical finding(s) in last {window_hours}h",
                severity="critical",
                audit_id=audits[-1].id,
            )
            self.alerts.append(alert)
            return [alert]
        return []

    def run_checks(self, agent_id: str) -> List[Alert]:
        self.alerts = []
        self.check_score_drop(agent_id)
        self.check_failure_spike(agent_id)
        self.check_critical_findings(agent_id)
        return self.alerts


class TrendTracker:
    def __init__(self, db: Session):
        self.db = db

    def daily_scores(self, agent_id: str, days: int = 30) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        audits = (
            self.db.query(Audit)
            .filter(Audit.agent_id == agent_id, Audit.created_at >= cutoff, Audit.status == "completed")
            .order_by(Audit.created_at.asc())
            .all()
        )
        return [
            {
                "date": a.created_at.date().isoformat(),
                "score": a.overall_score or 0.0,
                "audit_id": a.id,
            }
            for a in audits
        ]

    def category_trends(self, agent_id: str, days: int = 30) -> Dict[str, List[Dict[str, Any]]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        audits = (
            self.db.query(Audit)
            .filter(Audit.agent_id == agent_id, Audit.created_at >= cutoff, Audit.status == "completed")
            .order_by(Audit.created_at.asc())
            .all()
        )
        categories = [
            "reliability_score",
            "security_score",
            "tool_usage_score",
            "hallucination_score",
            "privacy_score",
            "cost_score",
            "latency_score",
            "instruction_following_score",
            "human_escalation_score",
        ]
        result: Dict[str, List[Dict[str, Any]]] = {c: [] for c in categories}
        for a in audits:
            for c in categories:
                result[c].append({"date": a.created_at.date().isoformat(), "value": getattr(a, c) or 0.0})
        return result
