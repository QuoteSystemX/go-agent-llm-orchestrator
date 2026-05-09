---
name: sentry-cli-expert
description: Advanced usage of Sentry CLI for monitoring issues, events, and releases.
version: 1.0.0
---

# 🕵️‍♂️ Sentry CLI Expert

Expert guidelines for monitoring application health and managing releases using the Sentry CLI.

## 🚀 Release Management

- **Automatic Releases**: Integrate `sentry-cli releases new <version>` into your CI/CD pipeline.
- **Source Maps**: Always upload source maps using `sentry-cli releases files <version> upload-sourcemaps` to get readable stack traces.
- **Commits**: Associate commits with releases to identify exactly which change introduced a bug.

## 🐛 Issue Triage

- **Filtering**: Use `sentry-cli issues list` to filter by environment (`production`, `staging`).
- **Events**: Dive into specific failures with `sentry-cli events <id>` to see breadcrumbs and context.

## 🛡 Security & Config

- Use `SENTRY_AUTH_TOKEN` environment variable instead of hardcoded tokens.
- Configure `.sentryclirc` for project and organization defaults.

---
> **Note**: This skill was imported from `skills.sh` to ensure Auth Hub has robust error tracking.
