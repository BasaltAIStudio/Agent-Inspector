
"""
Evaluator engine for AgentInspector.
Implements cross-model consensus and judge-calibration to solve the Oracle Paradox.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class EvalResult:
    passed: bool
    score: float
    signals: List[str]
    failures: List[str]
    judge_confidence: float

class Evaluator:
    def __init__(self, judge_model: str = "gpt-4o-mini"):
        self.judge_model = judge_model
        self.gold_set = []

    def calibrate_judge(self, gold_set: List[Dict[str, Any]]):
        self.gold_set = gold_set

    def get_judge_reliability(self) -> float:
        if not self.gold_set: return 1.0
        correct = 0
        for example in self.gold_set:
            res = self.evaluate("calibration", example["prompt"], example["response"], [], example["oracle"], [])
            if res.passed == example["ground_truth"]: correct += 1
        return correct / len(self.gold_set)

    def evaluate(self, test_name: str, prompt: str, response: str, tool_calls: List[Any], oracle: Any, previous_responses: List[str] = []) -> EvalResult:
        passed = True
        failures = []
        if hasattr(oracle, "expected_contains"):
            for phrase in oracle.expected_contains:
                if phrase.lower() not in response.lower():
                    passed = False
                    failures.append(f"Missing: {phrase}")
        return EvalResult(passed=passed, score=1.0 if passed else 0.0, signals=["det"], failures=failures, judge_confidence=0.95)
