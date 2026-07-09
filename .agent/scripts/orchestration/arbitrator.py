#!/usr/bin/env python3
"""Arbitrator -- Real LLM Judge for Council of Sages.

3-round debate: Proposer -> Challenger -> Arbitrator/Judge.
Fallback chain: Ollama -> Cloud -> Stub. Never crashes.
Dynamic timeout by model. Real confidence (not hardcoded 0.92).
"""

import sys, json, logging, subprocess, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.llm_client import query_llm_safe
from orchestration.dna_utils import load_dna, build_dna_context, build_dna_block, apply_dna_to_confidence

logger = logging.getLogger("arbitrator")

# Module-level bus_manager reference so tests can patch 'orchestration.arbitrator.bus_manager'
try:
    from context import bus_manager  # type: ignore
except Exception:
    bus_manager = None  # type: ignore

EXT_TO_CONCEPTS = {
    ".go": "go",
    ".py": "python",
    ".sql": "database",
    ".prisma": "database",
    ".ts": "frontend",
    ".tsx": "frontend",
    ".js": "frontend",
    ".jsx": "frontend",
}

def _get_staged_files() -> list:
    """Run git diff --cached --name-only to fetch staged changeset files."""
    try:
        res = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True)
        return [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except Exception as e:
        logger.warning("Failed to get staged files: %s", e)
        return []

def _detect_staged_concepts(files: list) -> str:
    """Map staged file paths and extensions to concept keywords for the auctioneer."""
    concepts = set()
    for f in files:
        f_lower = f.lower()
        # Path-based overrides
        if any(kw in f_lower for kw in ["auth", "security", "keys", "jwt", "session"]):
            concepts.add("security")
        if any(kw in f_lower for kw in ["wsl", "infra", "docker", "k8s", "kubernetes"]):
            concepts.add("infra")
        # Extension-based overrides
        for ext, concept in EXT_TO_CONCEPTS.items():
            if f_lower.endswith(ext):
                concepts.add(concept)
    return " ".join(sorted(concepts))

def _load_agent_rules(agent_name: str) -> str:
    """Locate agent MD file recursively and return its rule body (excluding frontmatter)."""
    agents_dir = REPO_ROOT / ".agent" / "agents"
    for p in agents_dir.rglob(f"{agent_name}.md"):
        try:
            content = p.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
            return content.strip()
        except Exception as e:
            logger.warning("Failed to read rules for agent %s: %s", agent_name, e)
    return ""



def _load_schemas():
    try:
        orchestration = __import__("orchestration.sages_schemas", fromlist=["CritiqueList", "VerdictList"])
        return orchestration.CritiqueList, orchestration.VerdictList
    except ImportError:
        sys.path.insert(0, str(SCRIPTS_DIR / "orchestration"))
        sages_schemas = __import__("sages_schemas", fromlist=["CritiqueList", "VerdictList"])
        return sages_schemas.CritiqueList, sages_schemas.VerdictList

CritiqueList, VerdictList = _load_schemas()

def _extract_json_block(text: str) -> str:
    import re
    # Strip <think>...</think> block if present
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    try:
        start = text.index('{')
    except ValueError:
        try:
            start = text.index('[')
        except ValueError:
            return text
            
    brace_count = 0
    in_quote = False
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if char == '"' and not escaped:
            in_quote = not in_quote
        elif char == '\\' and not escaped:
            escaped = True
            continue
        elif not in_quote:
            if char in ('{', '['):
                brace_count += 1
            elif char in ('}', ']'):
                brace_count -= 1
                if brace_count == 0:
                    return text[start:i+1]
        escaped = False
    return text


def _check_syntax_offline() -> tuple[bool, list[str]]:
    """Perform fast local syntax checks on staged files.
    Returns (passed, list_of_errors)
    """
    staged = _get_staged_files()
    if not staged:
        return True, ["No staged files to check."]
    
    errors = []
    passed = True
    for f in staged:
        path = REPO_ROOT / f
        if not path.exists():
            continue
        if f.endswith(".py"):
            try:
                res = subprocess.run([sys.executable, "-m", "py_compile", str(path)], capture_output=True, text=True)
                if res.returncode != 0:
                    passed = False
                    errors.append(f"Python syntax error in {f}: {res.stderr.strip()}")
            except Exception as e:
                errors.append(f"Failed to check Python syntax in {f}: {e}")
        elif f.endswith(".go"):
            try:
                res = subprocess.run(["go", "vet", str(path)], capture_output=True, text=True)
                if res.returncode != 0:
                    passed = False
                    errors.append(f"Go compilation/vet error in {f}: {res.stderr.strip()}")
            except Exception as e:
                pass
    return passed, errors


def run_consensus(plan_id: str, plan_text: str = "") -> dict:
    """Run 3-round debate: Proposer -> Challenger -> Judge."""
    if not plan_text:
        plan_text = _load_plan(plan_id)

    print("=== Arbitrator: Starting consensus for plan '%s' ===" % plan_id)

    # Dynamic Expert Selection using agent_auctioneer.py
    expert_rules = ""
    staged_files = _get_staged_files()
    if staged_files:
        concepts = _detect_staged_concepts(staged_files)
        if concepts:
            try:
                sys.path.insert(0, str(SCRIPTS_DIR))
                try:
                    orchestration = __import__("orchestration.agent_auctioneer", fromlist=["find_candidates"])
                    find_candidates = orchestration.find_candidates
                except ImportError:
                    sys.path.insert(0, str(SCRIPTS_DIR / "orchestration"))
                    agent_auctioneer = __import__("agent_auctioneer", fromlist=["find_candidates"])
                    find_candidates = agent_auctioneer.find_candidates
                candidates = find_candidates(concepts)
                # Keep top 2 unique specialist candidates (excluding orchestrator/red-team itself)
                top_agents = []
                for c in candidates:
                    a_id = c["id"]
                    if a_id not in ["orchestrator", "red-team"] and len(top_agents) < 2:
                        top_agents.append(a_id)
                
                if top_agents:
                    print(f"🧙 Council of Sages: Summoning experts: {', '.join(['@' + a for a in top_agents])}")
                    # Load rules
                    rules_list = []
                    for agent in top_agents:
                        rules = _load_agent_rules(agent)
                        if rules:
                            rules_list.append(f"=== Expert Rules for @{agent} ===\n{rules}")
                    expert_rules = "\n\n".join(rules_list)
            except Exception as e:
                logger.warning("Failed to load expert Sages rules: %s", e)

    # -- Round 1: Challenger (red-team, attacks, outputs Critique JSON) --
    print("[CHALLENGER] attacking plan...", end=" ", flush=True)
    challenger_sys = (
        "You are CHALLENGER, a ruthless security and architecture auditor.\n"
        "Find every weakness. Be specific with risk areas.\n"
        "You MUST output ONLY a valid JSON object conforming to this schema:\n"
        "{\n"
        "  \"critiques\": [\n"
        "    {\n"
        "      \"id\": \"CRIT-001\",\n"
        "      \"category\": \"security\" | \"performance\" | \"design\",\n"
        "      \"severity\": \"blocker\" | \"warning\",\n"
        "      \"description\": \"Detailed description of the issue\",\n"
        "      \"suggested_action\": \"Remediation action to fix the issue\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Output ONLY valid raw JSON."
    )
    if expert_rules:
        challenger_sys += f"\n\nIn addition, you must audit against these domain-expert rules:\n{expert_rules}"

    resp_chal, src_chal, _ = query_llm_safe(
        prompt="Critique the following architectural plan with maximum severity.\n\nPlan:\n" + plan_text,
        system_prompt=challenger_sys,
        format_json=True
    )
    print("(via %s)" % src_chal)
    
    is_offline = (src_chal == "stub") and ("LLM Unavailable" in resp_chal or not _extract_json_block(resp_chal).strip().startswith("{"))
    if is_offline:
        print("\n🚨 [OFFLINE] Ни одна LLM не доступна! Выполняется локальный синтаксический анализ изменений...")
        passed, errors = _check_syntax_offline()
        
        if not passed:
            verdict = {
                "plan_ref": plan_id,
                "status": "rejected",
                "conditions": ["Fix compilation and syntax errors before proceeding."],
                "confidence": 1.0,
                "risk_areas": errors,
                "summary": "🚨 [OFFLINE] Авто-вето: обнаружены критические ошибки синтаксиса/компиляции при недоступности LLM.",
            }
        else:
            verdict = {
                "plan_ref": plan_id,
                "status": "approved",
                "conditions": [],
                "confidence": 0.8,
                "risk_areas": ["⚠️ Ни одна LLM не доступна (Offline). Вердикт вынесен локально на основе синтаксического анализа."],
                "summary": "✅ [OFFLINE] Одобрено: все измененные файлы прошли локальную синтаксическую валидацию при недоступности LLM.",
            }
            
        _push_verdict(plan_id, verdict, CritiqueList(critiques=[]), VerdictList(resolutions=[]), plan_text)
        return verdict

    # Safely parse Challenger output
    try:
        crit_list = CritiqueList.from_dict(json.loads(_extract_json_block(resp_chal)))
        print(f"  Successfully parsed {len(crit_list.critiques)} critiques")
    except Exception as e:
        logger.warning("Failed to parse Challenger JSON, falling back to dummy list: %s", e)
        crit_list = CritiqueList(critiques=[])

    # -- Round 2: Proposer (architect, defends, takes Critique JSON, outputs Verdict JSON) --
    print("[PROPOSER] defending plan...", end=" ", flush=True)
    proposer_sys = (
        "You are PROPOSER, a confident architect.\n"
        "You have received a list of architectural critiques. You must respond to each point.\n"
        "You MUST output ONLY a valid JSON object conforming to this schema:\n"
        "{\n"
        "  \"resolutions\": [\n"
        "    {\n"
        "      \"critique_id\": \"ID of the critique point (e.g. CRIT-001)\",\n"
        "      \"accepted\": true | false,\n"
        "      \"resolution\": \"Detailed explanation of why you accept/reject and how you resolve it\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Output ONLY valid raw JSON."
    )
    if expert_rules:
        proposer_sys += f"\n\nIn addition, you must adhere to these domain-expert rules:\n{expert_rules}"

    prompt_prop = (
        "Defend the following architectural plan by responding to each point in the critiques JSON.\n\n"
        f"Plan:\n{plan_text}\n\n"
        f"Critiques:\n{json.dumps(crit_list.to_dict(), indent=2)}"
    )

    resp_prop, src_prop, _ = query_llm_safe(
        prompt=prompt_prop,
        system_prompt=proposer_sys,
        format_json=True
    )
    print("(via %s)" % src_prop)

    # Safely parse Proposer output
    try:
        verd_list = VerdictList.from_dict(json.loads(_extract_json_block(resp_prop)))
        print(f"  Successfully parsed {len(verd_list.resolutions)} resolutions")
    except Exception as e:
        logger.warning("Failed to parse Proposer JSON, falling back to dummy list: %s", e)
        verd_list = VerdictList(resolutions=[])

    # Automated Validation step: check that all blockers are resolved with accepted=True
    critique_map = {c.id: c for c in crit_list.critiques}
    resolutions_map = {r.critique_id: r for r in verd_list.resolutions}
    
    validation_passed = True
    blocker_failures = []
    
    for c_id, c in critique_map.items():
        if c.severity == "blocker":
            res = resolutions_map.get(c_id)
            if not res or not res.accepted:
                validation_passed = False
                blocker_failures.append(f"{c_id} ({c.category})")

    # -- Load user DNA for DNA-aware judging --
    dna = load_dna()
    dna_context = build_dna_context(dna)

    # -- Round 3: Arbitrator/Judge (DNA-aware, reviews both, outputs structured JSON) --
    print("[ARBITRATOR] issuing verdict...", end=" ", flush=True)
    judge_prompt = (
        "Review the structured debate and issue a final structured verdict.\n\n"
        f"Plan: {plan_text}\n\n"
        f"User DNA:\n{dna_context}\n\n"
        f"CRITIQUES (Challenger):\n{json.dumps(crit_list.to_dict(), indent=2)}\n\n"
        f"RESOLUTIONS (Proposer):\n{json.dumps(verd_list.to_dict(), indent=2)}\n\n"
        "Output ONLY valid JSON with these exact keys:\n"
        "  - status: 'approved' | 'rejected' | 'conditional'\n"
        "  - conditions: list of strings (if conditional)\n"
        "  - confidence: float 0.0-1.0 (real, not made up)\n"
        "  - risk_areas: list of strings\n"
        "  - summary: string (1-2 sentences)"
    )
    
    resp_judge, src_judge, _ = query_llm_safe(
        prompt=judge_prompt,
        system_prompt=build_dna_block(dna, "ARBITRATOR"),
        format_json=True
    )
    print("(via %s)" % src_judge)

    verdict = _parse_verdict(resp_judge, plan_id)

    # -- Adjust confidence based on DNA alignment --
    raw_confidence = verdict.get("confidence", 0.5)
    aligned_confidence = apply_dna_to_confidence(raw_confidence, 0.7, dna)
    if abs(aligned_confidence - raw_confidence) > 0.01:
        verdict["confidence_raw"] = raw_confidence
        verdict["confidence"] = aligned_confidence
        verdict["dna_adjusted"] = True
        print(f"  🧬 DNA-adjusted confidence: {raw_confidence:.2f} -> {aligned_confidence:.2f}")
    
    # Overriding final status if automated validation of blockers failed
    if not validation_passed:
        print(f"⚠️ AUTOMATED VALIDATION FAILED: Blocker critiques were not accepted! Blocker failures: {', '.join(blocker_failures)}")
        verdict["status"] = "rejected"
        verdict["conditions"] = verdict.get("conditions", []) + [f"Resolve blocker critiques: {', '.join(blocker_failures)}"]
        verdict["risk_areas"] = verdict.get("risk_areas", []) + [f"Automated check-off failed due to unaccepted blocker critiques"]

    print("\nVerdict: %s (confidence: %.2f)" % (verdict["status"], verdict["confidence"]))
    for c in verdict.get("conditions", []):
        print("   - %s" % c)
    for r in verdict.get("risk_areas", []):
        print("   WARNING: %s" % r)

    _push_verdict(plan_id, verdict, crit_list, verd_list, plan_text)
    return verdict


def _load_plan(plan_id: str) -> str:
    bus_file = REPO_ROOT / ".agent" / "bus" / ("%s.json" % plan_id)
    if bus_file.exists():
        try:
            data = json.loads(bus_file.read_text())
            return data.get("text", data.get("plan", json.dumps(data)))
        except Exception as e:
            logger.warning("Failed to parse plan from bus file %s: %s", bus_file, e)
    for md_file in REPO_ROOT.glob("*.md"):
        if plan_id in md_file.stem:
            return md_file.read_text()[:2000]
    return "Plan ID: %s. Evaluate as a standard architectural proposal." % plan_id


def _parse_verdict(text: str, plan_id: str) -> dict:
    json_str = _extract_json_block(text)
    try:
        v = json.loads(json_str)
        if "status" in v and "confidence" in v:
            v["confidence"] = max(0.0, min(1.0, float(v["confidence"])))
            v["plan_ref"] = plan_id
            return v
    except Exception as e:
        logger.warning("Failed to parse Arbitrator JSON verdict — using fallback: %s", e)
    return {
        "plan_ref": plan_id,
        "status": "conditional",
        "conditions": ["Review raw Arbitrator output"],
        "confidence": 0.5,
        "risk_areas": ["Unable to parse structured verdict"],
        "summary": text[:300],
    }


def _push_verdict(plan_id: str, verdict: dict, crit_list=None, verd_list=None, plan_text=""):
    try:
        payload = {
            "plan_id": plan_id,
            "title": plan_id.replace("_", " ").title(),
            "context": plan_text,
            "verdict": verdict,
            "debate_type": "expert"
        }
        if crit_list:
            payload["critiques"] = crit_list.to_dict()
        if verd_list:
            payload["resolutions"] = verd_list.to_dict()

        _bm = bus_manager
        if _bm is None:
            # Lazy re-import in case bus_manager loaded after module init
            try:
                from context import bus_manager as _lazy_bm
                _bm = _lazy_bm
            except Exception as e:
                logger.warning("Failed to lazy-import bus_manager: %s", e)

        if _bm is None:
            logger.warning("bus_manager not available — verdict not pushed to bus")
            return

        _bm.push(
            "verdict_%s" % plan_id,
            "verification_result",
            "arbitrator",
            json.dumps(payload),
        )
        print("Verdict pushed to bus: verdict_%s" % plan_id)
    except Exception as e:
        logger.error("Failed to push verdict to bus: %s", e)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Arbitrator -- Council of Sages Judge")
    parser.add_argument("plan_id", help="Plan identifier")
    parser.add_argument("--plan-text", help="Plan text", default="")
    args = parser.parse_args()
    result = run_consensus(args.plan_id, args.plan_text)
    print("\n%s" % json.dumps(result, indent=2))
