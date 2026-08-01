---
name: multica-mcp
description: "Guardrails for using Model Context Protocol (MCP) servers in the Multica Kubernetes namespace. Tool lists are dynamic — never rely on hardcoded tool names from docs."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 2.0.0
---

# Multica MCP Servers — Usage Guardrails

> Rules for working with MCP servers running in the `multica` Kubernetes namespace
> (`multica`, `agent-kit`, `kubernetes`, `browser`, `lean-ctx`, `codebase-memory-*`).

## 🎯 When to Use This Skill

- **Trigger**: When a task involves calling any MCP server from the `multica` namespace.

---

## 📋 Rules

### 1. The MCP handshake is the ONLY source of truth for tool names

- **Rule 1**: Your tool list (populated automatically via the MCP handshake at session start)
  contains the real, current names, descriptions, and input schemas of every available MCP tool.
  Use it directly.
- **Rule 2**: **Never** call an MCP tool name you found in a document, skill, example, or your
  own memory without confirming it exists in your current tool list. Server tool sets change
  between deployments; documented names go stale silently. (A previous version of this very
  skill mandated calling `get_mcp_endpoints` — a tool that never existed. An audit on 2026-08-01
  found that of 115 tool names documented across the MCP skills, only 1 matched a live server.)
- **Rule 3**: If a tool you expected is missing from your tool list, the server is offline,
  not connected for this task, or the tool was renamed/removed. Fall back to built-in tools
  (Bash/Read/etc.) or report the gap — do not retry guessed name variants.

### 2. Routing between overlapping capabilities

- **Rule 4**: Prefer the most specific server for the job: Multica issue operations → the
  `multica` server; cluster inspection → `kubernetes`; web page interaction → `browser`;
  large-file/context-efficient reading → `lean-ctx`; code-graph queries → `codebase-memory-*`.
- **Rule 5**: When both a built-in tool and an MCP tool can do the job, the built-in tool is
  usually cheaper and more reliable; reach for the MCP tool when it offers a real advantage
  (server-side state, cluster access, token savings).

---

## ❌ Anti-Patterns

- **Hardcoded tool names from docs**: the failure mode that motivated this rewrite. Trust the
  handshake, not the markdown.
- **Retrying name variants**: `list_pods` failed? Do not try `pods_list`, `listPods`, `get_pods`
  in a loop — check the actual tool list once.
- **Calling offline servers**: if a server's tools are absent from your tool list, it is not
  available for this session. Skip it.

## Changelog

- **2.0.0** (2026-08-01): Full rewrite after audit showed 114/115 documented tool names across
  the MCP skill family were wrong (nonexistent or renamed tools, including a mandatory
  `get_mcp_endpoints` discovery tool that was never implemented). Removed all hardcoded tool
  names, endpoints, and delegations to the 5 `mcp-*` sub-skills (deleted in the same change —
  they were attached to zero agents and documented fabricated tools). Multica is expected to
  inject an auto-generated, always-current MCP tools reference into task context
  (see multica repo `tasks/2026-08-01-mcp-tools-dynamic-injection.md`); until then, the MCP
  handshake tool list is the only source of truth.
- **1.3.0** (2026-07-31): Fixed delegation links to relative paths; attached to all 69 agents.
- **1.2.0**: Initial version with 5 sub-skill delegations.
