"""
Load tests for AgentInspector backend API.

Usage:
    # Start backend first
    cd backend
    uvicorn main:app --host 0.0.0.0 --port 8000

    # Run load tests
    locust -f tests/load_test.py --host=http://localhost:8000 -u 50 -r 5 --run-time 2m

    # Run headless
    locust -f tests/load_test.py --host=http://localhost:8000 -u 50 -r 5 --run-time 2m --headless
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime

from locust import HttpUser, between, task


class AgentInspectorUser(HttpUser):
    wait_time = between(1, 4)
    api_key = "ai_test_key_placeholder"
    created_agent_ids: list[str] = []
    created_audit_ids: list[str] = []

    def on_start(self) -> None:
        if not self.api_key or self.api_key == "ai_test_key_placeholder":
            resp = self.client.post("/api/v1/keys?owner=loadtest&rate_limit=1000")
            if resp.status_code in (200, 201):
                data = resp.json()
                self.api_key = data.get("api_key", "")
            else:
                self.api_key = "ai_loadtest"

    def headers(self) -> dict:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    @task(5)
    def health(self) -> None:
        self.client.get("/health", headers=self.headers(), name="health")

    @task(3)
    def create_agent(self) -> None:
        agent_id = f"loadtest-{uuid.uuid4().hex[:8]}"
        payload = {
            "agent_id": agent_id,
            "agent_name": f"Load Test Agent {random.randint(1, 10000)}",
            "framework": random.choice(["rest_api", "openai", "langchain"]),
            "endpoint": None,
            "tools": [{"name": "lookup_customer", "description": "Look up a customer"}],
            "expected_capabilities": ["lookup"],
            "prohibited_actions": ["delete"],
            "system_prompt": "You are a helpful assistant.",
            "webhook_url": None,
            "priority": random.randint(0, 10),
        }
        with self.client.post("/api/v1/audit", json=payload, headers=self.headers(), catch_response=True, name="create_audit") as resp:
            if resp.status_code in (200, 201):
                data = resp.json()
                audit_id = data.get("audit_id")
                if audit_id:
                    self.created_audit_ids.append(audit_id)
                resp.success()
            else:
                resp.failure(f"create_audit failed: {resp.status_code} {resp.text[:200]}")

    @task(2)
    def list_audits(self) -> None:
        with self.client.get("/api/v1/audits", headers=self.headers(), catch_response=True, name="list_audits") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"list_audits failed: {resp.status_code}")

    @task(1)
    def get_audit(self) -> None:
        if not self.created_audit_ids:
            return
        audit_id = random.choice(self.created_audit_ids[-20:])
        with self.client.get(f"/api/v1/audits/{audit_id}", headers=self.headers(), catch_response=True, name="get_audit") as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 404:
                resp.success()
            else:
                resp.failure(f"get_audit failed: {resp.status_code}")
