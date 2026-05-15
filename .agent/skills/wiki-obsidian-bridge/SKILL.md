---
name: wiki-obsidian-bridge
description: Bridges Karpathy Wiki-First methodology with Obsidian Flavored Markdown. Use when writing new wiki content, deciding between wiki formats, or ensuring documentation follows both Prose-First and OFM standards.
version: 1.0.0
scope_restriction: vault_path
---

# Wiki-Obsidian Bridge Skill

Bridges the Karpathy Wiki-First methodology with Obsidian Flavored Markdown. This skill teaches how to write documentation that is both:

1. **Deeply understandable** (Karpathy: Mental Models, Intuition, Prose-First)
2. **Obsidian-compatible** (OFM: wikilinks, callouts, properties, graph view)

## Core Principle

> The wiki is the specification. The code is the implementation.
> The vault is how you navigate the wiki.

## When to Use What

| Situation | Format | Skill |
|-----------|--------|-------|
| New Mental Model | OFM + Karpathy | `wiki-writing` + `wiki-obsidian-bridge` |
| New ADR / Decision | OFM + ADR template | `wiki-obsidian-bridge` |
| Code documentation (README, docs/) | Standard GFM | (none — don't touch) |
| Wiki file edit | OFM | `obsidian-markdown` |
| Post-edit validation | OFM check | `obsidian-validator` |

## Writing Workflow

1. **Plan**: Define the mental model (Karpathy: WHY → HOW → WHAT)
2. **Frontmatter**: Add required properties (title, tags, status, aliases)
3. **Content**: Write in OFM with wikilinks, callouts, and embeds
4. **Connect**: Link to related docs via `[[wikilinks]]`
5. **Verify**: Run `obsidian_validator.py check`

## Frontmatter Standard

Every wiki file MUST have:

```yaml
---
title: "Page Title"
tags:
  - domain/category
status: proposed | active | updated | deprecated | archived
---
```

> See `obsidian-markdown` skill references/PROPERTIES.md for full standard.

## Vault Boundaries

- ✅ Apply OFM to files in `wiki/` (the vault)
- ❌ Do NOT apply OFM to files in `docs/`, `README.md`, `CONTRIBUTING.md`
- ❌ Do NOT auto-convert existing documentation without explicit user request
- ❌ Do NOT create `wiki/` in a project without explicit user consent

## Integration

This skill works alongside:
- `obsidian-markdown` — OFM syntax reference
- `obsidian-validator` — vault integrity checks
- `wiki-writing` — Karpathy Wiki-First methodology
