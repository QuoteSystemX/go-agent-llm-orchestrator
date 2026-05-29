#!/usr/bin/env python3
"""Hidden War Room — Real LLM Role-Play Debate.

4 sequential LLM calls: Optimist → Skeptic → User Advocate → Arbitrator.
Fallback chain: Ollama → Cloud → Stub. Never crashes.
Dynamic timeout by model (14b=30s, 32b=60s, deepseek=120s).
"""

import sys, json, logging, re
from pathlib import Path

from lib.suppress import suppress

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.llm_client import query_llm_safe
from orchestration.dna_utils import load_dna, build_dna_block, check_veto, build_dna_context

logger = logging.getLogger("hidden_war_room")

# Module-level bus_manager reference so tests can patch 'orchestration.hidden_war_room.bus_manager'
try:
    from context import bus_manager  # type: ignore
except Exception:
    bus_manager = None  # type: ignore

# DNA is loaded once per session and cached
_DNA_CACHE = None

def _get_dna():
    global _DNA_CACHE
    if _DNA_CACHE is None:
        _DNA_CACHE = load_dna()
    return _DNA_CACHE


def run_war_room(topic: str, model: str = "qwen2.5-coder:14b") -> dict:
    """Run 4-role DNA-aware debate via real LLM calls.

    All roles receive DNA context. Advocate returns structured JSON with veto.
    Veto outcome is parsed, validated, and included in the final verdict.

    Returns structured verdict dict from Arbitrator (enriched with DNA data).
    """
    dna = _get_dna()
    dna_context = build_dna_context(dna)
    full_context = f"{dna_context}\n\nTopic: {topic}"

    print(f"⚔️  Opening Hidden War Room (via {model}) for: '{topic}'...")
    print(f"👤 DNA Profile: [{dna.dna}] (veto_mode={dna.veto_config.mode})")

    # ── Round 1: Optimist (DNA-aware) ──
    print("\n🎭 [OPTIMIST] debating...", end=" ", flush=True)
    resp_opt, src_opt, _ = query_llm_safe(
        prompt=f"Defend and promote this topic. Highlight all benefits and positive aspects.\n\n{full_context}",
        model=model,
        system_prompt=build_dna_block(dna, "OPTIMIST"),
    )
    print(f"(via {src_opt})")
    print(f"  {resp_opt[:200]}")

    # ── Round 2: Skeptic (DNA-aware, gets Optimist's answer) ──
    print("\n🎭 [SKEPTIC] debating...", end=" ", flush=True)
    resp_ske, src_ske, _ = query_llm_safe(
        prompt=f"Critique this proposal. Find hidden complexity, risks, edge cases.\n\n{full_context}\n\nThe Optimist argues:\n{resp_opt}",
        model=model,
        system_prompt=build_dna_block(dna, "SKEPTIC"),
    )
    print(f"(via {src_ske})")
    print(f"  {resp_ske[:200]}")

    # ── Round 3: User Advocate (DNA-aware, returns structured JSON veto) ──
    print("\n🎭 [USER ADVOCATE] debating...", end=" ", flush=True)
    resp_adv, src_adv, _ = query_llm_safe(
        prompt=f"Represent the user. Evaluate alignment with user DNA.\n\n{full_context}\n\nOptimist: {resp_opt}\n\nSkeptic: {resp_ske}",
        model=model,
        system_prompt=build_dna_block(dna, "USER ADVOCATE"),
    )
    print(f"(via {src_adv})")
    print(f"  {resp_adv[:200]}")

    # ── Parse Advocate veto from structured JSON ──
    veto = check_veto(resp_adv, dna)
    if veto.veto:
        print(f"  ⛔ VETO ({veto.severity}): {veto.veto_reason[:120]}")
        print(f"     Alignment: {veto.alignment_score}")
    else:
        print(f"  ✅ No veto. Alignment: {veto.alignment_score}")

    # ── Round 4: Arbitrator (DNA-aware, gets all 3 + veto) ──
    print("\n🎭 [ARBITRATOR] issuing verdict...", end=" ", flush=True)
    judge_model = "qwen2.5-coder:32b" if "32b" in model else model
    arb_prompt = (
        f"Analyze the following debate and issue a final structured verdict.\n\n"
        f"Topic: {topic}\n\n{dna_context}\n\n"
        f"OPTIMIST:\n{resp_opt}\n\nSKEPTIC:\n{resp_ske}\n\n"
        f"USER ADVOCATE:\n{resp_adv}\n\n"
    )
    if veto.veto:
        arb_prompt += (
            f"NOTE: The User Advocate issued a {veto.severity.upper()} veto "
            f"with alignment_score={veto.alignment_score}.\n"
            f"Veto reason: {veto.veto_reason}\n"
        )

    resp_arb, src_arb, _ = query_llm_safe(
        prompt=arb_prompt,
        model=judge_model,
        system_prompt=build_dna_block(dna, "ARBITRATOR"),
    )
    print(f"(via {src_arb}, judge={judge_model})")

    # Parse JSON verdict or wrap as unstructured
    verdict = _parse_verdict(resp_arb, topic)

    # ── Enrich verdict with DNA alignment data ──
    verdict["dna_alignment"] = {
        "profile": f"[{dna.dna}]",
        "alignment_score": veto.alignment_score,
        "veto_triggered": veto.veto,
        "veto_severity": veto.severity,
        "veto_reason": veto.veto_reason,
        "veto_threshold": dna.veto_config.threshold,
        "veto_config": {
            "mode": dna.veto_config.mode,
            "auto_reject": dna.veto_config.auto_reject,
        },
    }

    print(f"\n✅ CONSENSUS: {verdict['status']} (confidence: {verdict['confidence']})")
    if veto.veto:
        print(f"   ⛔ VETO: {veto.severity} (alignment: {veto.alignment_score})")
    if verdict.get("conditions"):
        for c in verdict["conditions"]:
            print(f"   └─ {c}")
    print(f"   Summary: {verdict['summary'][:200]}")

    _push_verdict(topic, verdict, dna, resp_opt, resp_ske, resp_adv, veto)
    return verdict


def _push_verdict(topic: str, verdict: dict, dna, resp_opt: str, resp_ske: str, resp_adv: str, veto):
    try:
        topic_slug = topic.lower().replace(" ", "_").replace("/", "-").replace("\\", "-")
        topic_slug = re.sub(r'[^a-z0-9_-]', '', topic_slug)

        payload = {
            "plan_id": topic_slug,
            "title": topic,
            "context": f"User DNA Profile: [{dna.dna}]\nTopic: {topic}",
            "verdict": verdict,
            "dna_profile": dna.to_dict(),
            "veto": veto.to_dict(),
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
        with suppress("hidden_war_room.parse_verdict", level=logging.ERROR):
            v = json.loads(match.group(0))
            if all(k in v for k in ("status", "confidence")):
                return v

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
