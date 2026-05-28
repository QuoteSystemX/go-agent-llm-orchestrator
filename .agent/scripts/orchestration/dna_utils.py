#!/usr/bin/env python3
"""DNA Utils — User Profile Loader & Veto Engine for Council of Sages.

Provides clean functions for:
  - Loading user DNA profile from canonical user_dna.json
  - Building role-specific DNA context blocks for LLM prompts
  - Checking Advocate veto against configurable thresholds
  - Adjusting Arbitrator confidence based on alignment score

Usage:
    from orchestration.dna_utils import load_dna, build_dna_block, check_veto

    dna = load_dna()
    context = build_dna_block(dna, role="USER ADVOCATE")
    veto = check_veto(advocate_response_json, dna)
"""

import json, sys, logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("dna_utils")

REPO_ROOT = Path(__file__).resolve().parents[3]
DNA_PATH = REPO_ROOT / ".agent" / "bus" / "user_dna.json"

# ── Import schemas with fallback ──
try:
    from orchestration.sages_schemas import DNAProfile, VetoItem, VetoConfig
except ImportError:
    sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts" / "orchestration"))
    from sages_schemas import DNAProfile, VetoItem, VetoConfig  # type: ignore


def load_dna() -> DNAProfile:
    """Load user DNA profile from canonical user_dna.json.

    Returns DNAProfile with defaults if file missing/corrupt.
    Never crashes — always returns a valid DNAProfile.
    """
    try:
        if DNA_PATH.exists():
            data = json.loads(DNA_PATH.read_text(encoding="utf-8"))
            profile = DNAProfile.from_dict(data)
            logger.info("DNA profile loaded: [%s]", profile.dna)
            return profile
    except Exception as e:
        logger.warning("Failed to load user_dna.json: %s. Using defaults.", e)

    return DNAProfile(dna="BALANCED", preferences=["Standard defaults"])


def build_dna_context(dna: DNAProfile) -> str:
    """Build a human-readable DNA context string for LLM prompts."""
    lines = [f"User DNA profile: [{dna.dna}]"]
    for pref in dna.preferences:
        lines.append(f"  - {pref}")
    lines.append(f"  - Veto mode: {dna.veto_config.mode}")
    lines.append(f"  - Veto threshold: {dna.veto_config.threshold}")
    return "\n".join(lines)


