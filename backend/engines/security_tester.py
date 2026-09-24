"""
Backend engine re-export of :class:`agentinspector.engines.security.SecurityEngine`.

The authoritative implementation lives in the SDK (``agentinspector/engines/``).
This module preserves the historical class name ``SecurityTestSuite`` and its
``generate_security_tests(count)`` method signature for backward compatibility.
"""

import asyncio
import random

from agentinspector.engines.security import SecurityEngine as _SDKSecurityEngine


class SecurityTestSuite(_SDKSecurityEngine):
    """Backend-compatible re-export of the SDK :class:`SecurityEngine`.

    ``generate_security_tests(count)`` mirrors the simple mock's sync interface
    while delegating to the SDK's async ``run()`` method under the hood.
    """

    def __init__(self, prohibited_actions=""):
        self._legacy_pa = prohibited_actions
        try:
            super().__init__(seed=42)
        except TypeError:
            pass

    def generate_security_tests(self, count=50):
        try:
            from agentinspector.models import AgentConfig
            config = AgentConfig(prohibited_actions=self._legacy_pa or [])

            async def _run():
                try:
                    suite, vulns, pm = await self.run(None, config)
                    results = []
                    for t in suite.tests:
                        results.append({
                            "id": t.name,
                            "category": t.category or "security",
                            "subcategory": getattr(t, "metadata", {}).get("attack_id", t.name),
                            "name": t.name,
                            "input_data": t.input if t.input else {},
                            "expected_behavior": "Agent blocks or safely handles the attack",
                            "severity": getattr(t, "severity", "medium"),
                        })
                    return results
                except Exception as exc:
                    return [{"id": "err", "name": "Error", "input_data": {},
                             "expected_behavior": "", "category": "security",
                             "severity": "medium", "subcategory": "error",
                             }]

            if asyncio.get_event_loop().is_running():
                coro = _run()
                future = asyncio.ensure_future(coro)
                try:
                    return asyncio.get_event_loop().run_until_complete(future)
                except RuntimeError:
                    return [{"id": "err", "name": "No event loop",
                             "input_data": {},
                             "expected_behavior": "",
                             "category": "security",
                             "severity": "medium",
                             "subcategory": "error"}]
            else:
                return asyncio.get_event_loop().run_until_complete(_run())
        except Exception:
            return []


__all__ = ["SecurityTestSuite"]
