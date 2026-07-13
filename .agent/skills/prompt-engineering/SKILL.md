---
name: prompt-engineering
description: Expert skill for designing, testing, and optimizing LLM prompts. Covers Chain-of-Thought (CoT), Few-shot, ReAct, A/B Testing, Semantic Benchmarking, and token optimization.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 1.0.0
---

# Prompt Engineering Skill (2026)

> Mastering the bridge between human intent and model execution.

---

## 🧠 Advanced Prompting Techniques

| Technique | Description | Use Case |
|-----------|-------------|----------|
| **Chain-of-Thought (CoT)** | Forcing the model to reason step-by-step before answering. | Complex logic, math, architecture. |
| **Few-shot Learning** | Providing 2-3 high-quality examples within the prompt. | Ensuring specific output formats or style. |
| **ReAct** | Reasoning + Acting. Model describes its thought, then picks a tool. | Agentic workflows with tool-use. |
| **Prompt Decomposition** | Breaking a massive prompt into 3-4 smaller, sequential ones. | Reducing hallucinations in long-context tasks. |

---

## 🧪 Benchmarking & A/B Testing

### Semantic Validation (Prompt Arena)
- **Golden Set**: A curated list of (Query → Expected Outcome).
- **A/B Testing**:
  1. Generate `Prompt_V1` and `Prompt_V2`.
  2. Run both against the same Golden Set.
  3. Compare using `semantic_similarity` or `LLM-as-a-judge`.

### Token Efficiency
- **Negative Prompting**: Explicitly listing what the model should NOT do to avoid verbosity.
- **Structural Compression**: Using Markdown headers and bullet points instead of prose to save tokens.

---

## 📐 Prompt Structure (The "AOS Standard")

1. **Role/Context**: "You are an expert Go engineer..."
2. **Mandate**: "Your goal is to refactor X while maintaining Y."
3. **Constraints**: "No external libraries. Use slog. Max 100 lines."
4. **Few-shot Examples**: (Optional) 1-2 examples of ideal input/output.
5. **Execution Instructions**: "Think step-by-step. End with a summary."

---

## 🛠 Automation Tools

| Tool | Action |
| :--- | :--- |
| `prompt_optimizer.py` | Analyzes token usage and suggests structural compression. |
| `qa_golden_engine.py` | Validates model output against expected patterns/semantics. |
| `hallucination_detector.py`| Scans output for "hallucinated" file paths or non-existent APIs. |

---

> **Principle:** A prompt is code. It must be versioned, tested, and optimized like any other software component.

## When to Use

- **Designing a new LLM prompt** — start with the task,
  then add structure, examples, and constraints.
- **Improving an existing prompt** — iterate based on failure
  modes, not vibes.
- **Evaluating prompt changes** — use a fixed eval set, measure
  before/after.
- **A/B testing prompts in production** — shadow mode, then
  gradual rollout.
- **Prompt libraries for common patterns** — summarization,
  extraction, classification, etc.

Avoid using this skill for:
- Building RAG or agents (use `@ai-engineer`).
- Fine-tuning (use `@ai-engineer` or external tools).
- Production deployment of LLMs (use `@devops-engineer`).

## Anti-Patterns

- **Don't use vague instructions** — "summarize this" is
  bad; "summarize in 3 bullets, max 100 chars" is good.
- **Don't skip few-shot examples** — they dramatically improve
  quality, especially for structured output.
- **Don't put critical info in the middle** — LLMs attend more
  to the beginning and end of context.
- **Don't mix multiple tasks in one prompt** — split them.
  "Translate AND summarize" is two prompts.
- **Don't use temperature 0 for creative tasks** — 0.7-0.9
  is better for diversity. Use 0 only for deterministic output.
- **Don't trust zero-shot eval** — always test on a held-out
  set. What works on 5 examples may fail on 50.
- **Don't ignore token cost** — long prompts are slow and
  expensive. Be concise where possible.

## Changelog

- **1.0.0** (2026-05-13): Initial version
