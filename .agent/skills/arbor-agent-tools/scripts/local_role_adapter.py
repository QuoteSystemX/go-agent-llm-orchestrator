#!/usr/bin/env python3
"""Local-LLM role adapter for the Arbor skill suite.

The real `arbor` binary's LLMConfig is shared by every agent (coordinator,
executor, judge) - there is no per-role provider/model override in its CLI
or config schema. Local models (tested: qwen2.5-coder:14b, qwen3.6-35b-a3b
via Ollama) reliably do single-shot completions but do not reliably sustain
the multi-step agentic loop the coordinator's IDEATE gate needs - the 14B
model never emitted a real tool_call, and the 35B model completed a full
OBSERVE tool-call sequence correctly but stalled at the IDEATE skill's
structured-reasoning requirement (Probe Block + 4 idea moves + 5-field
declaration).

This adapter therefore does NOT try to run the coordinator loop locally. It
routes only the two genuinely single-shot roles from
.agent/skills/arbor-agent-executor and .agent/skills/arbor-agent-merge-eval
through a local backend via mcp-llm-broker's `execute_prompt` tool:

  executor  - rewrite one file per instructions, no tool use required.
  judge     - score one file against a fixed rubric, forced JSON via
              `json_schema` (verified reliable even on the 14B model).

The coordinator/IDEATE/SELECT/DECIDE phases stay on Claude, driven by
arbor_state.py as today. Callers should treat a non-zero exit / ok=false
from this script as a signal to fall back to a Claude subagent for that
node, not as a hard failure of the run.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

TIERS = ("L1", "L2", "L3", "L4")
FRONTMATTER_MODEL_RE = re.compile(r"^model:\s*(\S+)\s*$", re.MULTILINE)

DEFAULT_RUBRIC_TEXT = (
    "Score 0-100 on each of: trigger_precision, metric_operationality, "
    "consistency, non_redundancy, structural_compliance. Then give an "
    "overall 0-100 score and a top_weaknesses list (max 3 items, most "
    "actionable first)."
)

DEFAULT_RUBRIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "trigger_precision": {"type": "integer"},
        "metric_operationality": {"type": "integer"},
        "consistency": {"type": "integer"},
        "non_redundancy": {"type": "integer"},
        "structural_compliance": {"type": "integer"},
        "overall": {"type": "integer"},
        "top_weaknesses": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "trigger_precision", "metric_operationality", "consistency",
        "non_redundancy", "structural_compliance", "overall", "top_weaknesses",
    ],
}

EXECUTOR_WRAPPER = (
    "You are rewriting a single file. Return ONLY the complete new file "
    "content - no explanations, no markdown code fences, no commentary "
    "before or after. If the file has YAML frontmatter (starts with '---'), "
    "preserve that structure.\n\n"
    "=== INSTRUCTIONS ===\n{instructions}\n\n"
    "=== CURRENT FILE CONTENT ({target}) ===\n{content}\n"
    "=== END CURRENT FILE CONTENT ===\n\n"
    "Now output the complete rewritten file, and nothing else."
)

SECTION_EXECUTOR_WRAPPER = (
    "You are rewriting ONE SECTION of a larger file. You are shown ONLY that "
    "section - not the whole file - and your job is to return ONLY the "
    "replacement for that section, nothing else: no explanations, no markdown "
    "code fences, no commentary before or after.\n\n"
    "CRITICAL: your output MUST start with this EXACT heading line, unchanged, "
    "as its first line:\n{start_marker}\n\n"
    "=== INSTRUCTIONS ===\n{instructions}\n\n"
    "=== SECTION TO REWRITE (from {target}) ===\n{content}\n"
    "=== END SECTION ===\n\n"
    "Now output the complete rewritten section, starting with the exact "
    "heading line above, and nothing else."
)

JUDGE_WRAPPER = (
    "You are an LLM-judge scoring a file against a fixed rubric. Score each "
    "dimension 0-100.\n\n"
    "=== RUBRIC ===\n{rubric}\n\n"
    "{calibration}"
    "=== FILE TO SCORE ({target}) ===\n{content}\n"
    "=== END FILE ===\n\n"
    "Return your scores via the required JSON schema only."
)


def resolve_broker_bin(cwd: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    candidates = [
        cwd / "bin" / "mcp-llm-broker",
        cwd / "bin" / "mcp-llm-broker-linux-amd64",
        cwd / ".agent" / "mcp-llm-broker" / "mcp-llm-broker",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    found = shutil.which("mcp-llm-broker")
    if found:
        return found
    raise SystemExit(
        "mcp-llm-broker binary not found - pass --broker-bin explicitly "
        "(tried bin/mcp-llm-broker*, .agent/mcp-llm-broker/mcp-llm-broker, PATH)"
    )


def detect_tier_from_frontmatter(target_file: Path) -> str | None:
    """Read the target agent file's own `model: L<n>` frontmatter field."""
    if not target_file.exists():
        return None
    text = target_file.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    frontmatter = text[3:end] if end != -1 else text
    m = FRONTMATTER_MODEL_RE.search(frontmatter)
    if m and m.group(1) in TIERS:
        return m.group(1)
    return None


