#!/usr/bin/env python3
"""Requirement Expander — ranked multi-layer standards lookup.

Layers (in ranking order):
  1. local_global_brain — keyword scan of .agent/standards/ files
  2. specialized_mcp    — LLM query when MCP is enabled
  3. general_web_search — LLM query as catch-all fallback
"""

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import sys
import json
import os
from pathlib import Path

CONFIG_PATH = Path(".agent/config/gateway_config.json")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _query_llm_safe(prompt: str) -> str:
    """Call LLM with graceful degradation to empty string."""
    try:
        from lib.llm_client import query_llm_safe  # type: ignore
        response, _source, _stats = query_llm_safe(prompt)
        return response.strip() if response else ""
    except Exception:
        return ""


def _search_standards(intent: str) -> list[str]:
    """Keyword-match intent tokens against .agent/standards/ files.

    Returns list of result strings: "filename: first matching line".
    """
    try:
        from lib.data_sources import read_standards_dir  # type: ignore
        standards = read_standards_dir()
    except Exception:
        standards = []

    if not standards:
        return []

    tokens = [t.lower() for t in intent.split() if len(t) > 2]
    matches = []
    for entry in standards:
        content_lower = entry["content"].lower()
        if any(tok in content_lower for tok in tokens):
            label = f"[LOCAL_GLOBAL_BRAIN] {entry['filename']}: {entry['first_line']}"
            matches.append(label)

    return matches


def expand_requirements(intent: str, feedback: str = None) -> list[str]:
    """Expand intent into ranked requirement suggestions.

    Returns list of result strings from all matched layers.
    """
    config = load_config()
    ranking = config.get("gateway", {}).get(
        "ranking_protocol", ["local_global_brain", "general_web_search"]
    )

    if feedback:
        print(f"🔄 Re-expanding requirements based on feedback: '{feedback}'")
        intent = f"{intent} focus on {feedback}"

    print(f"📝 Starting Ranked Requirement Expansion for: '{intent}'")

    results = []

    for layer in ranking:
        print(f"  🔍 Checking {layer}...")

        if layer == "local_global_brain":
            matches = _search_standards(intent)
            if matches:
                results.extend(matches)
                break  # sufficient match in layer 1

        elif layer == "specialized_mcp":
            mcp_config = config.get("gateway", {}).get("mcp_servers", {})
            if mcp_config.get("github", {}).get("enabled"):
                answer = _query_llm_safe(f"Find best practices for: {intent}")
                if answer:
                    results.append(f"[SPECIALIZED_MCP] {answer}")
                    break

        elif layer == "general_web_search":
            answer = _query_llm_safe(f"Current best practices for: {intent}")
            if answer:
                results.append(f"[GENERAL_WEB_SEARCH] {answer}")

    if results:
        print("\n✅ EXPANDED REQUIREMENTS FOUND:")
        for r in results:
            print(f"  {r}")
    else:
        print("\n⚠️ No specific standards found across all layers.")

    return results


if __name__ == "__main__":
    expand_requirements(" ".join(sys.argv[1:]))
