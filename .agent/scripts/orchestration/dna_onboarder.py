#!/usr/bin/env python3
"""
DNA Onboarding Wizard — interactive Q&A to initialize user DNA profile.

Reads questions + score weights + content blocks from dna_questions.json.
Computes 2-part DNA tag via weighted axis scoring (Plan B nuance).
Writes full PERSONA.md rewrite + syncs user_dna.json via personality_adapter.

Usage:
    python dna_onboarder.py            # interactive wizard
    python dna_onboarder.py --dry-run  # preview without writing
    python dna_onboarder.py --force    # re-onboard even if already initialized
    python dna_onboarder.py --config PATH  # override config file path
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"
DEFAULT_CONFIG = REPO_ROOT / ".agent" / "config" / "dna_questions.json"
PERSONA_FILE = REPO_ROOT / ".agent" / "rules" / "PERSONA.md"
DNA_BUS_FILE = REPO_ROOT / ".agent" / "bus" / "user_dna.json"


def load_config(config_path: Path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def _compute_dna(scores: dict[str, float], axes: dict, dna_labels: dict) -> tuple[str, str]:
    """Return (primary_label, secondary_label) from accumulated axis scores."""
    primary_key = max(axes["primary"], key=lambda k: scores.get(k, 0.0))
    secondary_key = max(axes["secondary"], key=lambda k: scores.get(k, 0.0))
    return dna_labels[primary_key], dna_labels[secondary_key]


def _build_persona_content(dna_tag: str, profiles: dict) -> str:
    profile = profiles.get(dna_tag, profiles["BALANCED"])
    stylistic_lines = "\n".join(f"- {s}" for s in profile["stylistic"])
    philosophy_lines = "\n".join(f"- {p}" for p in profile["philosophy"])
    return f"""\
# User Personality Profile (DNA) 🎭

This document defines the preferred communication style, technical depth, and coding philosophy for the current workspace.

## 🧬 Core DNA: [{dna_tag}]

### 🛰️ Stylistic Preferences

{stylistic_lines}

### 🛠️ Technical Philosophy

{philosophy_lines}

---
> [!NOTE]
> This profile is automatically read by `personality_adapter.py` to tune agent behavior.
"""


def _already_onboarded() -> bool:
    if not PERSONA_FILE.exists():
        return False
    content = PERSONA_FILE.read_text(encoding="utf-8")
    import re
    m = re.search(r"## 🧬 Core DNA: \[(.*?)\]", content)
    return bool(m and m.group(1) not in ("BALANCED", "UNKNOWN"))


def _ask_question(question: dict, index: int, total: int) -> dict:
    print(f"\n[{index}/{total}] {question['text']}")
    for i, choice in enumerate(question["choices"], 1):
        print(f"  {i}. {choice['label']}")
    while True:
        raw = input("  → ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(question["choices"]):
            return question["choices"][int(raw) - 1]
        print(f"  Please enter 1–{len(question['choices'])}")


def run_wizard(config: dict) -> tuple[str, list[dict]]:
    """Run the interactive Q&A. Returns (dna_tag, raw_answers)."""
    questions = config["questions"]
    axes = config["axes"]
    dna_labels = config["dna_labels"]

    scores: dict[str, float] = {k: 0.0 for axis in axes.values() for k in axis}
    raw_answers = []

    print("\n🧬 DNA Onboarding Wizard")
    print("   Answer 5 questions to initialize your development DNA profile.\n")

    for i, question in enumerate(questions, 1):
        chosen = _ask_question(question, i, len(questions))
        for axis_key, weight in chosen["weights"].items():
            scores[axis_key] = scores.get(axis_key, 0.0) + weight
        raw_answers.append({"question": question["text"], "answer": chosen["label"]})

    primary, secondary = _compute_dna(scores, axes, dna_labels)
    dna_tag = f"{primary} / {secondary}"
    return dna_tag, raw_answers


def write_outputs(dna_tag: str, raw_answers: list[dict], config: dict, dry_run: bool) -> None:
    persona_content = _build_persona_content(dna_tag, config["profiles"])

    if dry_run:
        print("\n── DRY RUN: PERSONA.md preview ──────────────────────────")
        print(persona_content)
        print("── DRY RUN: would also write user_dna.json (raw answers) ─")
        print(json.dumps({"dna": dna_tag, "raw_answers": raw_answers}, indent=2))
        return

    PERSONA_FILE.write_text(persona_content, encoding="utf-8")
    print(f"\n✅ PERSONA.md written → [{dna_tag}]")

    DNA_BUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = json.loads(DNA_BUS_FILE.read_text()) if DNA_BUS_FILE.exists() else {}
    except json.JSONDecodeError:
        existing = {}
    existing["raw_answers"] = raw_answers
    existing["dna"] = dna_tag
    DNA_BUS_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    adapter = SCRIPTS_DIR / "orchestration" / "personality_adapter.py"
    try:
        subprocess.run([sys.executable, str(adapter)], check=True)
        print("✅ personality_adapter synced user_dna.json")
    except Exception as exc:
        print(f"⚠️  personality_adapter failed (profile still written): {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DNA Onboarding Wizard")
    parser.add_argument("--force", action="store_true", help="Re-run even if already initialized")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to dna_questions.json")
    args = parser.parse_args()

    if not args.config.exists():
        print(f"❌ Config not found: {args.config}")
        sys.exit(1)

    config = load_config(args.config)

    if _already_onboarded() and not args.force and not args.dry_run:
        existing = ""
        import re
        m = re.search(r"## 🧬 Core DNA: \[(.*?)\]", PERSONA_FILE.read_text(encoding="utf-8"))
        if m:
            existing = m.group(1)
        print(f"⚠️  Already onboarded: [{existing}]. Use --force to re-run.")
        sys.exit(0)

    dna_tag, raw_answers = run_wizard(config)

    print(f"\n🧬 Computed DNA: [{dna_tag}]")

    write_outputs(dna_tag, raw_answers, config, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
