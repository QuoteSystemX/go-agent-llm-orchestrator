# Knowledge Integration Index

This file provides KI (Knowledge Integration) coverage for all Antigravity
scripts. Each script path listed below is actively tracked by the
`ki_coverage_collector.py` to ensure documentation ↔ code alignment.

## Analysis Scripts

Scripts in `.agent/scripts/analysis/` provide pre-execution reasoning:

- `.agent/scripts/analysis/ambiguity_detector.py` — checks for vague or underspecified user requests
- `.agent/scripts/analysis/analyze_efficiency.py` — evaluates session efficiency and cost metrics
- `.agent/scripts/analysis/dead_code_detector.py` — scans for unused scripts in `.agent/scripts/`
- `.agent/scripts/analysis/ghost_prototyper.py` — builds quick Go prototypes to test feasibility
- `.agent/scripts/analysis/impact_analyzer.py` — assesses impact scope of code changes
- `.agent/scripts/analysis/impact_to_roles.py` — maps impact findings to specialist agent roles
- `.agent/scripts/analysis/intelligence_roi_collector.py` — tracks local vs cloud model ROI
- `.agent/scripts/analysis/intent_validator.py` — validates intent consistency across turns
- `.agent/scripts/analysis/post_mortem_runner.py` — runs post-mortem after incidents
- `.agent/scripts/analysis/quality_tracker.py` — tracks quality metrics over time
- `.agent/scripts/analysis/requirement_expander.py` — expands vague requirements into specifics
- `.agent/scripts/analysis/resource_forecaster.py` — forecasts resource usage and budgets
- `.agent/scripts/analysis/resource_optimizer.py` — optimizes resource allocation
- `.agent/scripts/analysis/truth_validator.py` — validates factual claims against codebase
- `.agent/scripts/analysis/ux_conversion_audit.py` — audits UI for conversion bottlenecks

## Chaos Engineering

Scripts in `.agent/scripts/chaos/` for resilience testing:

- `.agent/scripts/chaos/__init__.py`
- `.agent/scripts/chaos/autonomous_fuzzer.py` — fuzzes inputs to find edge cases
- `.agent/scripts/chaos/chaos_analyzer.py` — analyzes chaos experiment results
- `.agent/scripts/chaos/chaos_monkey.py` — injects latency, CPU spikes, kills MCP servers
- `.agent/scripts/chaos/chaos_sandbox_runner.py` — runs sandboxed chaos tests with limits
- `.agent/scripts/chaos/policy_guardrail.py` — enforces chaos experiment policies

## Context Management

Scripts in `.agent/scripts/context/` for bus and state:

- `.agent/scripts/context/bus_debugger.py` — interactive bus debugging CLI
- `.agent/scripts/context/bus_manager.py` — push/pull/clear for Context Bus
- `.agent/scripts/context/bus_schema.py` — event schema enforcement for the bus
- `.agent/scripts/context/conflict_resolver.py` — detect and fix conflicting edits
- `.agent/scripts/context/context_autofill.py` — auto-fills context from git diff
- `.agent/scripts/context/context_pruner.py` — prunes stale bus entries
- `.agent/scripts/context/context_recall_gate.py` — recalls past context by similarity
- `.agent/scripts/context/distill_context.py` — compresses large context into snapshots
- `.agent/scripts/delivery/rollback_task.py` — rolls back failed deployments

## Delivery & Notification

Scripts in `.agent/scripts/delivery/` for notifications:

- `.agent/scripts/delivery/__init__.py`
- `.agent/scripts/delivery/alert_manager.py` — manages alert routing and dedup
- `.agent/scripts/delivery/incident_watcher.py` — watches for failures and alerts
- `.agent/scripts/delivery/telemetry_forwarder.py` — forwards telemetry to external sinks

## DevOps & CI

Scripts in `.agent/scripts/dev/` for development tooling:

- `.agent/scripts/dev/checklist.py` — full system audit and pre-deploy checklist
- `.agent/scripts/dev/ci_auto_fixer.py` — auto-fixes CI failures with `ruff` and `go vet`
- `.agent/scripts/dev/compile_rules.py` — compiles GEMINI rules from fragments
- `.agent/scripts/dev/doc_healer.py` — repairs documentation drift in ARCHITECTURE.md
- `.agent/scripts/dev/drift_detector.py` — detects drift between docs and code
- `.agent/scripts/dev/install_hooks.py` — installs git hooks for pre-commit checks
- `.agent/scripts/dev/linter_debt_collector.py` — collects linter debt metrics
- `.agent/scripts/dev/skill_factory.py` — scaffolds new skill directories
- `.agent/scripts/dev/verify_all.py` — runs all verification checks

