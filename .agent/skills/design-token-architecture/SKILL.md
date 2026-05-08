---
name: design-token-architecture
description: Design token architecture for modern web apps. Focuses on Tailwind v4 CSS-first tokens, semantic naming, OKLCH colors, and token-to-code mapping.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 1.0.0
---

# Design Token Architecture

> Unified design language across Figma, CSS, and Components.

---

## 1. Token Hierarchy

| Level | Type | Example | Purpose |
|-------|------|---------|---------|
| **L1: Primitives** | Raw values | `--gray-900: #1a1a1a` | Base color palette, spacing scale |
| **L2: Semantics** | Purpose-based | `--bg-primary: var(--gray-900)` | Defines *what* a value does |
| **L3: Components** | Element-specific | `--button-bg: var(--bg-primary)` | Fine-tuned control for UI components |

---

## 2. Tailwind v4 CSS-First Strategy

In Tailwind v4, the `@theme` block is the source of truth.

```css
@theme {
  /* 1. OKLCH Color Primitives */
  --color-brand-50: oklch(0.97 0.01 240);
  --color-brand-500: oklch(0.6 0.18 240);
  --color-brand-900: oklch(0.2 0.05 240);

  /* 2. Semantic Mappings */
  --color-bg-surface: var(--color-brand-50);
  --color-text-main: var(--color-brand-900);
  --color-accent: var(--color-brand-500);

  /* 3. Layout Tokens */
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 1rem;
  
  --spacing-safe: clamp(1rem, 5vw, 3rem);
}
```

---

## 3. Semantic Naming Conventions

### Backgrounds
- `--bg-base`: Page background
- `--bg-surface`: Cards, modals, sidebars
- `--bg-overlay`: Tooltips, dropdowns

### Content
- `--content-primary`: Main headings, body
- `--content-secondary`: Muted text, labels
- `--content-tertiary`: Placeholders, disabled

### Interactive
- `--cta-primary`: Main button background
- `--cta-hover`: Hover state for primary
- `--cta-active`: Active/Pressed state

---

## 4. Light/Dark Mode Logic

Use CSS variables to swap values without changing class names.

```css
:root {
  --bg-primary: white;
  --text-primary: black;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg-primary: oklch(0.15 0 0);
    --text-primary: oklch(0.98 0 0);
  }
}
```

---

## 5. Token Checkpoint

Before building UI, verify your token map:

- [ ] Does every color have an OKLCH primitive?
- [ ] Are we using semantic names (`--color-accent`) instead of primitives (`--color-blue-500`) in components?
- [ ] Does the spacing scale use logical names (`xs`, `sm`, `md`, `lg`)?
- [ ] Is dark mode handled via variable swap, not just `dark:` classes?

---

> **Rule:** Never hardcode a hex/rgb value in a component. If it's used more than once, it's a token.
