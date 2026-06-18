#!/usr/bin/env python3
"""True Arena -- Multi-Model Duel Engine.

Dynamically selects 2-3 models based on question complexity (via model_router).
Judge is the highest-ranked model among duelists.
--models flag overrides for manual selection only.
"""

import json, sys, argparse
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts"))

import logging
from lib.common import load_json_safe
from lib.llm_client import query_llm
from lib.suppress import suppress

ARENA_REPORTS_DIR = REPO_ROOT / ".agent" / "reports" / "arena"
TIER_ORDER = ["L1", "L2", "L3", "L4"]


def _load_rules():
    rules_file = REPO_ROOT / ".agent" / "config" / "router_rules.json"
    return load_json_safe(rules_file)


def _get_local_models() -> set:
    with suppress("arena_engine.local_models", level=logging.DEBUG):
        from lib.llm_client import call_mcp_broker
        res = call_mcp_broker("detect_backends", {})
        models = set()
        for backend in res.get("backends", []):
            if backend.get("available"):
                for m in backend.get("models", []):
                    models.add(m)
        return models
    return set()


def _tier_index(tier: str) -> int:
    try:
        return TIER_ORDER.index(tier)
    except ValueError:
        return 1


def _resolve_model_for_tier(tier: str, ollama_models: dict, local_models: set) -> str:
    primary = ollama_models.get(tier, "")
    if primary in local_models:
        return primary
    for alt in ollama_models.get("%s_alt" % tier, []):
        if alt in local_models:
            return alt
    return ""


def get_dynamic_duelists(prompt: str):
    """Resolve duelists + judge dynamically based on prompt complexity."""
    try:
        from lib.llm_client import call_mcp_broker
        res = call_mcp_broker("get_routing_decision", {"task_description": prompt})
        target_tier = res.get("tier", "L2")
        target_model = res.get("model_id", "qwen2.5-coder:14b")
    except Exception as e:
        print("Router failed: %s. Using defaults." % e)
        return ["qwen2.5-coder:14b"], "qwen2.5-coder:32b"
    print("Router: Tier [%s] -> recommended '%s'" % (target_tier, target_model))

    rules = _load_rules()
    ollama_models = rules.get("models", {}).get("ollama", {})
    rankings = rules.get("model_rankings", {})
    local_models = _get_local_models()

    if not local_models:
        return [target_model], target_model

    # Select tiers: target +- 1
    idx = _tier_index(target_tier)
    candidate_tiers = {target_tier}
    if idx > 0:
        candidate_tiers.add(TIER_ORDER[idx - 1])
    if idx < len(TIER_ORDER) - 1:
        candidate_tiers.add(TIER_ORDER[idx + 1])

    selected = []
    for t in TIER_ORDER:
        if t in candidate_tiers:
            m = _resolve_model_for_tier(t, ollama_models, local_models)
            if m:
                selected.append(m)

    if target_model not in selected and target_model in local_models:
        selected.append(target_model)

    seen = set()
    deduped = []
    for m in selected:
        if m not in seen:
            seen.add(m)
            deduped.append(m)

    if len(deduped) < 2:
        for m in sorted(local_models, key=lambda x: rankings.get(x, {}).get("rank_score", 0), reverse=True):
            if m not in seen and "embed" not in m.lower():
                deduped.append(m)
                seen.add(m)
            if len(deduped) >= 3:
                break

    def _rank(m):
        return rankings.get(m, {}).get("rank_score", 0)
    judge = max(deduped, key=_rank)

    print("   Duelists: %s" % ", ".join(deduped))
    print("   Judge:    %s" % judge)
    return deduped, judge


def _pick_judge(models, rankings=None):
    """Pick the best judge among models by rank_score, not position."""
    if rankings is None:
        rankings = _load_rules().get("model_rankings", {})
    def _rank(m):
        return rankings.get(m, {}).get("rank_score", 0)
    ranked = [(m, _rank(m)) for m in models]
    best = max(ranked, key=lambda x: x[1])
    if best[1] > 0:
        return best[0]
    return models[-1]  # fallback: last model (backwards compat)


def run_duel(prompt: str, models=None):
    if models:
        print("   Manual models: %s" % ", ".join(models))
    else:
        models, _ = get_dynamic_duelists(prompt)
    judge_model = _pick_judge(models)

    ARENA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    print("\n=== Starting True Arena Duel ===")
    print("  Prompt: %s..." % prompt[:120])

    responses = []
    for model in models:
        print("  Model: %s... " % model, end="", flush=True)
        response, stats = query_llm(prompt, model)
        responses.append({"model": model, "response": response, "stats": stats})
        t = stats.get("elapsed_seconds", 0)
        tps = stats.get("tps", 0)
        print(" %.1fs (%.0f tps)" % (t, tps))

    print("  Judging with %s... " % judge_model, end="", flush=True)
    judge_prompt = (
        "You are the Multi-Agent Judge.\n"
        "We have a prompt and multiple responses from different models.\n"
        "Your task:\n"
        "1. Analyze the responses.\n"
        "2. Find common ground (consensus).\n"
        "3. Identify unique insights from each.\n"
        "4. Synthesize the FINAL BEST ANSWER.\n\n"
        "PROMPT:\n%s\n\nRESPONSES:\n" % prompt
    )
    for i, r in enumerate(responses):
        judge_prompt += "\n--- RESPONSE %d (Model: %s) ---\n%s\n" % (i + 1, r["model"], r["response"])

    final_answer, judge_stats = query_llm(judge_prompt, judge_model)
    print(" %.1fs" % judge_stats.get("elapsed_seconds", 0))

    report_path = _save_report(prompt, models, responses, final_answer, judge_model)
    print("\n%s" % ("=" * 40))
    print("Duel Complete! Report: %s" % report_path)
    print("%s" % ("=" * 40))
    print("\nFINAL SYNTHESIS:\n%s" % final_answer)


def _save_report(prompt, models, responses, final_answer, judge_model):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ARENA_REPORTS_DIR / ("duel_%s.md" % ts)

    sections = []
    sections.append("# True Arena Duel Report\n")
    sections.append("- **Date**: %s" % datetime.now().isoformat())
    sections.append("- **Judge**: `%s`" % judge_model)
    sections.append("- **Models Participated**: %s\n" % ", ".join(models))
    sections.append("## Original Prompt\n\n> %s\n" % prompt)
    sections.append("## Synthesis (Consensus)\n\n%s\n" % final_answer)
    sections.append("## Individual Responses\n")
    for r in responses:
        sections.append("### Model: `%s`" % r["model"])
        sections.append("- **Latency**: %.2fs" % r["stats"].get("elapsed_seconds", 0))
        sections.append("- **TPS**: %.0f\n" % r["stats"].get("tps", 0))
        sections.append("#### Response\n```\n%s\n```\n" % r["response"])

    path.write_text("\n".join(sections))
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="True Arena - Multi-Model Duel Engine")
    parser.add_argument("prompt", help="Prompt to duel over")
    parser.add_argument("--models", nargs="+",
                        help="Override: specific models. Last one becomes judge. "
                             "Default: dynamic by question weight.")
    args = parser.parse_args()
    run_duel(args.prompt, args.models)
