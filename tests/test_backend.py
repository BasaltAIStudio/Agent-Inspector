import pytest
from fastapi.testclient import TestClient
from backend.database import engine as db_engine, Base, get_db, APIKeyRecord, SessionLocal
from backend.main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def admin_api_key():
    db = TestingSessionLocal()
    try:
        key = "ai_" + "0" * 32
        record = APIKeyRecord(key=key, owner="test-admin", rate_limit=100, scopes="admin", revoked=False)
        db.add(record)
        db.commit()
        return key
    finally:
        db.close()


@pytest.fixture
def api_key(admin_api_key):
    response = client.post(
        "/api/v1/keys?owner=test&rate_limit=100",
        headers={"X-API-Key": admin_api_key},
    )
    assert response.status_code == 200, response.text
    return response.json()["api_key"]


@pytest.fixture
def auth_headers(api_key):
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


class TestAgentEndpoints:
    def test_create_agent(self):
        response = client.post(
            "/api/v1/agents/",
            json={
                "name": "Test Agent",
                "description": "A test agent",
                "agent_type": "custom",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Agent"
        assert "id" in data

    def test_list_agents(self):
        client.post(
            "/api/v1/agents/",
            json={"name": "Agent 1", "description": "First agent", "agent_type": "custom"},
        )
        client.post(
            "/api/v1/agents/",
            json={"name": "Agent 2", "description": "Second agent", "agent_type": "openai"},
        )
        
        response = client.get("/api/v1/agents/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_agent(self):
        create_response = client.post(
            "/api/v1/agents/",
            json={"name": "Test Agent", "description": "Test", "agent_type": "custom"},
        )
        agent_id = create_response.json()["id"]
        
        response = client.get(f"/api/v1/agents/{agent_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Agent"

    def test_get_agent_not_found(self):
        response = client.get("/api/v1/agents/nonexistent")
        assert response.status_code == 404

    def test_delete_agent(self, api_key):
        create_response = client.post(
            "/api/v1/agents/",
            json={"name": "To Delete", "description": "Will be deleted", "agent_type": "custom"},
        )
        agent_id = create_response.json()["id"]
        
        response = client.delete(
            f"/api/v1/agents/{agent_id}",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        
        get_response = client.get(f"/api/v1/agents/{agent_id}")
        assert get_response.status_code == 404


class TestAuditEndpoints:
    def test_create_audit(self, auth_headers):
        agent_response = client.post(
            "/api/v1/agents/",
            json={"name": "Audit Test Agent", "description": "Test", "agent_type": "custom"},
        )
        agent_id = agent_response.json()["id"]
    
        response = client.post(
            "/api/v1/audit",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "agent_name": "Audit Test Agent",
                "framework": "rest_api",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == agent_id
        assert data["status"] == "queued"

    def test_list_audits(self, auth_headers):
        agent_response = client.post(
            "/api/v1/agents/",
            json={"name": "List Test Agent", "description": "Test", "agent_type": "custom"},
        )
        agent_id = agent_response.json()["id"]
    
        client.post(
            "/api/v1/audit",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "agent_name": "List Test Agent",
                "framework": "rest_api",
            },
        )
    
        response = client.get("/api/v1/audits", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_get_audit_detail(self, auth_headers):
        agent_response = client.post(
            "/api/v1/agents/",
            json={"name": "Detail Test Agent", "description": "Test", "agent_type": "custom"},
        )
        agent_id = agent_response.json()["id"]
        
        audit_response = client.post(
            "/api/v1/audit",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "agent_name": "Detail Test Agent",
                "framework": "rest_api",
            },
        )
        audit_id = audit_response.json()["audit_id"]
        
        response = client.get(f"/api/v1/audits/{audit_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["audit_id"] == audit_id

    def test_get_audit_tests(self, auth_headers):
        agent_response = client.post(
            "/api/v1/agents/",
            json={"name": "Tests Test Agent", "description": "Test", "agent_type": "custom"},
        )
        agent_id = agent_response.json()["id"]
        
        audit_response = client.post(
            "/api/v1/audit",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "agent_name": "Tests Test Agent",
                "framework": "rest_api",
            },
        )
        audit_id = audit_response.json()["audit_id"]
        
        response = client.get(f"/api/v1/audits/{audit_id}/tests", headers=auth_headers)
        assert response.status_code == 200


class TestHealthEndpoint:
    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestCostAnalyzer:
    def test_analyze(self):
        from backend.engines.cost_analyzer import CostAnalyzer
        
        analyzer = CostAnalyzer()
        test_results = [
            {"status": "pass", "cost": 0.01, "latency_ms": 500, "tokens_used": 100},
            {"status": "fail", "cost": 0.02, "latency_ms": 2000, "tokens_used": 200},
            {"status": "pass", "cost": 0.005, "latency_ms": 300, "tokens_used": 50},
        ]
        
        result = analyzer.analyze(test_results)
        
        assert "total_cost" in result
        assert "avg_cost_per_test" in result
        assert "findings" in result
        assert result["total_cost"] == 0.035

    def test_estimate_monthly_cost(self):
        from backend.engines.cost_analyzer import CostAnalyzer
        
        analyzer = CostAnalyzer()
        result = analyzer.estimate_monthly_cost(0.01, 100000)
        
        assert result["current_monthly"] == 1000
        assert result["optimized_monthly"] == 300
        assert result["savings"] == 700
        assert result["savings_percent"] == 70

    def test_detect_cost_anomalies(self):
        from backend.engines.cost_analyzer import CostAnalyzer
        
        analyzer = CostAnalyzer()
        normal_results = [
            {"status": "pass", "cost": 0.01, "latency_ms": 500, "tokens_used": 100, "test_name": f"normal{i}"}
            for i in range(10)
        ]
        anomaly_result = {"status": "pass", "cost": 10.0, "latency_ms": 500, "tokens_used": 100, "test_name": "expensive"}
        findings = analyzer.detect_anomalies(normal_results + [anomaly_result])
        assert len(findings) == 1
        assert "expensive" in findings[0]["description"]


class TestDeleteEndpoints:
    def test_delete_audit(self, api_key):
        agent_response = client.post(
            "/api/v1/agents/",
            json={"name": "Delete Audit Agent", "description": "Test", "agent_type": "custom"},
        )
        agent_id = agent_response.json()["id"]

        audit_response = client.post(
            "/api/v1/audit",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={
                "agent_id": agent_id,
                "agent_name": "Delete Audit Agent",
                "framework": "rest_api",
            },
        )
        audit_id = audit_response.json()["audit_id"]

        response = client.delete(
            f"/api/v1/audits/{audit_id}",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        assert response.json()["audit_id"] == audit_id

        get_response = client.get(
            f"/api/v1/audits/{audit_id}",
            headers={"X-API-Key": api_key},
        )
        assert get_response.status_code == 404


class TestAdminEndpoints:
    def test_list_keys(self, admin_api_key):
        response = client.get("/api/v1/keys", headers={"X-API-Key": admin_api_key})
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data

    def test_list_agents_admin(self, admin_api_key):
        response = client.get("/api/v1/admin/agents", headers={"X-API-Key": admin_api_key})
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data

    def test_list_logs(self, admin_api_key):
        response = client.get("/api/v1/logs", headers={"X-API-Key": admin_api_key})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_upsert_and_read_secret(self, admin_api_key):
        upsert_response = client.post(
            "/api/v1/secrets/test_secret",
            params={"value": "secret_value"},
            headers={"X-API-Key": admin_api_key},
        )
        assert upsert_response.status_code == 200

        read_response = client.get(
            "/api/v1/secrets/test_secret",
            headers={"X-API-Key": admin_api_key},
        )
        assert read_response.status_code == 200
        assert read_response.json()["value"] == "secret_value"

    def test_rotate_secret(self, admin_api_key):
        client.post(
            "/api/v1/secrets/rotate_secret",
            params={"value": "initial_value"},
            headers={"X-API-Key": admin_api_key},
        )
        rotate_response = client.post(
            "/api/v1/secrets/rotate_secret/rotate",
            headers={"X-API-Key": admin_api_key},
        )
        assert rotate_response.status_code == 200
        assert rotate_response.json()["rotated"] == "true"

    def test_sign_payload(self, admin_api_key):
        sign_response = client.post(
            "/api/v1/sign",
            params={"secret_name": "signing_secret", "payload": "test_payload"},
            headers={"X-API-Key": admin_api_key},
        )
        assert sign_response.status_code == 404


class TestMetricsAndDashboard:
    def test_metrics(self, api_key):
        response = client.get("/api/v1/metrics", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert "total_audits" in data
        assert "success_rate" in data

    def test_dashboard(self, api_key):
        response = client.get("/api/v1/dashboard", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
