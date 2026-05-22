#!/usr/bin/env python3
import json
import sys
import os
import re
import argparse
from pathlib import Path
from datetime import datetime

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

from lib.common import load_json_safe, save_json_atomic
from lib.llm_client import query_llm
from models.model_router import route

GOLDEN_TASKS_PATH = REPO_ROOT / ".agent" / "scripts" / "qa" / "golden_tasks.json"
REPORTS_DIR = REPO_ROOT / ".agent" / "reports" / "intelligence"

def run_benchmark():
    """Runs the intelligence regression tests."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    data = load_json_safe(GOLDEN_TASKS_PATH)
    tasks = data.get("tasks", [])
    
    if not tasks:
        print("❌ No tasks found in golden_tasks.json")
        return
        
    parser = argparse.ArgumentParser(description="Autonomous Intelligence Benchmark")
    parser.add_argument("--model", type=str, help="Override model for all tasks")
    args = parser.parse_args()
    
    print(f"🚀 Starting Intelligence Benchmark ({len(tasks)} tasks)...")
    if args.model:
        print(f"  🎯 Forced Model: {args.model}")
    
    results = []
    total_score = 0
    
    for task in tasks:
        print(f"  📝 Testing: {task['name']}...", end="", flush=True)
        
        # Determine model to use via router
        model = args.model if args.model else route(task['prompt']).model_id
        
        response, stats = query_llm(task['prompt'], model)
        
        # Grading
        score, feedback = grade_response(response, task['criteria'])
        
        result = {
            "id": task['id'],
            "name": task['name'],
            "model": model,
            "score": score,
            "passed": score >= task['criteria'].get("min_score", 0.7),
            "feedback": feedback,
            "stats": stats,
            "response": response
        }
        results.append(result)
        total_score += score
        
        status_icon = "✅" if result["passed"] else "❌"
        print(f" {status_icon} (Score: {score:.2f})")

    avg_score = total_score / len(tasks)
    report_path = save_report(results, avg_score)
    
    print("\n" + "="*40)
    print(f"📊 Benchmark Complete!")
    print(f"   Average Score: {avg_score:.2f}")
    print(f"   Report: {report_path}")
    print("="*40)
    
    if avg_score < 0.7:
        print("⚠️  CRITICAL: Intelligence regression detected!")
        sys.exit(1)

def grade_response(response, criteria):
    """Grades a response based on keywords and rules."""
    score = 0.0
    feedback = []
    
    if not response or "❌ Error" in response:
        return 0.0, ["Request failed"]
        
    # 1. Keywords (Positive)
    keywords = criteria.get("keywords", [])
    if keywords:
        found_kw = [kw for kw in keywords if kw.lower() in response.lower()]
        kw_score = len(found_kw) / len(keywords)
        score += kw_score * 0.5
        feedback.append(f"Found {len(found_kw)}/{len(keywords)} keywords")
        
    # 2. Negative Keywords
    neg_keywords = criteria.get("negative_keywords", [])
    if neg_keywords:
        found_neg = [kw for kw in neg_keywords if kw.lower() in response.lower()]
        if found_neg:
            score -= 0.5 * (len(found_neg) / len(neg_keywords))
            feedback.append(f"❌ FOUND FORBIDDEN KEYWORDS: {found_neg}")
        else:
            score += 0.2
            feedback.append("Passed safety check (no forbidden keywords)")
            
    # 3. Regex matches
    regex_patterns = criteria.get("regex", [])
    if regex_patterns:
        match_count = 0
        for pattern in regex_patterns:
            if re.search(pattern, response, re.MULTILINE):
                match_count += 1
        regex_score = match_count / len(regex_patterns)
        score += regex_score * 0.3
        feedback.append(f"Regex matches: {match_count}/{len(regex_patterns)}")

    # Normalize score
    final_score = max(0.0, min(1.0, score))
    return final_score, feedback

def save_report(results, avg_score):
    """Saves the results to a markdown report and JSON."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_json = REPORTS_DIR / f"report_{timestamp}.json"
    report_md = REPORTS_DIR / f"report_{timestamp}.md"
    
    save_json_atomic(report_json, {
        "timestamp": datetime.now().isoformat(),
        "average_score": avg_score,
        "results": results
    })
    
    with open(report_md, "w") as f:
        f.write(f"# Intelligence Benchmark Report\n\n")
        f.write(f"- **Date**: {datetime.now().isoformat()}\n")
        f.write(f"- **Average Score**: {avg_score:.2f}\n\n")
        
        f.write("## Task Summary\n\n")
        f.write("| Task ID | Name | Model | Score | Status |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for r in results:
            status = "✅ PASS" if r["passed"] else "❌ FAIL"
            f.write(f"| {r['id']} | {r['name']} | {r['model']} | {r['score']:.2f} | {status} |\n")
            
        f.write("\n## Detailed Findings\n\n")
        for r in results:
            f.write(f"### {r['name']} ({r['id']})\n")
            f.write(f"- **Model**: `{r['model']}`\n")
            f.write(f"- **Score**: {r['score']:.2f}\n")
            f.write(f"- **Feedback**: {', '.join(r['feedback'])}\n")
            f.write("\n#### Response\n")
            f.write("```\n" + r['response'][:1000] + "\n```\n\n")
            
    return report_md

if __name__ == "__main__":
    run_benchmark()
