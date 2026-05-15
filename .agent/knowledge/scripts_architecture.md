# Antigravity Hive: Scripts Architecture

## Overview

The script collection has been refactored into a domain-driven hierarchical structure to ensure maintainability and observability.

## Domains

- **Orchestration**: Agent lifecycle, auctions, and session management.
- **Health**: System monitoring, status reports, and security scans.
  - `.agent/scripts/health/status_report.py`
  - `.agent/scripts/health/security_scan.py`
- **Chaos**: Resilience drills and chaos engineering.
  - `.agent/scripts/chaos/chaos_monkey.py`
- **Context**: Bus management and conflict resolution.
  - `.agent/scripts/context/conflict_resolver.py`
- **Delivery**: Syncing agents and task deployment.
  - `.agent/scripts/delivery/sync_agents.py`
- **Dev**: Developer tools, checklists, and pre-commit reviews.
  - `.agent/scripts/dev/checklist.py`
  - `.agent/scripts/dev/pre_commit_review.py`
- **Models**: LLM routing, benchmarks, and training.
- **Knowledge**: Knowledge distillation and coverage tracking.
  - `.agent/scripts/knowledge/agent_squeeze.py` — high-integrity session knowledge distillation
  - `.agent/scripts/knowledge/ki_coverage_collector.py` — KI coverage metrics
  - `.agent/scripts/knowledge/knowledge_miner.py` — retroactive knowledge archaeology
- **Analysis**: Post-mortem reports and data distillation.

## Path Standards

All scripts MUST use `lib.paths` or dynamic calculation from `Path(__file__)` to find the repository root.
Correct `REPO_ROOT` calculation for a domain script:

```python
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[3]
```