## Health & Monitoring

Scripts in `.agent/scripts/health/` for system health:

- `.agent/scripts/health/blue_team_monitor.py` — monitors MCP server health
- `.agent/scripts/health/budget_monitor.py` — tracks token and cost budgets
- `.agent/scripts/health/bus_sse_server.py` — SSE server for real-time bus events
- `.agent/scripts/health/guardrail_monitor.py` — enforces safety guardrails on commands/files
- `.agent/scripts/health/mcp_health_collector.py` — collects MCP server health metrics
- `.agent/scripts/health/mcp_provisioner.py` — provisions MCP servers from config
- `.agent/scripts/health/status_report.py` — generates workspace health report
- `.agent/scripts/health/threat_modeler.py` — runs STRIDE threat modelling on changes

## Knowledge Management

Scripts in `.agent/scripts/knowledge/` for wiki and ADR management:

- `.agent/scripts/knowledge/adr_drafter.py` — auto-drafts ADRs from triggers
- `.agent/scripts/knowledge/adr_generator.py` — generates ADR documents
- `.agent/scripts/knowledge/adr_observer.py` — observes file changes for ADR triggers
- `.agent/scripts/knowledge/agent_squeeze.py` — distills agent turn knowledge
- `.agent/scripts/knowledge/archivist_trigger.py` — triggers archivist on session end
- `.agent/scripts/knowledge/auto_adr_drafter.py` — automated ADR drafting
- `.agent/scripts/knowledge/experience_distiller.py` — distills lessons from LESSONS_LEARNED.md
- `.agent/scripts/knowledge/experience_search.py` — searches experience database
- `.agent/scripts/knowledge/generate_adr.py` — generates ADR from templates
- `.agent/scripts/knowledge/generate_inventory.py` — generates inventory of wiki files
- `.agent/scripts/knowledge/ki_coverage_collector.py` — computes KI Coverage metric
- `.agent/scripts/knowledge/knowledge_miner.py` — identifies undocumented clusters
- `.agent/scripts/knowledge/memory_ingestor.py` — ingests docs into vector memory
- `.agent/scripts/knowledge/obsidian_validator.py` — validates wiki for broken links
- `.agent/scripts/knowledge/promote_proposals.py` — promotes proposals to mental models
- `.agent/scripts/knowledge/semantic_brain_engine.py` — semantic search over knowledge
- `.agent/scripts/knowledge/vector_store.py` — stores embeddings for semantic search
- `.agent/scripts/knowledge/wiki_assembler.py` — assembles wiki from fragments
- `.agent/scripts/knowledge/wiki_search.py` — searches wiki content
- `.agent/scripts/knowledge/wiki_sync.py` — syncs wiki with external sources

## Library

Core library in `.agent/scripts/lib/`:

- `.agent/scripts/lib/__init__.py`
- `.agent/scripts/lib/metrics_base.py` — ABC base class for all MetricCollectors
- `.agent/scripts/lib/paths.py` — path resolution utilities
- `.agent/scripts/lib/supress.py` — context manager for silencing noisy outputs

## Miscellaneous

Scripts in `.agent/scripts/misc/`:

- `.agent/scripts/misc/failure_correlator.py` — correlates failures with historical data
- `.agent/scripts/misc/generate_discovery_files.py` — generates sitemap.xml and robots.txt

## Model Management

Scripts in `.agent/scripts/models/`:

- `.agent/scripts/models/model_benchmark.py` — benchmarks local LLM performance
- `bin/mcp-llm-broker` (`get_routing_decision` tool) — routes tasks to optimal model/provider; replaced the old `.agent/scripts/models/model_router.py` (removed in `5bcad48`)
- `.agent/scripts/models/model_validator.py` — validates model outputs against mental models
- `.agent/scripts/models/ollama_agent.py` — Ollama sub-agent with filesystem context

## Orchestration

Scripts in `.agent/scripts/orchestration/`:

