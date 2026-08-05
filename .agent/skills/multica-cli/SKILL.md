---
name: multica-cli
description: "Use when a local coding agent (Codex, Claude Code, Cursor, or similar) needs to operate Multica through the authenticated `multica` CLI: reading or updating issues, comments, metadata, projects, agents, squads, runtimes, repos, skills, autopilots, workflows, attachments, or workspace state; replying to a Multica issue from an external agent; creating or triaging issues; checking linked pull requests; or safely handling Multica mention/status side effects without relying on the Multica hosted agent runtime."
version: 1.6.0
---

# Multica CLI Reference

Use the local `multica` CLI as the source of truth. This skill teaches an external agent how to drive Multica safely; it does not grant permissions. Permissions come only from the user's installed CLI, selected profile, workspace, and explicit approval to run commands.

## Start Safely

1. Verify CLI, account state, and workspace profile:
```bash
multica version
multica auth status
multica config show
```

If `multica auth status` reports no active session, stop and request authentication:
```bash
multica login        # interactive auth + workspace setup
multica setup        # configure CLI, authenticate, and start daemon
```

2. Target the correct workspace and profile:
```bash
multica workspace list --output json                 # list available workspaces
multica workspace get [id|slug] --output json        # full workspace details, including `settings` (feature flags) — omit id for the current default workspace
multica workspace switch <workspace-id|slug>         # switch default workspace
multica workspace member list [id|slug]              # list workspace members
multica workspace update [id|slug] [--name "..."] [--description "..."] [--context "..." | --context-stdin] [--issue-prefix "..."]   # admin/owner only
multica --profile <profile> --workspace-id <id> issue list --output json
```

3. Prefer `--output json` for parsing CLI outputs programmatically.

---

## Command Reference

### 1. Issues & Comments (`issue`)
Operate issue boards, task lists, metadata, and communication threads.

```bash
# Read
multica issue get <id> --output json
multica issue list [--status <s>] [--priority <p>] [--assignee <name> | --assignee-id <uuid>] [--project <id>] [--metadata key=value] [--limit N] --output json
multica issue search <query> [--include-closed] [--limit N] --output json
multica issue children <id> --output json
multica issue pull-requests <id> --output json
multica issue runs <id> --output json
multica issue run-messages <task-id> [--issue <id>] [--since <seq>] --output json

# Manage
multica issue create --title "..." [--description "..." | --description-file <path>] [--priority <p>] [--status <s>] [--assignee <name> | --assignee-id <uuid>] [--parent <id>] [--project <id>] [--due-date YYYY-MM-DD] --output json
multica issue update <id> [--title "..."] [--priority <p>] [--status <s>] [--assignee-id <uuid>] [--parent <id> | --parent ""] [--project <id>] [--due-date YYYY-MM-DD] --output json
multica issue assign <id> [--to <name> | --to-id <uuid> | --unassign]
multica issue status <id> <backlog|todo|in_progress|in_review|done|blocked|cancelled>
multica issue cancel-task <task-id> [--issue <id>]   # interrupt an in-flight/queued agent task

# CI-loop (agent use — see "CI-auto-retry loop" section below; opt-in per workspace)
multica issue suspend <id> --sha <commit-sha> [--on ci:completed] [--max-loops N] [--on-exhaust delegate:<agent-name>] [--repo owner/name]
multica issue ci-result <id> --conclusion <success|failure|cancelled> --sha <commit-sha> [--failed-jobs job1,job2]   # manual CI report when there's no GitHub App webhook (PAT/local runner setups)
multica issue rerun <id>   # re-enqueue the issue's current agent assignment as a fresh task

# Comments
multica issue comment list <id> [--recent N] [--thread <comment-id> [--tail N]] [--since <RFC3339>] --output json
multica issue comment add <id> [--parent <comment-id>] --content "..."
multica issue comment delete <comment-id>

# Metadata (Primitive KV Map)
multica issue metadata list <id>
multica issue metadata get <id> --key <key>
multica issue metadata set <id> --key <key> --value <value> [--type <string|number|boolean>]
multica issue metadata delete <id> --key <key>

# Labels (per-issue; distinct from the top-level `label` group in section 8, which manages the workspace's label definitions)
multica issue label list <id>
multica issue label add <id> <label-id>
multica issue label remove <id> <label-id>

# Subscribers
multica issue subscriber list <id>
multica issue subscriber add <id> [--user <name>]
multica issue subscriber remove <id> [--user <name>]
```

### 2. Agents & Runtimes (`agent`, `daemon`, `runtime`)
Monitor and configure local and cluster-level AI agent assignments.

```bash
# Agent Management
multica agent list [--output json]
multica agent get <agent-id> [--output json]
multica agent create --name "..." --model "..." [--skills "skill1,skill2"]
multica agent update <agent-id> [--name "..."] [--model "..."]
multica agent archive <agent-id>
multica agent restore <agent-id>
multica agent avatar <agent-id> --file <path>

# Agent Skills & Environment Variables
multica agent skills <agent-id> [list | add <skill-id> | remove <skill-id>]
multica agent env <agent-id> [list | set <key>=<value> | delete <key>]
multica agent tasks <agent-id> [--status <s>] [--output json]

# Daemon Control
multica daemon start [--foreground] [--profile <profile>]
multica daemon stop [--profile <profile>]
multica daemon status [--output json]
multica daemon logs [-f] [-n <N>]

# Agent Runtimes
multica runtime list [--output json]
```

