# Antigravity Hive: Health Metrics System

## Overview

The health score is a composite metric representing the overall state of the repository, from infrastructure integrity to documentation coverage.

## Score Breakdown

- **100%**: Ideal state.
- **>80%**: Good condition, ready for L1-L3 flows.
- **<60%**: Critical state, require L4 (Audit) flow.

## Key Metrics

1. **Sync Status (25%)**: Are agents on Claude, Opencode, and Antigravity platforms identical?
2. **Drift (15%)**: Is the code consistent with the Wiki and architectural documentation?
3. **KI Coverage (15%)**: What percentage of code files are referenced in the Knowledge Base? (Target: >20%)
4. **Security (10%)**: Results of the `security_scan.py` check.
5. **Stability (10%)**: Recent test results and Chaos Monkey events.
6. **ROI (10%)**: Ratio of local model usage (Ollama) vs cloud models.

## Verification

Run `python3 .agent/scripts/health/status_report.py` to get a real-time report.