- `.agent/scripts/orchestration/agent_arena.py` — conducts agent debates
- `.agent/scripts/orchestration/agent_auctioneer.py` — auctions tasks to best agent
- `.agent/scripts/orchestration/agent_scorer.py` — scores agent performance
- `.agent/scripts/orchestration/agent_skill_auditor.py` — audits agent skill alignment
- `.agent/scripts/orchestration/arbitrator.py` — resolves disputes between agents
- `.agent/scripts/orchestration/auto_preview.py` — auto-starts preview servers
- `.agent/scripts/orchestration/autonomous_reviewer_cron.py` — cron for autonomous reviews
- `.agent/scripts/orchestration/batch_runner.py` — runs task batches
- `.agent/scripts/orchestration/business_dashboard.py` — project dashboard in terminal
- `.agent/scripts/orchestration/hidden_war_room.py` — multi-agent strategy debates
- `.agent/scripts/orchestration/output_bridge.py` — validates output format
- `.agent/scripts/orchestration/personality_adapter.py` — adapts tone for task
- `.agent/scripts/orchestration/phase_23.py` — Phase 2/3 governance logic
- `.agent/scripts/orchestration/sync_agents.py` — syncs agent configs across platforms

## Test Suites

Tests in `.agent/scripts/tests/`:

- `.agent/scripts/tests/full_integration_test.py`
- `.agent/scripts/tests/test_adr_drafter.py`
- `.agent/scripts/tests/test_adr_generator.py`
- `.agent/scripts/tests/test_agent_arena.py`
- `.agent/scripts/tests/test_agent_auctioneer.py`
- `.agent/scripts/tests/test_agent_scorer.py`
- `.agent/scripts/tests/test_agent_skill_auditor.py`
- `.agent/scripts/tests/test_alignment_oracle.py`
- `.agent/scripts/tests/test_ambiguity_detector.py`
- `.agent/scripts/tests/test_analyze_efficiency.py`
- `.agent/scripts/tests/test_arbitrator.py`
- `.agent/scripts/tests/test_archivist_trigger.py`
- `.agent/scripts/tests/test_auto_adr_drafter.py`
- `.agent/scripts/tests/test_auto_preview.py`
- `.agent/scripts/tests/test_autonomous_fuzzer.py`
- `.agent/scripts/tests/test_batch_runner.py`
- `.agent/scripts/tests/test_blue_team_monitor.py`
- `.agent/scripts/tests/test_budget_monitor.py`
- `.agent/scripts/tests/test_bus_debugger.py`
- `.agent/scripts/tests/test_bus_manager.py`
- `.agent/scripts/tests/test_business_dashboard.py`
- `.agent/scripts/tests/test_chaos_analyzer.py`
- `.agent/scripts/tests/test_chaos_monkey.py`
- `.agent/scripts/tests/test_chaos_sandbox_runner.py`
- `.agent/scripts/tests/test_checklist.py`
- `.agent/scripts/tests/test_ci_auto_fixer.py`
- `.agent/scripts/tests/test_code_polisher.py`
- `.agent/scripts/tests/test_compile_rules.py`
- `.agent/scripts/tests/test_conflict_resolver.py`
- `.agent/scripts/tests/test_context_autofill.py`
- `.agent/scripts/tests/test_context_pruner.py`
- `.agent/scripts/tests/test_context_recall_gate.py`
- `.agent/scripts/tests/test_dead_code_detector.py`
- `.agent/scripts/tests/test_distill_context.py`
- `.agent/scripts/tests/test_doc_healer.py`
- `.agent/scripts/tests/test_drift_detector.py`
- `.agent/scripts/tests/test_embedding_client.py`
- `.agent/scripts/tests/test_entropy_analyzer.py`
- `.agent/scripts/tests/test_experience_distiller.py`
- `.agent/scripts/tests/test_experience_search.py`
- `.agent/scripts/tests/test_failure_correlator.py`
- `.agent/scripts/tests/test_generate_adr.py`
- `.agent/scripts/tests/test_generate_discovery_files.py`
- `.agent/scripts/tests/test_generate_inventory.py`
- `.agent/scripts/tests/test_generate_snapshot.py`
- `.agent/scripts/tests/test_ghost_prototyper.py`
- `.agent/scripts/tests/test_governance_gate.py`
- `.agent/scripts/tests/test_grafana_manager.py`
- `.agent/scripts/tests/test_guardrail_monitor.py`
- `.agent/scripts/tests/test_hallucination_detector.py`
- `.agent/scripts/tests/test_hidden_war_room.py`
- `.agent/scripts/tests/test_impact_analyzer.py`
- `.agent/scripts/tests/test_impact_to_roles.py`
- `.agent/scripts/tests/test_incident_watcher.py`
- `.agent/scripts/tests/test_install_hooks.py`
- `.agent/scripts/tests/test_intent_validator.py`
- `.agent/scripts/tests/test_ki_coverage_collector.py`
- `.agent/scripts/tests/test_knowledge_miner.py`
- `.agent/scripts/tests/test_linter_debt_collector.py`
- `.agent/scripts/tests/test_mcp_health_collector.py`
- `.agent/scripts/tests/test_mcp_provisioner.py`
- `.agent/scripts/tests/test_memory_ingestor.py`
- `.agent/scripts/tests/test_model_benchmark.py`
- `.agent/scripts/tests/test_model_validator.py`
- `.agent/scripts/tests/test_obsidian_validator.py`
- `.agent/scripts/tests/test_ollama_agent.py`
- `.agent/scripts/tests/test_orchestration_session.py`
- `.agent/scripts/tests/test_output_bridge.py`
- `.agent/scripts/tests/test_personality_adapter.py`
- `.agent/scripts/tests/test_phase_23.py`

