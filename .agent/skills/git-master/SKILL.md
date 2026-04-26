---
name: git-master
description: Expert-level Git operations, conflict resolution, and repository state management. Universal — works in Antigravity (Gemini) and Claude Code.
version: 1.0.0
---

# Git Master Skill

Systematic approach to complex Git operations with heavy emphasis on safety, conflict resolution, and history archaeology.

## 🛡️ Safety Protocol (MANDATORY)

Before any destructive or complex Git operation (merge, rebase, reset, cherry-pick):

### 1. Stash Uncommitted Changes

```bash
git stash save "Git Master: Pre-op stash $(date +%Y%m%d-%H%M%S)"
```

### 2. Create Recovery Branch

```bash
git branch recovery/$(date +%Y%m%d-%H%M%S)
```

### 3. Verify Clean Slate

```bash
git status --short  # must be empty (except stashed items)
```

---

## ⚔️ Conflict Resolution Protocol

### 1. Discovery

Locate all conflicting files:

```bash
grep -rl "^<<<<<<< " .
```

### 2. File-by-File Analysis

For each conflicting file:

- **Read the file**: Identify the blocks between `<<<<<<<`, `=======`, and `>>>>>>>`.
- **Identify Intent**:
  - `HEAD` (Current/Ours): Changes already in your branch.
  - `Incoming` (Theirs): Changes being merged/rebased in.
- **Resolution Strategy**:
  - **Semantic Merge**: If changes address different concerns, combine them.
  - **Prefer Ours**: If incoming changes are stale or redundant.
  - **Prefer Theirs**: If incoming changes are ground truth (e.g., from main).
  - **Ask**: If logic is too complex to determine safely.

### 3. Execution

Use the `Edit` or `Write` tool to write the resolved version.

**CRITICAL**: Ensure NO conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) remain in the final output.

### 4. Verification

```bash
# Check no markers remain
grep -rn "^<<<<<<< \|^=======$\|^>>>>>>> " . --include="*.go" --include="*.ts" --include="*.py" --include="*.md"

# Run relevant tests
go test ./... -race   # Go projects
npm test              # Node.js projects
```

---

## 🔍 History Archaeology

Understanding why a conflict exists or who owns a piece of code:

```bash
# Who changed this line and when
git blame -L <start>,<end> <file>

# Find when a string was introduced or removed
git log -S "<string>" --oneline --all

# Find branch divergence point
git merge-base <branch1> <branch2>

# Full diff since divergence
git diff $(git merge-base main HEAD)..HEAD

# Search commit messages
git log --grep="<keyword>" --oneline
```

---

## 🚨 Advanced Operations

### Bisect (find which commit introduced a bug)

```bash
git bisect start
git bisect bad HEAD          # current commit is broken
git bisect good <known-good> # last known working commit
# Git checks out midpoints; test each, then:
git bisect good  # or git bisect bad
# Until git identifies the culprit commit
git bisect reset  # restore HEAD when done
```

### Reflog (recover from disasters)

```bash
# See every HEAD movement (your safety net)
git reflog --date=iso | head -30

# Recover a deleted branch
git checkout -b recovered-branch <sha-from-reflog>

# Undo a bad rebase
git reset --hard HEAD@{N}  # N = position before rebase in reflog
```

### Worktree (work on multiple branches simultaneously)

```bash
# Create a worktree for a hotfix without disturbing current work
git worktree add ../hotfix-tree hotfix/critical-bug

# List active worktrees
git worktree list

# Remove when done
git worktree remove ../hotfix-tree
```

### Cherry-pick (apply specific commits)

```bash
# Apply single commit
git cherry-pick <sha>

# Apply range
git cherry-pick <sha1>..<sha2>

# If conflict during cherry-pick
git cherry-pick --continue  # after resolving
git cherry-pick --abort     # to cancel
```

### Interactive Rebase (clean history before PR)

```bash
# Squash last N commits
git rebase -i HEAD~N

# Reword, squash, fixup, drop — edit the pick lines
# Then: git push --force-with-lease (safer than --force)
```

---

## 🧹 Cleanup After Resolution

```bash
git add <resolved-files>
git commit -m "chore(git): resolve merge conflicts in <files>"
git stash pop  # restore stashed changes if any
git branch -d recovery/<timestamp>  # delete recovery branch if all good
```

---

## 🤝 Handoff Matrix

| Situation | Next Agent | What to pass |
|-----------|------------|--------------|
| Resolution introduced a regression | `debugger` | Conflicting file + resolution logic |
| PR needs final audit after merge | `reviewer` | Resolved branch name |
| Conflict is architectural (e.g., schema + API changed together) | `orchestrator` | Summary of both sides' intent |
| Conflict in test files | `test-engineer` | Conflicting test file + context |



## Changelog

- **1.0.0** (2026-04-26): Initial version
<!-- EMBED_END -->
