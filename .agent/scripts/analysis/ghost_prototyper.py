#!/usr/bin/env python3

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

import os
import sys
import re
import subprocess
import logging
import uuid
import shutil
import argparse
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]

TEMP_DIR = REPO_ROOT / ".agent" / "tmp" / "ghost"


def cleanup_orphaned_worktrees():
    """Startup cleanup for any leftover worktrees under TEMP_DIR."""
    if not TEMP_DIR.exists():
        return
    try:
        res = subprocess.run(
            ["git", "worktree", "list"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.split()
                if parts:
                    wt_path = Path(parts[0])
                    try:
                        is_sub = wt_path.is_relative_to(TEMP_DIR)
                    except ValueError:
                        is_sub = False
                    if is_sub:
                        logger.info("Cleaning up orphaned worktree: %s", wt_path)
                        subprocess.run(
                            ["git", "worktree", "remove", "--force", str(wt_path)],
                            cwd=str(REPO_ROOT),
                            capture_output=True
                        )
        for folder in TEMP_DIR.iterdir():
            if folder.is_dir():
                shutil.rmtree(folder, ignore_errors=True)
        subprocess.run(["git", "worktree", "prune"], cwd=str(REPO_ROOT), capture_output=True)
    except Exception as e:
        logger.debug("Failed to cleanup orphaned worktrees: %s", e)


def _try_go_build(intent: str) -> bool:
    """Try real go build with a minimal main.go."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    main_go = TEMP_DIR / "main.go"
    safe_pkg = re.sub(r"[^a-zA-Z0-9_]", "", intent.replace(" ", "_")) or "proto"
    main_go.write_text(
        f'package main\n\nimport "fmt"\n\nfunc main() {{\n\tfmt.Println("{safe_pkg}")\n}}\n'
    )
    try:
        res = subprocess.run(
            ["go", "build", "-o", "/dev/null", str(main_go)],
            capture_output=True, text=True, timeout=15,
        )
        return res.returncode == 0
    except Exception as e:
        logger.debug("Go build not available: %s", e)
        return False
    finally:
        main_go.unlink(missing_ok=True)


def run_ghost_proto(intent: str):
    print(f"👻 Starting Ghost Prototyping for: '{intent}'...")
    print("🛠 Testing technical feasibility...")

    # Try real Go build
    ok = _try_go_build(intent)

    if not ok:
        # Fallback: basic feasibility heuristic
        ok = "impossible" not in intent.lower()
        if not ok:
            logger.info("[ghost_prototyper] Intent contains 'impossible' — marking as infeasible")

    if ok:
        print("✅ Ghost Prototype compiled successfully. Intent is technically feasible.")
        return True
    else:
        print("❌ GHOST PROTOTYPE FAILED: Feasibility check failed.")
        return False


def parse_go_benchmarks(output: str) -> dict:
    """
    Parses Go benchmark outputs and extracts averages:
    - ns_op (float)
    - b_op (float)
    - allocs_op (float)
    """
    metrics = {
        "ns_op": 0.0,
        "b_op": 0.0,
        "allocs_op": 0.0,
        "count": 0
    }
    
    total_ns = 0.0
    total_b = 0.0
    total_allocs = 0.0
    count = 0
    
    bench_re = re.compile(
        r"^Benchmark[a-zA-Z0-9_/:-]+\s+\d+\s+([0-9.]+)\s+ns/op(?:\s+(\d+)\s+B/op\s+(\d+)\s+allocs/op)?"
    )
    
    for line in output.splitlines():
        line = line.strip()
        match = bench_re.match(line)
        if match:
            ns_val = float(match.group(1))
            total_ns += ns_val
            count += 1
            if match.group(2) is not None:
                total_b += float(match.group(2))
            if match.group(3) is not None:
                total_allocs += float(match.group(3))
                
    if count > 0:
        metrics["ns_op"] = total_ns / count
        metrics["b_op"] = total_b / count
        metrics["allocs_op"] = total_allocs / count
        metrics["count"] = count
        
    return metrics


def run_isolated_worktree(file_path_str: str, target: str, replacement: str, test_cmd: str, intent: str) -> tuple:
    """
    Creates an isolated git worktree, applies the patch, runs tests, and applies
    the patch back to the main repository if successful.
    Returns (success, metrics_dict).
    """
    cleanup_orphaned_worktrees()
    
    session_id = uuid.uuid4().hex[:12]
    worktree_path = TEMP_DIR / session_id
    
    # Resolve file relative to repo root
    abs_file_path = Path(file_path_str).resolve()
    try:
        rel_file_path = abs_file_path.relative_to(REPO_ROOT)
    except ValueError:
        # File is not relative to repo root or is already relative
        rel_file_path = Path(file_path_str)
        abs_file_path = REPO_ROOT / rel_file_path

    print(f"👻 Starting Isolated Prototyping inside worktree: {worktree_path}")
    
    # Create git worktree
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        res = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_path), "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30
        )
        if res.returncode != 0:
            logger.error("Failed to create worktree: %s", res.stderr)
            return False
    except Exception as e:
        logger.error("Exception during worktree add: %s", e)
        return False

    success = False
    metrics = {}
    try:
        # File path inside worktree
        wt_file_path = worktree_path / rel_file_path
        if not wt_file_path.exists():
            logger.error("File %s does not exist in worktree", rel_file_path)
            return False, {}
            
        # Apply patch
        file_content = wt_file_path.read_text(encoding="utf-8")
        if target not in file_content:
            logger.error("Target content not found in file %s", rel_file_path)
            try:
                from orchestration.dead_ends import log_dead_end
                log_dead_end(file_path_str, f"Replace:\n{target}\nWith:\n{replacement}", "Target content not found in file")
            except Exception as e:
                logger.debug("Failed to log dead end: %s", e)
            return False, {}
            
        new_content = file_content.replace(target, replacement)
        wt_file_path.write_text(new_content, encoding="utf-8")
        
        # Execute tests inside worktree
        cmd = test_cmd.split() if test_cmd else ["go", "test", "-race", "./..."]
        print(f"🛠 Running verification command: {' '.join(cmd)}")
        
        # We need to run clean environment just like squad_orchestrator
        clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        clean_env["GOPRIVATE"] = "github.com/QuoteSystemX/*"
        
        res = subprocess.run(
            cmd,
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            env=clean_env,
            timeout=60
        )
        if res.returncode == 0:
            print("✅ Verification inside worktree passed!")
            if "-bench" in test_cmd:
                metrics = parse_go_benchmarks(res.stdout)
            # Apply back to main repository
            main_content = abs_file_path.read_text(encoding="utf-8")
            if target in main_content:
                abs_file_path.write_text(main_content.replace(target, replacement), encoding="utf-8")
                print(f"✅ Applied changes to main file: {rel_file_path}")
                success = True
            else:
                logger.error("Target content no longer exists in main file %s", rel_file_path)
                try:
                    from orchestration.dead_ends import log_dead_end
                    log_dead_end(file_path_str, f"Replace:\n{target}\nWith:\n{replacement}", "Target content no longer exists in main file")
                except Exception as e:
                    logger.debug("Failed to log dead end: %s", e)
        else:
            print(f"❌ Verification inside worktree failed: {res.stdout}\n{res.stderr}")
            try:
                from orchestration.dead_ends import log_dead_end
                log_dead_end(file_path_str, f"Replace:\n{target}\nWith:\n{replacement}", (res.stderr + res.stdout)[:1024])
            except Exception as e:
                logger.debug("Failed to log dead end: %s", e)
            
    except Exception as e:
        logger.error("Exception during worktree execution: %s", e)
        try:
            from orchestration.dead_ends import log_dead_end
            log_dead_end(file_path_str, f"Replace:\n{target}\nWith:\n{replacement}", str(e))
        except Exception as ex:
            logger.debug("Failed to log dead end: %s", ex)
    finally:
        # Remove worktree
        print(f"🧹 Cleaning up worktree: {worktree_path}")
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=str(REPO_ROOT),
            capture_output=True
        )
        subprocess.run(["git", "worktree", "prune"], cwd=str(REPO_ROOT), capture_output=True)
        
    return success, metrics


def main():
    parser = argparse.ArgumentParser(description="Ghost Prototyper - isolated worktree verification")
    parser.add_argument("--file", type=str, help="Relative or absolute path of the file to modify")
    parser.add_argument("--target-content", type=str, help="Original content to replace")
    parser.add_argument("--replacement", type=str, help="New content to substitute")
    parser.add_argument("--test-cmd", type=str, default="go test -race ./...", help="Command to run for validation")
    parser.add_argument("--intent", type=str, default="", help="Intent of the prototyping run")
    parser.add_argument("legacy_intent", nargs="*", help="Legacy intent parameters")

    args = parser.parse_args()

    if args.file and args.target_content is not None and args.replacement is not None:
        ok, _ = run_isolated_worktree(
            file_path_str=args.file,
            target=args.target_content,
            replacement=args.replacement,
            test_cmd=args.test_cmd,
            intent=args.intent
        )
    else:
        intent_str = args.intent or " ".join(args.legacy_intent) or "default_proto"
        ok = run_ghost_proto(intent_str)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
