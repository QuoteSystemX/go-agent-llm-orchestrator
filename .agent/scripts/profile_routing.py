#!/usr/bin/env python3
"""Profiling script for L1 and L2 routing performance."""

import time
import json
import sys
import subprocess
import os

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def measure_step(name: str, func):
    """Measure execution time of a step."""
    start = time.perf_counter()
    result = func()
    elapsed = (time.perf_counter() - start) * 1000
    print(f"  ⏱  {name}: {elapsed:.1f}ms")
    return result, elapsed

def profile_task(task_desc: str, tier: str):
    """Profile a single task through the full pipeline."""
    print(f"\n{'='*60}")
    print(f"📊 Profiling {tier}: \"{task_desc[:50]}...\"")
    print(f"{'='*60}")
    
    total_start = time.perf_counter()
    step_times = {}
    
    # Step 1: Model Router
    def call_router():
        result = subprocess.run(
            [sys.executable, "model_router.py", task_desc, "--json"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return result.stdout
    
    router_output, t = measure_step("model_router.py", call_router)
    step_times["router"] = t
    
    try:
        router_data = json.loads(router_output)
        tier_result = router_data.get("tier", "?")
        model = router_data.get("model_id", "?")
        provider = router_data.get("provider", "?")
    except:
        tier_result = "?"
        model = "?"
        provider = "?"
        router_data = {}

    model_time = "?"
    model_tps = "?"
    rank_score = "?"

    # Try to parse model stats from router's human-readable output
    for line in router_output.split('\n'):
        for key, pattern in [("time", "time"), ("tps", "tps"), ("rank", "rank")]:
            if pattern in line.lower() and any(c.isdigit() for c in line):
                try:
                    val = ''.join(filter(lambda x: x.isdigit() or x == '.', line.split(':')[-1].strip()))
                    if val:
                        if key == "time":
                            model_time = val + "s"
                        elif key == "tps":
                            model_tps = val + " tok/s"
                        elif key == "rank":
                            rank_score = val
                except:
                    pass
    
    # Step 2: Health Check
    def health_check():
        result = subprocess.run(
            [sys.executable, "status_report.py"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return result.returncode
    
    _, t = measure_step("status_report.py", health_check)
    step_times["health"] = t
    
    # Step 3: Conflict Resolver
    def conflict_check():
        result = subprocess.run(
            [sys.executable, "conflict_resolver.py"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return result.returncode
    
    _, t = measure_step("conflict_resolver.py", conflict_check)
    step_times["conflict"] = t
    
    # Step 4: Ollama availability check
    def ollama_check():
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "2", "http://localhost:11434/api/tags"],
                capture_output=True, text=True, timeout=3
            )
            return result.returncode == 0 and "models" in result.stdout
        except:
            return False
    
    def ollama_pull_check():
        result = subprocess.run(
            [sys.executable, "model_router.py", task_desc],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return result.stdout
    
    _, t = measure_step("Ollama availability", ollama_check)
    step_times["ollama_check"] = t
    
    # Step 5: Actual model call (if we were to run it)
    # We'll just measure the overhead of building the prompt
    def prompt_prep():
        return f"[{tier}] {task_desc} → model={model}, provider={provider}"
    
    _, t = measure_step("prompt preparation", prompt_prep)
    step_times["prompt_prep"] = t
    
    # Total time
    total_ms = (time.perf_counter() - total_start) * 1000
    
    print(f"\n📈 Summary for {tier}:")
    print(f"  - Router decided: {tier_result} / {model} / {provider}")
    print(f"  - Model speed: {router_data.get('avg_time', '?')}s, {router_data.get('avg_tps', '?')} tok/s")
    print(f"  - Model score: {router_data.get('rank_score', '?')}")
    print(f"\n  Step timings:")
    for step, ms in sorted(step_times.items(), key=lambda x: -x[1]):
        print(f"    {step:15s}: {ms:6.1f}ms ({ms/total_ms*100:.1f}%)")
    print(f"  {'TOTAL':>15s}: {total_ms:6.1f}ms")
    
    return {
        "tier": tier,
        "task": task_desc,
        "decided_tier": tier_result,
        "model": model,
        "provider": provider,
        "model_time": router_data.get("avg_time"),
        "model_tps": router_data.get("avg_tps"),
        "rank_score": router_data.get("rank_score"),
        "total_ms": total_ms,
        "steps": step_times,
    }

def main():
    print("🚀 L1/L2 Performance Profiler")
    print("="*60)
    
    tasks = [
        ("list files in .agent directory", "L1"),
        ("check git status and recent commits", "L1"),
        ("fix typo in README.md", "L2"),
        ("add logging to status_report.py", "L2"),
    ]
    
    results = []
    for task, tier in tasks:
        r = profile_task(task, tier)
        results.append(r)
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 OVERALL SUMMARY")
    print(f"{'='*60}")
    print(f"\n{'Task':<45} {'Tier':<5} {'Routing':<6} {'Total':<8}")
    print("-"*70)
    for r in results:
        print(f"{r['task'][:44]:<45} {r['tier']:<5} {r['total_ms']-sum(r['steps'].values())+r['steps'].get('router',0):.0f}ms {r['total_ms']:.0f}ms")
    
    print(f"\nL1 average (routing overhead only):")
    l1_results = [r for r in results if r["tier"] == "L1"]
    if l1_results:
        avg = sum(r["total_ms"] for r in l1_results) / len(l1_results)
        print(f"  {avg:.1f}ms")
    
    print(f"\nL2 average (routing overhead only):")
    l2_results = [r for r in results if r["tier"] == "L2"]
    if l2_results:
        avg = sum(r["total_ms"] for r in l2_results) / len(l2_results)
        print(f"  {avg:.1f}ms")
    
    print(f"\n💡 For comparison:")
    print(f"  - L1 model (codestral:22b) inference: ~7400ms")
    print(f"  - L2 model (qwen2.5-coder:14b) inference: ~6400ms")
    print(f"  - Routing overhead: ~{sum(r['total_ms'] for r in results)/len(results):.0f}ms average")

if __name__ == "__main__":
    main()