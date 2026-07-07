#!/usr/bin/env python3
"""
Tough Auditor — Adversarial LLM-powered Git Diff Auditor & Gatekeeper.
Evaluates code changes with extreme criticism and severity, logs agent quality scores,
and warns or blocks if the quality is suboptimal.
"""

import sys
from pathlib import Path

# Setup unconditional path resolution
SCRIPTS_DIR = Path(__file__).resolve().parents[1]  # .agent/scripts
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

# Always add domain subfolders to sys.path so direct imports work unconditionally
for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
    d_path = str(SCRIPTS_DIR / domain)
    if d_path not in sys.path:
        sys.path.append(d_path)

import json
import os
import re
import subprocess
import urllib.request
from typing import Any, Dict, List, Tuple

try:
    from lib.paths import REPO_ROOT
    from lib.common import discover_ollama_url, discover_broker_url
    import agent_scorer
except ImportError:
    # Manual fallback just in case
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    from lib.common import discover_ollama_url, discover_broker_url
    import agent_scorer

OLLAMA_BASE_URL = discover_ollama_url()
BROKER_URL = discover_broker_url()

def get_git_diff() -> str:
    """Gets both staged and unstaged changes for a full session review."""
    try:
        # Check staged first
        staged = subprocess.check_output(["git", "diff", "--cached"], cwd=REPO_ROOT).decode("utf-8")
        # Check unstaged
        unstaged = subprocess.check_output(["git", "diff"], cwd=REPO_ROOT).decode("utf-8")
        
        diff = ""
        if staged.strip():
            diff += "=== STAGED CHANGES ===\n" + staged + "\n"
        if unstaged.strip():
            diff += "=== UNSTAGED CHANGES ===\n" + unstaged + "\n"
        return diff
    except Exception as e:
        print(f"⚠️ Error getting git diff: {e}")
        return ""

def get_available_models() -> List[str]:
    """Fetch available models from the broker."""
    url = f"{BROKER_URL}/v1/models"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read())
            return [m.get("id") for m in data.get("data", []) if m.get("id")]
    except Exception:
        return []

def select_model(available_models: List[str]) -> str:
    """Select the best available model for auditing, with fallbacks."""
    # Preferred order
    pref = [
        "qwen3-coder:30b",
        "qwen2.5-coder:14b",
        "qwen2.5-coder:32b",
        "codestral:22b",
        "gemma3:12b",
        "deepseek-r1:14b",
        "qwen2.5-coder:latest",
        "qwen2.5-coder"
    ]
    for model in pref:
        # Match base name or exact name
        for avail in available_models:
            if avail.lower().startswith(model.lower()) or model.lower() in avail.lower():
                return avail
    if available_models:
        return available_models[0]
    return "qwen2.5-coder:14b"  # Default fallback if offline

