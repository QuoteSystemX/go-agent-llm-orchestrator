---
name: go-dependency-manager
description: Handles private Go dependencies for QuoteSystemX. Ensures SSH access and GOPRIVATE settings are correctly configured to prevent agent breakage.
category: Backend & API
version: 1.0.0
files: scripts/harden_go_env.py
---

# Go Dependency Manager (QuoteSystemX)

This skill ensures that Go agents can correctly resolve, download, and test private QuoteSystemX repositories (like `model-ML`).

## 🚨 CRITICAL: Environment Setup

If you are working on a Go project that depends on `github.com/QuoteSystemX/*`, you **MUST** run the hardening script first:

```bash
python3 .agent/skills/go-dependency-manager/scripts/harden_go_env.py
```

## Why this is needed
1. **Private Repos**: Go by default tries to fetch via HTTPS and fails on private QuoteSystemX repos.
2. **SSH Access**: We use SSH keys for authentication. Git must be told to use SSH instead of HTTPS.
3. **Checksum DB**: Private repos should bypass the public Google Checksum Database via `GOPRIVATE`.

## Troubleshooting
If `go test` or `go mod download` fails:
1. Verify SSH key is active: `ssh -T git@github.com`.
2. Run the hardening script again.
3. Check `go env GOPRIVATE` — it must contain `github.com/QuoteSystemX/*`.

## When to Use

- **Adding a new dependency** — `go get pkg@version`, then
  commit `go.mod` and `go.sum`.
- **Upgrading dependencies** — `go get -u ./...` for all, or
  `go get pkg@version` for one. Always run `go mod tidy` after.
- **Replacing a dependency** — `go mod edit -droprequire=old` and
  `-require=new@version`, then `go mod tidy`.
- **Vendoring** — `go mod vendor` for offline builds.
- **Reviewing dependency changes** — `git diff go.mod` should
  show only expected changes.

Avoid using this skill for:
- General Go (use `@go-patterns`).
- Module design (use `@architecture`).
- CI (use `@devops-engineer`).

## Anti-Patterns

- **Don't use `@latest` in production code** — pin to
  specific versions or use `go.work` for monorepos.
- **Don't commit without `go.sum`** — it's the integrity check.
  `go mod tidy` regenerates it.
- **Don't use `replace` directives in published modules** — only
  for local forks. They break consumers.
- **Don't ignore vulnerability warnings** — `govulncheck ./...`
  catches known CVEs.
- **Don't add a dep without checking its maintenance status** —
  is it actively maintained? Last commit date? Open issues?
- **Don't vendor without reason** — it bloats the repo. Vendor
  only if you need offline builds.

## Changelog

- **1.0.0** (2026-05-13): Initial version
