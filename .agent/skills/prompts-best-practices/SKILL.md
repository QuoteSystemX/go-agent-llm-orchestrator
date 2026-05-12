---
name: prompts-best-practices
description: Advanced prompt engineering techniques for improving agent accuracy and reasoning.
version: 1.0.0
---

# 🧠 Prompt Engineering Best Practices

Expert guidelines for crafting high-performance prompts and structured reasoning for AI agents within the Paperclip ecosystem.

## 🏗 Structural Patterns

- **Role Priming**: Define a clear persona with deep domain expertise (e.g., "You are a Senior SRE...").
- **Context Pinning**: Provide specific project state, critical file contents, and environmental constraints.
- **Few-Shot Examples**: Include 2-3 examples of the input-output mapping to guide the model towards the desired logic.
- **Output Schemas**: Explicitly define the output format (Markdown, JSON, XML) to ensure machine-readability.

## 🛠 Reasoning & Safety

- **Chain of Thought**: Explicitly ask the model to "think step-by-step" or "analyze the problem before answering".
- **Constraints**: Use negative constraints ("NEVER...", "AVOID...") to keep the model within safety guardrails.
- **Socratic Gate**: Instruct the model to ask clarifying questions if the input is ambiguous.

## 🚀 Tools & Verification

### 1. Prompt Auditor
Run the internal script to analyze agent definitions for missing roles or constraints:

```bash
python3 .agent/skills/prompts-best-practices/scripts/verify_prompts.py
```

### 2. Standard Templates
Refer to `examples/expert-role.md` for a "Golden Path" implementation of a structured expert prompt.

## 📈 Prompt Hygiene Checklist
- [ ] Is there a clear Role defined?
- [ ] Are there explicit Constraints?
- [ ] Is the Output Format specified?
- [ ] Is Context provided or requested?
- [ ] Does it encourage reasoning (CoT)?

---
> **Note**: This skill ensures that all agents maintain the highest cognitive performance and reliability.

