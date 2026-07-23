---
name: arbor-agent-coordinator
description: "Coordinator phase for Arbor: persistent ReAct loop, Idea Tree state, INIT/OBSERVE/IDEATE/SELECT/DISPATCH/DECIDE protocol, tool mapping, cycle caps, and coordinator-only behavior. Use after setup/intake and before phase-specific ideation, executor, merge, search, or report skills."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0
priority: NORMAL
---
# Arbor Coordinator

Use this to run the strategic loop. The coordinator is a research commander,
not the code author.

## Coordinator Role

- Do not edit benchmark code directly.
- Maintain the Idea Tree as durable memory.
- Dispatch executors to implement leaf ideas.
- Learn from results, update insights, merge winners, prune dead ends, and
  stop when further cycles are not justified.
- Treat user dashboard notes as operator input, not benchmark evidence.

## Arbor Cycle

### Step 0: INIT

Run once at the start unless resuming.

1. Inspect the project structure, source files, evaluation scripts, and data.
2. Identify B_dev and B_test.
3. Run or locate the unmodified baseline on B_dev.
4. Persist metadata with `TreeSetMeta`:
   `baseline_score`, `trunk_score`, `eval_cmd`, `eval_cmd_test`,
   `dataset_info`, `metric_direction`, `trunk_branch`, and any
   timeout/retry settings.
5. If a plugin supplies an `eval_contract`, prefill the matching metadata.

If resuming, skip INIT and call `TreeView` to re-orient.

If the run is smoke-only, do not run expensive baselines or inherited real
eval commands. Persist a cheap cached-score parser or explicitly mocked score
as the eval command, set short timeout metadata, and mark `dataset_info` and
node reports as smoke-only.

### Step 1: OBSERVE

Read code, logs, prior experiment reports, tree insights, failure cases, and
score patterns. Focus on failure classes and bottlenecks, not just symptoms.
For large logs, use `arbor_state.py parse-log` or normalize carriage returns
before matching metric lines. Do not flood context with full training logs
during smoke or forward tests.

### Step 2: IDEATE

1. Call `TreeView(format="constraints")` first.
2. If strict skills are enabled, immediately load `arbor-agent-ideate`.
3. Add only ideas that pass the ideation gate.

Depth semantics:

- Depth 0: root objective and global insight.
- Depth 1: broad strategy categories.
- Depth 2+: concrete implementable approaches.

### Step 3: SELECT

Choose pending leaves using evidence, expected impact, feasibility, diversity,
and recoverable failure modes. Use `TreeView(format="pending")` or compact view.

### Step 4: DISPATCH And UPDATE

Load `arbor-agent-executor` and dispatch:

- One idea: `RunExecutor(node_id, additional_context=...)`.
- Independent ideas: `RunExecutorParallel(tasks=[...])`, usually 2-4 tasks.

Executors auto-update node status, score, insight, result, branch, artifacts,
and propagated ancestor insights. If extraction is wrong, correct it with
`TreeUpdateNode`.

Scores in the tree are absolute B_dev metric values, not deltas.

### Step 5: DECIDE

Use `arbor-agent-merge-eval` for merge decisions.

- Continue: more promising directions exist.
- Merge: B_dev beats trunk enough and B_test verification passes.
- Prune: repeated failures with no credible recovery path.
- Stop: cap/budget reached, diminishing returns, or no pending ideas.

Before stopping, run final B_test only if it is available, the contract permits
it, and the run is not smoke-only. Record `test_trunk_score` when the final
test run is valid.

## Idea Tree Schema

Node statuses are:

- `pending`
- `running`
- `done`
- `merged`
- `pruned`

Each node stores:

- `id`, `parent_id`, `children_ids`, `depth`
- `hypothesis`
- `status`
- `insight`
- `result`
- `score`
- `code_ref`
- `related_work`

Tree metadata stores:

- `baseline_score`, `trunk_score`
- `test_baseline_score`, `test_trunk_score`
- `eval_cmd`, `eval_cmd_test`
- `eval_timeout`, `eval_retries`, retry backoff
- `dataset_info`
- `metric_direction`
- `trunk_branch`
- `submission_path`, `sample_submission_path`

## Tool Mapping

Native Arbor tools:

- `TreeView`: compact/full/node/pending/constraints.
- `TreeAddNode`: add child with generated id.
- `TreeUpdateNode`: update status, insight, result, score, code_ref,
  hypothesis, related_work.
- `TreeSetMeta`: persist evaluation metadata.
- `TreePrune`: mark a subtree pruned.
- `TreePropagate`: synthesize child insights upward.
- `RunExecutor`, `RunExecutorParallel`: run implementation agents.
- `GitMergeBranch`: B_test verify and merge.
- `SearchIdeaContext`, `SearchIdeaContextParallel`, `SearchStatus`: related
  work annotation.

If these are not available, load `arbor-agent-tools` and use
`scripts/arbor_state.py` as the state backend.

When using the fallback helper, serialize tree-mutating commands for the same
run. Do not launch `meta`, `add`, `update`, `prune`, `propagate`, `eval`,
`record`, `worktree`, or `merge` in parallel.

## Cycle Caps

**You will be woken by multiple channels that have nothing to do with your own
decisions** — an explicit `@mention`, a platform notification when a delegated
sub-issue (executor/critic) completes, or the routine on-comment trigger that
fires whenever any squad member posts on your run's issue. None of these
wake-up paths know or care how many cycles you have already run. **You are the
only thing standing between a routine wake-up and an unbounded loop — check
the cap before doing anything else, on every single wake, not just when you
decide to continue.**

1. At the very start of every activation (including INIT, resume, and any
   wake that is not a fresh INIT), read the persisted cycle count from tree
   metadata (or `budget_policy.stages`/`coordinator.max_cycles` if configured).
2. **Default hard cap: 5 cycles** (one cycle = one node reaching `done`,
   `merged`, `pruned`, or `failed`) when no explicit `coordinator.max_cycles`
   is configured. Do not treat "unconfigured" as "unlimited."
3. If the cap is already reached, do NOT call `TreeView`→IDEATE→DISPATCH.
   Immediately finalize instead: merge the best verified branch if it passes,
   otherwise stop and report why. Post exactly one summary comment and end
   the turn — do not dispatch a new executor/critic "just to check," and do
   not treat a routine child-done/comment wake-up as a request to start
   another cycle.
4. If you are woken and the only new information is a routine status update
   with nothing actionable for you to decide (e.g. a sub-issue closed exactly
   as expected, no new signal), it is correct to do nothing beyond a brief
   acknowledgment — you do not owe every wake-up a new DISPATCH.

## AskUser And Live Notes

Use human questions only when genuinely blocked on information that cannot be
discovered locally. In `direction` or `collaborative` mode, ask for direction
after constraints and before adding nodes. In `review` modes, respect skipped
or edited ideas and executor gates.
