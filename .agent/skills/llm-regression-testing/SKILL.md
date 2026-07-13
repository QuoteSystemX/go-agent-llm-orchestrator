---
name: LLM Regression Testing
description: Standards for prompt benchmarking, quality metric calculation, and monitoring quality drift across model updates.
---

# LLM Regression Testing & Benchmarking

This skill covers the methodology for testing prompt performance, evaluating model updates, and monitoring token consumption across different LLM backends.

## 1. Benchmarking Workflow

```text
Prompt Update or Model Upgrade
            │
            ▼
    1. Select Datasets (B_dev, B_test)
            │
            ▼
    2. Execute Baseline Runs
            │
            ▼
    3. Measure Latency, Cost, and Accuracy
            │
            ▼
    4. Compute Parity Score (Target vs Baseline)
            │
            ▼
    5. Approve / Refuse Merge
```

---

## 2. Key Performance Metrics

### A. Quality & Correctness Metrics
*   **F1-Score / Exact Match (EM)**: Used for structured outputs. Checks if keys match schema constraints exactly.
*   **Semantic Similarity (LLM-As-A-Judge)**: A high-tier model (e.g., Claude 3.5 Sonnet) grades output quality from 1 to 10 based on criteria.
*   **Format Compliance**: The percentage of outputs that parse successfully (e.g., valid JSON/YAML).

### B. Latency & Resource Metrics
*   **Time to First Token (TTFT)**: Indicates responsiveness. Crucial for chat-based systems.
*   **Tokens per Second (TPS)**: Measurement of inference speed.
*   **Context Cache Efficiency**: Cache hit ratio for system prompts to decrease token pricing.

---

## 3. Test Runner Design Guidelines

*   **Caching**: Always use a local cache (e.g., SQLite or JSON cache) during prompt engineering to avoid executing identical remote LLM queries.
*   **Batching**: Distribute evaluations concurrently using worker pools to save execution time.
*   **Statistical Significance**: Run evaluations with temperature > 0 at least 3-5 times to collect average metrics and identify variances.


## When to Use

- **Setting up a regression suite for an LLM app** —
  start with a small "golden set" (5-20 cases) and grow.
- **Detecting prompt drift** — run the suite on every PR to catch
  silent prompt regressions.
- **Comparing models** — A/B test by running the same eval on
  two model versions.
- **Validating system prompts** — every change should be backed
  by eval results.
- **Catching hallucinations** — include fact-checking tests in
  your suite.

Avoid using this skill for:
- Unit tests (use `@testing-patterns`).
- Performance benchmarks (use `@performance-optimizer`).
- One-off model selection (use `@model_router`).

## Anti-Patterns

- **Don't test on examples that are in the training data** —
  the model will ace them. Use held-out sets the model has never
  seen.
- **Don't trust a single eval run** — LLMs are stochastic. Run
  3+ times and take the median.
- **Don't ignore flaky tests** — fix them. A flaky test is a
  useless test.
- **Don't use a single metric** — combine accuracy, latency, cost,
  and qualitative review.
- **Don't ship without a regression test for the bug you just
  fixed** — otherwise the bug will come back.
- **Don't skip adversarial tests** — add prompts designed to
  elicit bad behavior (jailbreaks, prompt injection, off-topic).