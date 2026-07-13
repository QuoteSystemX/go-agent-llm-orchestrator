---
name: mcp-kubernetes
description: "Mastery of the Kubernetes Model Context Protocol (MCP) server. Guides agents on cluster operations, ServiceMonitors, namespaces, deployments, and pod statuses."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
---

# MCP Kubernetes Cluster Skill

> Query, deploy, and monitor resources in the Kubernetes cluster using the cluster-local `kubernetes` MCP server.

## 🎯 When to Use This Skill

- **Trigger**: When managing deployments, pods, services, or ingress configurations in the cluster.
- **Trigger**: When configuring monitoring resources like ServiceMonitors for Prometheus.
- **Trigger**: When querying namespace status or service logs using the kubernetes MCP endpoint (`http://multica-mcp-servers:3203/mcp`).

---

## 📋 Kubernetes Operations & Rules

### 1. Namespace Isolation
- **Rule 1**: Every pod query or service creation **must** explicitly target the correct namespace (default: `multica`).
- **Rule 2**: Check ServiceAccount permissions before attempting to modify configmaps or secrets.
- **Rule 3**: Do not attempt to modify cluster-wide resources (ClusterRoles) unless explicitly authorized by the SRE engineer.

### 2. Service Monitoring Setup
- **Rule 4**: When exposing metrics endpoints, always define a `ServiceMonitor` in the `monitoring` namespace.
- **Rule 5**: Ensure that the target service has appropriate prometheus labels (`app: ...`).

---

## 💻 Code Examples & Resource Patterns

### Pod Status Query

```json
// Example of listing pods in the multica namespace
{
  "serverName": "kubernetes",
  "toolName": "list_pods",
  "arguments": {
    "namespace": "multica",
    "labelSelector": "app=multica-daemon"
  }
}
```

### Resource Manifest Configuration

| Kind | Target Namespace | Required Labels |
|---|---|---|
| `ServiceMonitor` | `monitoring` | `release: prometheus-stack` |
| `Deployment` | `multica` | `app: multica-daemon` |
| `Service` | `multica` | `app: multica-daemon` |

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Missing Namespace)**: Avoid running cluster commands without specifying the target namespace. Defaulting to `default` is a common pitfall.
- **Anti-Pattern (Overwriting Configs)**: Never replace active cluster configs without creating a backup copy of the original manifest first.
- **Anti-Pattern (Ignoring ServiceAccount constraints)**: Don't ignore permission errors. If the ServiceAccount lacks access, report it to the user.
- **Anti-Pattern (Raw YAML String Concatenation)**: Avoid building YAML files by string formatting. Always use standard templates or structured encoders.

---

## Additional Quality Guidelines
To ensure the highest standard of delivery, the following additional considerations must be met:
1. Maintain consistency with existing naming conventions in the codebase.
2. Implement comprehensive error handling and logging for all new components.
3. Ensure that all dependencies are declared and verified beforehand.
4. Write clean, self-documenting code with clear comments where necessary.
5. Validate performance under load and avoid premature optimizations.
