# Antigravity Hive: Scripts Domain Map

## Overview

This document maps all functional domains to their respective script locations.

## Domain: Ethics & Governance

Location: `.agent/agents/specialists/ethics/`

- [.agent/agents/specialists/ethics/ethics-auditor.md](file:///home/amudrykh/go/project/prompt-library/.agent/agents/specialists/ethics/ethics-auditor.md) — Lead Ethics Auditor.

## Domain: Health & Monitoring

Location: `.agent/scripts/health/`

- `.agent/scripts/health/__init__.py`
- `.agent/scripts/health/status_report.py`
- `.agent/scripts/health/security_scan.py`
- `.agent/scripts/health/mcp_provisioner.py`
- `.agent/scripts/health/drift_detector.py`
- `.agent/scripts/health/guardrail_monitor.py`
- `.agent/scripts/health/budget_monitor.py`
- `.agent/scripts/health/blue_team_monitor.py`
- `.agent/scripts/health/dependency_analyzer.py`
- `.agent/scripts/health/hallucination_detector.py`
- `.agent/scripts/health/policy_guardrail.py`
- `.agent/scripts/health/alignment_oracle.py`
- `.agent/scripts/health/predictive_watcher.py`
- `.agent/scripts/health/self_healer.py`

## Domain: Development & Git

Location: `.agent/scripts/dev/`

- `.agent/scripts/dev/__init__.py`
- `.agent/scripts/dev/checklist.py`
- `.agent/scripts/dev/pre_commit_review.py`
- `.agent/scripts/dev/conflict_resolver.py`
- `.agent/scripts/dev/lint_runner.py`
- `.agent/scripts/dev/test_runner.py`
- `.agent/scripts/dev/cli_bridge.py`

## Domain: Delivery & Sync

Location: `.agent/scripts/delivery/`

- `.agent/scripts/delivery/__init__.py`
- `.agent/scripts/delivery/sync_agents.py`
- `.agent/scripts/delivery/task_tracer.py`
- `.agent/scripts/delivery/sync_parity_collector.py`
- `.agent/scripts/delivery/task_miner.py`

## Domain: Knowledge & Intelligence

Location: `.agent/scripts/knowledge/`

- `.agent/scripts/knowledge/__init__.py`
- `.agent/scripts/knowledge/knowledge_miner.py`
- `.agent/scripts/knowledge/ki_coverage_collector.py`
- `.agent/scripts/knowledge/experience_distiller.py`
- [.agent/rules/PERSONA.md](file:///home/amudrykh/go/project/prompt-library/.agent/rules/PERSONA.md) — User stylistic DNA.
- [.agent/knowledge/adr_007_behavioral_adaptation.md](file:///home/amudrykh/go/project/prompt-library/.agent/knowledge/adr_007_behavioral_adaptation.md) — Adaptation protocol.
- `.agent/scripts/knowledge/semantic_brain_engine.py`
- `.agent/scripts/knowledge/adr_generator.py`
- `.agent/scripts/knowledge/promote_proposals.py`
- `.agent/scripts/knowledge/generate_inventory.py`
- `.agent/scripts/misc/generate_snapshot.py`

## Domain: Analysis & Insights

Location: `.agent/scripts/analysis/`

- `.agent/scripts/analysis/__init__.py`
- `.agent/scripts/analysis/ambiguity_detector.py`
- `.agent/scripts/analysis/impact_analyzer.py`
- `.agent/scripts/analysis/intelligence_roi_collector.py`
- `.agent/scripts/analysis/resource_forecaster.py`
- `.agent/scripts/analysis/post_mortem_runner.py`

## Domain: AI Models & Routing

Location: `.agent/scripts/models/`

- `.agent/scripts/models/__init__.py`
- `.agent/scripts/models/model_router.py`
- `.agent/scripts/models/ollama_agent.py`
- `.agent/scripts/models/prompt_optimizer.py`
- `.agent/scripts/models/model_validator.py`
- `.agent/scripts/models/profile_routing.py`
- `.agent/scripts/models/model_benchmark.py`
- `.agent/scripts/models/router_trainer.py`
- `.agent/scripts/models/embedding_client.py`
- `.agent/scripts/models/semantic_experience.py`

## Domain: Orchestration

Location: `.agent/scripts/orchestration/`

- `.agent/scripts/orchestration/__init__.py`
- `.agent/scripts/orchestration/agent_auctioneer.py`
- `.agent/scripts/orchestration/hidden_war_room.py`
- `.agent/scripts/orchestration/personality_adapter.py`
- `.agent/scripts/orchestration/wave_dispatcher.py`
- `.agent/scripts/orchestration/orchestration_session.py`
- `.agent/scripts/orchestration/agent_arena.py`
- `.agent/scripts/orchestration/agent_scorer.py`
- `.agent/scripts/orchestration/arbitrator.py`
- `.agent/scripts/orchestration/session_manager.py`
- `.agent/scripts/orchestration/war_room_manager.py`
- `.agent/scripts/orchestration/governance_gate.py`
- `.agent/scripts/orchestration/sprint_advisor.py`

## Domain: Testing

Location: `.agent/scripts/tests/`

- `.agent/scripts/tests/full_integration_test.py`
- `.agent/scripts/tests/final_regression.py`
- `.agent/scripts/tests/test_bus_manager.py`
- `.agent/scripts/tests/test_guardrail_monitor.py`
- `.agent/scripts/tests/test_resilience.py`

## Domain: Context & Bus

Location: `.agent/scripts/context/`

- `.agent/scripts/context/__init__.py`
- `.agent/scripts/context/bus_manager.py`
- [.agent/bus/personality_profile.json](file:///home/amudrykh/go/project/prompt-library/.agent/bus/personality_profile.json) — Active stylistic preferences.
- [.agent/bus/context.json](file:///home/amudrykh/go/project/prompt-library/.agent/bus/context.json) — Shared state.
- `.agent/scripts/context/bus_debugger.py`
- `.agent/scripts/context/conflict_resolver.py`
- `.agent/scripts/context/context_autofill.py`
- `.agent/scripts/context/distill_context.py`
- `.agent/scripts/context/semantic_context_optimizer.py`
