---
name: arbor-agent-executor
description: "Executor-dispatch phase for Arbor. Use when implementing an Idea Tree node through RunExecutor or RunExecutorParallel semantics: isolated git worktree, executor prompt construction, eval metadata injection, RunTraining policy, smoke/full evaluation, report parsing, artifact persistence, tree update, and insight propagation."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0
priority: NORMAL
---
# Arbor Executor

Use this when a pending Idea Tree leaf is selected for implementation.

## Dispatch Contract

The executor receives:

- Isolated worktree path and experiment branch.
- Node id and exact hypothesis.
- Evaluation info from tree metadata with `{cwd}` and `{node_id}` substituted.
- Ancestor insights.
- Additional context from the coordinator.

The executor must implement the assigned idea faithfully. It may choose how to
implement the idea, but it must not silently switch to a different direction.

## Worktree Lifecycle

Native `RunExecutor` does this automatically:

1. Validate node exists and is `pending` or `running`.
2. Enforce leaf-only dispatch when `max_tree_depth` is set.
3. Mark node `running`.
4. Create a git worktree from current trunk.
5. Run the executor agent in that worktree.
6. Finalize useful code changes with a commit.
7. Snapshot plugin outputs such as `submission.csv` if configured.
8. Remove the worktree but preserve the experiment branch.
9. Parse the executor report.
10. Update the node as `done` with `score`, `insight`, `result`, and
    `code_ref`.
11. Save experiment artifacts under `experiments/<node_id>/`.
12. Propagate insights upward.

When emulating manually, do the same sequence. Use `arbor-agent-tools` for
prompt generation and tree updates.

## Executor Workflow

The executor follows this loop:

1. **Understand**: read relevant files before editing.
2. **Implement**: make the idea active in code.
3. **Validate implementation**: run 2-3 small representative checks.
4. **Iterate until solid**: fix bugs and integration misses before judging the
   idea.
5. **Evaluate**: run the full B_dev eval once implementation is credible.
6. **Report**: include changes, baseline vs result, absolute score, and
   insight.

A bad score is useful only if the implementation was correct. Do not conclude
an idea failed from broken code.

## Evaluation Rules

- Use B_dev only. Never run B_test during routine executor work.
- Use the eval command injected from metadata. It should already target the
  executor worktree after `{cwd}` substitution.
- Save results to `results/<node_id>-<brief-description>/`.
- Report absolute score, not delta.
- If full eval is expensive, run smoke/subset checks first, then full eval
  when code is correct.

In smoke-only forward tests, the executor is not a real implementer. Do not
edit source, create a real worktree, commit, run training, or run the real
eval command. Generate a smoke prompt, save it as an artifact, and record a
mocked or cached-score report that is clearly labelled as plumbing evidence
only.

## Long Commands

Use `RunTraining` semantics for long training/eval commands:

- Under 5 minutes: normal shell/Bash is acceptable.
- 5 minutes or more: use `RunTraining` or the host equivalent with a generous
  timeout.
- Do not use `sleep && tail` polling loops.
- If timeout occurs, inspect partial metrics, logs, checkpoints, and decide
  whether to resume, reduce scope, debug, or report timeout as evidence.

For MLE/Kaggle, estimate:

```text
estimated_time = epochs * sec_per_epoch * num_folds * 1.3
```

If it exceeds 70 percent of executor budget, scale down before continuing.

## Report Schema

The coordinator extracts:

```json
{
  "score": 45.2,
  "insight": "1-3 sentence key learning",
  "result": "1-2 sentence factual outcome",
  "code_ref": "experiment branch or null"
}
```

Make the final report easy to parse:

- **Idea**
- **Changes**
- **Implementation Choices**
- **Baseline vs Result**
- **Score**
- **Analysis**
- **Insights**

## Parallel Dispatch

Use parallel dispatch for 2-4 independent pending leaves. Do not parallelize
GPU-heavy or mutually competing experiments unless budget permits. Validate all
nodes before launching. Respect human review gates and cycle caps.

