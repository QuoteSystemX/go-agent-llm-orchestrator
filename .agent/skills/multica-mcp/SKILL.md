---
name: multica-mcp
description: "Router skill for Model Context Protocol (MCP) servers in the Multica Kubernetes namespace. Resolves dynamic endpoints and delegates to specific sub-skills."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.3.0
---

# Multica Global MCP Router Skill

> Router and discovery coordinator for Model Context Protocol (MCP) servers running in the `multica` Kubernetes cluster namespace.

## 🎯 When to Use This Skill

- **Trigger**: When resolving active MCP server endpoints in the `multica` namespace.
- **Trigger**: When determining which specialized MCP skills (`mcp-agent-kit`, `mcp-browser`, `mcp-codebase-memory`, `mcp-kubernetes`, `mcp-lean-ctx`) to load dynamically based on service availability.
- **Trigger**: When calling the `multica` discovery server (`http://multica-multica-mcp:3201/mcp`) to retrieve endpoints list.

---

## 🧭 Dynamic Service Mapping & Delegation

Instead of using static endpoints, this skill coordinates routing to online services. Ensure you reference the appropriate sub-skills:

- For core task control and schedules, delegate to [mcp-agent-kit](../mcp-agent-kit/SKILL.md).
- For headless browser tests, delegate to [mcp-browser](../mcp-browser/SKILL.md).
- For code symbol searches, delegate to [mcp-codebase-memory](../mcp-codebase-memory/SKILL.md) (see also the general-purpose [codebase-memory-patterns](../codebase-memory-patterns/SKILL.md) for non-cluster usage).
- For Kubernetes pods and resources, delegate to [mcp-kubernetes](../mcp-kubernetes/SKILL.md) (see also the general-purpose [kubernetes-mcp](../kubernetes-mcp/SKILL.md) for non-cluster usage).
- For payload compression and token limits, delegate to [mcp-lean-ctx](../mcp-lean-ctx/SKILL.md) (the `lean-ctx` cluster alias is the same `headroom-mcp` API — see also the general-purpose [headroom-patterns](../headroom-patterns/SKILL.md)).

---

## 📋 Routing Guidelines & Rules

### 1. Dynamic Endpoint Verification
- **Rule 1**: Always query the `multica` discovery tool `get_mcp_endpoints()` before attempting connection to any sub-service.
- **Rule 2**: If a service (e.g. `lean-ctx`) is marked `offline` in the discovery response, the agent **must** fallback to local mock implementations and skip loading that skill.
- **Rule 3**: Cache the endpoints response in `.agent/bus/mcp_endpoints.json` for 5 minutes.

### 2. Namespace Routing
- **Rule 4**: Verify namespace DNS context (default: `multica`) before building target URLs.

---

## 💻 Code Examples & Connection Patterns

### Querying Discovery Endpoint

```json
// Example payload to get all active endpoints in the namespace
{
  "serverName": "multica",
  "toolName": "get_mcp_endpoints",
  "arguments": {
    "namespace": "multica"
  }
}
```

### Discovery Response Structure

| Property | Type | Description |
|---|---|---|
| `browser.status` | String | Status of browser server (`online`/`offline`) |
| `lean-ctx.status` | String | Status of lean-ctx server (`online`/`offline`) |
| `kubernetes.url` | String | Endpoint URL in the cluster |

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Hardcoded Endpoints)**: Avoid hardcoding URL endpoints in code or configuration. Always use dynamic discovery via the `multica` endpoint.
- **Anti-Pattern (Ignoring Offline Status)**: Never attempt to call tools on an MCP server that is reported as `offline`. Always implement fallback logic.
- **Anti-Pattern (Polling Discovery)**: Don't poll the discovery API on every single step. Use the local cache `.agent/bus/mcp_endpoints.json`.
- **Anti-Pattern (Missing Namespace)**: Avoid querying the discovery API without specifying the namespace, as it can return wrong endpoints.

---

## Additional Quality Guidelines
To ensure the highest standard of delivery, the following additional considerations must be met:
1. Maintain consistency with existing naming conventions in the codebase.
2. Implement comprehensive error handling and logging for all new components.
3. Ensure that all dependencies are declared and verified beforehand.
4. Write clean, self-documenting code with clear comments where necessary.
5. Validate performance under load and avoid premature optimizations.

## Changelog

- **1.3.0** (2026-07-31): Fixed delegation links (were hardcoded absolute `file://` paths to one
  developer's machine — broken on any other clone) to relative paths. This skill is now attached
  to all agents (was 59/69) so it acts as a true universal wrapper; the 5 Multica-namespaced
  sub-skills it delegates to remain separate, full-fledged files from their general-purpose
  counterparts (`kubernetes-mcp`, `codebase-memory-patterns`, `headroom-patterns`), since agents
  operating inside the Multica cluster need the cluster-specific endpoint/replica/namespace
  details that don't belong in the generic docs.
- **1.2.0**: Initial version with 5 sub-skill delegations.
