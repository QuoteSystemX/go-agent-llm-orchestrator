---
name: github-actions-expert
description: Guidelines for writing, securing, and optimizing GitHub Actions workflows.
version: 1.0.0
---

# 🐙 GitHub Actions Expert

Expert guidelines for building secure, fast, and automated pipelines for the Paperclip ecosystem.

## 🏗 Workflow Design

- **Triggers**: Use granular triggers (`on: push: paths: [...]`) to avoid unnecessary builds.
- **Caching**: Always cache `node_modules` and build outputs to speed up subsequent runs.
- **Matrices**: Use strategy matrices for testing across multiple Node.js or OS versions.

## 🛡 Security Best Practices

- **Secrets**: Use GitHub Secrets for all sensitive data. NEVER hardcode tokens.
- **Permissions**: Follow the principle of least privilege for `GITHUB_TOKEN`.
- **Pinned Actions**: Pin third-party actions to a specific commit SHA for supply chain security.

## 🚀 Optimization

- **Job Dependencies**: Use `needs` to chain jobs and fail early if a critical step (like linting) fails.
- **Environment Management**: Define separate environments for `production` and `staging` with required approvals.

---
> **Note**: This skill was imported from `skills.sh` to optimize the Auth Hub CI/CD pipeline.
