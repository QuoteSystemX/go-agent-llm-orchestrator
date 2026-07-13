---
name: kubernetes-mcp
description: "Detailed operational guidelines for interacting with the Kubernetes cluster via MCP tools."
version: 1.0.0
---

# Kubernetes MCP Operations Skill

This skill documents and guides specialized infrastructure agents on utilizing the `kubernetes` MCP server (19 tools) in the Multica environment.

---

## 🏗️ OPERATIONAL GUIDELINES & TOOLS

The `kubernetes` MCP server allows direct querying and manipulation of Kubernetes API resources in the cluster without executing raw `kubectl` command-line processes.

### Available Tool Scopes
- **Read Operations**: Retrieving pod lists, namespace information, deployment logs, service descriptions, ingress routes, and resource statuses.
- **Write/Mutate Operations**: Scaling deployments, triggering rolling updates, editing manifest annotations, and applying patches.

### Best Practices
- **Prefer MCP Tools over CLI**: Always use the provided MCP tools instead of executing `rtk kubectl ...` shell commands. It is safer, faster, and parses structural results automatically.
- **Scope by Namespace**: Limit queries to the target namespace to avoid unnecessary resource scan overhead and token pollution.
- **Logs Pagination**: When retrieving logs via MCP, specify reasonable lines limits to prevent token window exhaust.


## When to Use

- **Deploying MCP servers to Kubernetes** — use the
  `mcp-protocol-engineer` patterns for manifests.
- **Setting up ConfigMaps and Secrets** — for MCP server config
  and API keys.
- **Auto-scaling** — HPA based on CPU/memory, or custom metrics
  like requests/sec.
- **Rolling updates** — `kubectl rollout` with proper readiness
  probes.
- **Service mesh** — Istio/Linkerd for mTLS, observability, and
  traffic splitting.

Avoid using this skill for:
- Non-Kubernetes deployments (use `@devops-engineer`).
- Service design (use `@backend-specialist`).
- MCP protocol itself (use `@mcp-protocol-engineer`).

## Anti-Patterns

- **Don't run MCP servers with `latest` tag** — pin to a
  specific version for reproducibility.
- **Don't store API keys in plain ConfigMaps** — use Secrets (or
  external secret managers).
- **Don't skip resource limits** — `requests` and `limits` are
  required, not optional.
- **Don't use `latest` in MCP server manifests** — pin to a
  semver or SHA.
- **Don't expose MCP servers externally without auth** — even
  internal clusters should have RBAC + NetworkPolicy.
- **Don't use `imagePullPolicy: Always` in production** — use
  `IfNotPresent` to avoid unnecessary pulls.