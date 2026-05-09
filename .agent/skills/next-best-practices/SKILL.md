---
name: next-best-practices
description: Next.js best practices for RSC boundaries, data patterns, and performance optimization.
version: 1.0.0
---

# 🌐 Next.js Best Practices

Expert guidelines for building high-performance, scalable web applications with Next.js.

## 🏗 Rendering Strategy

- **RSC Boundaries**: Keep Client Components at the leaves of your component tree. Fetch data in Server Components where possible.
- **Streaming**: Use `Suspense` for granular loading states to improve perceived performance.
- **Static vs Dynamic**: Use Static Site Generation (SSG) for public pages and Incremental Static Regeneration (ISR) for frequently updated content.

## 📡 Data Fetching

- **Type Safety**: Use `Zod` or TypeScript interfaces for all API responses.
- **Caching**: Leverage Next.js's extended `fetch` for automatic deduplication and caching.
- **Server Actions**: Use for all mutations (forms, buttons) to ensure type safety and ease of use.

## 🚀 Optimization

- **Images & Fonts**: Always use `next/image` and `next/font` to prevent layout shifts and minimize bundle size.
- **Bundle Analysis**: Regularly check bundle size to avoid bloat from heavy third-party libraries.

---
> **Note**: This skill was imported from `skills.sh` to support the Next.js architecture of Paperclip.
