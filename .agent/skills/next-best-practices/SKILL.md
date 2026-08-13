---
name: next-best-practices
description: Next.js best practices for RSC boundaries, data patterns, and performance optimization.
version: 1.0.0
files: examples/server-component-pattern.tsx, scripts/check_rsc_boundaries.py
---

# 🌐 Next.js Best Practices

Expert guidelines for building high-performance, scalable web applications with Next.js App Router.

## 🏗 Rendering Strategy & RSC Boundaries

- **The Leaf Pattern**: Keep Client Components at the leaves of your component tree. Fetch data in Server Components where possible.
- **Async Components**: Use `async/await` directly in Server Components for data fetching.
- **Streaming & Suspense**: Always wrap data-dependent components in `Suspense` with meaningful fallback UI (Skeletons).
- **Static vs Dynamic**: Force static rendering for SEO pages using `generateStaticParams` and dynamic for dashboards using `dynamic = 'force-dynamic'`.

## 📡 Data Fetching & Mutations

- **Caching**: Leverage the Next.js `fetch` cache (`revalidate`, `tags`) to minimize DB load.
- **Server Actions**: Use Server Actions (`'use server'`) for all mutations. Implement optimistic updates in the client for better UX.
- **Validation**: Use `zod` for input validation in Server Actions to ensure type safety.

## 🚀 Tools & Verification

### 1. RSC Boundary Checker
Run the internal script to detect common App Router violations:

```bash
python3 .agent/skills/next-best-practices/scripts/check_rsc_boundaries.py
```

### 2. Implementation Patterns
See `examples/server-component-pattern.tsx` for a production-ready data fetching pattern using Suspense and caching.

## 📈 Performance Checklist
- [ ] Is data fetching consolidated in Server Components?
- [ ] Are Client Components kept at the leaves?
- [ ] Is `Suspense` used for all async data?
- [ ] Are images using `next/image`?
- [ ] Are fonts using `next/font`?

---
> **Note**: This skill ensures that Paperclip's web interface is fast, SEO-friendly, and maintainable.

## When to Use

- **Building a new Next.js app** — use App Router for new
  projects; Pages Router for legacy.
- **Server Components vs Client Components** — default to Server,
  use Client only when needed (interactivity, browser APIs).
- **Data fetching** — use `fetch` with caching/revalidation, or
  React Query for client-side.
- **Routing** — file-based routing with `app/` directory; nested
  layouts.
- **API routes** — Route Handlers (`app/api/`) for simple endpoints,
  separate backend for complex.

Avoid using this skill for:
- Pure React (use `@react-patterns`).
- Backend APIs (use `@backend-specialist`).
- Static sites without Next.js (use `@frontend-design`).

## Anti-Patterns

- **Don't use `'use client'` everywhere** — start with
  Server Components, add `'use client'` only for interactive parts.
- **Don't use `getServerSideProps` in App Router** — it's a
  Pages Router API. Use Server Components instead.
- **Don't fetch in `useEffect` for initial data** — use Server
  Components or React Query.
- **Don't skip the App Router metadata API** — `generateMetadata`
  is more flexible than `<head>` tags.
- **Don't use `next/image` for non-image files** — it's for
  images only. Use `<img>` for SVGs.
- **Don't forget the loading.tsx and error.tsx** — they're
  part of the App Router conventions.

## Changelog

- **1.0.0** (2026-05-13): Initial version
