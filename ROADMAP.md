# Product Roadmap: From "Tool" to "Standard"

## Phase 1: Friction Removal (Current)
- [x] **Fast Install**: One-click setup via `fast_install.sh`.
- [x] **Lifting the Fortress**: mTLS made optional by default in `nginx.conf`.
- [x] **Pivot**: Positioned as a Regression Testing Engine, not a general Ops platform.

## Phase 2: The Professionalization (Next 3 Months)
- [ ] **Frontend Migration**: Move from Streamlit to a Next.js/Tailwind app. The current dashboard is a prototype; the final product needs a high-density trace explorer.
- [ ] **CLI-First Workflow**: Make it possible to run full regression suites and view reports entirely in the terminal (JSON/Markdown output) without needing the dashboard.
- [ ] **Plugin System**: Allow custom "Oracles" for tool matching beyond TF-IDF.

## Phase 3: The Ecosystem (Long Term)
- [ ] **CI/CD Deep Integration**: Official GitHub Action and GitLab Runner for "Agent Guardrails" (block merge if regression tests fail).
- [ ] **Living Calibration**: Move from static `.jsonl` datasets to a dynamic feedback loop where production failures automatically update the calibration set.
- [ ] **Multi-Agent Orchestration Testing**: Extend the regression engine to handle multi-agent handoffs and race conditions.