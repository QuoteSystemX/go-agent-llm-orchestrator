#!/usr/bin/env python3
"""
Headroom Compression Benchmark
Tests compression ratios on realistic agent conversation histories
that Antigravity Kit agents produce in real sessions.
"""

import json
import sys
import time
from pathlib import Path

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:
    def count_tokens(text: str) -> int:
        return len(text) // 4

try:
    import headroom
    from headroom import compress, CompressConfig, SmartCrusher, SmartCrusherConfig, WasteSignals
    HEADROOM_AVAILABLE = True
except ImportError:
    HEADROOM_AVAILABLE = False

MODEL = "claude-sonnet-4-6"

# ─── Message Fixtures ──────────────────────────────────────────────────────────
# Each fixture returns a list[dict] — an Anthropic-format conversation
# that mirrors what a real agent session looks like.

def msg_user(text: str) -> dict:
    return {"role": "user", "content": text}

def msg_assistant(text: str) -> dict:
    return {"role": "assistant", "content": text}

def msg_tool_result(content: str) -> dict:
    return {"role": "user", "content": [{"type": "tool_result", "content": content}]}


def scenario_grep_heavy() -> tuple[str, list[dict]]:
    """Debugger runs grep across 8 packages — 40 matches returned."""
    matches = []
    pkgs = ["handler", "service", "repository", "middleware", "config", "router", "auth", "cache"]
    for pkg in pkgs:
        for i in range(5):
            matches.append({
                "file": f"internal/{pkg}/{pkg}_{i}.go",
                "line": 20 + i * 18,
                "content": (
                    f"func (h *{pkg.capitalize()}Handler) Process{i}(ctx context.Context, req *Request) (*Response, error) {{\n"
                    f"    span := tracer.Start(ctx, \"{pkg}.Process{i}\")\n"
                    f"    defer span.End()\n"
                    f"    if err := h.validate(req); err != nil {{\n"
                    f"        return nil, fmt.Errorf(\"{pkg}: validate: %w\", err)\n"
                    f"    }}\n"
                    f"    return h.{pkg}Svc.Execute{i}(ctx, req)\n"
                    f"}}"
                )
            })
    tool_output = json.dumps(matches, indent=2)
    messages = [
        msg_user("Find all handler functions across internal packages"),
        msg_assistant("Running grep across all internal packages..."),
        msg_tool_result(tool_output),
        msg_assistant("Found 40 handler functions. Analyzing patterns..."),
        msg_user("Which ones lack error handling?"),
    ]
    return "Grep-heavy session (debugger)", messages


def scenario_stack_trace_loop() -> tuple[str, list[dict]]:
    """SRE/War Room: 3 iterations of panic analysis with full traces."""
    trace = (
        "goroutine 1 [running]:\nruntime/debug.Stack()\n"
        "\t/usr/local/go/src/runtime/debug/stack.go:24 +0x5b\n\n"
    )
    frames = [
        ("github.com/QuoteSystemX/RecipientOFQuotes/internal/handler", "ProcessQuote", "handler.go", 142),
        ("github.com/QuoteSystemX/RecipientOFQuotes/internal/service", "ValidateAndExecute", "service.go", 87),
        ("github.com/QuoteSystemX/RecipientOFQuotes/internal/repository", "FindQuoteByID", "repo.go", 203),
        ("github.com/QuoteSystemX/RecipientOFQuotes/internal/db", "QueryContextWithRetry", "db.go", 55),
        ("database/sql", "(*DB).QueryContext", "sql.go", 1691),
        ("database/sql", "ctxDriverQuery", "ctxutil.go", 89),
        ("github.com/lib/pq", "(*conn).query", "conn.go", 411),
        ("net", "(*Resolver).lookupHostOS", "lookup_unix.go", 43),
        ("runtime", "goexit", "asm_amd64.s", 1598),
    ]
    for pkg, fn, file, line in frames:
        trace += f"{pkg}.{fn}(...)\n\t/home/runner/work/RecipientOFQuotes/{file}:{line} +0x1c3\n"
    trace += "\npanic: runtime error: invalid memory address or nil pointer dereference\n"
    trace += "[signal SIGSEGV: segmentation violation code=0x1 addr=0x0 pc=0x5a3f21]\n"

    messages = [
        msg_user("Production panic in RecipientOFQuotes. Analyze and fix."),
        msg_assistant("Fetching pod logs..."),
        msg_tool_result(trace),
        msg_assistant("I see a nil pointer in ProcessQuote. Checking the handler..."),
        msg_tool_result(trace),  # same trace appears again from second pod
        msg_assistant("Both pods show the same stack. The issue is in repository.FindQuoteByID."),
        msg_tool_result(trace),  # third occurrence from alertmanager
        msg_user("What's the root cause?"),
    ]
    return "Stack trace loop (War Room SRE)", messages


