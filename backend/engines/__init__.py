"""Backend engine wrappers and re-exports.

The canonical implementations live in the SDK package ``agentinspector/engines/``.
This module provides backward-compatible wrappers that preserve the historical
class names and constructor signatures used by ``AgentAuditor`` and older
backend code.

Active backend paths (``backend/routers/audits.py``, ``backend/celery_worker.py``)
use the SDK ``Inspector`` directly. The legacy ``AgentAuditor`` orchestrator
and its wrappers remain available for backward compatibility but are not used
by the current API or worker code paths.
"""

from agentinspector.engines.cost import CostEngine as SDKCostEngine
from agentinspector.engines.security import SecurityEngine as SDKSecurityEngine
from agentinspector.engines.test_generator import TestGenerator as SDKTestGenerator
from agentinspector.engines.tool_audit import ToolAuditEngine as SDKToolAuditEngine

from backend.engines.cost_analyzer import CostAnalyzer
from backend.engines.report_generator import ReportGenerator
from backend.engines.security_tester import SecurityTestSuite
from backend.engines.test_generator import TestGenerator as BackendTestGenerator
from backend.engines.tool_auditor import ToolAuditEngine as BackendToolAuditEngine
from backend.engines.webhook_queue import WebhookQueue

__all__ = [
    "SDKCostEngine",
    "SDKSecurityEngine",
    "SDKTestGenerator",
    "SDKToolAuditEngine",
    "CostAnalyzer",
    "ReportGenerator",
    "SecurityTestSuite",
    "BackendTestGenerator",
    "BackendToolAuditEngine",
    "WebhookQueue",
]
