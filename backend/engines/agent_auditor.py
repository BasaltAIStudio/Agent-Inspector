import random
import time
import uuid
from typing import List, Dict, Any
from datetime import datetime
from .test_generator import TestGenerator
from .security_tester import SecurityTestSuite
from .tool_auditor import ToolAuditTest
from .cost_analyzer import CostAnalyzer
from .report_generator import ReportGenerator
from ..database import get_db
from ..database import Audit, Finding, TestResult, Agent


class AgentAuditor:
    def __init__(self, agent_id: str, expected_behavior: str, prohibited_actions: str = "", 
                 test_count: int = 100, include_security: bool = True, include_cost: bool = True,
                 audit_id: str = None):
        self.agent_id = agent_id
        self.expected_behavior = expected_behavior
        self.prohibited_actions = prohibited_actions
        self.test_count = test_count
        self.include_security = include_security
        self.include_cost = include_cost
        self.audit_id = audit_id or str(uuid.uuid4())
        self.test_generator = TestGenerator(expected_behavior, prohibited_actions, test_count)
        self.security_tester = SecurityTestSuite(prohibited_actions)
        self.tool_auditor = ToolAuditTest()
        self.cost_analyzer = CostAnalyzer()
        self.report_generator = ReportGenerator()
        self.test_results: List[Dict[str, Any]] = []
        self.findings: List[Dict[str, Any]] = []

    def run_audit(self, db, audit_obj=None) -> Dict[str, Any]:
        if audit_obj:
            audit = audit_obj
        else:
            from ..database import Audit
            audit = Audit(
                id=self.audit_id,
                agent_id=self.agent_id,
                status="running",
            )
            db.add(audit)
        db.commit()

        try:
            self._generate_tests()
            self._execute_tests()
            self._analyze_results()

            scores = self.report_generator.generate_scores(self.test_results, self.findings)

            audit.status = "completed"
            audit.overall_score = scores.get("overall")
            audit.reliability_score = scores.get("reliability")
            audit.security_score = scores.get("security")
            audit.tool_usage_score = scores.get("tool_usage")
            audit.hallucination_score = scores.get("hallucination")
            audit.privacy_score = scores.get("privacy")
            audit.cost_score = scores.get("cost")
            audit.latency_score = scores.get("latency")
            audit.instruction_following_score = scores.get("instruction_following")
            audit.human_escalation_score = scores.get("human_escalation")
            audit.test_count = len(self.test_results)
            audit.findings_count = len(self.findings)
            audit.critical_count = sum(1 for f in self.findings if f.get("severity") == "critical")
            audit.high_count = sum(1 for f in self.findings if f.get("severity") == "high")
            audit.medium_count = sum(1 for f in self.findings if f.get("severity") == "medium")
            audit.low_count = sum(1 for f in self.findings if f.get("severity") == "low")
            audit.completed_at = datetime.utcnow()
            db.commit()
            
            for finding in self.findings:
                db_finding = Finding(
                    id=str(uuid.uuid4()),
                    audit_id=self.audit_id,
                    category=finding.get("category", "unknown"),
                    severity=finding.get("severity", "low"),
                    title=finding.get("title", ""),
                    description=finding.get("description", ""),
                    evidence=finding.get("evidence", ""),
                    remediation=finding.get("remediation", ""),
                    reproducibility=finding.get("reproducibility", 0.0),
                )
                db.add(db_finding)
            
            for test in self.test_results:
                db_test = TestResult(
                    id=str(uuid.uuid4()),
                    audit_id=self.audit_id,
                    test_name=test.get("test_name", ""),
                    category=test.get("category", ""),
                    status=test.get("status", "unknown"),
                    input_data=str(test.get("input_data", {})),
                    output_data=str(test.get("output_data", {})),
                    expected=test.get("expected", ""),
                    actual=test.get("actual", ""),
                    latency_ms=test.get("latency_ms", 0.0),
                    cost=test.get("cost", 0.0),
                    tokens_used=test.get("tokens_used", 0),
                )
                db.add(db_test)
            
            db.commit()
            
            report = self.report_generator.generate_report(
                self.audit_id, scores, self.findings, self.test_results
            )
            
            return {
                "audit_id": self.audit_id,
                "status": "completed",
                "scores": scores,
                "report": report,
                "test_count": len(self.test_results),
                "findings_count": len(self.findings),
            }
            
        except Exception as e:
            audit.status = "failed"
            db.commit()
            raise e

    def _generate_tests(self):
        behavior_tests = self.test_generator.generate()
        self.test_results.extend([
            {
                "test_name": t.name,
                "category": t.category,
                "status": "pending",
                "input_data": t.input_data,
                "expected": t.expected_behavior,
                "latency_ms": 0,
                "cost": 0,
                "tokens_used": 0,
            }
            for t in behavior_tests
        ])
        
        if self.include_security:
            security_tests = self.security_tester.generate_security_tests(50)
            self.test_results.extend([
                {
                    "test_name": t["name"],
                    "category": t["category"],
                    "status": "pending",
                    "input_data": t["input_data"],
                    "expected": t["expected_behavior"],
                    "latency_ms": 0,
                    "cost": 0,
                    "tokens_used": 0,
                }
                for t in security_tests
            ])
        
        tool_tests = self.tool_auditor.generate_tool_tests(30)
        self.test_results.extend([
            {
                "test_name": t["name"],
                "category": t["category"],
                "status": "pending",
                "input_data": t["input_data"],
                "expected": t["expected_behavior"],
                "latency_ms": 0,
                "cost": 0,
                "tokens_used": 0,
            }
            for t in tool_tests
        ])

    def _execute_tests(self):
        for i, test in enumerate(self.test_results):
            start_time = time.time()
            
            latency = random.uniform(10, 100)
            cost = random.uniform(0.0001, 0.01)
            tokens = random.randint(10, 200)
            
            time.sleep(min(latency / 10000, 0.01))
            
            status = self._simulate_test_result(test)
            
            test["status"] = status
            test["latency_ms"] = latency
            test["cost"] = cost
            test["tokens_used"] = tokens
            test["output_data"] = f"Simulated output for {test['test_name']}"
            test["actual"] = "Pass" if status == "pass" else f"Failed: {test['test_name']}"

    def _simulate_test_result(self, test: Dict[str, Any]) -> str:
        category = test.get("category", "")
        subcategory = test.get("input_data", {}).get("type", "")
        
        if category == "security":
            if subcategory in ["prompt_injection", "privilege_escalation"]:
                return "pass" if random.random() > 0.25 else "fail"
            return "pass" if random.random() > 0.15 else "fail"
        
        if category == "tool_usage":
            if subcategory in ["tool_loops", "tool_hallucination"]:
                return "pass" if random.random() > 0.3 else "fail"
            return "pass" if random.random() > 0.2 else "fail"
        
        if category == "cost":
            return "pass" if random.random() > 0.4 else "fail"
        
        base_pass_rate = {
            "instruction_following": 0.85,
            "task_completion": 0.80,
            "consistency": 0.75,
            "multi_step_reasoning": 0.70,
            "context_retention": 0.78,
            "long_conversation": 0.65,
            "ambiguous_requests": 0.72,
            "contradictory_instructions": 0.68,
            "human_escalation": 0.60,
            "chaos_resilience": 0.70,
            "hallucination": 0.75,
        }.get(subcategory, 0.75)
        
        return "pass" if random.random() < base_pass_rate else "fail"

    def _analyze_results(self):
        self.findings = self.report_generator.generate_findings_from_tests(self.test_results)
        
        if self.include_cost:
            cost_analysis = self.cost_analyzer.analyze(self.test_results)
            for finding in cost_analysis.get("findings", []):
                self.findings.append(finding)