def query_llm_auditor(diff: str, model: str) -> Tuple[float, str, List[str]]:
    """Query the local LLM with the adversarial Red-Team Auditor prompt."""
    url = f"{BROKER_URL}/v1/chat/completions"
    
    system_prompt = (
        "You are the Adversarial QA, Security, and Red-Team Code Auditor. "
        "Your task is to evaluate the provided Git Diff of an agent's changes with extreme criticism and severity. "
        "Assign an objective, tough quality score from 1.0 to 5.0 and provide a critique with actionable feedback. "
        "Be extremely harsh. Deduct points heavily for:\n"
        "- Missing or inadequate unit/integration test coverage.\n"
        "- Sloppy or missing error handling (e.g., bare excepts, ignored errors, silenced panics).\n"
        "- Code smells, logic gaps, race conditions, or unoptimized complexity.\n"
        "- Security vulnerabilities or secrets leaks (even inside comments/configs).\n"
        "- Missing or inadequate code comments or documentation.\n"
        "- Clean code issues (dirty formatting, trailing whitespace, or temporary garbage files).\n\n"
        "Score guidelines:\n"
        "- 5.0: Flawless, highly optimized, secure, fully tested, documented masterpiece. (Rarely given)\n"
        "- 4.0 - 4.8: High quality, fully functional and clean, minor suggestions.\n"
        "- 3.5 - 3.9: Standard acceptable code but lacks robust tests or detailed comments.\n"
        "- 1.0 - 3.4: Critical logic gaps, zero test coverage for complex logic, or bad safety/security issues. MUST BE BLOCKED.\n\n"
        "You MUST respond ONLY with a single valid JSON object. Do not include markdown code block formatting (no ```json). "
        "The JSON MUST have this exact schema:\n"
        "{\n"
        '  "score": <float>,\n'
        '  "critique": "A brief summary of your hard critique.",\n'
        '  "feedback": ["actionable point 1", "actionable point 2"]\n'
        "}"
    )

    prompt = f"Evaluate this staged/unstaged Git Diff:\n\n{diff}\n\nStrict JSON response only:"
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            choices = data.get("choices", [])
            response_text = ""
            if choices:
                response_text = choices[0].get("message", {}).get("content", "").strip()
            
            # Try to strip markdown fences if any
            if response_text.startswith("```"):
                response_text = re.sub(r"^```(?:json)?\n", "", response_text)
                response_text = re.sub(r"\n```$", "", response_text)
                
            try:
                parsed = json.loads(response_text)
                score = float(parsed.get("score", 4.0))
                critique = parsed.get("critique", "No critique provided.")
                feedback = parsed.get("feedback", [])
                return score, critique, feedback
            except Exception as parse_err:
                # Fallback parser using regex
                print(f"⚠️ Failed to parse LLM JSON: {parse_err}. Attempting regex recovery...")
                score_match = re.search(r'"score"\s*:\s*([0-9.]+)', response_text)
                score = float(score_match.group(1)) if score_match else 4.0
                critique_match = re.search(r'"critique"\s*:\s*"([^"]+)"', response_text)
                critique = critique_match.group(1) if critique_match else "Diff audited."
                feedback = re.findall(r'"([^"]+)"', response_text)
                if len(feedback) > 2:
                    feedback = feedback[2:] # Skip score and critique keys if matched
                return score, critique, feedback
    except Exception as e:
        print(f"⚠️ Error during LLM audit query: {e}")
        return 4.0, f"Auditor query failed: {e}", []

def audit_changes(agent_name: str, task_id: str) -> float:
    """Main audit execution. Evaluates diff, queries LLM, logs score, returns score."""
    print("🏟️ --- TOUGH AUDITOR ACTIVATED ---")
    
    diff = get_git_diff()
    if not diff.strip():
        print("ℹ️ No staged/unstaged code changes found. Logging perfect audit score.")
        agent_scorer.log_score(agent_name, task_id, 5.0, "Clean session, no code changes.")
        return 5.0
        
    models = get_available_models()
    if not models:
        print("⚠️ Ollama is offline or unavailable. Gracefully bypassing audit with neutral score (4.0).")
        agent_scorer.log_score(agent_name, task_id, 4.0, "Ollama offline. Bypassed with standard neutral score.")
        return 4.0
        
    selected = select_model(models)
    print(f"🤖 Selected Auditor Model: {selected}")
    print(f"⚖️ Running adversarial evaluation of the session's diff...")
    
    score, critique, feedback = query_llm_auditor(diff, selected)
    
    # Compile comment with critique and feedback points
    comments = f"{critique}"
    if feedback:
        comments += " Feedback: " + "; ".join(feedback)
        
    print(f"\n========================================")
    print(f"⚖️ AUDITOR VERDICT FOR @{agent_name}:")
    print(f"  - Score   : {score}/5.0")
    print(f"  - Critique: {critique}")
    if feedback:
        print(f"  - Feedback:")
        for point in feedback:
            print(f"    * {point}")
    print(f"========================================\n")
    
    agent_scorer.log_score(agent_name, task_id, score, comments)
    return score

if __name__ == "__main__":
    agent = sys.argv[1] if len(sys.argv) > 1 else "orchestrator"
    task = sys.argv[2] if len(sys.argv) > 2 else "session_task"
    audit_changes(agent, task)
