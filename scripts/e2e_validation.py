"""End-to-end validation script for AgentInspector backend."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine as db_engine, get_db, APIKeyRecord, SessionLocal

Base.metadata.drop_all(bind=db_engine)
Base.metadata.create_all(bind=db_engine)


def override_get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

AGENT_NAME = "e2e-validation-agent"


def main() -> None:
    db = SessionLocal()
    try:
        print("==> Seeding admin API key")
        admin_key = "ai_" + "0" * 32
        admin_record = APIKeyRecord(key=admin_key, owner="e2e-admin", rate_limit=100, scopes="admin", revoked=False)
        db.add(admin_record)
        db.commit()
        print(f"    admin key={admin_key}")
    finally:
        db.close()

    print("==> Creating regular API key")
    key_resp = client.post(
        "/api/v1/keys?owner=e2e-user&rate_limit=100",
        headers={"X-API-Key": admin_key},
    )
    assert key_resp.status_code == 200, key_resp.text
    api_key = key_resp.json()["api_key"]
    print(f"    api_key={api_key}")

    print("==> Creating agent")
    create_resp = client.post(
        "/api/v1/agents",
        json={"name": AGENT_NAME, "provider": "openai", "model": "gpt-4o", "description": "E2E validation agent"},
    )
    assert create_resp.status_code == 201, create_resp.text
    agent = create_resp.json()
    agent_id = agent["id"]
    print(f"    created agent {agent_id}")

    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    print("==> Creating audit")
    audit_resp = client.post(
        "/api/v1/audit",
        json={"agent_id": agent_id, "agent_name": AGENT_NAME, "framework": "rest_api", "include_security": True, "include_behaviour": True, "include_cost": True},
        headers=headers,
    )
    assert audit_resp.status_code in (200, 201), audit_resp.text
    audit = audit_resp.json()
    audit_id = audit["audit_id"]
    print(f"    created audit {audit_id}")

    print("==> Fetching audit detail")
    detail_resp = client.get(f"/api/v1/audits/{audit_id}", headers=headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    print(f"    audit status={detail.get('status')}")

    print("==> Fetching audit tests")
    tests_resp = client.get(f"/api/v1/audits/{audit_id}/tests", headers=headers)
    assert tests_resp.status_code == 200, tests_resp.text
    tests = tests_resp.json()
    print(f"    test_count={len(tests)}")

    print("==> Health check")
    health = client.get("/health")
    assert health.status_code == 200, health.text
    print(f"    health={health.json()}")

    print("==> E2E validation passed")


if __name__ == "__main__":
    main()
