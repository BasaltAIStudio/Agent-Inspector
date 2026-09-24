from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import verify_api_key_and_rate_limit
from backend.monitoring import Alert, Monitor, TrendTracker

router = APIRouter()


class AlertResponse(BaseModel):
    alert_type: str
    message: str
    severity: str
    audit_id: str | None = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class TrendResponse(BaseModel):
    dates: List[str]
    scores: List[float]
    audit_ids: List[str]


@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    agent_id: str,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> List[AlertResponse]:
    monitor = Monitor(db)
    alerts = monitor.run_checks(agent_id)
    return [AlertResponse(**a.to_dict()) for a in alerts]


@router.get("/trends", response_model=TrendResponse)
async def get_trends(
    agent_id: str,
    days: int = 30,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> TrendResponse:
    tracker = TrendTracker(db)
    data = tracker.daily_scores(agent_id, days=min(days, 365))
    return TrendResponse(
        dates=[d["date"] for d in data],
        scores=[d["score"] for d in data],
        audit_ids=[d["audit_id"] for d in data],
    )


@router.get("/category-trends")
async def get_category_trends(
    agent_id: str,
    days: int = 30,
    api_key: str = Depends(verify_api_key_and_rate_limit),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    tracker = TrendTracker(db)
    return tracker.category_trends(agent_id, days=min(days, 365))