def pulled_model_names(broker_bin: str, timeout: int) -> set[str]:
    """Union of model names currently pulled/available across detected backends."""
    proc = subprocess.run(
        [broker_bin, "-tool", "detect_backends", "-args", "{}"],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        return set()
    try:
        data = json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return set()
    names: set[str] = set()
    for backend in data.get("backends", []):
        for m in backend.get("models") or []:
            names.add(m)
    return names


def resolve_tier_to_model(cwd: Path, broker_bin: str, tier: str, timeout: int) -> str:
    """Map an L1-L4 tier to a concrete, currently-pulled local model name.

    Reads .agent/config/router_rules.json's models.ollama[tier] (primary) and
    [tier]_alt (fallbacks, in order), and picks the first one that is actually
    pulled per `detect_backends`. This mirrors what the broker's own internal
    router does for auto-routing, but resolved client-side because
    `execute_prompt`'s `model` field is a hard override with no tier/fallback
    logic of its own (only `call_agent` reads `tier`, and that path is scoped
    to invoking a named agent's own persona, not a meta-editing instruction).
    """
    if tier not in TIERS:
        raise SystemExit(f"invalid tier {tier!r} - must be one of {TIERS}")
    rules_path = cwd / ".agent" / "config" / "router_rules.json"
    if not rules_path.exists():
        raise SystemExit(f"router_rules.json not found at {rules_path} - pass --model explicitly")
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    ollama = rules.get("models", {}).get("ollama", {})
    primary = ollama.get(tier)
    alts = ollama.get(f"{tier}_alt", [])
    candidates = [m for m in [primary, *alts] if m]
    if not candidates:
        raise SystemExit(f"no models configured for tier {tier} in {rules_path}")

    pulled = pulled_model_names(broker_bin, timeout)
    for candidate in candidates:
        if candidate in pulled:
            return candidate
    raise SystemExit(
        f"none of tier {tier}'s configured models are pulled locally "
        f"(tried {candidates}, pulled: {sorted(pulled)}) - pull one with "
        f"`ollama pull <name>` or pass --model explicitly"
    )


def resolve_model(args: argparse.Namespace, cwd: Path, broker_bin: str) -> str:
    if args.model:
        return args.model
    tier = args.tier or detect_tier_from_frontmatter(Path(args.target_file))
    if not tier:
        raise SystemExit(
            "no --model given, no --tier given, and the target file's frontmatter "
            "has no recognizable 'model: L1'..'L4' field - pass one explicitly"
        )
    resolved = resolve_tier_to_model(cwd, broker_bin, tier, args.timeout)
    print(f"[tier {tier} -> {resolved}]", file=sys.stderr)
    return resolved


def call_broker(
    broker_bin: str,
    prompt: str,
    model: str,
    timeout: int,
    json_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    args: dict[str, Any] = {"prompt": prompt, "model": model}
    if json_schema is not None:
        args["json_schema"] = json.dumps(json_schema)
    proc = subprocess.run(
        [broker_bin, "-tool", "execute_prompt", "-args", json.dumps(args)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"broker call failed (exit {proc.returncode}): {proc.stderr[-2000:]}"
        )
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"broker returned non-JSON stdout: {exc}\n{proc.stdout[:2000]}")


def strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip() + "\n"


def extract_section(full_text: str, start_marker: str, end_marker: str | None) -> tuple[str, str, str]:
    """Split full_text into (before, section, after) around two exact-match lines.

    `section` includes the start_marker line through (but not including) the
    end_marker line. If end_marker is None, section runs to end-of-file and
    `after` is empty. Raises SystemExit if a marker line isn't found verbatim.
    """
    lines = full_text.splitlines(keepends=True)
    stripped = [ln.rstrip("\n") for ln in lines]
    try:
        start_idx = stripped.index(start_marker)
    except ValueError:
        raise SystemExit(f"--section-start marker not found verbatim in file: {start_marker!r}")
    if end_marker is None:
        end_idx = len(lines)
    else:
        try:
            end_idx = stripped.index(end_marker, start_idx + 1)
        except ValueError:
            raise SystemExit(f"--section-end marker not found verbatim after start: {end_marker!r}")
    before = "".join(lines[:start_idx])
    section = "".join(lines[start_idx:end_idx])
    after = "".join(lines[end_idx:])
    return before, section, after


def cmd_executor(args: argparse.Namespace) -> None:
    cwd = Path(args.cwd).resolve()
    broker_bin = resolve_broker_bin(cwd, args.broker_bin)
    model = resolve_model(args, cwd, broker_bin)
    target = Path(args.target_file)
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    if args.instructions_file:
        instructions = Path(args.instructions_file).read_text(encoding="utf-8")
    else:
        instructions = args.instructions
    if not instructions:
        raise SystemExit("provide --instructions or --instructions-file")

    section_mode = bool(args.section_start)
    if section_mode:
        before, section, after = extract_section(current, args.section_start, args.section_end)
        prompt = SECTION_EXECUTOR_WRAPPER.format(
            start_marker=args.section_start,
            instructions=instructions,
            target=target,
            content=section,
        )
    else:
        before = after = ""
        prompt = EXECUTOR_WRAPPER.format(
            instructions=instructions,
            target=target,
            content=current or "(file does not exist yet)",
        )

    result = call_broker(broker_bin, prompt, model, args.timeout)
    rewritten_piece = strip_code_fence(result.get("response", ""))

    ok = bool(rewritten_piece.strip())
    if section_mode and ok:
        # Structural invariant: the rewritten section must still open with the
        # exact original heading, so splicing it back can't silently drop or
        # duplicate the boundary line. Models frequently drop the marker's
        # leading indentation (e.g. YAML "  key:" -> "key:") while getting the
        # content right - tolerate that specific slip by re-normalizing the
        # marker's original leading whitespace back onto the first line,
        # rather than failing content that is otherwise a correct edit.
        stripped_piece = rewritten_piece.lstrip()
        stripped_marker = args.section_start.lstrip()
        if stripped_piece.startswith(stripped_marker):
            leading_ws = args.section_start[:len(args.section_start) - len(stripped_marker)]
            rewritten_piece = leading_ws + stripped_piece
            ok = True
        else:
            ok = False
    elif args.require_prefix and ok:
        ok = rewritten_piece.lstrip().startswith(args.require_prefix)

    rewritten_full = before + rewritten_piece + after if section_mode else rewritten_piece

    out_path = Path(args.output_file or args.target_file)
    if ok:
        out_path.write_text(rewritten_full, encoding="utf-8")

    print(json.dumps({
        "ok": ok,
        "model": result.get("model"),
        "source": result.get("source"),
        "output_file": str(out_path) if ok else None,
        "output_chars": len(rewritten_full),
        "mode": "section" if section_mode else "whole-file",
    }, indent=2))
    if not ok:
        # Signal to the caller: fall back to a Claude executor for this node.
        raise SystemExit(2)


def cmd_judge(args: argparse.Namespace) -> None:
    cwd = Path(args.cwd).resolve()
    broker_bin = resolve_broker_bin(cwd, args.broker_bin)
    model = resolve_model(args, cwd, broker_bin)
    target = Path(args.target_file)
    content = target.read_text(encoding="utf-8")

    if args.rubric_file:
        rubric = Path(args.rubric_file).read_text(encoding="utf-8")
    else:
        rubric = args.rubric or DEFAULT_RUBRIC_TEXT

    calibration = ""
    if args.calibration_file:
        calibration = (
            "=== CALIBRATION (prior scores for context) ===\n"
            + Path(args.calibration_file).read_text(encoding="utf-8")
            + "\n\n"
        )
    elif args.calibration:
        calibration = (
            "=== CALIBRATION (prior scores for context) ===\n"
            + args.calibration
            + "\n\n"
        )

    schema = DEFAULT_RUBRIC_SCHEMA
    if args.schema_file:
        schema = json.loads(Path(args.schema_file).read_text(encoding="utf-8"))

    prompt = JUDGE_WRAPPER.format(
        rubric=rubric, calibration=calibration, target=target, content=content
    )
    result = call_broker(broker_bin, prompt, model, args.timeout, json_schema=schema)
    try:
        scores = json.loads(result.get("response", ""))
    except json.JSONDecodeError:
        print(json.dumps({
            "ok": False,
            "error": "judge returned non-JSON",
            "raw": result.get("response"),
        }, indent=2))
        raise SystemExit(2)

    required = schema.get("required", [])
    missing = [k for k in required if k not in scores]
    payload = {
        "ok": not missing,
        "missing_fields": missing,
        "model": result.get("model"),
        **scores,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if args.output_file:
        Path(args.output_file).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    if missing:
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("executor", help="Single-shot local-LLM file rewrite")
    sp.add_argument("--cwd", default=".")
    sp.add_argument("--broker-bin")
    sp.add_argument("--model", help="Explicit model name - overrides --tier and frontmatter auto-detect")
    sp.add_argument("--tier", choices=TIERS, help="L1-L4 - resolved to a pulled model via router_rules.json")
    sp.add_argument("--target-file", required=True)
    sp.add_argument("--output-file")
    sp.add_argument("--instructions")
    sp.add_argument("--instructions-file")
    sp.add_argument("--require-prefix", help="e.g. '---' to sanity-check YAML frontmatter survived (whole-file mode only)")
    sp.add_argument("--section-start", help="exact heading line - switches to section-patch mode: only this section is sent to/returned by the model, everything else is preserved byte-for-byte")
    sp.add_argument("--section-end", help="exact heading line marking the end of the section (exclusive); omit to patch to end-of-file")
    sp.add_argument("--timeout", type=int, default=180)
    sp.set_defaults(func=cmd_executor)

    sp = sub.add_parser("judge", help="Single-shot local-LLM rubric scoring")
    sp.add_argument("--cwd", default=".")
    sp.add_argument("--broker-bin")
    sp.add_argument("--model", help="Explicit model name - overrides --tier and frontmatter auto-detect")
    sp.add_argument("--tier", choices=TIERS, help="L1-L4 - resolved to a pulled model via router_rules.json")
    sp.add_argument("--target-file", required=True)
    sp.add_argument("--rubric")
    sp.add_argument("--rubric-file")
    sp.add_argument("--calibration")
    sp.add_argument("--calibration-file")
    sp.add_argument("--schema-file")
    sp.add_argument("--output-file")
    sp.add_argument("--timeout", type=int, default=180)
    sp.set_defaults(func=cmd_judge)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
