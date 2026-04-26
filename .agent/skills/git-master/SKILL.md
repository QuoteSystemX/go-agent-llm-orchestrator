---
name: git-master
description: Expert-level Git operations, conflict resolution, and repository state management.
---

# Git Master Skill

This skill provides a systematic approach to complex Git operations, with a heavy emphasis on safety and conflict resolution.

## 🛡️ Safety Protocol (MANDATORY)

Before any destructive or complex Git operation (merge, rebase, reset):

### 1. Stash Uncommitted Changes

- `git stash save "Git Master: Pre-op stash"`

### 2. Create Recovery Branch

- `git branch recovery/$(date +%Y%m%d-%H%M%S)`

### 3. Verify Clean Slate

- `git status --short` should be empty (except for stashed items).

## ⚔️ Conflict Resolution Protocol

When a merge or rebase results in conflicts:

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
  - **Semantic Merge**: If changes are in different parts of the file or address different concerns, combine them.
  - **Prefer Ours**: If incoming changes are stale or redundant.
  - **Prefer Theirs**: If incoming changes are the "ground truth" (e.g., from a master branch update).
  - **Ask**: If the logic is too complex to determine safely.

### 3. Execution

- Use the `replace_file_content` or `multi_replace_file_content` tool to write the resolved version.
- **CRITICAL**: Ensure NO conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) remain in the final output.

### 4. Verification

- **Lint**: Run `python .agent/scripts/lint_runner.py` to ensure no syntax errors were introduced.
- **Test**: Run relevant tests if available.

## 🔍 History Archaeology

To understand why a conflict exists or who owns a piece of code:

- **Blame**: `git blame -L <start>,<end> <file>`
- **Log Search**: `git log -S "<string>" --oneline`
- **Branch Point**: `git merge-base <branch1> <branch2>`

## 🧹 Cleanup

After successful resolution:

1. `git add <files>`
2. `git commit -m "chore(git): resolve merge conflicts in <files>"`
3. `git stash pop` (if a stash was created)

<!-- EMBED_END -->
