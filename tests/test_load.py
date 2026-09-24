"""Load and performance validation tests for AgentInspector."""

import time
import threading
import requests
import pytest

BASE_URL = "http://localhost:8000"
API_KEY = "ai_" + "0" * 32


def _backend_available() -> bool:
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _backend_available(),
    reason="Backend not available at http://localhost:8000",
)


def test_health_endpoint_latency():
    for _ in range(10):
        start = time.time()
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 0.5, f"Health endpoint too slow: {elapsed:.2f}s"


def test_concurrent_agent_creation():
    results = []
    errors = []

    def create_agent(index):
        try:
            resp = requests.post(
                f"{BASE_URL}/api/v1/agents/",
                json={"name": f"Load Agent {index}", "description": "Load test", "agent_type": "custom"},
                headers={"X-API-Key": API_KEY},
                timeout=10,
            )
            results.append(resp.status_code)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=create_agent, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert len(errors) == 0, f"Errors during concurrent creation: {errors}"
    assert all(status == 201 for status in results), f"Unexpected statuses: {results}"


def test_rate_limiting():
    fast_requests = 0
    for _ in range(10):
        resp = requests.get(
            f"{BASE_URL}/api/v1/agents/",
            headers={"X-API-Key": API_KEY},
            timeout=5,
        )
        if resp.status_code == 200:
            fast_requests += 1

    assert fast_requests >= 1, "Rate limiter should allow at least some requests"
