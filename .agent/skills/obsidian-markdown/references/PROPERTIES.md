# Frontmatter Properties Standard

This document defines the standard frontmatter properties for all files in the wiki vault.

## Required Properties

Every `.md` file in the vault MUST have these:

```yaml
---
title: "Page Title"           # Human-readable title
tags:
  - domain                    # At least one tag from the domain list
status: proposed              # See status values below
---
```

### Status Values

| Status | Meaning |
|--------|---------|
| `proposed` | Draft, not yet reviewed |
| `active` | Currently in use / valid |
| `updated` | Recently modified |
| `deprecated` | No longer current, kept for history |
| `archived` | Historical record only |

## Recommended Properties

```yaml
---
aliases:
  - Alternative Name           # Alternative names for link resolution
date: 2026-05-15               # Creation or last review date
cssclasses:
  - custom-class               # Optional Obsidian CSS classes
---
```

## Tag Convention

Tags follow the pattern: `domain/subdomain`

| Domain | Examples |
|--------|----------|
| `architecture` | `architecture/adr`, `architecture/decision` |
| `agent` | `agent/orchestrator`, `agent/skill` |
| `infrastructure` | `infra/ci`, `infra/deployment` |
| `development` | `dev/python`, `dev/go`, `dev/testing` |
| `knowledge` | `knowledge/mental-model`, `knowledge/pattern` |
| `project` | `project/roadmap`, `project/planning` |
| `obsidian` | `obsidian/vault`, `obsidian/migration` |

## Example: ADR File

```yaml
---
title: "ADR-051: Obsidian Vault Integration"
date: 2026-05-15
status: proposed
tags:
  - architecture/adr
  - obsidian/vault
  - project/planning
aliases:
  - obsidian-migration-plan
---
```

## Example: Mental Model

```yaml
---
title: "Orchestrator Agent Mental Model"
date: 2026-04-28
status: active
tags:
  - agent/orchestrator
  - knowledge/mental-model
aliases:
  - orchestrator-patterns
cssclasses:
  - wide
---
```

## Validation

Run the following to verify frontmatter compliance:

```bash
python3 .agent/scripts/knowledge/obsidian_validator.py check --frontmatter
```
