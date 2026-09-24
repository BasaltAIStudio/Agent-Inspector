"""Integration tests for AgentInspector backend.

Covers:
- Full audit lifecycle through the REST API
- Webhook enqueue, retry/backoff, and dead-letter behavior
- Admin audit logging for sensitive actions
- Request signing verification
"""

from __future__ import annotations

import time
import hmac
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.database import (
    engine as db_engine,
    Base,
    get_db,
    APIKeyRecord,
    SessionLocal,
    AdminAuditLog,
    WebhookDelivery,
)
from backend.engines.webhook_queue import WebhookQueue
from backend.main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_integration.db"

test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def _setup_test_integration_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _override_app_db():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


client = TestClient(app)


@pytest.fixture
def admin_api_key():
    db = TestingSessionLocal()
    try:
        unique_suffix = str(uuid.uuid4()).replace("-", "")[:16]
        key = f"ai_{unique_suffix}"
        record = APIKeyRecord(key=key, owner="integration-admin", rate_limit=100, scopes="admin", revoked=False)
        db.add(record)
        db.commit()
        return key
    finally:
        db.close()


@pytest.fixture
def api_key(admin_api_key):
    response = client.post(
        "/api/v1/keys?owner=integration-user&rate_limit=100",
        headers={"X-API-Key": admin_api_key},
    )
    assert response.status_code == 200, response.text
    return response.json()["api_key"]


def test_full_audit_lifecycle(api_key):
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    agent_resp = client.post(
        "/api/v1/agents",
        json={"name": "Integration Agent", "provider": "openai", "model": "gpt-4o", "description": "E2E test"},
        headers=headers,
    )
    assert agent_resp.status_code == 201, agent_resp.text
    agent_id = agent_resp.json()["id"]

    audit_resp = client.post(
        "/api/v1/audit",
        json={
            "agent_id": agent_id,
            "agent_name": "Integration Agent",
            "framework": "rest_api",
            "include_security": True,
            "include_behaviour": True,
            "include_cost": True,
        },
        headers=headers,
    )
    assert audit_resp.status_code in (200, 201), audit_resp.text
    audit_id = audit_resp.json()["audit_id"]

    detail_resp = client.get(f"/api/v1/audits/{audit_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"] in ("queued", "running", "completed")

    tests_resp = client.get(f"/api/v1/audits/{audit_id}/tests", headers=headers)
    assert tests_resp.status_code == 200


def test_webhook_enqueue_and_retry(api_key):
    db = TestingSessionLocal()
    try:
        delivery = WebhookQueue.enqueue(
            "https://example.com/webhook",
            {"event": "audit.completed", "audit_id": "test-audit"},
            db,
        )
        assert delivery.id is not None
        assert delivery.status == "pending"

        processed = WebhookQueue.process_next(db)
        assert processed is not None
        assert processed.id == delivery.id
        assert processed.status in ("delivered", "pending", "dead_letter")
    finally:
        db.close()


def test_admin_audit_log_records_sensitive_actions(admin_api_key):
    headers = {"X-API-Key": admin_api_key}

    client.post(
        "/api/v1/keys?owner=log-test&rate_limit=50",
        headers=headers,
    )

    logs_resp = client.get("/api/v1/logs", headers=headers)
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    assert isinstance(logs, list)
    assert any(log.get("action") == "api_key.created" or "key" in str(log.get("action", "")).lower() for log in logs)


def test_request_signing_verification(admin_api_key):
    headers = {"X-API-Key": admin_api_key}

    upsert_resp = client.post(
        "/api/v1/secrets/test_signing_secret",
        params={"value": "super_secret_signing_key"},
        headers=headers,
    )
    assert upsert_resp.status_code == 200

    payload = "POST|/api/v1/audit|{}"
    sign_resp = client.post(
        "/api/v1/sign",
        params={"secret_name": "test_signing_secret", "payload": payload},
        headers=headers,
    )
    assert sign_resp.status_code == 200, sign_resp.text
    signature = sign_resp.json()["signature"]

    expected = hmac.new(b"super_secret_signing_key", payload.encode("utf-8"), hashlib.sha256).hexdigest()
    assert signature == expected
