"""
Backend engine re-export of :class:`agentinspector.engines.tool_audit.ToolAuditEngine`.

The authoritative implementation lives in the SDK (``agentinspector/engines/``).
This module preserves the historical class name ``ToolAuditEngine`` for
backward compatibility with any existing backend code.
"""

from agentinspector.engines.tool_audit import ToolAuditEngine as _SDKToolAuditEngine


class ToolAuditEngine(_SDKToolAuditEngine):
    """Backend-compatible re-export of the SDK :class:`ToolAuditEngine`."""

    pass


__all__ = ["ToolAuditEngine"]
