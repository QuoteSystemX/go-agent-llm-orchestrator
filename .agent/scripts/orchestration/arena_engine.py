#!/usr/bin/env python3
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

from lib.common import load_json_safe
from lib.llm_client import query_llm

ARENA_REPORTS_DIR = REPO_ROOT / ".agent" / "reports" / "arena"

DEFAULT_MODELS = [
    "qwen3-coder:30b",
    "codestral:22b",
    "qwen2.5-coder:14b"
]

JUDGE_MODEL = "qwen3-coder:30b"

def run_duel(prompt, models=None):
    """Runs a duel between models for a given prompt."""
    if models is None:
        models = DEFAULT_MODELS
        
    ARENA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"🏟️ Starting True Arena Duel...")
    print(f"  Prompt: {prompt[:100]}...")
    
    responses = []
    
    for model in models:
        print(f"  🤖 Model: {model}...", end="", flush=True)
        response, stats = query_llm(prompt, model)
        responses.append({
            "model": model,
            "response": response,
            "stats": stats
        })
        print(" DONE")
        
    print(f"  ⚖️ Judging with {JUDGE_MODEL}...")
    
    judge_prompt = f"""You are the Multi-Agent Judge. 
We have a prompt and multiple responses from different models.
Your task: 
1. Analyze the responses.
2. Find common ground (consensus).
3. Identify unique insights from each.
4. Synthesize the FINAL BEST ANSWER.

PROMPT:
{prompt}

RESPONSES:
"""
    for i, r in enumerate(responses):
        judge_prompt += f"\n--- RESPONSE {i+1} (Model: {r['model']}) ---\n{r['response']}\n"
        
    final_answer, judge_stats = query_llm(judge_prompt, JUDGE_MODEL)
    
    report_path = save_arena_report(prompt, models, responses, final_answer)
    
    print("\n" + "="*40)
    print(f"📊 Duel Complete!")
    print(f"   Final Recommendation Generated.")
    print(f"   Report: {report_path}")
    print("="*40)
    
    print("\nFINAL SYNTHESIS:")
    print(final_answer)

def save_arena_report(prompt, models, responses, final_answer):
    """Saves the arena results to markdown."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_md = ARENA_REPORTS_DIR / f"duel_{timestamp}.md"
    
    with open(report_md, "w") as f:
        f.write(f"# True Arena Duel Report\n\n")
        f.write(f"- **Date**: {datetime.now().isoformat()}\n")
        f.write(f"- **Models Participated**: {', '.join(models)}\n\n")
        
        f.write(f"## Original Prompt\n\n> {prompt}\n\n")
        
        f.write("## Synthesis (Consensus)\n\n")
        f.write(final_answer + "\n\n")
        
        f.write("## Individual Responses\n\n")
        for r in responses:
            f.write(f"### Model: `{r['model']}`\n")
            f.write(f"- **Latency**: {r['stats'].get('elapsed_seconds', 0):.2f}s\n")
            f.write(f"- **TPS**: {r['stats'].get('tps', 0):.0f}\n")
            f.write("\n#### Response\n")
            f.write("```\n" + r['response'] + "\n```\n\n")
            
    return report_md

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="True Arena - Multi-Model Duel Engine")
    parser.add_argument("prompt", help="Prompt to duel over")
    parser.add_argument("--models", nargs="+", help="Models to include in duel")
    args = parser.parse_args()
    
    run_duel(args.prompt, args.models)