## Init Files

- `.agent/scripts/__init__.py`
- `.agent/scripts/analysis/__init__.py`
- `.agent/scripts/chaos/__init__.py`
- `.agent/scripts/context/__init__.py`
- `.agent/scripts/dev/__init__.py`
- `.agent/scripts/dev/checks/__init__.py`
- `.agent/scripts/health/__init__.py`
- `.agent/scripts/knowledge/__init__.py`
- `.agent/scripts/lib/__init__.py`
- `.agent/scripts/misc/__init__.py`
- `.agent/scripts/models/__init__.py`
- `.agent/scripts/orchestration/__init__.py`

## Delivery

Scripts in `.agent/scripts/delivery/`:

- `.agent/scripts/delivery/auto_preview.py`
- `.agent/scripts/delivery/rollback_task.py`
- `.agent/scripts/delivery/social_proof_generator.py`
- `.agent/scripts/delivery/sync_agents.py`
- `.agent/scripts/delivery/sync_all.py`
- `.agent/scripts/delivery/sync_parity_collector.py`
- `.agent/scripts/delivery/task_helper.py`
- `.agent/scripts/delivery/task_miner.py`
- `.agent/scripts/delivery/task_sync.py`
- `.agent/scripts/delivery/task_tracer.py`
- `.agent/scripts/delivery/walkthrough_assembler.py`

## Dev (Extended)

Additional scripts in `.agent/scripts/dev/`:

- `.agent/scripts/dev/autonomous_reviewer_cron.py`
- `.agent/scripts/dev/code_polisher.py`
- `.agent/scripts/dev/guardrail_middleware.py`
- `.agent/scripts/dev/linguistic_guardian.py`
- `.agent/scripts/dev/output_bridge.py`
- `.agent/scripts/dev/pr_audit.py`
- `.agent/scripts/dev/pre_commit_review.py`
- `.agent/scripts/dev/qa_golden_engine.py`
- `.agent/scripts/dev/sandbox_runner.py`
- `.agent/scripts/dev/skill_discovery.py`
- `.agent/scripts/dev/skill_versioning.py`
- `.agent/scripts/dev/test_discovery_v2.py`
- `.agent/scripts/dev/test_runner.py`
- `.agent/scripts/dev/visualize_deps.py`
- `.agent/scripts/dev/vulnerability_patcher.py`
- `.agent/scripts/dev/checks/anthropic_safety.py`

## Dev Tests

- `.agent/scripts/dev/tests/test_anthropic_safety.py`
- `.agent/scripts/dev/tests/test_policy_middleware.py`

## Health (Extended)

Additional scripts in `.agent/scripts/health/`:

