---
name: app-builder
description: Main application building orchestrator. Creates full-stack applications from natural language requests. Determines project type, selects tech stack, coordinates agents.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent
version: 1.0.0
files: agent-coordination.md, feature-building.md, project-detection.md, scaffolding.md, tech-stack.md, templates/astro-static/TEMPLATE.md, templates/chrome-extension/TEMPLATE.md, templates/cli-tool/TEMPLATE.md, templates/electron-desktop/TEMPLATE.md, templates/express-api/TEMPLATE.md, templates/flutter-app/TEMPLATE.md, templates/monorepo-turborepo/TEMPLATE.md, templates/nextjs-fullstack/TEMPLATE.md, templates/nextjs-saas/TEMPLATE.md, templates/nextjs-static/TEMPLATE.md, templates/nuxt-app/TEMPLATE.md, templates/python-fastapi/TEMPLATE.md, templates/react-native-app/TEMPLATE.md
---

# App Builder - Application Building Orchestrator

> Analyzes user's requests, determines tech stack, plans structure, and coordinates agents.

## 🎯 Selective Reading Rule

**Read ONLY files relevant to the request!** Check the content map, find what you need.

| File | Description | When to Read |
|------|-------------|--------------|
| `project-detection.md` | Keyword matrix, project type detection | Starting new project |
| `tech-stack.md` | 2026 default stack, alternatives | Choosing technologies |
| `agent-coordination.md` | Agent pipeline, execution order | Coordinating multi-agent work |
| `scaffolding.md` | Directory structure, core files | Creating project structure |
| `feature-building.md` | Feature analysis, error handling | Adding features to existing project |
| `templates/SKILL.md` | **Project templates** | Scaffolding new project |

---

## 📦 Templates (13)

Quick-start scaffolding for new projects. **Read the matching template only!**

| Template | Tech Stack | When to Use |
|----------|------------|-------------|
| [nextjs-fullstack](templates/nextjs-fullstack/TEMPLATE.md) | Next.js + Prisma | Full-stack web app |
| [nextjs-saas](templates/nextjs-saas/TEMPLATE.md) | Next.js + Stripe | SaaS product |
| [nextjs-static](templates/nextjs-static/TEMPLATE.md) | Next.js + Framer | Landing page |
| [astro-static](templates/astro-static/TEMPLATE.md) | Astro 4.x + MDX | Content-focused site, blog, docs |
| [nuxt-app](templates/nuxt-app/TEMPLATE.md) | Nuxt 3 + Pinia | Vue full-stack app |
| [express-api](templates/express-api/TEMPLATE.md) | Express + JWT | REST API |
| [python-fastapi](templates/python-fastapi/TEMPLATE.md) | FastAPI | Python API |
| [react-native-app](templates/react-native-app/TEMPLATE.md) | Expo + Zustand | Mobile app |
| [flutter-app](templates/flutter-app/TEMPLATE.md) | Flutter + Riverpod | Cross-platform mobile |
| [electron-desktop](templates/electron-desktop/TEMPLATE.md) | Electron + React | Desktop app |
| [chrome-extension](templates/chrome-extension/TEMPLATE.md) | Chrome MV3 | Browser extension |
| [cli-tool](templates/cli-tool/TEMPLATE.md) | Node.js + Commander | CLI app |
| [monorepo-turborepo](templates/monorepo-turborepo/TEMPLATE.md) | Turborepo + pnpm | Monorepo |

---

## 🔗 Related Agents

| Agent | Role |
|-------|------|
| `project-planner` | Task breakdown, dependency graph |
| `frontend-specialist` | UI components, pages |
| `backend-specialist` | API, business logic |
| `database-architect` | Schema, migrations |
| `devops-engineer` | Deployment, preview |

---

## Usage Example

```
User: "Make an Instagram clone with photo sharing and likes"

App Builder Process:
1. Project type: Social Media App
2. Tech stack: Next.js + Prisma + Cloudinary + Clerk
3. Create plan:
   ├─ Database schema (users, posts, likes, follows)
   ├─ API routes (12 endpoints)
   ├─ Pages (feed, profile, upload)
   └─ Components (PostCard, Feed, LikeButton)
4. Coordinate agents
5. Report progress
6. Start preview
```

## When to Use

- **Scaffolding a new fullstack app** — frontend + backend
  + DB + auth, with sensible defaults.
- **Choosing a stack** — match the team's skills + project
  requirements, not the trendiest framework.
- **Setting up CI/CD** — test, build, deploy on every PR.
- **Wiring auth and RBAC** — use a proven library (NextAuth,
  Auth.js, Clerk); don't roll your own.
- **Adding observability** — logs, metrics, traces from day 1.

Avoid using this skill for:
- Frontend-only apps (use `@frontend-design`).
- Backend-only services (use `@backend-specialist`).
- Pure mobile apps (use mobile skills).

## Anti-Patterns

- **Don't pick a stack based on hype** — pick based on team
  familiarity, hiring pool, and project requirements.
- **Don't skip auth in the MVP** — retrofitting auth is 10x harder
  than building it from day 1.
- **Don't hardcode secrets in `.env`** — use a secrets manager
  (Vault, AWS Secrets Manager, Doppler).
- **Don't deploy without CI/CD** — manual deploys lead to drift
  between dev and prod.
- **Don't use `latest` tags in production** — pin to specific
  versions for reproducibility.
- **Don't skip the database migration plan** — schema changes
  need a forward and backward migration path.

## Changelog

- **1.0.0** (2026-04-26): Initial version