def scenario_build_log_analysis() -> tuple[str, list[dict]]:
    """CI/CD analysis: full build log from a failing pipeline."""
    log_lines = []
    packages = [
        "github.com/QuoteSystemX/go-agent-llm-orchestrator/pkg/router",
        "github.com/QuoteSystemX/go-agent-llm-orchestrator/pkg/handler",
        "github.com/QuoteSystemX/go-agent-llm-orchestrator/pkg/service",
        "github.com/QuoteSystemX/go-agent-llm-orchestrator/pkg/repository",
        "github.com/QuoteSystemX/go-agent-llm-orchestrator/pkg/middleware",
        "github.com/QuoteSystemX/go-agent-llm-orchestrator/pkg/config",
        "github.com/QuoteSystemX/go-agent-llm-orchestrator/internal/auth",
        "github.com/QuoteSystemX/go-agent-llm-orchestrator/internal/cache",
    ]
    for pkg in packages:
        log_lines.append(f"# {pkg}")
        for i in range(12):
            log_lines.append(f"  [{i+1:02d}/12] compiling {pkg.split('/')[-1]}_{i}.go")
        log_lines.append(f"ok  \t{pkg}\t0.{len(pkg) % 9}42s")

    log_lines += [
        "",
        "FAIL\tgithub.com/QuoteSystemX/go-agent-llm-orchestrator/pkg/router [build failed]",
        "./router/router.go:142:3: undefined: handleTimeout",
        "./router/router.go:156:15: too many arguments in call to route.Match",
        "./router/router.go:178:9: cannot use req (type *fasthttp.RequestCtx) as type *http.Request",
        "",
        "FAIL\tgithub.com/QuoteSystemX/go-agent-llm-orchestrator [build failed]",
        "exit status 1",
    ]
    build_log = "\n".join(log_lines)

    messages = [
        msg_user("CI pipeline is failing. Here's the build log. What's wrong?"),
        msg_tool_result(build_log),
        msg_assistant("The build fails in pkg/router due to undefined handleTimeout and type mismatch."),
        msg_tool_result(build_log),  # re-fetched after attempted fix
        msg_user("Still failing. Check again."),
    ]
    return "Build log analysis (CI/CD)", messages


