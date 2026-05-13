#!/usr/bin/env python3
"""
Master Checklist Runner - Antigravity Kit
==========================================

Orchestrates all validation scripts in priority order.
Supports --fix for auto-correcting common issues.
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
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)


import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple, Optional

# Import from common lib
try:
    from lib.paths import WATCHDOG_RULES_PATH, CONFIG_DIR, RULES_DIR, REPO_ROOT
    from lib.common import load_json_safe, validate_json
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from lib.paths import WATCHDOG_RULES_PATH, CONFIG_DIR, RULES_DIR, REPO_ROOT
    from lib.common import load_json_safe, validate_json

# ANSI colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}\n")

def print_step(text: str):
    print(f"{Colors.BOLD}{Colors.BLUE}🔄 {text}{Colors.ENDC}")

def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")

def print_error(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

# Define priority-ordered checks
CORE_CHECKS = [
    ("Security Scan", ".agent/skills/vulnerability-scanner/scripts/security_scan.py", True),
    ("Lint Check", ".agent/skills/lint-and-validate/scripts/lint_runner.py", True),
    ("Schema Validation", ".agent/skills/database-design/scripts/schema_validator.py", False),
    ("Test Runner", ".agent/skills/testing-patterns/scripts/test_runner.py", False),
    ("UX Audit", ".agent/skills/frontend-design/scripts/ux_audit.py", False),
    ("SEO Check", ".agent/skills/seo-fundamentals/scripts/seo_checker.py", False),
    ("Dead Code Detector", ".agent/scripts/analysis/dead_code_detector.py", False),
    ("Resource Forecast", ".agent/scripts/analysis/resource_forecaster.py", False),
    ("Skill Discovery", ".agent/scripts/dev/skill_discovery.py", False),
    ("Incident Watcher", ".agent/scripts/health/incident_watcher.py", False),
]

def check_watchdog_schema() -> tuple[bool, str]:
    """Validate watchdog_rules.json against its schema."""
    schema_path = CONFIG_DIR / "watchdog_schema.json"
    if not WATCHDOG_RULES_PATH.exists():
        return True, "No watchdog rules found, skipping."
    
    rules = load_json_safe(WATCHDOG_RULES_PATH)
    return validate_json(rules, schema_path)

def check_script_coverage(domain: str, critical_only: Optional[List[str]] = None) -> tuple[bool, str]:
    """Check if scripts in a domain directory have corresponding tests."""
    script_dir = REPO_ROOT / ".agent" / "scripts" / domain
    test_dir = REPO_ROOT / ".agent" / "scripts" / "tests"
    
    if not script_dir.exists():
        return True, f"Domain {domain} not found, skipping."
        
    missing = []
    for script in script_dir.glob("*.py"):
        if script.name == "__init__.py": continue
        if critical_only and script.name not in critical_only: continue
        
        test_file = test_dir / f"test_{script.name}"
        if not test_file.exists():
            missing.append(script.name)
            
    if missing:
        return False, f"Missing tests in {domain}: {', '.join(missing)}"
    return True, f"All {domain} scripts have tests."

def run_fix():
    """Attempt to fix common issues."""
    print_header("🛠 AUTO-FIXING ISSUES")
    
    # 1. Ensure core directories exist
    from lib.paths import BUS_DIR, CONFIG_DIR, RULES_DIR, AGENT_DIR, SCRIPTS_DIR
    dirs = [
        AGENT_DIR, 
        BUS_DIR, 
        CONFIG_DIR, 
        RULES_DIR, 
        SCRIPTS_DIR,
        REPO_ROOT / ".agent/logs",
        REPO_ROOT / "wiki/archive/experience",
        REPO_ROOT / "tasks"
    ]
    for d in dirs:
        if not d.exists():
            print_step(f"Creating directory: {d}")
            d.mkdir(parents=True, exist_ok=True)
            print_success(f"Created {d}")

    # 2. Fix permissions for scripts
    print_step("Ensuring scripts are executable...")
    for script in SCRIPTS_DIR.glob("**/*.py"):
        try:
            current_mode = script.stat().st_mode
            script.chmod(current_mode | 0o111)
        except Exception as e:
            print_warning(f"Failed to set permissions for {script}: {e}")
    print_success("Script permissions checked.")

    # 3. Basic watchdog rules if missing or broken
    rules_valid = False
    if WATCHDOG_RULES_PATH.exists():
        rules = load_json_safe(WATCHDOG_RULES_PATH)
        if rules and "limits" in rules and "dangerous_operations" in rules:
            rules_valid = True
        else:
            print_warning("watchdog_rules.json is invalid or incomplete. Healing...")

    if not WATCHDOG_RULES_PATH.exists() or not rules_valid:
        print_step("Restoring default watchdog_rules.json")
        default_rules = {
            "limits": {
                "token_budget_per_task": 200000,
                "cost_limit_per_task_usd": 5.0
            },
            "dangerous_operations": {
                "commands": {
                    "block": ["rm -rf /", "mkfs", "dd if="],
                    "warn": ["rm -rf", "chmod -R 777"]
                },
                "files": {
                    "protected": [".env*", "id_rsa*", "*.pem"]
                }
            }
        }
        import json
        with open(WATCHDOG_RULES_PATH, 'w', encoding="utf-8") as f:
            json.dump(default_rules, f, indent=2)
        print_success("Healed watchdog rules.")
    
    # 4. Auto-update Visualization and Dashboard
    print_step("Updating Visualization and Dashboard...")
    try:
        import dev.visualize_deps; import sys; sys.modules['visualize_deps'] = sys.modules['dev.visualize_deps']; import dev.visualize_deps as visualize_deps
        import health.status_report; import sys; sys.modules['status_report'] = sys.modules['health.status_report']; import health.status_report as status_report
        import delivery.task_tracer; import sys; sys.modules['task_tracer'] = sys.modules['delivery.task_tracer']; import delivery.task_tracer as task_tracer
        import models.prompt_optimizer; import sys; sys.modules['prompt_optimizer'] = sys.modules['models.prompt_optimizer']; import models.prompt_optimizer as prompt_optimizer
        
        # Trace check: warning if changes exist but no task is active
        staged = task_tracer.get_staged_files()
        if staged and not task_tracer.find_active_task():
            print_warning("Changes detected but no active task found in tasks/.")
            
        visualize_deps.generate_mermaid()
        score, metrics = status_report.calculate_health()
        
        # Add cost metrics to dashboard (simplified for demo)
        opt_report = prompt_optimizer.analyze_telemetry()
        if "HIGH USAGE" in opt_report:
            score -= 10
            metrics["Cost Status"] = "⚠️ HIGH"
        else:
            metrics["Cost Status"] = "✅ OK"
            
        status_report.export_to_html(score, metrics)
        
        # Bridge Team: Sync knowledge to Obsidian and external agents
        print_step("Mirroring knowledge via Bridge Team...")
        try:
            import knowledge.obsidian_sync; import sys; sys.modules['obsidian_sync'] = sys.modules['knowledge.obsidian_sync']; import knowledge.obsidian_sync as obsidian_sync
            import delivery.sync_agents; import sys; sys.modules['sync_agents'] = sys.modules['delivery.sync_agents']; import delivery.sync_agents as sync_agents
            obsidian_sync.sync_to_obsidian()
            # sync_agents.run_sync() # Optional: heavy sync, maybe keep it manual or for releases
        except Exception as e:
            print_warning(f"Bridge Team sync failed: {e}")
        
        print_success("Visualization, Dashboard, Documentation, and Bridge Sync updated.")
    except Exception as e:
        print_warning(f"Failed to update visualization: {e}")

    print_success("Auto-fix complete.")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Antigravity Kit validation checklist")
    parser.add_argument("project", help="Project path to validate")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix simple issues")
    parser.add_argument("--url", help="URL for performance checks")
    
    args = parser.parse_args()
    
    if args.fix:
        run_fix()

    print_header("🚀 ANTIGRAVITY KIT - MASTER CHECKLIST")
    
    results = []
    overall_passed = True
    
    # Custom Check: Watchdog Schema
    print_step("Checking Watchdog Rules Schema")
    ok, msg = check_watchdog_schema()
    if ok:
        print_success(f"Watchdog Schema: {msg}")
        results.append({"name": "Watchdog Schema", "passed": True})
    else:
        print_error(f"Watchdog Schema: {msg}")
        results.append({"name": "Watchdog Schema", "passed": False})

    # Custom Check: Orchestration Coverage
    print_step("Checking Orchestration Logic Coverage")
    critical_orch = [
        "governance_gate.py", "agent_auctioneer.py", 
        "arbitrator.py", "hidden_war_room.py"
    ]
    ok, msg = check_script_coverage("orchestration", critical_only=critical_orch)
    if ok:
        print_success(f"Orchestration Coverage: {msg}")
        results.append({"name": "Orchestration Coverage", "passed": True})
    else:
        print_error(f"Orchestration Coverage: {msg}")
        results.append({"name": "Orchestration Coverage", "passed": False})
        overall_passed = False

    # Custom Check: Health Logic Coverage
    print_step("Checking Health Logic Coverage")
    critical_health = [
        "status_report.py", "policy_guardrail.py", "drift_detector.py", 
        "guardrail_monitor.py", "security_scan.py"
    ]
    ok, msg = check_script_coverage("health", critical_only=critical_health)
    if ok:
        print_success(f"Health Coverage: {msg}")
        results.append({"name": "Health Coverage", "passed": True})
    else:
        print_error(f"Health Coverage: {msg}")
        results.append({"name": "Health Coverage", "passed": False})
        overall_passed = False

    # Custom Check: Delivery Logic Coverage
    print_step("Checking Delivery Logic Coverage")
    critical_delivery = [
        "sync_agents.py", "task_tracer.py", 
        "rollback_task.py", "auto_preview.py"
    ]
    ok, msg = check_script_coverage("delivery", critical_only=critical_delivery)
    if ok:
        print_success(f"Delivery Coverage: {msg}")
        results.append({"name": "Delivery Coverage", "passed": True})
    else:
        print_error(f"Delivery Coverage: {msg}")
        results.append({"name": "Delivery Coverage", "passed": False})
        overall_passed = False

    # Custom Check: Resilience Logic Coverage
    print_step("Checking Resilience Logic Coverage")
    critical_resilience = [
        "chaos_monkey.py", "failure_correlator.py",
        "test_factory.py", "self_healer.py"
    ]
    # Search in multiple domains
    resilience_found = True
    for s in critical_resilience:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["chaos", "misc", "health", "dev", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            resilience_found = False
            print_error(f"Missing test for {s}")
    
    if resilience_found:
        print_success("Resilience Coverage: All critical resilience scripts have tests.")
        results.append({"name": "Resilience Coverage", "passed": True})
    else:
        results.append({"name": "Resilience Coverage", "passed": False})
        overall_passed = False

    # Custom Check: Knowledge Integrity Coverage
    print_step("Checking Knowledge Integrity Coverage")
    critical_knowledge = [
        "wiki_assembler.py", "output_bridge.py",
        "compile_rules.py", "doc_healer.py"
    ]
    ki_found = True
    for s in critical_knowledge:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["knowledge", "dev", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            ki_found = False
            print_error(f"Missing test for {s}")
    
    if ki_found:
        print_success("Knowledge Integrity: All critical documentation scripts have tests.")
        results.append({"name": "Knowledge Integrity", "passed": True})
    else:
        results.append({"name": "Knowledge Integrity", "passed": False})
        overall_passed = False

    # Custom Check: Strategic Foresight Coverage
    print_step("Checking Strategic Foresight Coverage")
    critical_foresight = [
        "intelligence_roi_collector.py", "ghost_prototyper.py",
        "truth_validator.py", "hallucination_detector.py"
    ]
    foresight_found = True
    for s in critical_foresight:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["analysis", "health", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('intelligence_', '').replace('.py', '')}.py"
        if not test_file.exists():
            foresight_found = False
            print_error(f"Missing test for {s}")
    
    if foresight_found:
        print_success("Strategic Foresight: All predictive analytics scripts have tests.")
        results.append({"name": "Strategic Foresight", "passed": True})
    else:
        results.append({"name": "Strategic Foresight", "passed": False})
        overall_passed = False

    # Custom Check: Context & Memory Coverage
    print_step("Checking Context & Memory Coverage")
    critical_memory = [
        "bus_manager.py", "distill_context.py",
        "context_pruner.py", "entropy_analyzer.py"
    ]
    memory_found = True
    for s in critical_memory:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["context", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            memory_found = False
            print_error(f"Missing test for {s}")
    
    if memory_found:
        print_success("Context & Memory: All state orchestration scripts have tests.")
        results.append({"name": "Context & Memory", "passed": True})
    else:
        results.append({"name": "Context & Memory", "passed": False})
        overall_passed = False

    # Custom Check: Knowledge Brain Coverage
    print_step("Checking Knowledge Brain Coverage")
    critical_brain = [
        "vector_store.py", "knowledge_miner.py",
        "discovery_brain_sync.py", "ki_coverage_collector.py"
    ]
    brain_found = True
    for s in critical_brain:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["knowledge", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            brain_found = False
            print_error(f"Missing test for {s}")
    
    if brain_found:
        print_success("Knowledge Brain: All semantic wisdom scripts have tests.")
        results.append({"name": "Knowledge Brain", "passed": True})
    else:
        results.append({"name": "Knowledge Brain", "passed": False})
        overall_passed = False

    # Custom Check: DevEx & Automation Coverage
    print_step("Checking DevEx & Automation Coverage")
    critical_devex = [
        "skill_factory.py", "ci_auto_fixer.py",
        "linter_debt_collector.py", "sandbox_runner.py"
    ]
    devex_found = True
    for s in critical_devex:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["dev", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            devex_found = False
            print_error(f"Missing test for {s}")
    
    if devex_found:
        print_success("DevEx & Automation: All engineering tools have tests.")
        results.append({"name": "DevEx & Automation", "passed": True})
    else:
        results.append({"name": "DevEx & Automation", "passed": False})
        overall_passed = False

    # Custom Check: UX & Business Intelligence Coverage
    print_step("Checking UX & Business Intelligence Coverage")
    critical_biz = [
        "ux_conversion_audit.py", "business_dashboard.py",
        "intent_validator.py", "analyze_efficiency.py"
    ]
    biz_found = True
    for s in critical_biz:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["analysis", "health", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            biz_found = False
            print_error(f"Missing test for {s}")
    
    if biz_found:
        print_success("UX & Business Intelligence: All impact analysis tools have tests.")
        results.append({"name": "UX & Business Intelligence", "passed": True})
    else:
        results.append({"name": "UX & Business Intelligence", "passed": False})
        overall_passed = False

    # Custom Check: Security & Resilience Coverage
    print_step("Checking Security & Resilience Coverage")
    critical_sec = [
        "threat_modeler.py", "vulnerability_patcher.py",
        "autonomous_fuzzer.py", "blue_team_monitor.py", "chaos_analyzer.py"
    ]
    sec_found = True
    for s in critical_sec:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["health", "dev", "chaos", "analysis", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            sec_found = False
            print_error(f"Missing test for {s}")
    
    if sec_found:
        print_success("Security & Resilience: All defensive tools have tests.")
        results.append({"name": "Security & Resilience", "passed": True})
    else:
        results.append({"name": "Security & Resilience", "passed": False})
        overall_passed = False

    # Custom Check: Advanced Task & Sync Coverage
    print_step("Checking Advanced Task & Sync Coverage")
    critical_task = [
        "task_miner.py", "task_sync.py",
        "sync_parity_collector.py", "walkthrough_assembler.py", "social_proof_generator.py"
    ]
    task_sync_found = True
    for s in critical_task:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["delivery", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            task_sync_found = False
            print_error(f"Missing test for {s}")
    
    if task_sync_found:
        print_success("Advanced Task & Sync: All goal synchronization tools have tests.")
        results.append({"name": "Advanced Task & Sync", "passed": True})
    else:
        results.append({"name": "Advanced Task & Sync", "passed": False})
        overall_passed = False

    # Custom Check: System Integrity & Protocol Coverage
    print_step("Checking System Integrity & Protocol Coverage")
    critical_integrity = [
        "chaos_monkey.py", "bus_manager.py",
        "conflict_resolver.py", "doc_healer.py", "output_bridge.py"
    ]
    integrity_found = True
    for s in critical_integrity:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["chaos", "context", "dev", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            integrity_found = False
            print_error(f"Missing test for {s}")
    
    if integrity_found:
        print_success("System Integrity & Protocol: All core protocol tools have tests.")
        results.append({"name": "System Integrity & Protocol", "passed": True})
    else:
        results.append({"name": "System Integrity & Protocol", "passed": False})
        overall_passed = False

    # Custom Check: ADR & Documentation Coverage
    print_step("Checking ADR & Documentation Coverage")
    critical_docs = [
        "adr_drafter.py", "adr_generator.py", "auto_adr_drafter.py",
        "generate_adr.py", "archivist_trigger.py", "generate_snapshot.py",
        "wiki_sync.py"
    ]
    docs_found = True
    for s in critical_docs:
        found_in_any = any((Path(REPO_ROOT) / ".agent" / "scripts" / d / s).exists() for d in ["knowledge", "misc", "dev", "."])
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            docs_found = False
            print_error(f"Missing test for {s}")
    
    if docs_found:
        print_success("ADR & Documentation: All governance tools have tests.")
        results.append({"name": "ADR & Documentation", "passed": True})
    else:
        results.append({"name": "ADR & Documentation", "passed": False})
        overall_passed = False

    # Custom Check: Governance & Compliance Coverage
    print_step("Checking Governance & Compliance Coverage")
    critical_gov = [
        "budget_monitor.py", "context_recall_gate.py", "incident_watcher.py",
        "model_validator.py", "obsidian_validator.py", "pr_audit.py",
        "pre_commit_review.py"
    ]
    gov_found = True
    for s in critical_gov:
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            gov_found = False
            print_error(f"Missing test for {s}")
    
    if gov_found:
        print_success("Governance & Compliance: All enforcement tools have tests.")
        results.append({"name": "Governance & Compliance", "passed": True})
    else:
        results.append({"name": "Governance & Compliance", "passed": False})
        overall_passed = False

    # Custom Check: Semantic Memory & AI Engineering Coverage
    print_step("Checking Semantic Memory Coverage")
    critical_ai = [
        "embedding_client.py", "experience_search.py", "memory_ingestor.py",
        "semantic_brain_engine.py", "semantic_context_optimizer.py", "vector_store.py"
    ]
    ai_found = True
    for s in critical_ai:
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            ai_found = False
            print_error(f"Missing test for {s}")
            
    if ai_found:
        print_success("Semantic Memory: All AI engineering tools have tests.")
        results.append({"name": "Semantic Memory", "passed": True})
    else:
        results.append({"name": "Semantic Memory", "passed": False})
        overall_passed = False

    # Custom Check: Infrastructure & MCP Resilience
    print_step("Checking Infrastructure & MCP Resilience Coverage")
    critical_infra = [
        "mcp_health_collector.py", "mcp_provisioner.py",
        "wsl_health_collector.py", "install_hooks.py", "resource_optimizer.py"
    ]
    infra_found = True
    for s in critical_infra:
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            infra_found = False
            print_error(f"Missing test for {s}")
            
    if infra_found:
        print_success("Infrastructure: All MCP and infrastructure tools have tests.")
        results.append({"name": "Infrastructure", "passed": True})
    else:
        results.append({"name": "Infrastructure", "passed": False})
        overall_passed = False

    # Custom Check: Model Routing & Benchmarking
    print_step("Checking Model Routing Coverage")
    critical_routing = [
        "model_benchmark.py", "ollama_agent.py",
        "profile_routing.py", "router_trainer.py"
    ]
    routing_found = True
    for s in critical_routing:
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            routing_found = False
            print_error(f"Missing test for {s}")
            
    if routing_found:
        print_success("Model Routing: All routing and benchmarking tools have tests.")
        results.append({"name": "Model Routing", "passed": True})
    else:
        results.append({"name": "Model Routing", "passed": False})
        overall_passed = False

    # Custom Check: Miscellaneous Utilities
    print_step("Checking Miscellaneous Utilities Coverage")
    critical_misc = [
        "bus_debugger.py", "code_polisher.py",
        "context_autofill.py", "generate_discovery_files.py",
        "impact_to_roles.py", "post_mortem_runner.py",
        "qa_golden_engine.py", "test_runner.py"
    ]
    misc_found = True
    for s in critical_misc:
        test_file = Path(REPO_ROOT) / ".agent" / "scripts" / "tests" / f"test_{s.replace('.py', '')}.py"
        if not test_file.exists():
            misc_found = False
            print_error(f"Missing test for {s}")
            
    if misc_found:
        print_success("Miscellaneous: All utility and polish scripts have tests.")
        results.append({"name": "Miscellaneous", "passed": True})
    else:
        results.append({"name": "Miscellaneous", "passed": False})
        overall_passed = False

    # Custom Check: Analysis Logic Coverage
    print_step("Checking Analysis Logic Coverage")
    critical_analysis = [
        "quality_tracker.py", "dead_code_detector.py",
        "impact_analyzer.py", "requirement_expander.py",
        "ambiguity_detector.py", "resource_forecaster.py"
    ]
    ok, msg = check_script_coverage("analysis", critical_only=critical_analysis)
    if ok:
        print_success(f"Analysis Coverage: {msg}")
        results.append({"name": "Analysis Coverage", "passed": True})
    else:
        print_error(f"Analysis Coverage: {msg}")
        results.append({"name": "Analysis Coverage", "passed": False})
        overall_passed = False

    # Custom Check: Models Logic Coverage
    print_step("Checking Models Logic Coverage")
    critical_models = ["model_router.py", "prompt_optimizer.py"]
    ok, msg = check_script_coverage("models", critical_only=critical_models)
    if ok:
        print_success(f"Models Coverage: {msg}")
        results.append({"name": "Models Coverage", "passed": True})
    else:
        print_error(f"Models Coverage: {msg}")
        results.append({"name": "Models Coverage", "passed": False})
        overall_passed = False

    # Custom Check: Knowledge Logic Coverage
    print_step("Checking Knowledge Logic Coverage")
    critical_knowledge = ["experience_distiller.py", "obsidian_sync.py"]
    ok, msg = check_script_coverage("knowledge", critical_only=critical_knowledge)
    if ok:
        print_success(f"Knowledge Coverage: {msg}")
        results.append({"name": "Knowledge Coverage", "passed": True})
    else:
        print_error(f"Knowledge Coverage: {msg}")
        results.append({"name": "Knowledge Coverage", "passed": False})
        overall_passed = False

    # Custom Check: Context Logic Coverage
    print_step("Checking Context Logic Coverage")
    critical_context = ["bus_manager.py", "conflict_resolver.py"]
    ok, msg = check_script_coverage("context", critical_only=critical_context)
    if ok:
        print_success(f"Context Coverage: {msg}")
        results.append({"name": "Context Coverage", "passed": True})
    else:
        print_error(f"Context Coverage: {msg}")
        results.append({"name": "Context Coverage", "passed": False})
        overall_passed = False

    # Custom Check: Dev Logic Coverage
    print_step("Checking Dev Logic Coverage")
    critical_dev = ["visualize_deps.py", "checklist.py"]
    ok, msg = check_script_coverage("dev", critical_only=critical_dev)
    if ok:
        print_success(f"Dev Coverage: {msg}")
        results.append({"name": "Dev Coverage", "passed": True})
    else:
        print_error(f"Dev Coverage: {msg}")
        results.append({"name": "Dev Coverage", "passed": False})
        overall_passed = False

    # Core checks execution
    print_header("📋 CORE CHECKS")
    
    for name, script_path, mandatory in CORE_CHECKS:
        full_path = REPO_ROOT / script_path
        if not full_path.exists():
            print_warning(f"Skipping {name}: Script {script_path} not found.")
            continue
            
        print_step(f"Running {name}...")
        try:
            # Run the script and capture output
            result = subprocess.run(
                [sys.executable, str(full_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print_success(f"{name} passed.")
                results.append({"name": name, "passed": True})
            else:
                if mandatory:
                    print_error(f"{name} failed!")
                    print(result.stdout)
                    print(result.stderr)
                    overall_passed = False
                else:
                    print_warning(f"{name} failed (non-blocking).")
                results.append({"name": name, "passed": False})
                
        except Exception as e:
            print_error(f"Error running {name}: {e}")
            if mandatory:
                overall_passed = False
            results.append({"name": name, "passed": False})

    print_header("🏁 FINAL STATUS")
    for res in results:
        status = f"{Colors.GREEN}PASS{Colors.ENDC}" if res["passed"] else f"{Colors.RED}FAIL{Colors.ENDC}"
        print(f"| {res['name']:<25} | {status} |")
    
    if not overall_passed:
        print_error("\nChecklist FAILED. Please fix the mandatory issues above.")
        sys.exit(1)
    else:
        print_success("\nAll core checks passed! Ready to proceed.")

if __name__ == "__main__":
    main()
