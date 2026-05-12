---
trigger: always_on
---

# 🛡️ QuoteSystemX Go Dependency Management

> **MANDATORY**: For all Go projects within the QuoteSystemX organization.

## 🚨 Problem Statement
Agents often fail to resolve or test Go projects that depend on private repositories (e.g., `model-ML`) because of missing environment configuration or SSH/HTTPS mismatches.

## 🛠 Required Protocol
Whenever an agent is tasked with **testing, building, or modifying** a Go project that has dependencies on `github.com/QuoteSystemX/*`:

1.  **Load Skill**: Immediately read `@[skills/go-dependency-manager]`.
2.  **Harden Environment**: Execute the hardening script BEFORE running any `go` or `git` commands:
    ```bash
    python3 .agent/skills/go-dependency-manager/scripts/harden_go_env.py
    ```
    *   **CI/CD**: The script auto-detects `GH_TOKEN` or `GITHUB_TOKEN` and uses HTTPS auth.
    *   **Local**: Falls back to SSH (`git@github.com:`) if no token is found.
3.  **Persist Context**: If the agent is handing off work or starting a new phase, verify that `GOPRIVATE` is still set and the Git configuration is intact.

## 🔍 Examples of Breakage
- `go test ./...` returns 401/403 or "repository not found".
- `go mod tidy` fails to fetch `github.com/QuoteSystemX/model-ML`.
- Linter fails because it cannot resolve internal library types.

**Solution**: Run `harden_go_env.py`.
