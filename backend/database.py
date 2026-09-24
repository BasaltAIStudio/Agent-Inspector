from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import enum
import os
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agentinspector.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Scope(enum.Enum):
    AUDIT_READ = "audit:read"
    AUDIT_WRITE = "audit:write"
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:write"
    ADMIN = "admin"


class APIKeyRecord(Base):
    __tablename__ = "api_keys"
    key = Column(String, primary_key=True, index=True)
    owner = Column(String)
    rate_limit = Column(Integer, default=100)
    scopes = Column(Text, default="audit:read,audit:write,agent:read")
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    revoked = Column(Boolean, default=False)
    hashed_key = Column(String, nullable=True)


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    agent_type = Column(String)
    config = Column(Text)
    endpoint = Column(String)
    api_key = Column(String)
    tenant_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    audits = relationship("Audit", back_populates="agent")


class Audit(Base):
    __tablename__ = "audits"

    id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"))
    agent_name = Column(String)
    framework = Column(String)
    status = Column(String, default="pending")
    overall_score = Column(Float)
    reliability_score = Column(Float)
    security_score = Column(Float)
    tool_usage_score = Column(Float)
    hallucination_score = Column(Float)
    privacy_score = Column(Float)
    cost_score = Column(Float)
    latency_score = Column(Float)
    instruction_following_score = Column(Float)
    human_escalation_score = Column(Float)
    test_count = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    webhook_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    agent = relationship("Agent", back_populates="audits")
    findings = relationship("Finding", back_populates="audit")
    test_results = relationship("TestResult", back_populates="audit")


class Finding(Base):
    __tablename__ = "findings"

    id = Column(String, primary_key=True, index=True)
    audit_id = Column(String, ForeignKey("audits.id"))
    category = Column(String)
    severity = Column(String)
    title = Column(String)
    description = Column(Text)
    evidence = Column(Text)
    remediation = Column(Text)
    reproducibility = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    audit = relationship("Audit", back_populates="findings")


class TaskQueue(Base):
    __tablename__ = "task_queue"

    id = Column(String, primary_key=True, index=True)
    audit_id = Column(String, ForeignKey("audits.id"))
    status = Column(String, default="pending")
    priority = Column(Integer, default=0)
    retries = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    cancellation_token = Column(String, nullable=True)


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(String, primary_key=True, index=True)
    audit_id = Column(String, ForeignKey("audits.id"))
    test_name = Column(String)
    category = Column(String)
    status = Column(String)
    input_data = Column(Text)
    output_data = Column(Text)
    expected = Column(Text)
    actual = Column(Text)
    latency_ms = Column(Float)
    cost = Column(Float)
    tokens_used = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    audit = relationship("Audit", back_populates="test_results")


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    actor_key = Column(String, nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    success = Column(Boolean, default=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SecretVault(Base):
    __tablename__ = "secret_vault"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=True)
    encrypted_value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    webhook_url = Column(String, nullable=False, index=True)
    payload = Column(Text, nullable=False)
    status = Column(String, default="pending", index=True)
    retry_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    failed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_error = Column(Text, nullable=True)


class SchedulerRun(Base):
    __tablename__ = "scheduler_runs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    job_type = Column(String, nullable=False)
    last_run_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, nullable=False)
    error = Column(Text, nullable=True)


class BackupRecord(Base):
    __tablename__ = "backups"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    size_bytes = Column(Integer, nullable=True)
    path = Column(String, nullable=True)
    checksum = Column(String, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