def build_dna_block(dna: DNAProfile, role: str) -> str:
    """Build a role-specific DNA context block for the given role.

    Each role gets a tailored DNA prompt:
      - OPTIMIST: emphasize DNA-friendly benefits
      - SKEPTIC: find DNA-conflicting risks
      - USER ADVOCATE: full DNA + veto instructions (returns JSON)
      - ARBITRATOR: weighted consideration
    """
    base = f"User DNA profile: [{dna.dna}]\n"
    prefs_str = "\n".join(f"  - {p}" for p in dna.preferences)

    role_blocks = {
        "OPTIMIST": (
            "You are OPTIMIST, an enthusiastic architect.\n"
            "When highlighting benefits, emphasize solutions that align with "
            "the user's DNA preferences below. Advocate for simplicity, speed, "
            "and minimal complexity.\n"
            f"{base}{prefs_str}\n"
            "Keep response under 200 words."
        ),
        "SKEPTIC": (
            "You are SKEPTIC, a cynical senior engineer.\n"
            "When finding risks, focus on over-engineering, unnecessary abstraction, "
            "boilerplate, and performance overhead — all of which conflict with "
            "the user's DNA preferences below.\n"
            f"{base}{prefs_str}\n"
            "Keep response under 200 words."
        ),
        "USER ADVOCATE": (
            "You are USER ADVOCATE, the voice of the end-user.\n"
            f"{base}{prefs_str}\n\n"
            "You MUST defend the user's DNA values. If the proposed solution "
            "violates the user's preferences (e.g., suggests heavy boilerplate "
            "when DNA is MINIMALIST), you must issue a veto.\n\n"
            "You MUST output ONLY valid JSON with these exact keys:\n"
            "{\n"
            '  "veto": true/false,\n'
            '  "severity": "soft" | "hard",\n'
            '  "veto_reason": "why this violates user DNA or null",\n'
            '  "alignment_score": 0.0-1.0,\n'
            '  "suggested_alternative": "simpler approach or null"\n'
            "}\n\n"
            "Guidelines:\n"
            f"  - VETO if alignment_score < {dna.veto_config.threshold}\n"
            "  - Use 'hard' severity for clear DNA violations\n"
            "  - Use 'soft' severity for partial misalignment\n"
            "  - Always suggest a simpler alternative on veto"
        ),
        "ARBITRATOR": (
            "You are ARBITRATOR, the neutral high-court judge.\n"
            "Consider the User Advocate's veto and alignment score when "
            "issuing your final verdict. The user's DNA preferences are:\n"
            f"{base}{prefs_str}\n\n"
            "If a veto was issued, factor it into your confidence and status.\n"
            "Output ONLY valid JSON with keys:\n"
            "  - status: 'approved' | 'rejected' | 'conditional'\n"
            "  - conditions: list of strings\n"
            "  - confidence: float 0.0-1.0 (real, not made up)\n"
            "  - risk_areas: list of strings\n"
            "  - summary: string"
        ),
    }

    return role_blocks.get(role, f"{base}{prefs_str}")


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) and extract JSON."""
    import re
    # Remove ```json ... ``` blocks (multi-line)
    match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # No fences found, return as-is
    return text.strip()

def check_veto(advocate_response: str, dna: DNAProfile) -> VetoItem:
    """Parse Advocate JSON response and determine veto outcome.

    Handles raw JSON, markdown-fenced JSON (```json...```), 
    and malformed responses gracefully.

    Args:
        advocate_response: Raw JSON string from Advocate LLM call.
        dna: Loaded DNAProfile with veto config.

    Returns:
        VetoItem with parsed/validated veto result.
    """
    try:
        cleaned = _strip_code_fences(advocate_response)
        data = json.loads(cleaned)
        veto = VetoItem.from_dict(data)
        veto.validate()
        return veto
    except Exception as e:
        logger.warning("Failed to parse Advocate veto JSON: %s", e)
        logger.debug("Raw response: %s", advocate_response[:300])
        return VetoItem(
            veto=False,
            alignment_score=0.5,
            veto_reason=f"Parse error: {e}",
        )


def apply_dna_to_confidence(confidence: float, alignment: float, dna: DNAProfile) -> float:
    """Adjust Arbitrator confidence based on DNA alignment score.

    Formula: final = raw_confidence * (0.5 + 0.5 * alignment_score)
    Then clamped by veto_config.confidence_decay on veto.

    Args:
        confidence: Raw confidence from Arbitrator (0.0-1.0).
        alignment: Alignment score from Advocate (0.0-1.0).
        dna: DNAProfile with veto config.

    Returns:
        Adjusted confidence (0.0-1.0).
    """
    adjusted = confidence * (0.5 + 0.5 * alignment)

    # If alignment is very low, apply confidence_decay
    if alignment < dna.veto_config.threshold:
        adjusted *= (1.0 - dna.veto_config.confidence_decay)

    return max(0.0, min(1.0, adjusted))


def load_dna_legacy_compat() -> str:
    """Legacy compat: returns just the DNA tag string.
    
    Used by code that expects `load_user_profile()` -> str.
    Will be deprecated once all callers use DNAProfile.
    """
    return load_dna().dna


if __name__ == "__main__":
    # Quick smoke test
    dna = load_dna()
    print(f"DNA: [{dna.dna}]")
    print(f"Preferences: {len(dna.preferences)} items")
    print(f"Veto config: mode={dna.veto_config.mode}, threshold={dna.veto_config.threshold}")
    print()
    print("=== OPTIMIST BLOCK ===")
    print(build_dna_block(dna, "OPTIMIST"))
    print()
    print("=== ADVOCATE BLOCK ===")
    print(build_dna_block(dna, "USER ADVOCATE"))