## Manual Emulation

If native `RunExecutor` is unavailable:

1. Create a worktree/branch or copy the repo if worktrees are unsafe.
2. Generate the prompt from the main session while substituting the executor
   worktree as `{cwd}`:
   ```bash
   python <tools>/arbor_state.py prompt-executor --cwd <project> --run-name <run> \
     --node-id <id> --workdir <worktree> \
     --output <project>/.arbor/sessions/<run>/experiments/<id>/executor_prompt.md
   ```
   For smoke/forward tests, add `--smoke` and include smoke-only additional
   context.
3. Launch a fresh agent in that worktree with the generated prompt.
4. Run B_dev from the worktree. With the fallback helper, keep session state
   in `<project>` and run the command in `<worktree>`:
   ```bash
   python <tools>/arbor_state.py eval --cwd <project> --run-name <run> \
     --split dev --exec-cwd <worktree> --cmd "<eval_cmd>" --node-id <id>
   ```
5. Capture the executor report. Before calling `record --report-file`, create
   the referenced report file. If no file exists yet, pass the report body with
   `--raw-report` instead.
6. Record outcome:
   ```bash
   python <tools>/arbor_state.py record --cwd <project> --run-name <run> \
     --node-id <id> --score <score> --insight "<insight>" \
     --result "<result>" --code-ref <branch>
   ```
7. Run `propagate` or manually update parent/root insights.

For smoke/forward tests, skip worktree creation, source edits, fresh agent
launch, and B_dev execution. Save the generated prompt under
`experiments/<node_id>/`, then use `record` with a cached or mocked report.

## Local LLM Adapter Mode (executor only)

`<tools>/local_role_adapter.py` (same directory as `arbor_state.py`) routes
the executor role through a local model via `mcp-llm-broker`'s
`execute_prompt` instead of a fresh Claude subagent:

```bash
python <tools>/local_role_adapter.py executor \
  --cwd <project> --model <local-model-name> \
  --target-file <path/to/file> \
  --instructions "<what to change>" \
  --require-prefix "---"   # optional sanity check, e.g. YAML frontmatter survived
```

Tested and confirmed working (2026-08-13, `qwen2.5-coder:14b` and
`qwen3.6-35b-a3b` via Ollama through `mcp-llm-broker`): clean single-shot
file rewrites, no stray commentary or code fences, meaning preserved. Use
this for executor nodes that are a pure "rewrite this file per these
instructions" task with no need to explore other files first.

A non-zero exit / `ok: false` from the adapter means the local model
produced an empty or otherwise unusable result — fall back to a normal
Claude-subagent executor for that node, don't treat it as a run failure.

**Do NOT use the local adapter's `judge` subcommand yet.** Tested
2026-08-13 on both models above: local judges do not discriminate reliably
between weak and strong candidates. On a real before/after pair (Claude
scored baseline 48/100, final synthesis 91/100), both local models scored
the *weak, generic baseline higher* than the improved file (14B: 92 vs 87;
35B: 86 vs 82) — the inverse of the correct ranking. Keep judge/scoring on
Claude until this is revisited (likely needs few-shot calibration examples
or chain-of-thought scoring rather than a single forced-JSON call).

**Do NOT attempt to run the coordinator (OBSERVE/IDEATE/SELECT/DECIDE) on a
local model.** Confirmed 2026-08-13: `qwen2.5-coder:14b` via the real
`arbor` CLI never emitted a real tool_call (echoed one as plain text
instead); `qwen3.6-35b-a3b` completed a correct OBSERVE tool-call sequence
but stalled at the `arbor-agent-ideate` gate's structured-reasoning
requirement (Probe Block + 4 idea moves + 5-field declaration) and ended
the session with 0 ideas. The real `arbor` binary's `LLMConfig` is also
shared by every agent role - there is no per-role provider/model override
in its CLI or config schema, so this limitation cannot be worked around by
configuration alone.
