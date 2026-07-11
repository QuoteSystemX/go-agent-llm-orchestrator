#!/usr/bin/env python3
"""
Arbor Critic Agent Quality Benchmarker
Measures quality improvements across loop iterations.

Benchmark Dimensions:
  1. Completeness   - Does the agent cover all required workflow steps?
  2. Precision      - Are there numeric thresholds, not vague statements?
  3. Coverage       - Edge cases, anti-patterns, escalation paths
  4. Observability  - Structured logging, audit trail requirements
  5. Output Schema  - Is the output format machine-readable and typed?

Usage:
  python3 benchmark_critic.py [path/to/arbor-critic.md]
"""

import sys
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass
class DimensionResult:
    name: str
    score: int
    max_score: int
    findings: List[str] = field(default_factory=list)

    @property
    def pct(self) -> float:
        return (self.score / self.max_score) * 100 if self.max_score > 0 else 0.0


def benchmark_completeness(content: str) -> DimensionResult:
    """Check all mandatory workflow steps are present."""
    checks = [
        ("Protected path check step", r"protected\s*path|protected\s*glob|data/\*\*", 2),
        ("B_test evaluation trigger", r"eval_cmd_test|B_test", 2),
        ("Metric comparison logic", r"trunk_score|baseline_score", 2),
        ("Code quality audit step", r"code.review|quality\s*audit|diff\s*footprint", 1),
        ("Merge approval/rejection", r"APPROVE|REJECT|merge", 1),
        ("Post-merge metadata update", r"TreeSetMeta|trunk_score.*=", 1),
        ("Final stop protocol", r"final.stop|hand.?off", 1),
    ]
    score = 0
    findings = []
    for label, pattern, pts in checks:
        if re.search(pattern, content, re.IGNORECASE):
            score += pts
            findings.append(f"✅ {label}")
        else:
            findings.append(f"❌ MISSING: {label}")
    return DimensionResult("Completeness", score, sum(p for _, _, p in checks), findings)


def benchmark_precision(content: str) -> DimensionResult:
    """Check for numeric thresholds vs vague statements."""
    checks = [
        ("Numeric improvement threshold (% value)", r"\d+\.?\d*\s*%", 3),
        ("Retry count specified", r"eval_retries|\d+\s*time", 2),
        ("Diff line limit defined", r"\d+\s*lines?", 2),
        ("Timeout reference", r"eval_timeout|timeout", 1),
        ("Statistical runs count", r"3.?5?\s*times|minimum\s*of\s*\d", 2),
    ]
    score = 0
    findings = []
    for label, pattern, pts in checks:
        if re.search(pattern, content, re.IGNORECASE):
            score += pts
            findings.append(f"✅ {label}")
        else:
            findings.append(f"❌ MISSING: {label}")
    return DimensionResult("Precision", score, sum(p for _, _, p in checks), findings)


def benchmark_coverage(content: str) -> DimensionResult:
    """Check edge cases, anti-patterns and escalation logic."""
    checks = [
        ("Overfitting detection rule", r"overfitting|B_dev.*diverge|diverge.*B_dev", 2),
        ("High variance handling", r"variance|std\b|standard\s*deviation", 2),
        ("Tie-breaking rule (delta=0)", r"tie|delta.*0|exactly\s*0", 2),
        ("Smoke/forward test exception", r"smoke|forward\s*test", 2),
        ("Escalation logic", r"ESCALATE|stagnation|consecutive", 2),
        ("Anti-pattern detection table", r"hardcoded.*score|tampered.*eval|deleted.*test", 2),
        ("Missing baseline handling", r"missing.*baseline|baseline.*missing", 1),
        ("Security alert on path violation", r"SECURITY_ALERT|security.alert", 1),
    ]
    score = 0
    findings = []
    for label, pattern, pts in checks:
        if re.search(pattern, content, re.IGNORECASE):
            score += pts
            findings.append(f"✅ {label}")
        else:
            findings.append(f"❌ MISSING: {label}")
    return DimensionResult("Coverage", score, sum(p for _, _, p in checks), findings)


def benchmark_observability(content: str) -> DimensionResult:
    """Check for structured logging, audit trail and monitoring requirements."""
    checks = [
        ("Structured log format defined", r"\[CRITIC\]|log.*format|emit.*structured", 2),
        ("Log fields: node_id, gate, status", r"node_id.*gate.*status|gate.*status.*score", 2),
        ("Metadata update after merge", r"TreeSetMeta|TreeUpdateNode", 2),
        ("Warning flags in output", r"WARNING:|WARN:", 1),
        ("Info-level logging", r"INFO:|log.*info", 1),
    ]
    score = 0
    findings = []
    for label, pattern, pts in checks:
        if re.search(pattern, content, re.IGNORECASE):
            score += pts
            findings.append(f"✅ {label}")
        else:
            findings.append(f"❌ MISSING: {label}")
    return DimensionResult("Observability", score, sum(p for _, _, p in checks), findings)


def benchmark_output_schema(content: str) -> DimensionResult:
    """Check for machine-readable, typed output schema."""
    checks = [
        ("JSON verdict block defined", r'"verdict"\s*:', 2),
        ("Gate results structured per gate", r'"gate_results"', 2),
        ("Numeric score fields", r'"b_test_score"|"delta"', 2),
        ("next_action field for coordinator", r'"next_action"', 2),
        ("Boolean flags in schema", r'"overfitting_flag"|"high_variance_flag"', 2),
    ]
    score = 0
    findings = []
    for label, pattern, pts in checks:
        if re.search(pattern, content, re.IGNORECASE):
            score += pts
            findings.append(f"✅ {label}")
        else:
            findings.append(f"❌ MISSING: {label}")
    return DimensionResult("Output Schema", score, sum(p for _, _, p in checks), findings)


def run_benchmark(file_path: Path) -> None:
    content = file_path.read_text(encoding="utf-8")

    dimensions = [
        benchmark_completeness(content),
        benchmark_precision(content),
        benchmark_coverage(content),
        benchmark_observability(content),
        benchmark_output_schema(content),
    ]

    total_score = sum(d.score for d in dimensions)
    total_max = sum(d.max_score for d in dimensions)
    total_pct = (total_score / total_max) * 100

    print(f"\n{'='*60}")
    print(f"  Arbor Critic Quality Benchmark")
    print(f"  File: {file_path}")
    print(f"{'='*60}\n")

    for dim in dimensions:
        bar = "█" * int(dim.pct / 5) + "░" * (20 - int(dim.pct / 5))
        print(f"  {dim.name:<18} [{bar}] {dim.score:>2}/{dim.max_score} ({dim.pct:.0f}%)")
        for f in dim.findings:
            print(f"    {f}")
        print()

    print(f"{'='*60}")
    bar = "█" * int(total_pct / 5) + "░" * (20 - int(total_pct / 5))
    print(f"  TOTAL SCORE  [{bar}] {total_score}/{total_max} ({total_pct:.1f}%)")
    print(f"{'='*60}\n")

    if total_pct >= 90:
        grade = "🏆 GOLD — Production Ready"
    elif total_pct >= 75:
        grade = "🥈 SILVER — Solid, minor gaps"
    elif total_pct >= 50:
        grade = "🥉 BRONZE — Functional but incomplete"
    else:
        grade = "❌ BELOW BASELINE — Requires major revision"

    print(f"  Grade: {grade}\n")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "/home/amudrykh/go/project/prompt-library/.agent/agents/qa/arbor-critic.md"
    )
    if not target.exists():
        print(f"ERROR: File not found: {target}")
        sys.exit(1)
    run_benchmark(target)
