#!/usr/bin/env python3
"""Hidden War Room — Real LLM Role-Play Debate.

4 sequential LLM calls: Optimist → Skeptic → User Advocate → Arbitrator.
Fallback chain: Ollama → Cloud → Stub. Never crashes.
Dynamic timeout by model (14b=30s, 32b=60s, deepseek=120s).
"""

import sys, json, logging, re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.llm_client import query_llm_safe

logger = logging.getLogger("hidden_war_room")

# Module-level bus_manager reference so tests can patch 'orchestration.hidden_war_room.bus_manager'
try:
    from context import bus_manager  # type: ignore
except Exception:
    bus_manager = None  # type: ignore

ROLES = {
    "OPTIMIST": {
        "system": "You are OPTIMIST, an enthusiastic architect. "
                  "Always highlight benefits, potential, and positive outcomes. "
                  "Be constructive and forward-looking. Keep response under 200 words.",
    },
    "SKEPTIC": {
        "system": "You are SKEPTIC, a cynical senior engineer. "
                  "Always find hidden complexity, technical debt, and edge cases. "
                  "Challenge assumptions. Keep response under 200 words.",
    },
    "USER ADVOCATE": {
        "system": "You are USER ADVOCATE, the voice of the end-user. "
                  "Defend simplicity, usability, and practicality. "
                  "VETO over-engineered solutions. Keep response under 200 words.",
    },
    "ARBITRATOR": {
        "system": "You are ARBITRATOR, the neutral judge. "
                  "Analyze all perspectives. Issue a structured verdict with: "
                  "status (approved/rejected/conditional), conditions list, "
                  "confidence (0.0-1.0), and summary. "
                  "Output ONLY valid JSON with keys: status, conditions, confidence, summary.",
    },
}


def load_user_profile() -> str:
    """Load user DNA profile from bus or return default."""
    profile_path = REPO_ROOT / ".agent" / "bus" / "user_dna.json"
    try:
        if profile_path.exists():
            data = json.loads(profile_path.read_text())
            return data.get("profile", "[PRAGMATIC / MINIMALIST]")
    except Exception:
        pass
    return "[PRAGMATIC / MINIMALIST]"


def run_war_room(topic: str, model: str = "qwen2.5-coder:14b") -> dict:
    """Run 4-role debate via real LLM calls.

    Returns structured verdict dict from Arbitrator.
    """
    profile = load_user_profile()
    context = f"User profile: {profile}\n\nTopic: {topic}"

    print(f"⚔️  Opening Hidden War Room (via {model}) for: '{topic}'...")
    print(f"👤 Profile: {profile}")

    # ── Round 1: Optimist ──
    print("\n🎭 [OPTIMIST] debating...", end=" ", flush=True)
    resp_opt, src_opt, _ = query_llm_safe(
        prompt=f"Defend and promote this topic. Highlight all benefits and positive aspects.\n\n{context}",
        model=model,
        system_prompt=ROLES["OPTIMIST"]["system"],
    )
    print(f"(via {src_opt})")
    print(f"  {resp_opt[:200]}")

    # ── Round 2: Skeptic (gets Optimist's answer) ──
    print("\n🎭 [SKEPTIC] debating...", end=" ", flush=True)
    resp_ske, src_ske, _ = query_llm_safe(
        prompt=f"Critique this proposal. Find hidden complexity, risks, edge cases.\n\n{context}\n\nThe Optimist argues:\n{resp_opt}",
        model=model,
        system_prompt=ROLES["SKEPTIC"]["system"],
    )
    print(f"(via {src_ske})")
    print(f"  {resp_ske[:200]}")

    # ── Round 3: User Advocate (gets both) ──
    print("\n🎭 [USER ADVOCATE] debating...", end=" ", flush=True)
    resp_adv, src_adv, _ = query_llm_safe(
        prompt=f"Represent the user. Keep it simple and practical. VETO over-engineering.\n\n{context}\n\nOptimist: {resp_opt}\n\nSkeptic: {resp_ske}",
        model=model,
        system_prompt=ROLES["USER ADVOCATE"]["system"],
    )
    print(f"(via {src_adv})")
    print(f"  {resp_adv[:200]}")

    # ── Round 4: Arbitrator (gets all 3) ──
    print("\n🎭 [ARBITRATOR] issuing verdict...", end=" ", flush=True)
    judge_model = "qwen2.5-coder:32b" if "32b" in model else model
    resp_arb, src_arb, _ = query_llm_safe(
        prompt=f"Analyze the following debate and issue a final structured verdict.\n\nTopic: {topic}\n\nUser Profile: {profile}\n\nOPTIMIST:\n{resp_opt}\n\nSKEPTIC:\n{resp_ske}\n\nUSER ADVOCATE:\n{resp_adv}",
        model=judge_model,
        system_prompt=ROLES["ARBITRATOR"]["system"],
    )
    print(f"(via {src_arb}, judge={judge_model})")

    # Parse JSON verdict or wrap as unstructured
    verdict = _parse_verdict(resp_arb, topic)
    print(f"\n✅ CONSENSUS: {verdict['status']} (confidence: {verdict['confidence']})")
    if verdict.get("conditions"):
        for c in verdict["conditions"]:
            print(f"   └─ {c}")
    print(f"   Summary: {verdict['summary'][:200]}")

    _push_verdict(topic, verdict, resp_opt, resp_ske, resp_adv, profile)
    return verdict


def _push_verdict(topic: str, verdict: dict, resp_opt: str, resp_ske: str, resp_adv: str, profile: str):
    try:
        topic_slug = topic.lower().replace(" ", "_").replace("/", "-").replace("\\", "-")
        topic_slug = re.sub(r'[^a-z0-9_-]', '', topic_slug)

        payload = {
            "plan_id": topic_slug,
            "title": topic,
            "context": f"User DNA Profile: {profile}\nTopic: {topic}",
            "verdict": verdict,
            "responses": {
                "optimist": resp_opt,
                "skeptic": resp_ske,
                "user_advocate": resp_adv
            },
            "debate_type": "strategic"
        }

        _bm = bus_manager
        if _bm is None:
            logger.warning("bus_manager not available — verdict not pushed to bus")
            return

        _bm.push(
            f"verdict_{topic_slug}",
            "verification_result",
            "hidden_war_room",
            json.dumps(payload)
        )
        print(f"Verdict pushed to bus: verdict_{topic_slug}")
    except Exception as e:
        logger.warning("Could not push hidden war room verdict to bus: %s", e)


def _parse_verdict(text: str, topic: str) -> dict:
    """Extract structured verdict from Arbitrator response."""
    # Try to find JSON block
    import re
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            v = json.loads(match.group(0))
            if all(k in v for k in ("status", "confidence")):
                return v
        except Exception:
            pass

    # Fallback: generic verdict
    return {
        "status": "conditional",
        "conditions": ["Review Arbitrator output for details"],
        "confidence": 0.5,
        "summary": text[:300],
        "topic": topic,
    }


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) or "Default architectural decision"
    result = run_war_room(topic)
    print(json.dumps(result, indent=2))