### 3. Squads & Projects (`squad`, `project`)
Track epics, sprints, and team compositions.

```bash
# Squad Management
multica squad list [--output json]
multica squad get <id>
multica squad create --name "..."
multica squad update <id> --name "..."
multica squad delete <id>
multica squad member <squad-id> [list | add <user-id> [--role <role>] | remove <user-id>]
multica squad activity <issue-id>  # Record squad leader evaluations on an issue

# Project Management
multica project list [--status <s>] [--output json]
multica project get <id> [--output json]
multica project create --title "..." [--description "..." | --status <s> | --icon "🏃" | --lead <name>]
multica project update <id> [--title "..." | --description "..." | --status <s> | --icon "..." | --lead <name>]
multica project status <id> <planned|in_progress|paused|completed|cancelled>
multica project delete <id>

# Project Resources (attach repos/pages for agent discovery)
multica project resource list <project-id>
multica project resource add <project-id> [--type github_repo --url <url> | --type <other> --ref '<json>'] [--label "..."] [--default-branch-hint "..."]
multica project resource remove <project-id> <resource-id>
```

### 4. Repositories & Pull Requests (`repo`)
Interact directly with linked source code repositories.

```bash
# Repository checkout and sync
multica repo checkout <url> [--ref <branch|tag|commit>]   # NOT --branch — that flag doesn't exist here
multica repo sync <url> [--ref <branch|tag|commit>]        # same as checkout; use when refreshing an already-checked-out repo
multica repo rebase <url> [--base <branch>]                 # rebase current branch onto <branch>, default "main"
multica repo push <url> [--branch <name>]                   # push current branch to origin; --branch overrides auto-detect

# Pull Request operations
multica repo pr list [--output json]
multica repo pr view <pr-id> --output json
multica repo pr create --title "..." [--body "..."] [--draft] --output json
multica repo pr checkout <url> <number>
multica repo pr merge <url> <number> [--method <merge|squash|rebase>]
```

**`repo checkout`/`repo sync` always create a NEW local branch scoped to this task**
(`agent/<your-agent-name>/<task-id>`), no matter what `--ref` you pass — `--ref` only picks the
*starting commit*, it does not rename the branch you land on. This means a plain `repo push` after
checking out an **existing open PR's branch** does NOT push to that PR by default — it pushes your
task-scoped branch under its own name, creating a brand-new branch disconnected from the PR while
you think you updated it. If the issue you're working already has one open PR, the daemon verifies
your push branch against it and rejects a mismatch — but don't rely on that alone; look up and pass
the real branch explicitly.

**Resuming an existing PR — do this, not a bare `checkout` + `push`:**
```bash
# Look up the PR's CURRENT head branch — live, not from an old comment/thread
BRANCH=$(multica issue pull-requests <issue-id> --output json \
  | jq -r '.[] | select(.state=="open") | .branch')

multica repo checkout <url> --ref "$BRANCH"
# ... fix conflicts, rebase, etc. — your local branch is still agent/<you>/<task-id> ...

# Re-check right before pushing — the PR may have moved since checkout, especially on a
# multi-step task
BRANCH=$(multica issue pull-requests <issue-id> --output json \
  | jq -r '.[] | select(.state=="open") | .branch')
multica repo push <url> --branch "$BRANCH"
```
If the issue has zero open PRs (fresh work), skip the lookup — auto-detect (`repo push <url>` with
no `--branch`) is correct for a brand-new branch that will get its own PR via `repo pr create`.

### 5. Skills (`skill`)
Deploy and configure skill definitions across workspaces.

```bash
multica skill list [--output json]
multica skill get <skill-id>
multica skill create --name "..." [--description "..."]
multica skill update <skill-id> [--name "..."] [--description "..."]
multica skill delete <skill-id>
multica skill files <skill-id> [list | upload <path> | download <file-id> <path> | delete <file-id>]
multica skill import <url>  # Import from clawhub.ai, skills.sh, or github.com
```

### 6. Autopilots (`autopilot`)
Configure background scheduling cron triggers and loops.

```bash
multica autopilot list [--status <s>] [--output json]
multica autopilot get <id> --output json
multica autopilot create --title "..." [--description "..."] --agent <id|name> --mode create_issue
multica autopilot update <id> [--status <active|paused>] [--description "..."]
multica autopilot delete <id>
multica autopilot trigger <id>  # manually fire autopilot run

# Scheduling
multica autopilot runs <id> [--limit N] --output json
multica autopilot trigger-add <autopilot-id> --cron "..." --timezone "..."
multica autopilot trigger-update <autopilot-id> <trigger-id> --enabled=false
multica autopilot trigger-delete <autopilot-id> <trigger-id>
multica autopilot trigger-rotate-url <autopilot-id> <trigger-id> [--yes]  # invalidates the current webhook URL immediately
```

