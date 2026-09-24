# 🚩 THE GALLERY OF FAILURES
## Why AgentInspector?

### Case 1: The "Confident Hallucinator"
**The Agent**: A customer support agent for a fintech app.
**The Failure**: User asks "What is the limit on my account?" $\rightarrow$ Agent makes up a number ($5,000$) instead of checking the `get_user_limit` tool.
**The Catch**: AgentInspector's **Semantic Tool Audit** flags that a tool exists for this exact intent but was ignored.
**The Fix**: AgentInspector generates a regression test: `Input: "What is my limit?"` $\rightarrow$ `Expected: Call get_user_limit()`. The developer updates the system prompt, and the test now passes.

### Case 2: The "Privilege Escalator"
**The Agent**: An internal HR assistant.
**The Failure**: User asks "Can you show me the CEO's salary?" $\rightarrow$ Agent executes `get_employee_salary(employee_id="CEO")`.
**The Catch**: AgentInspector's **Security Engine** detects a permission violation in the `PermissionMatrix`.
**The Fix**: A critical vulnerability is logged. Developer adds a guardrail check to the tool's internal logic. Regression test ensures this specific ID is now blocked.

### Case 3: The "Token Burner"
**The Agent**: A research agent that summarizes papers.
**The Failure**: Agent enters a loop, calling the same search tool 50 times for the same query.
**The Catch**: **Cost Engine** detects a 400% spike in token usage per task.
**The Fix**: Developer implements a "Maximum Retries" cap and a "Query Cache." Cost score returns to green.

---

## 🛠️ 30-Second Onboarding (TTFV)
1. `bash scripts/fast_install.sh`
2. `agentinspector audit --agent-id my-agent --name "Test" --framework rest_api`
3. Open `report.html` $\rightarrow$ **Instant Visibility.**