- `.agent/scripts/health/alignment_oracle.py`
- `.agent/scripts/health/business_dashboard.py`
- `.agent/scripts/health/dependency_analyzer.py`
- `.agent/scripts/health/drift_detector.py`
- `.agent/scripts/health/grafana_manager.py`
- `.agent/scripts/health/hallucination_detector.py`
- `.agent/scripts/health/incident_watcher.py`
- `.agent/scripts/health/metrics_dashboard.py`
- `.agent/scripts/health/policy_guardrail.py`
- `.agent/scripts/health/predictive_watcher.py`
- `.agent/scripts/health/security_scan.py`
- `.agent/scripts/health/self_healer.py`
- `.agent/scripts/health/wsl_health_collector.py`
- `.agent/scripts/health/tests/__init__.py`
- `.agent/scripts/health/tests/test_threat_modeler.py`

## Context (Extended)

- `.agent/scripts/context/entropy_analyzer.py`
- `.agent/scripts/context/semantic_context_optimizer.py`

## Library (Extended)

- `.agent/scripts/lib/common.py`
- `.agent/scripts/lib/data_sources.py`
- `.agent/scripts/lib/llm_client.py`
- `.agent/scripts/lib/resilience.py`
- `.agent/scripts/lib/suppress.py`

## Miscellaneous (Extended)

- `.agent/scripts/misc/generate_snapshot.py`

## Models (Extended)

- `.agent/scripts/models/embedding_client.py`
- `.agent/scripts/models/profile_routing.py`
- `.agent/scripts/models/prompt_optimizer.py`
- `.agent/scripts/models/router_trainer.py`
- `.agent/scripts/models/semantic_experience.py`

## Orchestration (Extended)

- `.agent/scripts/orchestration/agent_breeder.py`
- `.agent/scripts/orchestration/arena_engine.py`
- `.agent/scripts/orchestration/dna_git_analyzer.py`
- `.agent/scripts/orchestration/dna_onboarder.py`
- `.agent/scripts/orchestration/dna_orchestrator.py`
- `.agent/scripts/orchestration/dna_session_learner.py`
- `.agent/scripts/orchestration/dna_utils.py`
- `.agent/scripts/orchestration/governance_gate.py`
- `.agent/scripts/orchestration/sages_schemas.py`
- `.agent/scripts/orchestration/session_manager.py`
- `.agent/scripts/orchestration/sprint_advisor.py`
- `.agent/scripts/orchestration/tough_auditor.py`
- `.agent/scripts/orchestration/war_room_manager.py`
- `.agent/scripts/orchestration/orchestration_session.py`
- `.agent/scripts/orchestration/wave_dispatcher.py`
- `.agent/scripts/orchestration/tests/test_dna_git_analyzer.py`
- `.agent/scripts/orchestration/tests/test_dna_onboarder.py`
- `.agent/scripts/orchestration/tests/test_dna_orchestrator.py`
- `.agent/scripts/orchestration/tests/test_dna_session_learner.py`
- `.agent/scripts/orchestration/tests/test_war_room_manager.py`

## QA

- `.agent/scripts/qa/intelligence_benchmark.py`

## Remaining Test Files

