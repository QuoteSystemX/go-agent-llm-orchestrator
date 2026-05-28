#!/usr/bin/env python3
"""
GuardrailPipeline — extensible output validation pipeline.

Usage:
    pipeline = GuardrailPipeline()
    pipeline.register_check(my_check_fn, name="my_check", halt_on_fail=True)
    result = pipeline.run(text)
    if not result.passed:
        result.print_veto()
        sys.exit(1)

Each check function signature: (text: str) -> list[dict]
Each violation dict must contain: {rule_id, category, severity, description}
Optional keys: match, line, source.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]

POLICY_REPORT_PATH = REPO_ROOT / ".agent" / "bus" / "policy_report.json"

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


# ============================================================================
#  DATA TYPES
# ============================================================================

@dataclass
class CheckRegistration:
    name: str
    fn: Callable[[str], list[dict]]
    halt_on_fail: bool = True


@dataclass
class PipelineResult:
    passed: bool
    violations: list[dict] = field(default_factory=list)
    check_results: dict[str, list[dict]] = field(default_factory=dict)

    @property
    def severity(self) -> str:
        if not self.violations:
            return "none"
        return max(
            (v.get("severity", "low") for v in self.violations),
            key=lambda s: SEVERITY_ORDER.get(s, 0),
        )

    def print_veto(self) -> None:
        print("\n" + "=" * 60)
        print("🔴 RED-TEAM VETO: Policy guardrail blocked this output.")
        print("=" * 60)
        for v in self.violations:
            sev = v.get("severity", "?").upper()
            desc = v.get("description", "")
            rule = v.get("rule_id", "?")
            src = v.get("source", "")
            src_str = f" [{src}]" if src else ""
            print(f"  [{sev}]{src_str} {desc} (rule: {rule})")
        print("=" * 60)
        print("⚠️  Regenerate response without disallowed content.\n")

    def log_to_report(self, path: Path = POLICY_REPORT_PATH) -> None:
        try:
            existing = json.loads(path.read_text()) if path.exists() else {"violations": []}
        except (json.JSONDecodeError, OSError):
            existing = {"violations": []}

        existing["violations"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "VIOLATION",
            "severity": self.severity,
            "violations": self.violations,
        })
        existing["last_updated"] = datetime.now(timezone.utc).isoformat()

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(existing, indent=2))


# ============================================================================
#  PIPELINE
# ============================================================================

class GuardrailPipeline:
    """Ordered pipeline of registered check functions."""

    def __init__(self) -> None:
        self._checks: list[CheckRegistration] = []

    def register_check(
        self,
        fn: Callable[[str], list[dict]],
        *,
        name: str = "",
        halt_on_fail: bool = True,
    ) -> "GuardrailPipeline":
        self._checks.append(CheckRegistration(
            name=name or fn.__name__,
            fn=fn,
            halt_on_fail=halt_on_fail,
        ))
        return self

    def run(self, text: str) -> PipelineResult:
        all_violations: list[dict] = []
        check_results: dict[str, list[dict]] = {}

        for reg in self._checks:
            try:
                violations = reg.fn(text) or []
            except Exception as exc:
                violations = [{
                    "rule_id": f"{reg.name}.error",
                    "category": "pipeline_error",
                    "severity": "medium",
                    "description": f"Check '{reg.name}' raised: {exc}",
                }]

            for v in violations:
                v.setdefault("source", reg.name)

            check_results[reg.name] = violations
            all_violations.extend(violations)

            if violations and reg.halt_on_fail:
                break

        passed = len(all_violations) == 0
        return PipelineResult(
            passed=passed,
            violations=all_violations,
            check_results=check_results,
        )