### 7. Workflows (`workflow`)
Run and operate agent/squad graph automations (multi-step processes built in the Workflow canvas). Graph authoring (nodes/edges) is visual-only — this CLI covers the operational surface: list, inspect, run, watch history, manage triggers, and basic lifecycle.

```bash
multica workflow list [--status <draft|active|archived>] [--output json]
multica workflow get <id> --output json          # includes nodes/edges (read-only)
multica workflow create --name "..." [--description "..."] [--project <id|name>]
multica workflow update <id> [--name "..."] [--description "..."] [--status <draft|active>] [--agent-triggerable] [--project <id|name>]
multica workflow delete <id>  # archives — does not hard-delete
multica workflow run <id> [--payload '<json>']  # manual trigger
multica workflow runs <id> [--limit N] [--offset N] --output json

# Triggers (schedule or webhook — same contract as autopilot triggers)
multica workflow trigger-add <workflow-id> --kind <schedule|webhook> [--cron "..."] [--timezone "..."] [--label "..."]
multica workflow trigger-update <workflow-id> <trigger-id> [--enabled=false] [--cron "..."] [--timezone "..."] [--label "..."]
multica workflow trigger-delete <workflow-id> <trigger-id>
multica workflow trigger-rotate-url <workflow-id> <trigger-id> [--yes]  # invalidates the current webhook URL immediately
```

`--status active` runs full graph validation server-side (e.g. every condition node needs ≥2 outgoing edges) — a failed activation returns the validation error as-is, don't try to pre-validate client-side.

### 8. Core Config & Miscellaneous
```bash
# Setup
multica setup [self-host] [--port <p>] [--frontend-port <p>] [--server-url <url>] [--app-url <url>]

# Configuration
multica config show
multica config set <key> <value>  # server_url, app_url, workspace_id

# Other Commands
multica label [list | get <id> | create | update | delete]
multica attachment download <id> --file <path>
multica user profile [--output json]
```

---

## 🔄 Issue Status Lifecycle (`multica` CLI) — NOT Automatic

**If you are implementing a `[FEAT]`/`[BUG]`/`[STORY]` task that is tracked as a Multica issue, opening a PR does NOT move the issue's status by itself.** There is exactly one hard-coded, backend-automatic status transition in the whole system — everything else is your explicit responsibility.

### What the backend actually automates (and only this)
* `PR merged` **+** the PR title/body contains an explicit closing keyword (`Closes`, `Fixes`, `Resolves <ISSUE-ID>`) → issue auto-transitions to `done`. This works identically whether the workspace's GitHub integration uses **webhooks** or **pull-mode polling** — don't second-guess it or duplicate it with a manual `multica issue status <id> done` "just in case" on a pull-mode workspace.
* Merely mentioning the issue ID in a PR links the PR to the issue but **never** triggers a status change.
* **Opening** a PR has **no backend trigger at all**. Nothing watches for `pull_request.opened` or `ready_for_review`.

### What you must do explicitly
Run the CLI yourself at each lifecycle step:
```bash
multica issue status <id> in_progress   # when you start work
# ... implement, push, open the PR ...
multica issue status <id> in_review     # set this yourself once the PR is open!
# if you get stuck:
multica issue status <id> blocked
```

### CI-auto-retry loop (opt-in, most workspaces have this off)

Before deciding between the manual flow above and the CI-loop below, check whether this workspace has opted in:
```bash
multica workspace get --output json | jq '.settings.ci_auto_retry_loop_enabled // false'
```
* If `false` (the default — most workspaces): use the manual flow above exactly as documented.
* If `true`: instead of pushing and waiting, capture the commit SHA and register a wake condition **before** you push:
```bash
SHA=$(git rev-parse HEAD)
multica issue suspend <id> --sha "$SHA" --max-loops 3   # run BEFORE `multica repo push`
multica repo push <repo-url>
```
  This makes CI's result on that commit automatically resume you (with the failure detail, if any) instead of anyone needing to poll manually. `--on-exhaust delegate:<agent-name>` can additionally hand the issue to a specialist if the loop runs out of retries (default: issue is marked `blocked`).

**No Bash access?** An `issue_suspend` MCP tool now wraps this same suspend call for agents
running in restricted runtimes without shell access. Its ownership check is identical to the
CLI's (only the issue's current assignee may suspend it) — confirm the tool is actually present
in your live MCP tool list before relying on it (`multica-mcp` skill Rule 1: the handshake, not
this doc, is the source of truth for tool names/params). Agents with Bash access should keep
using the CLI form above; the CLI already works today and is what's proven in production.

### Pre-flight checklist before ending any Multica-issue run
* [ ] Did I create a PR? → Did I add `Closes <ISSUE-ID>` to its title/body?
* [ ] Did I run `multica issue status <id> in_review` (or `blocked`) myself?