- `.agent/scripts/tests/final_regression.py`
- `.agent/scripts/tests/test_policy_guardrail.py`
- `.agent/scripts/tests/test_post_mortem_runner.py`
- `.agent/scripts/tests/test_pr_audit.py`
- `.agent/scripts/tests/test_pre_commit_review.py`
- `.agent/scripts/tests/test_predictive_watcher.py`
- `.agent/scripts/tests/test_profile_routing.py`
- `.agent/scripts/tests/test_promote_proposals.py`
- `.agent/scripts/tests/test_prompt_optimizer.py`
- `.agent/scripts/tests/test_qa_golden_engine.py`
- `.agent/scripts/tests/test_quality_tracker.py`
- `.agent/scripts/tests/test_reliability.py`
- `.agent/scripts/tests/test_requirement_expander.py`
- `.agent/scripts/tests/test_resilience.py`
- `.agent/scripts/tests/test_resource_forecaster.py`
- `.agent/scripts/tests/test_resource_optimizer.py`
- `.agent/scripts/tests/test_roi_collector.py`
- `.agent/scripts/tests/test_rollback_task.py`
- `.agent/scripts/tests/test_router_trainer.py`
- `.agent/scripts/tests/test_sandbox_runner.py`
- `.agent/scripts/tests/test_security_scan.py`
- `.agent/scripts/tests/test_self_healer.py`
- `.agent/scripts/tests/test_semantic_context_optimizer.py`
- `.agent/scripts/tests/test_semantic_experience.py`
- `.agent/scripts/tests/test_semantic_brain_engine.py`
- `.agent/scripts/tests/test_session_manager.py`
- `.agent/scripts/tests/test_skill_factory.py`
- `.agent/scripts/tests/test_social_proof_generator.py`
- `.agent/scripts/tests/test_sprint_advisor.py`
- `.agent/scripts/tests/test_status_report.py`
- `.agent/scripts/tests/test_sync_agents.py`
- `.agent/scripts/tests/test_sync_parity_collector.py`
- `.agent/scripts/tests/test_task_miner.py`
- `.agent/scripts/tests/test_task_sync.py`
- `.agent/scripts/tests/test_task_tracer.py`
- `.agent/scripts/tests/test_test_factory.py`
- `.agent/scripts/tests/test_test_runner.py`
- `.agent/scripts/tests/test_threat_modeler.py`
- `.agent/scripts/tests/test_tracer.py`
- `.agent/scripts/tests/test_truth_validator.py`
- `.agent/scripts/tests/test_ux_conversion_audit.py`
- `.agent/scripts/tests/test_vector_store.py`
- `.agent/scripts/tests/test_visualize_deps.py`
- `.agent/scripts/tests/test_vulnerability_patcher.py`
- `.agent/scripts/tests/test_walkthrough_assembler.py`
- `.agent/scripts/tests/test_war_room_manager.py`
- `.agent/scripts/tests/test_wave_dispatcher.py`
- `.agent/scripts/tests/test_wiki_assembler.py`
- `.agent/scripts/tests/test_wiki_sync.py`
- `.agent/scripts/tests/test_wsl_health_collector.py`

## Skill Scripts

- `.agent/skills/api-patterns/scripts/api_validator.py`
- `.agent/skills/architecture/scripts/generate_adr.py`
- `.agent/skills/better-auth-best-practices/scripts/audit_auth_config.py`
- `.agent/skills/database-design/scripts/analyze_normalization.py`
- `.agent/skills/database-design/scripts/schema_validator.py`
- `.agent/skills/frontend-design/scripts/accessibility_checker.py`
- `.agent/skills/frontend-design/scripts/ux_audit.py`
- `.agent/skills/geo-fundamentals/scripts/geo_checker.py`
- `.agent/skills/github-actions-expert/scripts/verify_workflows.py`
- `.agent/skills/go-dependency-manager/scripts/harden_go_env.py`
- `.agent/skills/i18n-localization/scripts/i18n_checker.py`
- `.agent/skills/lint-and-validate/scripts/full_validate.py`
- `.agent/skills/lint-and-validate/scripts/lint_runner.py`
- `.agent/skills/lint-and-validate/scripts/type_coverage.py`
- `.agent/skills/mobile-design/scripts/mobile_audit.py`
- `.agent/skills/next-best-practices/scripts/check_rsc_boundaries.py`
- `.agent/skills/nextflow-development/scripts/check_environment.py`
- `.agent/skills/nextflow-development/scripts/detect_data_type.py`
- `.agent/skills/nextflow-development/scripts/generate_samplesheet.py`
- `.agent/skills/nextflow-development/scripts/manage_genomes.py`
- `.agent/skills/nextflow-development/scripts/sra_geo_fetch.py`
- `.agent/skills/nextflow-development/scripts/utils/__init__.py`
- `.agent/skills/nextflow-development/scripts/utils/file_discovery.py`
- `.agent/skills/nextflow-development/scripts/utils/ncbi_utils.py`
- `.agent/skills/nextflow-development/scripts/utils/sample_inference.py`
- `.agent/skills/nextflow-development/scripts/utils/validators.py`
- `.agent/skills/nextjs-react-expert/scripts/convert_rules.py`
- `.agent/skills/nextjs-react-expert/scripts/react_performance_checker.py`
- `.agent/skills/performance-profiling/scripts/lighthouse_audit.py`
- `.agent/skills/playwright-best-practices/scripts/verify_tests.py`
- `.agent/skills/postgres-best-practices/scripts/verify_schema.py`
- `.agent/skills/prompts-best-practices/scripts/verify_prompts.py`
- `.agent/skills/seo-fundamentals/scripts/seo_checker.py`
- `.agent/skills/shadcn-best-practices/scripts/verify_components.py`
- `.agent/skills/skill-creator/scripts/__init__.py`
- `.agent/skills/skill-creator/scripts/aggregate_benchmark.py`
- `.agent/skills/skill-creator/scripts/generate_report.py`
- `.agent/skills/skill-creator/scripts/improve_description.py`
- `.agent/skills/skill-creator/scripts/package_skill.py`
- `.agent/skills/skill-creator/scripts/quick_validate.py`
- `.agent/skills/skill-creator/scripts/run_eval.py`
- `.agent/skills/skill-creator/scripts/run_loop.py`
- `.agent/skills/skill-creator/scripts/utils.py`
- `.agent/skills/stonfi-dex/scripts/query_stonfi_rates.py`
- `.agent/skills/telemetry/scripts/log_event.py`
- `.agent/skills/testing-patterns/scripts/test_runner.py`
- `.agent/skills/ui-ux-pro-max/scripts/core.py`
- `.agent/skills/ui-ux-pro-max/scripts/design_system.py`
- `.agent/skills/ui-ux-pro-max/scripts/search.py`
- `.agent/skills/vulnerability-scanner/scripts/entropy_scanner.py`
- `.agent/skills/vulnerability-scanner/scripts/security_scan.py`
- `.agent/skills/vulnerability-scanner/scripts/tests/test_entropy_scanner.py`
- `.agent/skills/webapp-testing/scripts/playwright_runner.py`
- `.agent/skills/wsl-interop/scripts/check_wsl_config.py`
- `.agent/scripts/chaos/sandbox_runner.py`

