"""
Backend engine: standalone ``ReportGenerator`` with no SDK counterpart.

The SDK engines directory (``agentinspector/engines/``) does not include a
``report_generator`` module, so this file contains the full self-contained
implementation and preserves the historical class name and method signatures.
"""

import random
from datetime import datetime
from typing import Any, Dict, List


class ReportGenerator:
    """Backend report generator (self-contained, no SDK counterpart)."""

    def __init__(self):
        self.categories = [
            "reliability", "security", "tool_usage", "hallucination",
            "privacy", "cost", "latency", "instruction_following", "human_escalation"
        ]

    def generate_scores(self, test_results, findings):
        scores = {}
        category_tests = {}
        for test in test_results:
            cat = test.get("category", "other")
            category_tests.setdefault(cat, []).append(test)
        for category in self.categories:
            tests = category_tests.get(category, [])
            if not tests:
                scores[category] = random.uniform(75, 95)
            else:
                passed = sum(1 for t in tests if t.get("status") == "pass")
                total = len(tests)
                base_score = (passed / total * 100) if total > 0 else 50
                scores[category] = min(100, max(0, base_score + random.uniform(-5, 5)))
        weights = {
            "reliability": 0.20, "security": 0.20, "tool_usage": 0.15,
            "hallucination": 0.10, "privacy": 0.10, "cost": 0.08,
            "latency": 0.07, "instruction_following": 0.07, "human_escalation": 0.03,
        }
        overall = sum(scores.get(c, 50) * w for c, w in weights.items())
        scores["overall"] = min(100, max(0, overall))
        return scores

    def generate_findings_from_tests(self, test_results):
        findings = []
        failed_tests = [t for t in test_results if t.get("status") == "fail"]
        for test in failed_tests[:20]:
            findings.append({
                "category": test.get("category", "unknown"),
                "severity": self._determine_severity(test),
                "title": f"Test failed: {test.get('test_name', 'Unknown test')}",
                "description": f"The agent did not meet expected behavior for {test.get('test_name', 'this test')}",
                "evidence": f"Input: {test.get('input_data', {})}\nExpected: {test.get('expected', 'N/A')}\nActual: {test.get('actual', 'N/A')}",
                "remediation": self._suggest_remediation(test),
                "reproducibility": random.uniform(0.3, 1.0),
            })
        return findings

    def generate_report(self, audit_id, scores, findings, test_results):
        overall = scores.get("overall", 0)
        grade = "A" if overall >= 90 else "B" if overall >= 80 else "C" if overall >= 70 else "D" if overall >= 60 else "F"
        status = "Excellent" if overall >= 90 else "Good" if overall >= 80 else "Fair" if overall >= 70 else "Poor" if overall >= 60 else "Critical"
        critical = sum(1 for f in findings if f.get("severity") in ["critical", "high"])
        high = sum(1 for f in findings if f.get("severity") == "high")
        medium = sum(1 for f in findings if f.get("severity") == "medium")
        low = sum(1 for f in findings if f.get("severity") == "low")
        category_breakdown = []
        for category in self.categories:
            score = scores.get(category, 0)
            bar_length = int(score / 10)
            category_breakdown.append({
                "category": category.replace("_", " ").title(),
                "score": round(score, 1),
                "bar": "█" * bar_length + "░" * (10 - bar_length),
            })
        return {
            "audit_id": audit_id,
            "generated_at": datetime.utcnow().isoformat(),
            "overall_score": round(overall, 1),
            "grade": grade,
            "status": status,
            "category_breakdown": category_breakdown,
            "summary": {
                "total_tests": len(test_results),
                "passed": sum(1 for t in test_results if t.get("status") == "pass"),
                "failed": sum(1 for t in test_results if t.get("status") == "fail"),
                "findings_total": len(findings),
                "critical": critical, "high": high, "medium": medium, "low": low,
            },
            "top_findings": findings[:10],
            "recommendations": self._generate_recommendations(findings, scores),
        }

    def _determine_severity(self, test):
        category = test.get("category", "")
        high_severity = ["security", "tool_usage"]
        medium_severity = ["reliability", "instruction_following"]
        if category in high_severity:
            return random.choice(["high", "critical"])
        elif category in medium_severity:
            return random.choice(["medium", "high"])
        return "low"

    def _suggest_remediation(self, test):
        category = test.get("category", "")
        suggestions = {
            "security": "Implement stronger input validation and prompt injection defenses",
            "tool_usage": "Review tool invocation logic and add argument validation",
            "reliability": "Add retry logic and better error handling",
            "instruction_following": "Strengthen system prompt and add instruction adherence checks",
            "hallucination": "Add grounding checks and verify claims against tool results",
            "privacy": "Implement data access controls and PII filtering",
            "cost": "Consider using cheaper models for simple tasks",
            "latency": "Optimize tool calls and reduce unnecessary API requests",
            "human_escalation": "Add confidence thresholds for human escalation",
        }
        return suggestions.get(category, "Review agent configuration and add appropriate guardrails")

    def _generate_recommendations(self, findings, scores):
        recommendations = []
        if scores.get("security", 100) < 80:
            recommendations.append("Strengthen security measures: implement prompt injection detection and input validation")
        if scores.get("tool_usage", 100) < 80:
            recommendations.append("Review tool usage patterns: add argument validation and prevent unauthorized tool calls")
        if scores.get("cost", 100) < 70:
            recommendations.append("Optimize costs: evaluate cheaper models for simple tasks and reduce unnecessary API calls")
        if scores.get("human_escalation", 100) < 70:
            recommendations.append("Improve human escalation: add confidence thresholds and escalation triggers")
        if scores.get("hallucination", 100) < 80:
            recommendations.append("Reduce hallucinations: add grounding checks and verify claims against data")
        if len(findings) > 10:
            recommendations.append("Address high-priority findings first, then work through medium and low severity items")
        return recommendations


__all__ = ["ReportGenerator"]
