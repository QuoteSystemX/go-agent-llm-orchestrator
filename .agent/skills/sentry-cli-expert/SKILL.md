---
name: sentry-cli-expert
description: Advanced usage of Sentry CLI for monitoring application health, managing releases, triaging issues, and integrating error tracking into CI/CD pipelines.
version: 2.0.0
---

# 🕵️‍♂️ Sentry CLI Expert

Expert guidelines for monitoring application health and managing releases using the Sentry CLI.

---

## 📌 When To Use This Skill

Activate this skill when:
- Setting up Sentry release tracking in a CI/CD pipeline.
- Uploading source maps for readable stack traces in production.
- Triaging and filtering issues programmatically via the Sentry CLI.
- Configuring Sentry authentication and project defaults securely.

---

## 🚀 Release Management

```bash
# 1. Create a new release
sentry-cli releases new <version>

# 2. Associate commits (identifies which change introduced a bug)
sentry-cli releases set-commits <version> --auto

# 3. Upload source maps for readable stack traces
sentry-cli releases files <version> upload-sourcemaps ./dist \
  --url-prefix '~/static/js' \
  --validate

# 4. Finalize the release (marks it as deployed)
sentry-cli releases finalize <version>

# 5. Mark deployed to an environment
sentry-cli releases deploys <version> new -e production
```

> **Rule**: Always run steps 1 → 2 → 3 → 4 → 5 in order. Skipping `finalize` causes the release to appear as incomplete in the Sentry dashboard.

---

## 🐛 Issue Triage

```bash
# List open issues in production
sentry-cli issues list --environment production --status unresolved

# Get all events for a specific issue (with breadcrumbs and context)
sentry-cli events <issue-id>

# Resolve issues in bulk
sentry-cli issues resolve <issue-id-1> <issue-id-2>

# Ignore an issue
sentry-cli issues ignore <issue-id>
```

---

## 🛡️ Security & Configuration

```bash
# ✅ CORRECT: Use environment variable, never hardcode
export SENTRY_AUTH_TOKEN=<token-from-vault>

# ✅ Project-level config via .sentryclirc
[defaults]
project = my-project
org = my-org
url = https://sentry.io/
```

```bash
# ❌ WRONG: Hardcoded token in script
sentry-cli releases new v1.0 --auth-token sntry_abc123...
```

---

## ⚠️ Anti-Patterns & Pitfalls

- ❌ **Don't skip `set-commits`**: Without commit association, Sentry cannot identify the commit that introduced a regression.
- ❌ **Don't upload unminified source maps**: Always set `--validate` to catch malformed maps before they reach production.
- ❌ **Don't use `--auth-token` CLI flag in CI scripts**: It exposes tokens in process lists. Use `SENTRY_AUTH_TOKEN` env var instead.
- ❌ **Don't skip `finalize`**: An unfinalized release shows as "unreleased" in dashboards and breaks release health metrics.
- ❌ **Don't reuse version strings**: Each release must have a unique version. Use `git describe --tags` or `$GITHUB_SHA` for automatic versioning.

---

## 📋 CI/CD Integration Checklist

| Step | Command | Required |
| :--- | :--- | :---: |
| Create release | `sentry-cli releases new $VERSION` | ✅ |
| Associate commits | `sentry-cli releases set-commits --auto` | ✅ |
| Upload source maps | `sentry-cli releases files ... upload-sourcemaps` | ✅ for JS/TS |
| Finalize release | `sentry-cli releases finalize $VERSION` | ✅ |
| Mark deployed | `sentry-cli releases deploys $VERSION new -e $ENV` | ✅ |

---

## Changelog

- **2.0.0** (2026-07-11): Added when-to-use, examples, anti-patterns, CI checklist, security rules
- **1.0.0** (2026-05-13): Initial version