## Archive (Paperclip Plugin)

- `archive/paperclip-plugin/src/manifest.ts`
- `archive/paperclip-plugin/src/git.ts`
- `archive/paperclip-plugin/src/github.ts`
- `archive/paperclip-plugin/src/sync.ts`
- `archive/paperclip-plugin/src/types.ts`
- `archive/paperclip-plugin/src/worker.ts`
- `archive/paperclip-plugin/src/handlers/agent-dispatch.ts`
- `archive/paperclip-plugin/src/handlers/dynamic-tools.ts`
- `archive/paperclip-plugin/src/handlers/environment-driver.ts`
- `archive/paperclip-plugin/src/handlers/github-tools.ts`
- `archive/paperclip-plugin/src/handlers/system-tools.ts`
- `archive/paperclip-plugin/src/handlers/workspace-tools.ts`
- `archive/paperclip-plugin/src/lib/agent-router.ts`
- `archive/paperclip-plugin/src/lib/logger.ts`
- `archive/paperclip-plugin/src/lib/mcp-client.ts`
- `archive/paperclip-plugin/src/lib/types.ts`
- `archive/paperclip-plugin/src/ui/UnifiedHub.tsx`
- `archive/paperclip-plugin/src/ui/components/shared/BaseUI.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/AnalyticsTab.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/CouncilTab.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/JobsTab.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/KnowledgeTab.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/LspTab.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/NetworkTab.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/OverviewTab.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/RegistryTab.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/SecurityTab.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/WorkflowsTab.tsx`
- `archive/paperclip-plugin/src/ui/components/tabs/WorkspaceTab.tsx`

## Archive (Auth Hub)

- `archive/paperclip-plugin-auth-hub/src/manifest.ts`
- `archive/paperclip-plugin-auth-hub/src/worker.ts`
- `archive/paperclip-plugin-auth-hub/src/handlers/claude.ts`
- `archive/paperclip-plugin-auth-hub/src/handlers/google.ts`
- `archive/paperclip-plugin-auth-hub/src/lib/types.ts`
- `archive/paperclip-plugin-auth-hub/src/ui/AuthDashboard.tsx`
- `archive/paperclip-plugin-auth-hub/src/ui/AuthSidebar.tsx`
- `archive/paperclip-plugin-auth-hub/src/ui/entry.ts`

## Scratch

- `scratch/analyze_scripts.py`
- `scratch/evaluate_plans.py`

## Top-level Scripts

- `.agent/scripts/clean_cycles.py`
- `.agent/scripts/sandbox_security.py`
- `.agent/scripts/test_factory.py`
- `scripts/browser-resilience.js`
- `scripts/test-dashboard.js`
