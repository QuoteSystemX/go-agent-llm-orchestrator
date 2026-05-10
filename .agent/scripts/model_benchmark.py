#!/usr/bin/env python3
"""Benchmark Ollama models for speed and quality.

Usage:
    python3 model_benchmark.py
    python3 model_benchmark.py --quick  # L1 only
    python3 model_benchmark.py --model qwen3.6:27b
"""

import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OLLAMA_URL = "http://172.31.0.1:11434/api/generate"

@dataclass
class BenchmarkResult:
    model: str
    tier: str
    task: str
    time_seconds: float
    tokens_per_second: float = 0.0
    success: bool = True
    error: Optional[str] = None
    quality_score: int = 0  # 1-5
    output_preview: str = ""


def is_wsl() -> bool:
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except:
        return False


def query_ollama(prompt: str, model: str, timeout: int = 120) -> tuple[str, float]:
    """Send prompt to Ollama, return (response, time_taken)."""
    req_data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 4096}
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(req_data).encode(),
        headers={"Content-Type": "application/json"}
    )
    
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
            elapsed = time.time() - start
            response = result.get("response", "")
            
            # Estimate tokens (rough: ~4 chars per token)
            chars = len(response)
            tokens = chars // 4
            tps = tokens / elapsed if elapsed > 0 else 0
            
            return response, elapsed, tps
    except Exception as e:
        return f"ERROR: {e}", time.time() - start, 0


def gather_context(task_type: str) -> str:
    """Gather relevant context data for task."""
    scripts_dir = REPO_ROOT / ".agent" / "scripts"
    
    if task_type == "simple":
        # Count lines
        import subprocess
        result = subprocess.run(
            ["find", str(scripts_dir), "-name", "*.py", "-exec", "wc", "-l", "{}", "+"],
            capture_output=True, text=True, timeout=30
        )
        return f"Line counts in scripts:\n{result.stdout[:2000]}"
    
    elif task_type == "medium":
        # Find TODOs
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "TODO\\|FIXME", str(scripts_dir), "--include=*.py"],
            capture_output=True, text=True, timeout=30
        )
        return f"TODO/FIXME in scripts:\n{result.stdout[:3000]}"
    
    elif task_type == "complex":
        # Analyze tech debt
        import subprocess
        todos = subprocess.run(
            ["grep", "-rn", "TODO\\|FIXME", str(scripts_dir), "--include=*.py"],
            capture_output=True, text=True, timeout=30
        )
        lib_usage = subprocess.run(
            ["grep", "-l", "from lib.common", str(scripts_dir), "--include=*.py"],
            capture_output=True, text=True, timeout=30
        )
        return f"""Technical debt analysis context:

TODO/FIXME markers:
{todos.stdout[:2000] if todos.stdout else 'None found'}

Scripts using lib.common:
{lib_usage.stdout[:1000] if lib_usage.stdout else 'None found'}
"""
    
    elif task_type == "analysis":
        # Compare configs
        router = (REPO_ROOT / ".agent" / "config" / "router_rules.json").read_text()
        adaptive = (REPO_ROOT / ".agent" / "rules" / "ADAPTIVE_ROUTING.md").read_text()
        return f"""Config comparison context:

router_rules.json (first 3000 chars):
{router[:3000]}

ADAPTIVE_ROUTING.md (thresholds section):
{adaptive[adaptive.find('Complexity Assessment'):adaptive.find('Complexity Assessment')+1000] if 'Complexity Assessment' in adaptive else adaptive[:1000]}
"""
    
    return ""


def score_quality(response: str, task: str) -> int:
    """Score response quality 1-5."""
    if response.startswith("ERROR"):
        return 0
    
    # Basic quality heuristics
    score = 3  # default
    
    # Longer responses usually more detailed
    if len(response) > 1000:
        score += 1
    
    # Contains actionable items
    if any(word in response.lower() for word in ["file:", "script:", "recommend", "fix", "issue"]):
        score += 1
    
    # Has structured output
    if any(char in response for char in ["1.", "2.", "- ", "* ", "```"]):
        score += 1
    
    return min(score, 5)


