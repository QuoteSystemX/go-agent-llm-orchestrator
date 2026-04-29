---
name: lint-and-validate
description: Automatic quality control, linting, and static analysis procedures. Use after every code modification to ensure syntax correctness and project standards. Triggers onKeywords: lint, format, check, validate, types, static analysis.
allowed-tools: Read, Glob, Grep, Bash
version: 1.0.0
---

# Lint and Validate Skill

> **MANDATORY:** Run appropriate validation tools after EVERY code change. Do not finish a task until the code is error-free.

### Procedures by Ecosystem

#### Node.js / TypeScript
1. **Lint/Fix:** `npm run lint` or `npx eslint "path" --fix`
2. **Types:** `npx tsc --noEmit`
3. **Security:** `npm audit --audit-level=high`

#### Python
1. **Linter (Ruff):** `ruff check "path" --fix` (Fast & Modern)
2. **Security (Bandit):** `bandit -r "path" -ll`
3. **Types (MyPy):** `mypy "path"`

## 🛠 Self-Healing Protocol (MANDATORY)

If any linting or formatting check fails, you MUST attempt self-healing before making manual edits:

1. **Invoke Self-Heal**: `python3 .agent/scripts/self_heal.py .`
2. **Review Result**: If it returns `SUCCESS`, verify that the code still functions correctly.
3. **Manual Fix**: Only if `self_heal.py` cannot fix the remaining errors, proceed with manual code corrections.

---

## The Quality Loop
1. **Write/Edit Code**
2. **Run Self-Heal**: `python3 .agent/scripts/self_heal.py .`
3. **Analyze Master Checklist**: `python3 .agent/scripts/checklist.py .`
4. **Fix & Repeat**: Submitting code with failures in the Master Checklist is NOT allowed.

---

## Error Handling
- If `lint` fails: Fix the style or syntax issues immediately.
- If `tsc` fails: Correct type mismatches before proceeding.
- If no tool is configured: Check the project root for `.eslintrc`, `tsconfig.json`, `pyproject.toml` and suggest creating one.

---
**Strict Rule:** No code should be committed or reported as "done" without passing these checks.

---

## Scripts

| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/lint_runner.py` | Unified lint check | `python scripts/lint_runner.py <project_path>` |
| `scripts/type_coverage.py` | Type coverage analysis | `python scripts/type_coverage.py <project_path>` |

## Changelog

- **1.0.0** (2026-04-26): Initial version
