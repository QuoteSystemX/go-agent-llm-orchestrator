# Mental Model: Governance & Financial Control

## Problem Statement
Autonomous agents can consume significant compute resources (and tokens) if left unchecked. A "rogue" loop or a misconfigured high-frequency schedule can lead to unexpected costs.

## Intuition
Governance is the **Circuit Breaker** of the Jules Orchestrator. 

Imagine a credit card with a spending limit. The `BudgetManager` acts as the banking system that authorizes every transaction (Task Execution). If you reach your daily limit or monthly quota, the "card" is declined. 

The insight here is that **Financial Safety is a hard constraint**, while performance is a soft one. We prioritize preventing cost overruns over finishing a task quickly.

## Core Invariants
1. **Deny-by-Default (on limit)**: If no budget rule exists, the system uses default safety limits. If a limit is exceeded, execution is strictly forbidden.
2. **Atomic Quotas**: Daily usage counts only successful task initiations to prevent "double-charging" for failed starts.
3. **Graceful Warning**: The system warns the user (via UI and Telegram) when usage crosses the 80% (or configurable) threshold.

## Budget Types
- **System-Wide**: A global "Kill Switch" for the entire orchestrator instance.
- **Project-Specific**: Allows higher budgets for critical repositories (e.g., `main-app`) and tighter limits for experimental ones.

## Failure Modes
- **Clock Drift**: If the server time is incorrect, daily resets might happen at the wrong time.
- **Race Conditions**: Two tasks starting at the exact same millisecond might bypass the limit check if not properly synchronized. 
  *   *Solution*: The `TrafficManager` uses a `sync.Mutex` and the `TrafficManager.Execute` method wraps the entire check-and-acquire cycle.
