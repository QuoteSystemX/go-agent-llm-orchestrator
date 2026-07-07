---
name: chaos-engineering
description: "Planning resilience experiments, measuring recovery speeds, and writing Mean Time to Recovery (MTTR) audits."
version: 1.0.0
---

# Chaos Engineering Skill (Master Level)

This skill defines the methodological guidelines for planning resilience experiments, measuring recovery speeds, and writing comprehensive Mean Time to Recovery (MTTR) audits.

---

## 🎯 Primary Goal
Systematically verify and improve system resilience through planned experiment loops, ensuring that failures are expected, handled, and recovered from automatically.

---

## 🔬 The Chaos Experiment Lifecycle

Every experiment conducted under Chaos Engineering must follow these five steps:

```
1. DEFINE BASELINE → 2. FORMULATE HYPOTHESIS → 3. INJECT FAULT → 4. AUDIT RESPONSE → 5. CALCULATE MTTR
```

1. **Define Baseline**: Establish metric normals (e.g., CPU < 20%, API latency < 100ms, MCP reconnects = 0).
2. **Formulate Hypothesis**: *"If we block port 8080 (MCP), the orchestrator agent will detect the crash in under 2 seconds and switch to the secondary channel without losing session history."*
3. **Inject Fault**: Trigger the designated fault injector (e.g. `--mcp`).
4. **Audit Response**: Read active recovery logs and monitor the error handling flow.
5. **Calculate MTTR**: Determine the duration between the start of the failure and the full return to normal baseline metrics.

---

## 📊 Concrete MTTR Audit Report Template

After executing an experiment, trigger the analyzer script to generate a report:

```bash
# Analyze recovery logs and calculate metrics
python3 .agent/scripts/chaos/chaos_analyzer.py --event mcp_crash
```

### Approved MTTR Report Structure:
```markdown
# Chaos Audit: MCP Port Crash resilience

## Executive Summary
On 2026-05-23, we simulated a total MCP port block to test orchestrator failover.

## Baseline vs. Peak Metrics
- **Baseline Latency**: 45ms
- **Peak Latency during attack**: 520ms
- **Memory Consumption**: Stable (no leaks detected during reconnect loop)

## Resilience Metrics
- **Detection Time**: 1.2 seconds (Time to recognize connection is dead)
- **Failover Trigger Time**: 1.8 seconds (Time to route to fallback gateway)
- **Recovery Time (MTTR)**: 3.4 seconds (Total time back to baseline performance)

## Verdict
✅ **PASSED**: The recovery system met our SLO (Service Level Objective) limit of MTTR < 5.0 seconds. No data loss occurred on the Context Bus.
```

---

## 🛡️ Best Practices for Recovery Engineering
- **Circuit Breakers**: Always wrap external API calls in a circuit breaker pattern (e.g., using Go `gobreaker` or TS `opossum`). Stop requests immediately if error rate exceeds 50%.
- **Exponential Backoff**: When reconnecting to databases or message brokers, use exponential backoff:
  $$T_{retry} = 2^{attempt} \times 100\text{ms} + \text{jitter}$$
- **Degraded Fallbacks**: If a search service fails, degrade gracefully by returning cached local database results instead of throwing a generic `500 Server Error`.
