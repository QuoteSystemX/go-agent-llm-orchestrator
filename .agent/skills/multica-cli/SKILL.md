---
name: multica-cli
description: "Use when a local coding agent (Codex, Claude Code, Cursor, or similar) needs to operate Multica through the authenticated `multica` CLI: reading or updating issues, comments, metadata, projects, agents, squads, runtimes, repos, skills, autopilots, workflows, attachments, or workspace state; replying to a Multica issue from an external agent; creating or triaging issues; checking linked pull requests; or safely handling Multica mention/status side effects without relying on the Multica hosted agent runtime."
version: 1.2.0
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
multica workspace switch <workspace-id|slug>         # switch default workspace
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
multica issue children <id> --output json
multica issue pull-requests <id> --output json
multica issue runs <id> --output json
multica issue run-messages <task-id> [--issue <id>] [--since <seq>] --output json

# Manage
multica issue create --title "..." [--description "..." | --description-file <path>] [--priority <p>] [--status <s>] [--assignee <name> | --assignee-id <uuid>] [--parent <id>] [--project <id>] [--due-date YYYY-MM-DD] --output json
multica issue update <id> [--title "..."] [--priority <p>] [--status <s>] [--assignee-id <uuid>] [--parent <id> | --parent ""] [--project <id>] [--due-date YYYY-MM-DD] --output json
multica issue assign <id> [--to <name> | --to-id <uuid> | --unassign]
multica issue status <id> <backlog|todo|in_progress|in_review|done|blocked|cancelled>

# Comments
multica issue comment list <id> [--recent N] [--thread <comment-id> [--tail N]] [--since <RFC3339>] --output json
multica issue comment add <id> [--parent <comment-id>] --content "..."
multica issue comment delete <comment-id>

# Metadata (Primitive KV Map)
multica issue metadata list <id>
multica issue metadata get <id> --key <key>
multica issue metadata set <id> --key <key> --value <value> [--type <string|number|boolean>]
multica issue metadata delete <id> --key <key>

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
```

### 4. Repositories & Pull Requests (`repo`)
Interact directly with linked source code repositories.

```bash
# Repository checkout and sync
multica repo checkout <repo-id> [--branch <name>]
multica repo sync             # sync working directory to remote origin
multica repo rebase           # rebase current branch against base branch
multica repo push             # push current branch to origin

# Pull Request operations
multica repo pr list [--output json]
multica repo pr view <pr-id> --output json
multica repo pr create --title "..." [--body "..."] [--draft] --output json
multica repo pr checkout <pr-id>
multica repo pr merge <pr-id> [--method <merge|squash|rebase>]
```

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

### Pre-flight checklist before ending any Multica-issue run
* [ ] Did I create a PR? → Did I add `Closes <ISSUE-ID>` to its title/body?
* [ ] Did I run `multica issue status <id> in_review` (or `blocked`) myself?
