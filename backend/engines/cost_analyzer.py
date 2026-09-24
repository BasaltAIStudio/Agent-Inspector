"""
Backend engine re-export of :class:`agentinspector.engines.cost.CostEngine`.

The authoritative implementation lives in the SDK (``agentinspector/engines/``).
This module preserves the historical class name ``CostAnalyzer`` and the
``analyze(list_of_dicts)`` / ``detect_anomalies(list_of_dicts)`` /
``estimate_monthly_cost(avg, requests)`` signatures that ``AgentAuditor`` and
``tests/test_backend.py`` rely on.
"""

import statistics
from typing import Any, Dict, List

from agentinspector.engines.cost import CostEngine as _SDKCostEngine


def _to_dict(obj):
    """Convert a dataclass or object to a plain dict, with field-name mapping."""
    if hasattr(obj, "__dataclass_fields__"):
        raw = {f: getattr(obj, f) for f in obj.__dataclass_fields__}
        raw["avg_cost_per_test"] = raw.pop("avg_cost_per_task", raw.get("avg_cost_per_test", 0))
        raw.setdefault("findings", [])
        return raw
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return obj


class CostAnalyzer(_SDKCostEngine):
    """Backend-compatible re-export of the SDK :class:`CostEngine`.

    Adds compatibility methods that accept the list-of-dicts format the
    simple mock used, while delegating ``analyze()`` to the authoritative
    SDK implementation.
    """

    def analyze(self, test_results=None, **kwargs):
        if test_results is not None and not hasattr(test_results, "tests"):
            try:
                from agentinspector.models import ExecutionTrace
                traces = []
                for d in test_results:
                    if isinstance(d, ExecutionTrace):
                        traces.append(d)
                    elif isinstance(d, dict):
                        traces.append(ExecutionTrace(
                            model=d.get("model", "gpt-4o-mini"),
                            tokens_input=d.get("tokens_used", 0),
                            tokens_output=d.get("tokens_used", 0) // 2,
                            total_cost=d.get("cost", 0.0),
                            response=d.get("actual", ""),
                            trace_id=d.get("test_name", ""),
                        ))
                raw = _SDKCostEngine.analyze(self, traces=traces)
                return _to_dict(raw)
            except Exception:
                pass
        return _SDKCostEngine.analyze(self)

    def detect_anomalies(self, test_results):
        """Backward-compat: replicate backend mock's cost-based anomaly detection."""
        costs = [t["cost"] for t in test_results if isinstance(t, dict) and t.get("cost")]
        if len(costs) < 2:
            return []
        mean = statistics.mean(costs)
        stdev = statistics.stdev(costs)
        if stdev == 0:
            return []
        findings = []
        for t in test_results:
            cost = t.get("cost", 0)
            if cost > mean + 2 * stdev:
                findings.append({
                    "category": "cost_anomaly",
                    "severity": "high",
                    "title": "Cost anomaly detected",
                    "description": (
                        f"Test '{t.get('test_name', 'unknown')}' "
                        f"cost ${cost:.4f}, which is >2σ above mean ${mean:.4f}"
                    ),
                    "remediation": "Review test configuration and model selection for this test",
                    "estimated_savings": f"${cost - mean:.4f} per occurrence",
                })
        return findings

    def estimate_monthly_cost(self, avg_cost_per_request, monthly_requests=100000):
        """Backward-compat: replicate backend mock's monthly cost estimate."""
        current_monthly = avg_cost_per_request * monthly_requests
        optimized_monthly = avg_cost_per_request * 0.3 * monthly_requests
        savings = current_monthly - optimized_monthly
        return {
            "current_monthly": current_monthly,
            "optimized_monthly": optimized_monthly,
            "savings": savings,
            "savings_percent": (savings / current_monthly * 100) if current_monthly > 0 else 0,
        }


__all__ = ["CostAnalyzer"]
