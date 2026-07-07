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
