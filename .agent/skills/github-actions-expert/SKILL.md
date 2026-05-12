---
name: github-actions-expert
description: Guidelines for writing, securing, and optimizing GitHub Actions workflows.
version: 1.0.0
---

# 🐙 GitHub Actions Expert

Expert guidelines for building secure, fast, and automated pipelines for the Paperclip ecosystem.

## 🏗 Workflow Design

- **Triggers**: Use granular triggers (`on: push: paths: [...]`) to avoid unnecessary builds.
- **Caching**: Always cache `node_modules`, `~/.npm`, and build outputs to speed up subsequent runs.
- **Matrices**: Use strategy matrices for testing across multiple Node.js or OS versions, but keep them lean to control costs.

## 🛡 Security Best Practices

- **Secrets**: Use GitHub Secrets for all sensitive data. NEVER hardcode tokens in the workflow YAML.
- **Permissions**: Follow the principle of least privilege for `GITHUB_TOKEN`. Explicitly set `permissions: contents: read`.
- **Pinned Actions**: Pin third-party actions to a specific commit SHA (e.g., `uses: actions/checkout@8ade135...`) for supply chain security.

## 🚀 Tools & Verification

### 1. Workflow Validator
Run the internal verification script before committing changes to `.github/workflows`:

```bash
python3 .agent/skills/github-actions-expert/scripts/verify_workflows.py
```

### 2. Standard Templates
Refer to `examples/ci-standard.yml` for the "Golden Path" of a Paperclip CI pipeline.

## 📈 Optimization Checklist
- [ ] Are path filters used?
- [ ] Is caching enabled?
- [ ] Are jobs using `needs` to fail fast?
- [ ] Is `GITHUB_TOKEN` scoped?
- [ ] Are actions pinned?

---
> **Note**: This skill ensures that CI/CD pipelines are not just functional, but resilient and secure.

