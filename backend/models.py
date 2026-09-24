from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class AgentCreate(BaseModel):
    name: str
    description: str
    agent_type: str = "custom"
    config: Optional[str] = None
    endpoint: Optional[str] = None
    api_key: Optional[str] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    agent_type: str
    endpoint: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditCreate(BaseModel):
    agent_id: str
    expected_behavior: str
    prohibited_actions: Optional[str] = None
    test_count: int = Field(default=100, ge=10, le=1000)
    include_security: bool = True
    include_cost: bool = True
    include_chaos: bool = True


class AuditResponse(BaseModel):
    id: str
    agent_id: str
    status: str
    overall_score: Optional[float]
    reliability_score: Optional[float]
    security_score: Optional[float]
    tool_usage_score: Optional[float]
    hallucination_score: Optional[float]
    privacy_score: Optional[float]
    cost_score: Optional[float]
    latency_score: Optional[float]
    instruction_following_score: Optional[float]
    human_escalation_score: Optional[float]
    test_count: int
    findings_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class FindingResponse(BaseModel):
    id: str
    category: str
    severity: str
    title: str
    description: str
    evidence: str
    remediation: str
    reproducibility: float

    class Config:
        from_attributes = True


class TestResultResponse(BaseModel):
    id: str
    test_name: str
    category: str
    status: str
    latency_ms: float
    cost: float
    tokens_used: int

    class Config:
        from_attributes = True


class AuditReport(BaseModel):
    audit: AuditResponse
    findings: List[FindingResponse]
    test_results: List[TestResultResponse]
    summary: Dict[str, Any]
