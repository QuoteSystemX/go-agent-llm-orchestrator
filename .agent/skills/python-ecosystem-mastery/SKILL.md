---
name: python-ecosystem-mastery
description: Mastery of modern Python tooling — uv, poetry, dependency management, and build systems.
allowed-tools: Read, Write, Edit, Glob, Grep, Run
version: 1.0.0
---

# 🛠 Python Ecosystem Mastery

> Stop fighting with dependencies. Master the 2026 toolchain.

---

## 1. The `uv` Revolution (Primary)
In 2026, **`uv`** is the standard for high-performance Python development.
- **`uv sync`**: Installs everything in milliseconds.
- **`uv lock`**: Reliable lockfiles.
- **`uv run`**: Ephemeral environments for scripts.

### Pattern: Fast Scripting
```bash
# Run a script with specific dependencies without a manual venv
uv run --with httpx --with pydantic my_script.py
```

---

## 2. Dependency Governance
- **`poetry`**: Use for complex library development with multiple extras.
- **`pdm`**: Best for PEP 582 (no-venv) local development.
- **`dependency-groups`**: Use the standard `pyproject.toml` sections for dev/test/lint.

---

## 3. Build Systems & Packaging
- **`hatch`**: For modern, standards-compliant packaging.
- **`setuptools`**: Only for legacy or complex C-extensions not compatible with Hatch/Poetry.
- **`maturin`**: For shipping Rust-backed Python packages.

---

## 4. Linting & Formatting (The "Standard" Stack)
Use **`ruff`** for EVERYTHING. It replaces:
- Flake8, Isort, Black, Pylint, Autoflake, Yesqa, Bandit.

### Recommended `ruff` config:
```toml
[tool.ruff]
select = ["E", "F", "I", "N", "UP", "ASYNC", "S", "T20"]
ignore = ["D100"] # Missing docstring in public module
```

---

## 🛠 Ecosystem Scripts

| Script | Purpose |
|--------|---------|
| `uv_migrate.py` | Converts `requirements.txt` or `poetry.lock` to `uv.lock`. |
| `dependency_audit.py` | Runs `safety` and `pip-audit` against the current environment. |
| `ruff_fix_all.py` | Runs `ruff --fix` and `ruff format` on the entire project. |

## Changelog

- **1.0.0** (2026-05-13): Initial version