def scenario_api_spec_review() -> tuple[str, list[dict]]:
    """Frontend specialist reviews large OpenAPI spec for 6 endpoints."""
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "QuoteSystem API", "version": "2.1.0"},
        "components": {
            "schemas": {
                "Quote": {"type": "object", "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "amount": {"type": "number", "format": "double"},
                    "currency": {"type": "string", "enum": ["USD", "EUR", "GBP"]},
                    "status": {"type": "string", "enum": ["PENDING", "ACTIVE", "EXPIRED", "SETTLED"]},
                    "created_at": {"type": "string", "format": "date-time"},
                    "expires_at": {"type": "string", "format": "date-time"},
                    "metadata": {"type": "object", "additionalProperties": True},
                }},
            }
        },
        "paths": {}
    }
    for ep in ["quotes", "recipients", "providers", "settlements", "analytics", "audit", "webhooks", "tokens"]:
        spec["paths"][f"/api/v2/{ep}"] = {}
        for method in ["get", "post", "put", "delete", "patch"]:
            spec["paths"][f"/api/v2/{ep}"][method] = {
                "operationId": f"{method}_{ep}",
                "summary": f"{method.upper()} {ep}",
                "description": (
                    f"Handles {method.upper()} operations on the {ep} collection. "
                    f"Requires Bearer authentication. Rate limited 1000 req/min per API key. "
                    f"Returns JSON with cursor-based pagination. Cache-Control: max-age=60."
                ),
                "parameters": [
                    {"name": "Authorization", "in": "header", "required": True, "schema": {"type": "string"}},
                    {"name": "X-Request-ID", "in": "header", "schema": {"type": "string", "format": "uuid"}},
                    {"name": "X-Idempotency-Key", "in": "header", "schema": {"type": "string"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20, "maximum": 100}},
                    {"name": "cursor", "in": "query", "schema": {"type": "string"}},
                    {"name": "sort", "in": "query", "schema": {"type": "string", "enum": ["asc", "desc"]}},
                ],
                "responses": {
                    "200": {"description": "Success"},
                    "201": {"description": "Created"},
                    "400": {"description": "Bad Request", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
                    "401": {"description": "Unauthorized"},
                    "403": {"description": "Forbidden"},
                    "404": {"description": "Not Found"},
                    "409": {"description": "Conflict"},
                    "429": {"description": "Rate Limited"},
                    "500": {"description": "Internal Server Error"},
                },
            }

    messages = [
        msg_user("Review this OpenAPI spec for consistency and missing auth patterns."),
        msg_tool_result(json.dumps(spec, indent=2)),
        msg_assistant("Analyzing 8 endpoints × 5 methods = 40 operations..."),
        msg_user("Which endpoints are missing idempotency keys?"),
        msg_tool_result(json.dumps(spec, indent=2)),  # re-read for second analysis pass
    ]
    return "API spec review (frontend specialist)", messages


def scenario_test_run_output() -> tuple[str, list[dict]]:
    """Test engineer: verbose pytest/gotest output with many passing tests."""
    test_output = "=== RUN   TestSuite\n"
    test_cases = [
        ("TestHandlerProcess", "0.042s", True),
        ("TestHandlerValidate", "0.018s", True),
        ("TestHandlerAuthenticate", "0.091s", True),
        ("TestServiceExecute", "0.034s", True),
        ("TestServiceCalculate", "0.022s", True),
        ("TestRepositoryFind", "0.187s", True),
        ("TestRepositoryCreate", "0.203s", True),
        ("TestRepositoryUpdate", "0.195s", True),
        ("TestRepositoryDelete", "0.178s", True),
        ("TestMiddlewareAuth", "0.009s", True),
        ("TestMiddlewareRateLimit", "0.012s", True),
        ("TestMiddlewareCORS", "0.007s", True),
        ("TestIntegrationQuoteFlow", "1.420s", True),
        ("TestIntegrationRecipientFlow", "1.203s", True),
        ("TestIntegrationSettlementFlow", "0.987s", False),
        ("TestE2EQuoteLifecycle", "3.401s", True),
    ]
    for name, duration, passed in test_cases:
        status = "PASS" if passed else "FAIL"
        test_output += f"--- {status}: {name} ({duration})\n"
        if not passed:
            test_output += (
                f"    settlement_test.go:142: expected status SETTLED, got PENDING\n"
                f"    settlement_test.go:143: quote ID: 550e8400-e29b-41d4-a716-446655440000\n"
                f"    settlement_test.go:144: timeout after 30s waiting for settlement confirmation\n"
            )
    test_output += f"\nFAIL\tgithub.com/QuoteSystemX/RecipientOFQuotes\t7.814s\n"
    test_output = test_output * 3  # same suite re-run 3 times

    messages = [
        msg_user("Tests are failing. Run the test suite and fix the settlement test."),
        msg_tool_result(test_output),
        msg_assistant("TestIntegrationSettlementFlow is failing with a timeout. Investigating..."),
        msg_tool_result(test_output),
        msg_assistant("Found the issue. The settlement timeout is 30s but the mock takes 35s."),
        msg_tool_result(test_output),  # after fix attempt
        msg_user("Is it fixed?"),
    ]
    return "Test suite analysis (test-engineer)", messages


def scenario_agent_bus_history() -> tuple[str, list[dict]]:
    """Orchestrator reads full bus dump with 15 completed agent tasks."""
    bus_objects = []
    agents = ["backend-specialist", "test-engineer", "debugger", "frontend-specialist"]
    task_types = ["verification_result", "code_chunk", "incident", "state_snapshot"]
    for i in range(15):
        bus_objects.append({
            "id": f"bus_obj_{i:04d}",
            "type": task_types[i % 4],
            "author": agents[i % 4],
            "status": "COMPLETED",
            "timestamp": f"2026-06-07T{9 + i//4:02d}:{(i*7)%60:02d}:00Z",
            "content": {
                "summary": f"Task {i} completed: analyzed {142 + i*10} files, found {i*2} issues",
                "findings": [
                    {
                        "severity": ["HIGH", "MEDIUM", "LOW"][j % 3],
                        "file": f"src/module_{i}/handler_{j}.go",
                        "line": j * 15 + 20,
                        "issue": "potential nil dereference" if j % 2 == 0 else "missing error propagation",
                        "suggestion": "Add nil check before pointer dereference and propagate error up the call stack",
                        "code_before": f"result := handler.Process(ctx)\nreturn result.Data",
                        "code_after": f"result, err := handler.Process(ctx)\nif err != nil {{ return nil, err }}\nif result == nil {{ return nil, ErrNilResult }}\nreturn result.Data, nil",
                    }
                    for j in range(4)
                ],
                "metrics": {
                    "files_scanned": 142 + i * 10,
                    "issues_found": i * 2,
                    "test_coverage": f"{72 + i}%",
                    "duration_ms": 850 + i * 120,
                    "tokens_used": 12000 + i * 800,
                },
            },
        })

    messages = [
        msg_user("Give me a status report on all running agents."),
        msg_tool_result(json.dumps(bus_objects, indent=2)),
        msg_assistant("15 tasks completed. 3 HIGH severity findings need attention."),
        msg_user("Focus on HIGH severity items. Re-read bus and summarize."),
        msg_tool_result(json.dumps(bus_objects, indent=2)),
    ]
    return "Agent Bus history (orchestrator)", messages


# ─── Benchmark Engine ──────────────────────────────────────────────────────────

def analyze_waste(messages: list[dict]) -> dict:
    """Run WasteSignals analysis on the raw message content."""
    full_text = " ".join(
        c if isinstance(c, str) else
        (c[0]["content"] if isinstance(c, list) and c else "")
        for m in messages
        for c in [m.get("content", "")]
    )
    try:
        ws = WasteSignals(full_text)
        return {
            "repetition": ws.repetition_tokens,
            "json_bloat": ws.json_bloat_tokens,
            "whitespace": ws.whitespace_tokens,
        }
    except Exception:
        return {}


def run_scenario(
    label: str,
    messages: list[dict],
    config: "CompressConfig",
) -> dict:
    tokens_in = sum(
        count_tokens(
            m["content"] if isinstance(m["content"], str)
            else (m["content"][0].get("content", "") if isinstance(m["content"], list) else "")
        )
        for m in messages
    )

    t0 = time.perf_counter()
    result = compress(messages, model=MODEL, config=config)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    tokens_out = result.tokens_after if result.tokens_after else sum(
        count_tokens(
            m["content"] if isinstance(m["content"], str)
            else (m["content"][0].get("content", "") if isinstance(m["content"], list) else "")
        )
        for m in result.messages
    )

    if tokens_out == 0:
        tokens_out = tokens_in

    saved = tokens_in - tokens_out
    ratio = saved / tokens_in * 100 if tokens_in > 0 else 0.0
    transforms = result.transforms_applied or []

    waste = analyze_waste(messages)

    return {
        "label": label,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "saved": saved,
        "ratio_pct": ratio,
        "transforms": ", ".join(transforms[:3]) if transforms else "none",
        "elapsed_ms": elapsed_ms,
        "waste": waste,
    }


def print_report(results: list[dict], config_name: str) -> None:
    W = 80
    print()
    print("=" * W)
    print(f"  HEADROOM BENCHMARK  —  Antigravity Kit Agent Sessions  [{config_name}]")
    print("=" * W)
    hdr = f"{'Scenario':<38} {'Tok In':>7} {'Tok Out':>8} {'Saved':>7} {'Ratio':>7}"
    print(hdr)
    print("-" * W)

    total_in = total_out = 0
    for r in results:
        ratio_str = f"{r['ratio_pct']:.1f}%"
        flag = "✅" if r["ratio_pct"] >= 40 else ("🟡" if r["ratio_pct"] >= 15 else "⚪")
        row = (
            f"{r['label']:<38} {r['tokens_in']:>7,} {r['tokens_out']:>8,} "
            f"{r['saved']:>7,} {ratio_str:>7}  {flag}"
        )
        print(row)
        total_in += r["tokens_in"]
        total_out += r["tokens_out"]

    total_saved = total_in - total_out
    total_ratio = total_saved / total_in * 100 if total_in else 0
    avg_ms = sum(r["elapsed_ms"] for r in results) / len(results)

    print("-" * W)
    print(f"{'TOTAL':<38} {total_in:>7,} {total_out:>8,} {total_saved:>7,} {total_ratio:.1f}%")
    print("=" * W)

    print(f"\n  Total savings:   {total_saved:,} tokens  ({total_ratio:.1f}% reduction)")
    print(f"  Avg latency:     {avg_ms:.1f} ms per scenario")

    cost_without = total_in / 1_000_000 * 3.0
    cost_with    = total_out / 1_000_000 * 3.0
    print(f"\n  Cost estimate (Sonnet @ $3 / 1M input tokens):")
    print(f"    Without Headroom :  ${cost_without:.5f}")
    print(f"    With Headroom    :  ${cost_with:.5f}")
    print(f"    Saved            :  ${cost_without - cost_with:.5f} per benchmark run")
    print()


def main():
    if not HEADROOM_AVAILABLE:
        print("❌  headroom-ai not installed. Run: pip install 'headroom-ai[mcp]>=0.23.0'")
        sys.exit(1)

    print(f"\n  headroom v{headroom.__version__} | tiktoken token counting")

    scenarios_fns = [
        scenario_grep_heavy,
        scenario_stack_trace_loop,
        scenario_build_log_analysis,
        scenario_api_spec_review,
        scenario_test_run_output,
        scenario_agent_bus_history,
    ]

    configs = [
        ("default (protect_recent=4)", CompressConfig(
            compress_user_messages=True,
            protect_recent=4,
        )),
        ("aggressive (target_ratio=0.25)", CompressConfig(
            compress_user_messages=True,
            protect_recent=1,
            target_ratio=0.25,
        )),
    ]

    for config_name, config in configs:
        results = []
        for fn in scenarios_fns:
            label, messages = fn()
            r = run_scenario(label, messages, config)
            results.append(r)
        print_report(results, config_name)

    # SmartCrusher standalone (JSON arrays) — separate section
    print("=" * 80)
    print("  SMARTCRUSHER — JSON Array Tool Outputs (standalone)")
    print("=" * 80)
    hdr = f"{'Content':<40} {'Tok In':>7} {'Tok Out':>8} {'Saved':>7} {'Ratio':>7}"
    print(hdr)
    print("-" * 80)

    crusher = SmartCrusher(SmartCrusherConfig(
        min_tokens_to_crush=50,
        max_items_after_crush=10,
        dedup_identical_items=True,
    ))

    grep_json = json.dumps([{
        "file": f"src/pkg_{i%8}/handler_{i}.go", "line": i*12, "match": "func Handle",
        "context": f"func Handle{i}(ctx context.Context) (*Resp, error) {{ return svc.Execute{i}(ctx) }}",
        "score": round(0.99 - i*0.01, 2)} for i in range(40)], indent=2)
    json_fixtures = [
        ("Grep results (40 matches)",      grep_json, "Handle function"),
        ("Bus objects (15 items)",         json.dumps([
            {"id": f"obj_{i}", "type": "verification_result", "author": "test-engineer",
             "status": "COMPLETED", "findings": [{"sev": "HIGH", "file": f"handler_{j}.go"} for j in range(5)],
             "metrics": {"files": 142, "issues": i*2, "coverage": f"{70+i}%"}}
            for i in range(15)], indent=2), "verification findings"),
        ("OpenAPI paths (8 endpoints)",    json.dumps([
            {"path": f"/api/v2/{ep}", "methods": ["GET","POST","PUT","DELETE"],
             "auth": "Bearer", "rate_limit": "1000/min", "pagination": "cursor",
             "params": ["limit", "cursor", "sort", "filter"],
             "responses": {str(c): "see spec" for c in [200,201,400,401,403,404,429,500]}}
            for ep in ["quotes","recipients","providers","settlements","analytics","audit","webhooks","tokens"]
        ], indent=2), "authentication requirements"),
    ]

    sc_total_in = sc_total_out = 0
    for label, content, query in json_fixtures:
        tokens_in = count_tokens(content)
        result = crusher.crush_array_json(content, query=query)
        out_text = str(result.get("items", content))
        dropped = result.get("dropped_summary", "")
        if dropped:
            out_text += "\n" + dropped
        tokens_out = count_tokens(out_text)
        saved = tokens_in - tokens_out
        ratio = saved / tokens_in * 100 if tokens_in else 0
        flag = "✅" if ratio >= 40 else ("🟡" if ratio >= 15 else "⚪")
        print(f"{label:<40} {tokens_in:>7,} {tokens_out:>8,} {saved:>7,} {ratio:>6.1f}%  {flag}")
        sc_total_in += tokens_in
        sc_total_out += tokens_out

    sc_saved = sc_total_in - sc_total_out
    sc_ratio = sc_saved / sc_total_in * 100 if sc_total_in else 0
    print("-" * 80)
    print(f"{'TOTAL':<40} {sc_total_in:>7,} {sc_total_out:>8,} {sc_saved:>7,} {sc_ratio:>6.1f}%")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
