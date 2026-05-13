---
name: go-dependency-manager
description: Handles private Go dependencies for QuoteSystemX. Ensures SSH access and GOPRIVATE settings are correctly configured to prevent agent breakage.
category: Backend & API
version: 1.0.0
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

## Changelog

- **1.0.0** (2026-05-13): Initial version
