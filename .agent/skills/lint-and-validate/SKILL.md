---
name: lint-and-validate
description: "Automatic quality control, linting, and static analysis procedures. Use after every code modification to ensure syntax correctness and project standards. Triggers onKeywords: lint, format, check, validate, types, static analysis."
allowed-tools: Read, Glob, Grep, Bash
version: 1.0.0
files: scripts/full_validate.py, scripts/lint_runner.py, scripts/type_coverage.py
---

# 🧹 Lint & Validate

Expert guidelines for maintaining code quality, consistency, and correctness through automated validation pipelines.

## 🏗 Quality Gates

Every code change must pass through a series of quality gates before being merged. This ensures that the codebase remains clean and bug-free.

### The 4 Pillars of Validation:
1. **Static Analysis**: Linter (ESLint, Flake8) to catch syntax and style issues.
2. **Type Safety**: Type checkers (TypeScript, MyPy) to prevent runtime type errors.
3. **Security Scanning**: Automated tools to find hardcoded secrets and vulnerabilities.
4. **Architectural Guardrails**: Custom scripts to verify project-specific patterns (e.g., RSC boundaries).

## 🚀 Tools & Automation

### 1. Universal Validator
Run the all-in-one validation script to check the entire project state:

```bash
python3 .agent/skills/lint-and-validate/scripts/full_validate.py
```

### 2. Self-Healing Protocol
If any linting or formatting check fails, you MUST attempt self-healing before making manual edits:

```bash
python3 .agent/scripts/dev/ci_auto_fixer.py
```

Auto-discovers changed Python files (via `git diff`, falling back to a full scan of `.agent/scripts/` if none are found), applies auto-fixable `ruff` fixes to each, and opens `tasks/ci-auto-fix-needed.md` for any issues it couldn't fix automatically. Takes no arguments.

## 📈 Quality Checklist
- [ ] Does it pass ESLint/Flake8?
- [ ] Are there any TypeScript/MyPy errors?
- [ ] Have custom validators (e.g., RSC check) been run?
- [ ] Are all new files covered by the linter?
- [ ] Is there any dead code or unused imports?

---
> **Note**: This skill ensures that Paperclip's codebase remains professional, predictable, and performant.

## Changelog

- **1.0.0** (2026-05-13): Initial version

## ❌ Anti-Patterns & Pitfalls to Avoid
- **Anti-Pattern**: Avoid implementing features without checking requirements first.
- **Anti-Pattern**: Never skip validation steps.

## Additional Quality Guidelines
To ensure the highest standard of delivery, the following additional considerations must be met:
1. Maintain consistency with existing naming conventions in the codebase.
2. Implement comprehensive error handling and logging for all new components.
3. Ensure that all dependencies are declared and verified beforehand.
4. Write clean, self-documenting code with clear comments where necessary.
5. Validate performance under load and avoid premature optimizations.
