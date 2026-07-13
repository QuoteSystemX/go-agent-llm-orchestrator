---
name: web-design-guidelines
description: Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
metadata:
  author: vercel
  version: "1.0.0"
  argument-hint: <file-or-pattern>
version: 1.0.0
---

# Web Interface Guidelines

Review files for compliance with Web Interface Guidelines.

## How It Works

1. Fetch the latest guidelines from the source URL below
2. Read the specified files (or prompt user for files/pattern)
3. Check against all rules in the fetched guidelines
4. Output findings in the terse `file:line` format

## Guidelines Source

Fetch fresh guidelines before each review:

```
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
```

Use WebFetch to retrieve the latest rules. The fetched content contains all the rules and output format instructions.

## Usage

When a user provides a file or pattern argument:
1. Fetch guidelines from the source URL above
2. Read the specified files
3. Apply all rules from the fetched guidelines
4. Output findings using the format specified in the guidelines

If no files specified, ask the user which files to review.

---

## Related Skills

| Skill | When to Use |
|-------|-------------|
| **[frontend-design](../frontend-design/SKILL.md)** | Before coding - Learn design principles (color, typography, UX psychology) |
| **web-design-guidelines** (this) | After coding - Audit for accessibility, performance, and best practices |

## Design Workflow

```
1. DESIGN   → Read frontend-design principles
2. CODE     → Implement the design
3. AUDIT    → Run web-design-guidelines review ← YOU ARE HERE
4. FIX      → Address findings from audit
```

## When to Use

- **Designing a new web app** — start with information
  architecture, then visual hierarchy, then interaction design.
- **Establishing a design system** — define tokens (colors,
  spacing, typography) before components.
- **Reviewing UI work** — use the design checklist (contrast,
  spacing, focus states, mobile, dark mode).
- **A/B testing** — use real users, not opinions.
- **Accessibility audit** — axe-core, Lighthouse, manual keyboard
  testing.

Avoid using this skill for:
- Pure code architecture (use `@architecture`).
- Backend (use `@backend-specialist`).
- Brand identity work (use `@visual-explainer`).

## Anti-Patterns

- **Don't use color alone to convey information** —
  always pair with icon, text, or pattern (color-blind users).
- **Don't use more than 2 typefaces** — one for headings, one for
  body. More = visual chaos.
- **Don't use pure black (#000) or pure white (#FFF)** — they're
  harsh. Use off-black/white (e.g., #0a0a0a) for less eye strain.
- **Don't ignore focus states** — keyboard users need them.
  Default browser focus is often invisible.
- **Don't use `cursor: pointer` on non-interactive elements** —
  it's misleading and breaks accessibility.
- **Don't ship without testing on real devices** — emulators
  miss real-world rendering quirks.

## Changelog

- **1.0.0** (2026-04-26): Initial version
