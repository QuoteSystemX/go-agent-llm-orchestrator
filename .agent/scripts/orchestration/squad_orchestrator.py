#!/usr/bin/env python3
"""
Dynamic squad orchestrator.

Parses the agent hierarchy from .agent/agents/ metadata, builds a dependency
graph, and executes code → test → self-heal cycles.

Usage:
    python3 squad_orchestrator.py --scan-only          # print Mermaid diagram
    python3 squad_orchestrator.py --dry-run --task "..." # simulate without LLM
    python3 squad_orchestrator.py --task "..."         # full run
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import time
from typing import Any, Dict, List, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts"))

from lib.common import load_json_safe, save_json_atomic  # noqa: E402
from lib.llm_client import query_llm_safe  # noqa: E402
from orchestration.squad_schemas import AgentNode, HierarchyGraph, TaskState  # noqa: E402

logger = logging.getLogger(__name__)

AGENTS_DIR = REPO_ROOT / ".agent" / "agents"
BUS_OUTPUTS_DIR = REPO_ROOT / ".agent" / "bus" / "outputs"
ROUTER_RULES_PATH = REPO_ROOT / ".agent" / "config" / "router_rules.json"

# Local model names (all Ollama/Jan models = $0 cost)
_LOCAL_PROVIDERS = {"ollama", "jan", "lm-studio", "stub", "cache", "unknown"}


def _load_pricing() -> Dict[str, float]:
    rules = load_json_safe(ROUTER_RULES_PATH)
    return rules.get("pricing_per_1k_tokens", {})


def _estimate_cost(model: str, source: str, tokens_in: int, tokens_out: int) -> float:
    if source in _LOCAL_PROVIDERS or not model:
        return 0.0
    pricing = _load_pricing()
    rate = pricing.get(model, pricing.get("default_cloud", pricing.get("local", 0.0)))
    total_tokens = tokens_in + tokens_out
    return round(rate * total_tokens / 1000, 6)

# Roles that must never write or execute code
MANAGEMENT_ROLES: frozenset[str] = frozenset({
    "cto", "ceo", "reviewer", "product-manager", "product-owner",
    "risk-manager", "release-manager", "wiki-architect",
    "documentation-writer", "analyst", "backend-lead", "frontend-lead",
    "ml-lead", "platform-lead", "quality-security-lead", "data-lead",
    "trading-lead",
})

# Tools forbidden for management/architectural roles
FORBIDDEN_MANAGEMENT_TOOLS: frozenset[str] = frozenset({
    "write_file", "edit_file", "create_directory", "run_command",
    "Write", "Edit", "Bash",
})

_CODE_BLOCK_RE = re.compile(
    r"```(?:go|python|bash|sh|json|yaml|javascript|typescript|rust|c|cpp)\b",
    re.IGNORECASE,
)

MAX_SELF_HEAL_RETRIES = 3


# ─── AgentScanner ─────────────────────────────────────────────────────────────

class AgentScanner:
    """Recursively scans .agent/agents/ and parses YAML frontmatter into AgentNode objects."""

    def scan(self, agents_dir: Path = AGENTS_DIR) -> List[AgentNode]:
        nodes: List[AgentNode] = []
        for md_file in sorted(agents_dir.rglob("*.md")):
            node = self._parse(md_file)
            if node:
                nodes.append(node)
        logger.debug("AgentScanner: found %d agents in %s", len(nodes), agents_dir)
        return nodes

    # Frontmatter delimiter must be at the start of a line to avoid false splits
    # on YAML comments that contain '---' (e.g. "# --- Squad Leads ---").
    _FM_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)

    def _parse(self, path: Path) -> Optional[AgentNode]:
        try:
            text = path.read_text(encoding="utf-8")
            match = self._FM_RE.match(text)
            if not match:
                return None
            fm = yaml.safe_load(match.group(1)) or {}
        except Exception as exc:
            logger.debug("Skipping %s: %s", path, exc)
            return None

        name = fm.get("name", "")
        if not name:
            return None

        hierarchy = fm.get("hierarchy", {}) or {}

        tools_raw = fm.get("tools", "") or ""
        tools_clean = str(tools_raw).strip().strip("[]").strip()
        tools = [t.strip().strip('"').strip("'") for t in tools_clean.split(",") if t.strip()]

        domains_raw = fm.get("domains", "") or ""
        if isinstance(domains_raw, list):
            domains = [str(d) for d in domains_raw]
        else:
            domains_clean = str(domains_raw).strip().strip("[]").strip()
            domains = [d.strip().strip('"').strip("'") for d in domains_clean.split(",") if d.strip()]

        delegates_raw = hierarchy.get("delegates_to", []) or []
        delegates = [d for d in delegates_raw if isinstance(d, str)]

        return AgentNode(
            name=name,
            description=str(fm.get("description", "")),
            reports_to=hierarchy.get("reports_to"),
            delegates_to=delegates,
            domains=domains,
            tools=tools,
        )


# ─── GraphBuilder ─────────────────────────────────────────────────────────────

class GraphBuilder:
    """Builds a validated HierarchyGraph from a flat list of AgentNode objects."""

    def __init__(self, nodes: List[AgentNode]) -> None:
        self._nodes = nodes

    def build(self) -> HierarchyGraph:
        graph = HierarchyGraph(nodes={n.name: n for n in self._nodes})
        graph.validate_integrity()
        return graph

    def to_mermaid(self, graph: HierarchyGraph) -> str:
        lines = ["graph TD"]
        seen: set[str] = set()
        for name, node in graph.nodes.items():
            s = name.replace("-", "_")
            for delegate in node.delegates_to:
                d = delegate.replace("-", "_")
                edge = f"{s}-->{d}"
                if edge not in seen:
                    seen.add(edge)
                    lines.append(f'    {s}["{name}"] --> {d}["{delegate}"]')
        return "\n".join(lines)


# ─── ToolSandbox ──────────────────────────────────────────────────────────────

class ToolSandbox:
    """Enforces tool access policies for a given agent role."""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self._restricted = agent_name in MANAGEMENT_ROLES

    def check(self, tool_name: str) -> None:
        """Raise PermissionError if the agent is not allowed to use this tool."""
        if self._restricted and tool_name in FORBIDDEN_MANAGEMENT_TOOLS:
            raise PermissionError(
                f"[ToolSandbox] Security violation: agent '{self.agent_name}' "
                f"attempted to call forbidden tool '{tool_name}'"
            )

    def filter_tools(self, tools: List[str]) -> List[str]:
        if not self._restricted:
            return tools
        return [t for t in tools if t not in FORBIDDEN_MANAGEMENT_TOOLS]


# ─── Output Guardrails ────────────────────────────────────────────────────────

def check_output_guardrails(agent_name: str, response: str) -> Tuple[bool, str]:
    """
    Returns (passed, response).
    Management roles must not produce code blocks — violation is logged
    and (False, response) is returned so the caller can request a rewrite.
    """
    if agent_name not in MANAGEMENT_ROLES:
        return True, response

    if _CODE_BLOCK_RE.search(response):
        logger.warning(
            "[Guardrail] Management agent '%s' produced code output — violation. Rewrite required.",
            agent_name,
        )
        return False, response

    return True, response


# ─── ExecutionEngine ──────────────────────────────────────────────────────────

class ExecutionEngine:
    """
    Traverses the agent graph, routes the task from CTO → lead → specialist/QA,
    runs parallel execution, verifies with `go test -race ./...`, and self-heals
    up to MAX_SELF_HEAL_RETRIES times.
    """

    def __init__(self, graph: HierarchyGraph, dry_run: bool = False, sandbox: bool = False) -> None:
        self.graph = graph
        self.dry_run = dry_run
        self.sandbox = sandbox
        self._session_id = uuid.uuid4().hex[:12]
        self._start_time = time()
        self._trace: Dict[str, Any] = {
            "session_id": self._session_id,
            "traversal_path": [],
            "llm_calls": [],
            "verification_attempts": [],
            "final_status": "unknown",
            "total_elapsed_seconds": 0.0,
        }
        if not self.dry_run and not any("test" in arg for arg in sys.argv):
            self._harden_environment()
        # Clear dead ends registry for new session
        if not self.dry_run:
            try:
                from orchestration.dead_ends import clear_dead_ends
                clear_dead_ends()
                logger.info("[Engine] Cleared dead-ends registry for new session.")
            except Exception as e:
                logger.debug("Failed to clear dead ends: %s", e)

    def _harden_environment(self) -> None:
        logger.info("[Engine] Hardening Go environment before execution...")
        harden_script = REPO_ROOT / ".agent" / "skills" / "go-dependency-manager" / "scripts" / "harden_go_env.py"
        if harden_script.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(harden_script)],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    logger.info("[Engine] Environment hardening successful.")
                else:
                    logger.warning("[Engine] Environment hardening returned code %d: %s", result.returncode, result.stderr)
            except Exception as e:
                logger.error("[Engine] Failed to run environment hardening: %s", e)
        else:
            logger.warning("[Engine] Go hardening script not found at %s", harden_script)

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self, state: TaskState) -> TaskState:
        try:
            state = self._route_from_cto(state)
        except Exception as exc:
            logger.error("[Engine] Fatal error: %s", exc)
            state.status = "failed"
        finally:
            self._persist_trace(state)
        return state

    # ── CTO routing ───────────────────────────────────────────────────────────

    def _route_from_cto(self, state: TaskState) -> TaskState:
        cto = self.graph.nodes.get("cto")
        if not cto:
            raise ValueError("'cto' node not found in graph")

        self._visit("cto", state)

        lead_candidates = [
            n for n in cto.delegates_to
            if n in self.graph.nodes and n in MANAGEMENT_ROLES
        ]
        lead_name = self._pick_lead(state, lead_candidates) or "backend-lead"
        logger.info("[Engine] CTO → %s", lead_name)
        return self._delegate_to_lead(lead_name, state)

    def _pick_lead(self, state: TaskState, candidates: List[str]) -> Optional[str]:
        candidate_nodes = [
            self.graph.nodes[c] for c in candidates if c in self.graph.nodes
        ]
        domains_map = {n.name: n.domains for n in candidate_nodes}

        if self.dry_run:
            return candidates[0] if candidates else None

        options = "\n".join(
            f"- {name}: {', '.join(domains)}" for name, domains in domains_map.items()
        )
        prompt = (
            f"Task: {state.issue_description}\n\n"
            f"Available leads and their domains:\n{options}\n\n"
            f"Reply with ONLY the agent name (e.g. backend-lead). Nothing else."
        )
        response, _, stats = self._call_llm("cto", prompt)
        for name in domains_map:
            if name in response:
                return name
        return None

    # ── Lead delegation ───────────────────────────────────────────────────────

    def _delegate_to_lead(self, lead_name: str, state: TaskState) -> TaskState:
        if lead_name not in self.graph.nodes:
            logger.warning("[Engine] Lead '%s' not in graph, using default subtasks", lead_name)
            state.subtasks = self._default_subtasks(state)
        else:
            self._visit(lead_name, state)
            state.subtasks = self._decompose_task(lead_name, state)

        state.status = "executing"

        lead_node = self.graph.nodes.get(lead_name)
        delegates = lead_node.delegates_to if lead_node else []

        dev_agent = self._find_agent_by_keyword(delegates, "go") or "go-specialist"
        test_agent = self._find_agent_by_keyword(delegates, "test") or "test-engineer"

        self._run_parallel(state, dev_agent, test_agent)

        state.status = "testing"
        return self._verification_loop(state, dev_agent)

    def _decompose_task(self, lead_name: str, state: TaskState) -> List[Dict[str, str]]:
        if self.dry_run:
            return self._default_subtasks(state)

        prompt = (
            f"You are {lead_name}. Decompose the task into subtasks for "
            f"go-specialist (implementation) and test-engineer (tests).\n\n"
            f"Task: {state.issue_description}\n\n"
            f'Reply ONLY with a JSON array: [{{"agent":"go-specialist","task":"..."}}, ...]'
        )
        for _ in range(2):
            response, _, _ = self._call_llm(lead_name, prompt)
            ok, _ = check_output_guardrails(lead_name, response)
            if ok:
                break
            prompt = (
                f"Rewrite without code blocks. Return ONLY a JSON array of subtasks.\n"
                f"Task: {state.issue_description}"
            )

        import json as _json
        try:
            match = re.search(r"\[.*?\]", response, re.DOTALL)
            if match:
                return _json.loads(match.group())
        except Exception:
            pass

        return self._default_subtasks(state)

    @staticmethod
    def _default_subtasks(state: TaskState) -> List[Dict[str, str]]:
        return [
            {"agent": "go-specialist", "task": state.issue_description},
            {"agent": "test-engineer", "task": f"Write tests for: {state.issue_description}"},
        ]

    def _run_parallel(
        self, state: TaskState, dev_agent: str, test_agent: str
    ) -> None:
        def _execute(agent_name: str, task_desc: str) -> None:
            self._visit(agent_name, state)
            if self.dry_run:
                return
            prompt = f"You are {agent_name}. Complete the following task:\n\n{task_desc}"
            self._call_llm(agent_name, prompt)

        dev_task = next(
            (s["task"] for s in state.subtasks if s.get("agent") == dev_agent),
            state.issue_description,
        )
        test_task = next(
            (s["task"] for s in state.subtasks if s.get("agent") == test_agent),
            f"Write tests for: {state.issue_description}",
        )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                pool.submit(_execute, dev_agent, dev_task): dev_agent,
                pool.submit(_execute, test_agent, test_task): test_agent,
            }
            for future in as_completed(futures):
                agent = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    logger.error("[Engine] Agent '%s' raised: %s", agent, exc)

    # ── Verification & self-healing ───────────────────────────────────────────

    def _verification_loop(self, state: TaskState, dev_agent: str) -> TaskState:
        errors: Optional[str] = None
        for attempt in range(1, MAX_SELF_HEAL_RETRIES + 1):
            success, errors = self._run_tests()
            self._trace["verification_attempts"].append({
                "attempt": attempt,
                "command": "go test -race ./...",
                "success": success,
                "errors": errors if not success else None,
            })

            if success:
                logger.info("[Engine] Tests passed on attempt %d", attempt)
                state.status = "completed"
                state.test_results = {"attempts": attempt, "status": "passed"}
                return state

            logger.warning(
                "[Engine] Tests failed (attempt %d/%d), starting tree-based auto-healing with '%s'",
                attempt, MAX_SELF_HEAL_RETRIES, dev_agent,
            )
            if attempt < MAX_SELF_HEAL_RETRIES:
                import time as _time
                delay = 2 ** attempt
                logger.info("[Engine] Sleeping for %d seconds (exponential backoff) before tree-based auto-healing", delay)
                _time.sleep(delay)
                
                heal_success, best_patch_intent = self._tree_auto_heal(state, dev_agent, errors or "")
                if heal_success:
                    logger.info("[Engine] Tree-based auto-healing found a fix on attempt %d: %s", attempt, best_patch_intent)
                else:
                    logger.warning("[Engine] Tree-based auto-healing failed to find a fix on attempt %d", attempt)

        logger.error("[Engine] Verification exhausted after %d retries", MAX_SELF_HEAL_RETRIES)
        state.status = "failed"
        state.test_results = {
            "attempts": MAX_SELF_HEAL_RETRIES,
            "status": "failed",
            "last_errors": errors,
        }
        return state

    def _tree_auto_heal(self, state: TaskState, dev_agent: str, errors: str) -> Tuple[bool, Optional[str]]:
        """
        Generates 2-3 hypotheses and evaluates them using ghost_prototyper in worktrees.
        Returns (success, best_patch_intent).
        """
        self._visit(dev_agent, state)
        
        prompt = (
            f"You are {dev_agent}. The following tests or benchmarks failed:\n\n{errors}\n\n"
            f"Generate 2-3 alternative hypotheses/patches to resolve the issue.\n"
            f"Please explore different dimensions of the problem, including:\n"
            f"- Concurrency & Synchronization (data races, deadlock avoidance, lock contention)\n"
            f"- Edge Cases & Safety Guards (nil checks, boundary validations, empty slice handling)\n"
            f"- Performance & Leaks (minimizing memory allocations, preventing goroutine/resource leaks)\n\n"
            f"For each hypothesis, specify the file path, the exact target content block to replace, "
            f"and the replacement content.\n\n"
            f"Reply ONLY with a JSON array in the following format:\n"
            f"[\n"
            f"  {{\n"
            f"    \"intent\": \"Brief description\",\n"
            f"    \"file\": \"relative/path/to/file.go\",\n"
            f"    \"target\": \"exact original content to replace\",\n"
            f"    \"replacement\": \"new content to substitute\"\n"
            f"  }},\n"
            f"  ...\n"
            f"]\n"
        )
        
        hypotheses = []
        if self.dry_run:
            hypotheses = [
                {
                    "intent": "fix nil pointer check",
                    "file": "main.go",
                    "target": "fmt.Println(proto)",
                    "replacement": "if proto != '' { fmt.Println(proto) }"
                },
                {
                    "intent": "adjust timeout",
                    "file": "main.go",
                    "target": "timeout := 15",
                    "replacement": "timeout := 30"
                }
            ]
        else:
            response, _, _ = self._call_llm(dev_agent, prompt)
            import json as _json
            try:
                match = re.search(r"\[.*?\]", response, re.DOTALL)
                if match:
                    hypotheses = _json.loads(match.group())
            except Exception as e:
                logger.warning("[Engine] Failed to parse hypotheses JSON: %s", e)
                
        if not hypotheses:
            logger.warning("[Engine] No valid hypotheses generated.")
            return False, None

        # Determine test command to run. Default to go test -race ./...
        test_cmd = "go test -race ./..."
        if state.issue_description and any(kw in state.issue_description.lower() for kw in ["optimize", "bench", "benchmark", "performance"]):
            test_cmd = "go test -bench=. -benchmem ./..."

        baseline_metrics = {}
        if not self.dry_run and "-bench" in test_cmd:
            logger.info("[Engine] Running baseline benchmarks on trunk...")
            clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
            clean_env["GOPRIVATE"] = "github.com/QuoteSystemX/*"
            res = subprocess.run(
                test_cmd.split(),
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                env=clean_env,
                timeout=60
            )
            if res.returncode == 0:
                from analysis.ghost_prototyper import parse_go_benchmarks
                baseline_metrics = parse_go_benchmarks(res.stdout)
                logger.info("[Engine] Baseline metrics: %s", baseline_metrics)
            
        logger.info("[Engine] Generated %d hypotheses. Starting evaluation using command: %s", len(hypotheses), test_cmd)
        
        successful_candidates = []
        for i, hyp in enumerate(hypotheses):
            logger.info("[Engine] Branch %d/%d: %s on %s", i+1, len(hypotheses), hyp.get("intent"), hyp.get("file"))
            file_path = hyp.get("file", "")
            target = hyp.get("target", "")
            replacement = hyp.get("replacement", "")
            patch_repr = f"Replace:\n{target}\nWith:\n{replacement}"

            from orchestration.dead_ends import is_dead_end
            if is_dead_end(file_path, patch_repr):
                logger.warning("[Engine] Skipping hypothesis branch %d: identified as dead end", i+1)
                continue

            metrics = {}
            if self.dry_run:
                success = (i == 0 or (state.issue_description and "bench" in state.issue_description and i < 2))
                if success:
                    logger.info("[Engine] Mock verification passed!")
                    if "-bench" in test_cmd:
                        metrics = {"ns_op": 100.0 - i * 10, "b_op": 50.0 - i * 5, "allocs_op": 5.0 - i, "count": 1}
            else:
                from analysis.ghost_prototyper import run_isolated_worktree
                try:
                    success, metrics = run_isolated_worktree(
                        file_path_str=file_path,
                        target=target,
                        replacement=replacement,
                        test_cmd=test_cmd,
                        intent=hyp.get("intent", "")
                    )
                except Exception as e:
                    logger.error("[Engine] Worktree evaluation failed with exception: %s", e)
                    success, metrics = False, {}
            
            if success:
                hyp["metrics"] = metrics
                successful_candidates.append(hyp)
                
        if not successful_candidates:
            logger.warning("[Engine] All hypotheses failed to resolve the issue.")
            return False, None
            
        # Select best candidate: if benchmarks are available, compare them
        if "-bench" in test_cmd:
            # Sort by allocs_op first, then b_op, then ns_op (lower is better)
            bench_candidates = [c for c in successful_candidates if c.get("metrics", {}).get("count", 0) > 0]
            if bench_candidates:
                bench_candidates.sort(key=lambda c: (
                    c["metrics"]["allocs_op"],
                    c["metrics"]["b_op"],
                    c["metrics"]["ns_op"]
                ))
                best_candidate = bench_candidates[0]
            else:
                best_candidate = successful_candidates[0]
        else:
            best_candidate = successful_candidates[0]

        logger.info("[Engine] Selected winning hypothesis: %s (metrics: %s)", best_candidate.get("intent"), best_candidate.get("metrics"))
        return True, best_candidate.get("intent")

    def _run_tests(self) -> Tuple[bool, Optional[str]]:
        if self.dry_run:
            return True, None

        if getattr(self, "sandbox", False):
            logger.info("[Engine] Running tests inside Docker sandbox...")
            # Ensure Docker image is built
            build_res = subprocess.run(
                ["docker", "build", "-f", ".agent/config/Dockerfile.sandbox", "-t", "agent-sandbox", "."],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
            if build_res.returncode != 0:
                logger.error("[Engine] Docker sandbox build failed:\n%s", build_res.stderr)
                return False, f"Docker sandbox build failed:\n{build_res.stderr[:1000]}"

            result = subprocess.run(
                ["docker", "run", "--rm", "agent-sandbox"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
        else:
            clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
            clean_env["GOPRIVATE"] = "github.com/QuoteSystemX/*"
            result = subprocess.run(
                ["go", "test", "-race", "./..."],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                env=clean_env,
            )
        if result.returncode == 0:
            return True, None
        return False, (result.stderr + result.stdout)[:4096]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _visit(self, agent_name: str, state: TaskState) -> None:
        state.active_node = agent_name
        state.trace_path.append(agent_name)
        self._trace["traversal_path"].append(agent_name)
        logger.info("[Engine] → %s", agent_name)

    def _call_llm(
        self, agent_name: str, prompt: str
    ) -> Tuple[str, str, Dict[str, Any]]:
        # Dynamically inject relevant lessons from experience base (FOXY method)
        try:
            from knowledge.semantic_brain_engine import search_lessons
            from lib.paths import LESSONS_PATH
            
            # Use query terms from the prompt to find relevant past lessons
            matches = search_lessons(prompt, top_n=2)
            
            local_lessons = []
            if LESSONS_PATH.exists():
                content = LESSONS_PATH.read_text(encoding="utf-8")
                parts = re.split(r'\n### ', content)
                entries = parts[1:] if len(parts) > 1 else []
                
                query_terms = set(prompt.lower().split())
                for entry in entries:
                    entry_lower = entry.lower()
                    score = sum(2 if term in entry_lower else 0 for term in query_terms)
                    if score > 0:
                        local_lessons.append((score, entry.strip()))
                local_lessons.sort(key=lambda x: x[0], reverse=True)
                
            combined = []
            seen = set()
            for res in matches:
                clean_c = re.sub(r'^(##|###)\s*', '', res['content'].strip())
                if clean_c not in seen:
                    seen.add(clean_c)
                    combined.append(clean_c)
                    
            for score, entry in local_lessons[:2]:
                clean_c = re.sub(r'^(##|###)\s*', '', entry)
                if clean_c not in seen:
                    seen.add(clean_c)
                    combined.append(clean_c)
                    
            if combined:
                lessons_block = "\n> [!IMPORTANT]\n> ### 🧠 Relevant Historical Experience (FOXY method)\n"
                for lesson in combined[:2]:
                    lines = lesson.splitlines()
                    if lines:
                        lessons_block += f"> - **{lines[0]}**\n"
                        for line in lines[1:]:
                            lessons_block += f">   {line}\n"
                prompt = prompt + "\n" + lessons_block
        except Exception as e:
            logger.debug("Experience injection skipped: %s", e)

        t0 = time()
        response, source, stats = query_llm_safe(prompt=prompt)
        latency = round(time() - t0, 3)
        stats["latency_seconds"] = latency

        model = stats.get("model", "unknown")
        tokens_in = stats.get("tokens_in", stats.get("prompt_tokens", 0))
        tokens_out = stats.get("tokens_out", stats.get("completion_tokens", 0))

        self._trace["llm_calls"].append({
            "agent_name": agent_name,
            "model": model,
            "latency_seconds": latency,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "estimated_cost_usd": _estimate_cost(model, source, tokens_in, tokens_out),
        })
        return response, source, stats

    def _find_agent_by_keyword(self, names: List[str], keyword: str) -> Optional[str]:
        for name in names:
            if keyword in name:
                return name
        for name in names:
            node = self.graph.nodes.get(name)
            if node and any(keyword in d for d in node.domains):
                return name
        return None

    def _persist_trace(self, state: TaskState) -> None:
        self._trace["final_status"] = state.status
        self._trace["total_elapsed_seconds"] = round(time() - self._start_time, 3)
        BUS_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        trace_path = BUS_OUTPUTS_DIR / f"squad_trace_{self._session_id}.json"
        save_json_atomic(trace_path, self._trace)
        logger.info("[Engine] Trace → %s", trace_path)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Squad Orchestrator — dynamic agent graph execution"
    )
    p.add_argument(
        "--scan-only", action="store_true",
        help="Print the agent dependency graph as a Mermaid diagram and exit",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Simulate task execution without real LLM calls or file writes",
    )
    p.add_argument(
        "--task", type=str, default="",
        help="Task description to execute through the agent graph",
    )
    p.add_argument(
        "--sandbox", action="store_true",
        help="Run tests and validation commands inside a Docker sandbox",
    )
    return p


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
    )

    args = _build_parser().parse_args()

    scanner = AgentScanner()
    nodes = scanner.scan()
    logger.info("Scanned %d agents", len(nodes))

    builder = GraphBuilder(nodes)
    try:
        graph = builder.build()
    except ValueError as exc:
        logger.error("Graph validation failed: %s", exc)
        sys.exit(1)

    if args.scan_only:
        print(builder.to_mermaid(graph))
        return

    task = args.task.strip() or "Implement a feature (no task specified)"
    state = TaskState(issue_description=task)

    engine = ExecutionEngine(graph, dry_run=args.dry_run, sandbox=args.sandbox)
    final = engine.run(state)

    print(f"\n=== STATUS: {final.status.upper()} ===")
    print(f"Path: {' → '.join(final.trace_path)}")
    if final.test_results:
        print(f"Tests: {final.test_results}")


if __name__ == "__main__":
    main()
