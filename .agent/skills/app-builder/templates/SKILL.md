---
name: templates
description: Project scaffolding templates for new applications. Use when creating new projects from scratch. Contains 12 templates for various tech stacks.
allowed-tools: Read, Glob, Grep
---

# Project Templates

> Quick-start templates for scaffolding new projects.

---

## 🎯 Selective Reading Rule

**Read ONLY the template matching user's project type!**

| Template | Tech Stack | When to Use |
|----------|------------|-------------|
| [nextjs-fullstack](nextjs-fullstack/TEMPLATE.md) | Next.js + Prisma | Full-stack web app |
| [nextjs-saas](nextjs-saas/TEMPLATE.md) | Next.js + Stripe | SaaS product |
| [nextjs-static](nextjs-static/TEMPLATE.md) | Next.js + Framer | Landing page |
| [express-api](express-api/TEMPLATE.md) | Express + JWT | REST API |
| [python-fastapi](python-fastapi/TEMPLATE.md) | FastAPI | Python API |
| [react-native-app](react-native-app/TEMPLATE.md) | Expo + Zustand | Mobile app |
| [flutter-app](flutter-app/TEMPLATE.md) | Flutter + Riverpod | Cross-platform |
| [electron-desktop](electron-desktop/TEMPLATE.md) | Electron + React | Desktop app |
| [chrome-extension](chrome-extension/TEMPLATE.md) | Chrome MV3 | Browser extension |
| [cli-tool](cli-tool/TEMPLATE.md) | Node.js + Commander | CLI app |
| [monorepo-turborepo](monorepo-turborepo/TEMPLATE.md) | Turborepo + pnpm | Monorepo |
| [astro-static](astro-static/TEMPLATE.md) | Astro + MDX | Blog / Docs |

---

## Usage

1. User says "create [type] app"
2. Match to appropriate template
3. Read ONLY that template's TEMPLATE.md
4. Follow its tech stack and structure


## When to Use

- **Creating a new project template** — use this skill's
  patterns as a starting point.
- **Choosing between templates** — Cookiecutter, Cookiecutter-
  Ghosen, Cruft, Copier, Yeoman, or a custom shell script.
- **Customizing templates** — fork, then keep in sync with
  upstream periodically.
- **Distributing templates** — git repo, package manager, or
  CLI (like `pipx`, `brew`).

Avoid using this skill for:
- App-specific code generation (use AI code generation skills).
- Pure documentation (use `@documentation-templates`).
- DevOps templates (use `@app-builder`).

## Anti-Patterns

- **Don't use a template without reading the output first** —
  some templates ask interactive questions, others overwrite
  files silently.
- **Don't use templates with no version** — pin to a tag or commit
  for reproducibility.
- **Don't fork without tracking upstream** — periodic `git fetch
  upstream && git merge` keeps you current with bug fixes.
- **Don't put secrets in templates** — use `.env.example` with
  placeholders, not real keys.
- **Don't ignore template validation** — most templates have
  `--validate` or `make test` to check the output.
- **Don't create one-off templates** — generalize first, then
  template once you see the pattern 3+ times.