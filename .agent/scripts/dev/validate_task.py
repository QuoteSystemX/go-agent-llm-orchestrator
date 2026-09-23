#!/usr/bin/env python3
"""
validate_task.py — Validates task files against TEMPLATE.md requirements.

Usage:
    python3 .agent/scripts/dev/validate_task.py tasks/*.md
    python3 .agent/scripts/dev/validate_task.py tasks/2026-09-21-P2-bug-foo.md

Exit codes:
    0 = all tasks valid
    1 = one or more tasks have validation errors

MVT (Minimal Viable Task) sections are ALWAYS required.
Full sections are required for L2+ tasks.
"""

import sys
import re
from pathlib import Path

# ── MVT sections (always required) ──────────────────────────────────────────
MVT_SECTIONS = [
    "Context",
    "Scope",
    "Acceptance Criteria",
    "Dependencies",
    "Files Likely to Change",
]

# ── Full sections (required for L2+) ────────────────────────────────────────
FULL_SECTIONS = [
    "Root Cause",
    "Implementation Plan",
    "Open Questions",
    "Labels",
    "Pre-Commit Checklist",
]

# ── Flow detection ───────────────────────────────────────────────────────────
FLOW_PATTERN = re.compile(r"Flow:\s*\[?L(\d)\]?")


def detect_flow(content: str) -> int | None:
    """Extract L<N> from the Flow header."""
    m = FLOW_PATTERN.search(content)
    if m:
        return int(m.group(1))
    return None


def find_sections(content: str) -> dict[str, str]:
    """
    Return {section_name: content_until_next_section}.
    Only splits on ## (level 2) headings. ### (level 3) are treated as content.
    """
    lines = content.split("\n")
    sections: dict[str, str] = {}
    current_name = None
    current_lines: list[str] = []

    for line in lines:
        # Only match ## (level 2) sections, NOT ### (level 3)
        m = re.match(r"^##\s+(.+)$", line)
        if m and not re.match(r"^###", line):
            # Save previous section
            if current_name:
                sections[current_name] = "\n".join(current_lines)
            # Strip emojis and markers
            raw = m.group(1)
            clean = re.sub(r"[—–].*$", "", raw).strip()
            clean = re.sub(r"\s*\(.*\)\s*$", "", clean).strip()
            current_name = clean
            current_lines = []
        else:
            if current_name:
                current_lines.append(line)

    # Save last section
    if current_name:
        sections[current_name] = "\n".join(current_lines)

    return sections


def section_matches(actual: str, required: str) -> bool:
    """Flexible matching: check if actual section name contains the required keyword."""
    # Strip common emojis from actual name
    actual_clean = re.sub(r"^[✅❌📌📝⚠️🔍📋🤖📈🧠]+\s*", "", actual).strip()
    actual_lower = actual_clean.lower()
    required_lower = required.lower()
    # Exact match
    if actual_lower == required_lower:
        return True
    # Keyword match (e.g., "Scope" matches "Scope & Boundaries")
    if required_lower in actual_lower:
        return True
    # Reverse keyword match
    if actual_lower in required_lower:
        return True
    return False


def has_checkboxes(content: str) -> bool:
    """Check if section has at least one [ ] or [x] checkbox."""
    return bool(re.search(r"\[[ x]\]", content))


def validate_task(filepath: str) -> list[str]:
    """Validate a single task file. Returns list of error messages."""
    errors: list[str] = []
    path = Path(filepath)

    if not path.exists():
        return [f"File not found: {filepath}"]

    content = path.read_text(encoding="utf-8")
    sections = find_sections(content)
    flow = detect_flow(content)
    task_name = path.stem

    # ── Check Flow header ────────────────────────────────────────────────
    if flow is None:
        errors.append("Missing Flow header (e.g., 'Flow: [L2]')")

    # ── MVT sections (always required) ──────────────────────────────────
    for section in MVT_SECTIONS:
        matched = any(section_matches(name, section) for name in sections)
        if not matched:
            errors.append(f"MVT missing: '## {section}' (always required)")
        else:
            # Find the actual section name
            actual_name = next(name for name in sections if section_matches(name, section))
            sec_content = sections[actual_name].strip()
            if not sec_content:
                errors.append(f"MVT empty: '## {section}' has no content")
            # Check DoD has checkboxes
            if section == "Acceptance Criteria" and not has_checkboxes(sec_content):
                errors.append(f"MVT DoD: '## {section}' has no checkboxes ([ ] or [x])")

    # ── Full sections (required for L2+) ────────────────────────────────
    if flow is not None and flow >= 2:
        for section in FULL_SECTIONS:
            matched = any(section_matches(name, section) for name in sections)
            if not matched:
                errors.append(f"Full section missing (L{flow}+): '## {section}'")

    # ── Check DoD quality ───────────────────────────────────────────────
    dod_name = next((n for n in sections if section_matches(n, "Acceptance Criteria")), None)
    if dod_name:
        dod = sections[dod_name]
        checkbox_count = len(re.findall(r"\[[ x]\]", dod))
        if checkbox_count < 3:
            errors.append(
                f"DoD has only {checkbox_count} checkboxes — recommend ≥3 for measurable criteria"
            )

    # ── Check Scope has In/Out ──────────────────────────────────────────
    scope_name = next((n for n in sections if section_matches(n, "Scope")), None)
    if scope_name:
        scope = sections[scope_name]
        if "In Scope" not in scope and "in scope" not in scope.lower():
            errors.append("Scope section missing 'In Scope' subsection")
        if "Out of Scope" not in scope and "out of scope" not in scope.lower():
            errors.append("Scope section missing 'Out of Scope' subsection")

    # ── Check Dependencies format ───────────────────────────────────────
    deps_name = next((n for n in sections if section_matches(n, "Dependencies")), None)
    if deps_name:
        deps = sections[deps_name]
        if deps.strip().lower() in ("", "нет", "none", "n/a"):
            pass  # Explicitly no dependencies — OK
        elif "<task-slug>" in deps:
            errors.append("Dependencies has placeholder '<task-slug>' — fill in real values")

    # ── Check Files section has actual paths ────────────────────────────
    files_name = next((n for n in sections if section_matches(n, "Files")), None)
    if files_name:
        files = sections[files_name]
        if "<path/" in files:
            errors.append("Files section has placeholder '<path/...>' — fill in real paths")

    # ── Check Labels section ────────────────────────────────────────────
    labels_name = next((n for n in sections if section_matches(n, "Labels")), None)
    if labels_name:
        labels = sections[labels_name]
        if "type:" not in labels:
            errors.append("Labels missing 'type:' tag")
        if "priority:" not in labels:
            errors.append("Labels missing 'priority:' tag")

    # ── Prefix errors with task name ────────────────────────────────────
    return [f"[{task_name}] {e}" for e in errors]


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_task.py <task_file.md> [task_file2.md ...]")
        sys.exit(1)

    all_errors: list[str] = []
    for filepath in sys.argv[1:]:
        errors = validate_task(filepath)
        all_errors.extend(errors)

    if all_errors:
        print("❌ Task validation failed:\n")
        for err in all_errors:
            print(f"  • {err}")
        print(f"\n{len(all_errors)} error(s) found.")
        sys.exit(1)
    else:
        print("✅ All tasks valid.")
        sys.exit(0)


if __name__ == "__main__":
    main()
