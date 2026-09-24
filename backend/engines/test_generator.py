"""
Backend engine re-export of :class:`agentinspector.engines.test_generator.TestGenerator`.

The authoritative implementation lives in the SDK (``agentinspector/engines/``).
This module preserves the historical class name ``TestGenerator`` and its
three-argument constructor ``(expected_behavior, prohibited_actions, test_count)``
that :class:`AgentAuditor` relies on, while delegating test production to
the SDK implementation.
"""

import random

from agentinspector.engines.test_generator import TestGenerator as _SDKTestGenerator


class TestGenerator(_SDKTestGenerator):
    """Backend-compatible re-export of the SDK :class:`TestGenerator`.

    Accepts the legacy three-argument constructor ``(expected_behavior,
    prohibited_actions, test_count)`` used by :class:`AgentAuditor`,
    then creates the underlying ``AgentConfig`` internally and delegates
    to the SDK ``generate_suite()`` implementation.
    """

    def __init__(self, expected_behavior, prohibited_actions=None, test_count=100):
        self._legacy_eb = expected_behavior
        self._legacy_pa = prohibited_actions or ""
        self._legacy_tc = test_count
        try:
            from agentinspector.models import AgentConfig
            config = AgentConfig(
                expected_capabilities=[],
                prohibited_actions=prohibited_actions or [],
            )
            super().__init__(config, seed=42)
        except Exception:
            pass  # fall back to no-arg init; generate() will produce empty list

    def generate(self):
        try:
            suite = self.generate_suite()
            results = []
            for test in suite.tests:
                from types import SimpleNamespace
                results.append(SimpleNamespace(
                    name=test.name,
                    category=test.category,
                    input_data=test.input if test.input else {},
                    expected_behavior=self._legacy_eb,
                ))
            return results
        except Exception:
            return []


__all__ = ["TestGenerator"]
