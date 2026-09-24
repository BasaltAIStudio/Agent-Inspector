# Competitive Positioning: The "Regression Gap"

## The Market Problem
Most agent tools (Langfuse, Arize, Promptfoo) fall into two camps:
1. **Observability (The "Mirror")**: They show you what happened (traces), but they don't tell you if it was *correct* relative to a baseline.
2. **Red-Teaming (The "Hammer")**: They try to break the agent once, but they don't provide a systematic way to prevent regressions over time.

## AgentInspector's Position: The "Safety Net"
AgentInspector fills the gap between observing and red-teaming by providing a **Regression Suite**.

| Feature | Langfuse/Arize | Promptfoo | **AgentInspector** |
| :--- | :---: | :---: | :---: |
| **Traces/Logs** | ✅ | ❌ | ✅ |
| **One-off Evals** | ✅ | ✅ | ✅ |
| **Auto-Regressions** | ❌ | ❌ | ✅ (Failure $\rightarrow$ Test) |
| **Semantic Tool Audit**| ❌ | ❌ | ✅ (TF-IDF Matching) |
| **On-Prem/Air-Gapped** | Partial | ✅ | ✅ (Local-First) |
| **Admin Secret Vault** | ❌ | ❌ | ✅ |

## Why we win
We win by reducing the "Developer Anxiety" of updating an agent. 

Instead of saying *"I think the new prompt improved things,"* developers can say *"I ran the AgentInspector suite, and the 45 regression tests generated from previous failures all passed."*