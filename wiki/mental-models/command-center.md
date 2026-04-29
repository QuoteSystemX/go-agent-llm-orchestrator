# Mental Model: Jules Command Center

## Problem Statement
In an autonomous agentic system, the biggest risk is "the black box" — when the system is running but the operator has no visibility into *why* it's stalled, *how* much it's spending, or *if* the internal documentation is still accurate.

## Intuition
The Command Center is the **Air Traffic Control (ATC)** of Jules. 

Imagine a busy airport where planes (Tasks) are arriving and departing. Without ATC, you don't know which planes are circling (Queued), which ones are grounded due to fuel limits (Budget), or if the flight manuals (Wiki) are out of date. The Command Center provides the radar, the logbook, and the fuel gauges to ensure safe and transparent operations.

The core insight is that **Observability = Trust**. By exposing the internal state (Traffic Queue, Audit Logs, Budgets) in a high-fidelity dashboard, the user can let the system run on "Autopilot" while maintaining the ability to intervene instantly.

## Core Invariants
1. **Budget Enforcement**: No task can transition to `RUNNING` if the `BudgetManager` flags it as exceeding limits.
2. **Audit Integrity**: Every automated intervention (like Supervisor responses) must be recorded in the `audit_logs` table.
3. **Drift Awareness**: The system must surface the synchronization status between the code and the `ARCHITECTURE.md` to prevent "documentation rot".

## Data Flow
1. **Traffic Control**: Task is scheduled → `TrafficManager.Execute` is called → `BudgetManager` checks current usage vs limits → Task enters `waiting` map → Task acquires worker slot → Task starts.
2. **Drift Monitoring**: `DriftDetector` runs in background → Hashes wiki vs code → Sets `has_drift` flag on Repository projects.
3. **Governance**: Admin sets limits in UI → `AdminServer` updates `budgets` table → `BudgetManager` reloads state.

## Failure Modes
- **Budget Lockout**: If limits are set too low, all tasks will stall. Solution: UI surfaces "Budget Exceeded" status clearly.
- **Queue Starvation**: High-priority tasks might block low-priority ones indefinitely. Solution: UI allows manual priority bumps.
- **Stale Audit**: If the database is under heavy load, audit logs might be delayed. Solution: Use WAL mode and non-blocking log writes.