def run_benchmark(model: str, tier: str, task: str, quick: bool = False) -> BenchmarkResult:
    """Run single benchmark."""
    print(f"  Testing {model} on [{tier}] {task}...", end=" ", flush=True)
    
    context = gather_context(task)
    prompt = f"""Task: {task}

Context data:
{context}

Provide a concise response with:
1. Key findings
2. Specific recommendations
3. Priority (HIGH/MEDIUM/LOW)

Keep response under 500 words."""
    
    if quick:
        prompt = prompt[:500]  # Truncate for quick test
    
    response, elapsed, tps = query_ollama(prompt, model, timeout=180 if not quick else 60)
    quality = score_quality(response, task) if not response.startswith("ERROR") else 0
    
    success = not response.startswith("ERROR")
    
    result = BenchmarkResult(
        model=model,
        tier=tier,
        task=task,
        time_seconds=elapsed,
        tokens_per_second=tps,
        success=success,
        error=response if not success else None,
        quality_score=quality,
        output_preview=response[:200] if success else ""
    )
    
    status = "✅" if success else "❌"
    print(f"{status} {elapsed:.1f}s ({(tps):.0f} tok/s, quality: {quality}/5)")
    
    return result


def run_full_benchmark(quick: bool = False):
    """Run full benchmark across all models and tasks."""
    
    print("="*60)
    print("🚀 OLLAMA MODEL BENCHMARK")
    print("="*60)
    print(f"WSL: {is_wsl()}")
    print(f"Ollama: {OLLAMA_URL}")
    print(f"Mode: {'QUICK' if quick else 'FULL'}")
    print("="*60)
    print()
    
    # Load models from router config
    rules = json.loads((REPO_ROOT / ".agent" / "config" / "router_rules.json").read_text())
    ollama_models = rules["models"]["ollama"]
    
    tasks = ["simple", "medium", "complex", "analysis"]
    
    results: List[BenchmarkResult] = []
    
    # Run benchmarks
    print("📊 Running benchmarks...\n")
    
    for tier in ["L1", "L2", "L3", "L4"]:
        if tier not in ollama_models:
            continue
        
        model = ollama_models[tier]
        print(f"\n🔹 {tier} Tier: {model}")
        print("-"*40)
        
        for task in tasks:
            if quick and task != "medium":
                continue
            
            result = run_benchmark(model, tier, task, quick)
            results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("📊 BENCHMARK RESULTS SUMMARY")
    print("="*60)
    
    # Group by tier
    by_tier = {}
    for r in results:
        if r.tier not in by_tier:
            by_tier[r.tier] = []
        by_tier[r.tier].append(r)
    
    for tier in sorted(by_tier.keys()):
        tier_results = by_tier[tier]
        avg_time = sum(r.time_seconds for r in tier_results) / len(tier_results)
        avg_tps = sum(r.tokens_per_second for r in tier_results) / len(tier_results)
        avg_quality = sum(r.quality_score for r in tier_results) / len(tier_results)
        success_rate = sum(1 for r in tier_results if r.success) / len(tier_results) * 100
        
        model = tier_results[0].model
        print(f"\n{tier} ({model}):")
        print(f"  Avg time: {avg_time:.1f}s")
        print(f"  Avg speed: {avg_tps:.0f} tok/s")
        print(f"  Avg quality: {avg_quality:.1f}/5")
        print(f"  Success rate: {success_rate:.0f}%")
    
    # Best per tier
    print("\n" + "="*60)
    print("🏆 RECOMMENDED MODELS BY TIER")
    print("="*60)
    
    for tier in sorted(by_tier.keys()):
        tier_results = by_tier[tier]
        # Score = speed * quality / time
        scored = [(r, r.tokens_per_second * r.quality_score / max(r.time_seconds, 0.1)) for r in tier_results]
        best = max(scored, key=lambda x: x[1])[0]
        print(f"{tier}: {best.model} ({best.time_seconds:.1f}s, quality: {best.quality_score}/5)")
    
    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "wsI_detected": is_wsl(),
        "quick_mode": quick,
        "results": [
            {
                "model": r.model,
                "tier": r.tier,
                "task": r.task,
                "time": r.time_seconds,
                "tps": r.tokens_per_second,
                "quality": r.quality_score,
                "success": r.success
            }
            for r in results
        ]
    }
    
    output_path = REPO_ROOT / ".agent" / "bus" / "benchmark_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    print(f"\n✅ Results saved to {output_path}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark Ollama models")
    parser.add_argument("--quick", action="store_true", help="Quick benchmark (L1 only, truncated prompts)")
    parser.add_argument("--model", help="Test single model only")
    parser.add_argument("--task", default="medium", help="Task to test")
    
    args = parser.parse_args()
    
    if args.model:
        # Single model test
        print(f"Testing single model: {args.model}")
        result = run_benchmark(args.model, "L?", args.task)
        print(f"\nResult: {result.time_seconds:.1f}s, {result.tokens_per_second:.0f} tok/s, quality: {result.quality_score}/5")
    else:
        run_full_benchmark(quick=args.quick)
