#!/usr/bin/env python3
"""Agent Arena -- Role-based agent debate and verdict engine.

Runs structured multi-round debates between candidate agents using LLM calls.
Falls back to stub text when LLM is unavailable (Ollama offline, etc.).
"""

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts"))

JUDGE_AGENT = "project-planner"
NUM_ROUNDS = 2
# Hard cap for the entire debate (seconds) to avoid blocking pipelines
MAX_DEBATE_SECONDS = 120


def _generate_argument(
    candidate: str,
    subtask: str,
    round_num: int,
    prior_rounds: list,
    role: str,
) -> tuple[str, str]:
    """Generate one debate argument via LLM.

    Returns (argument_text, source) where source is 'ollama'|'cloud'|'stub'.
    """
    prior_context = ""
    if prior_rounds:
        lines = []
        for r in prior_rounds:
            arg = r["arguments"].get(candidate, "")
            if arg:
                lines.append(f"Round {r['round']}: {arg}")
        prior_context = "\n".join(lines)

    prompt = (
        f"You are agent '{candidate}' arguing in a structured debate.\n"
        f"Role being filled: {role}\n"
        f"Subtask to solve: {subtask}\n"
        + (f"Your prior argument:\n{prior_context}\n" if prior_context else "")
        + f"Round {round_num}: Argue clearly and concisely (3-5 sentences) why "
        f"your approach is the best choice for this subtask."
    )

    try:
        from lib.llm_client import query_llm_safe  # type: ignore
        response, source, _ = query_llm_safe(prompt, default_model="qwen2.5-coder:14b")
        text = response.strip() if response else ""
        if text:
            return text, source
    except Exception:
        pass

    # Explicit stub fallback
    return (
        f"[stub] {candidate} proposes a systematic approach to '{subtask}' "
        f"in round {round_num}, emphasising correctness and maintainability.",
        "stub",
    )


def _judge_debate(role: str, subtask: str, rounds: list, candidates: list) -> str:
    """Ask LLM to pick a winner based on all debate rounds."""
    debate_text = ""
    for r in rounds:
        debate_text += f"\n--- Round {r['round']} ---\n"
        for candidate, arg in r["arguments"].items():
            debate_text += f"{candidate}: {arg}\n"

    prompt = (
        f"You are the judge for a structured agent debate.\n"
        f"Role: {role}\n"
        f"Subtask: {subtask}\n"
        f"Candidates: {', '.join(candidates)}\n\n"
        f"Debate transcript:\n{debate_text}\n\n"
        f"Pick the single best candidate for this role and subtask. "
        f"Respond with ONLY the candidate name, nothing else."
    )

    try:
        from lib.llm_client import query_llm_safe  # type: ignore
        response, _, _ = query_llm_safe(prompt, default_model="qwen2.5-coder:14b")
        winner = response.strip().split("\n")[0].strip()
        if winner in candidates:
            return winner
    except Exception:
        pass

    # Fallback: first candidate
    return candidates[0] if candidates else JUDGE_AGENT


def conduct_debate(session_id: str, role: str, candidates: list, subtask: str) -> dict:
    """Run a structured LLM-driven debate between candidate agents.

    Returns a report dict with rounds, winner, and metadata.
    Falls back to stub responses when LLM is unavailable.
    """
    start_time = time.time()
    rounds = []
    sources: list[str] = []

    for i in range(NUM_ROUNDS):
        if time.time() - start_time > MAX_DEBATE_SECONDS:
            break

        arguments = {}
        for c in candidates:
            text, source = _generate_argument(c, subtask, i + 1, rounds, role)
            arguments[c] = text
            sources.append(source)

        rounds.append({"round": i + 1, "arguments": arguments})

    winner = _judge_debate(role, subtask, rounds, list(candidates))
    elapsed = round(time.time() - start_time, 2)

    # Determine overall source quality
    unique_sources = set(sources)
    overall_source = "stub" if unique_sources <= {"stub"} else (
        "ollama" if "ollama" in unique_sources else "cloud"
    )

    return {
        "session_id": session_id,
        "role": role,
        "subtask": subtask,
        "candidates": list(candidates),
        "judge": JUDGE_AGENT,
        "winner": winner,
        "rounds": rounds,
        "source": overall_source,
        "total_elapsed_seconds": elapsed,
    }


def format_verdict(winner: str, risks: list) -> dict:
    """Format a final verdict with mitigation plan for each identified risk."""
    mitigation_plan = [f"Address risk: {r}" for r in risks]
    return {
        "winner": winner,
        "mitigation_plan": mitigation_plan,
        "status": "decided_via_arena",
    }


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: agent_arena.py <session_id> <role> <subtask> <candidates_csv>")
        sys.exit(1)

    session_id = sys.argv[1]
    role = sys.argv[2]
    subtask = sys.argv[3]
    candidates = sys.argv[4].split(",")

    report = conduct_debate(session_id, role, candidates, subtask)
    print(json.dumps(report, indent=2))
