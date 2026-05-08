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
