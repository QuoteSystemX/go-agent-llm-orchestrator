---
name: supabase-postgres-best-practices
description: Postgres performance optimization and best practices from Supabase. Use this skill when writing, reviewing, or optimizing Postgres queries, schema designs, or database configurations.
license: MIT
metadata:
  author: supabase
  version: "1.1.1"
  organization: Supabase
  date: January 2026
  abstract: Comprehensive Postgres performance optimization guide for developers using Supabase and Postgres. Contains performance rules across 8 categories, prioritized by impact from critical (query performance, connection management) to incremental (advanced features). Each rule includes detailed explanations, incorrect vs. correct SQL examples, query plan analysis, and specific performance metrics to guide automated optimization and code generation.
version: 1.0.0
files: references/_contributing.md, references/_sections.md, references/_template.md, references/advanced-full-text-search.md, references/advanced-jsonb-indexing.md, references/conn-idle-timeout.md, references/conn-limits.md, references/conn-pooling.md, references/conn-prepared-statements.md, references/data-batch-inserts.md, references/data-n-plus-one.md, references/data-pagination.md, references/data-upsert.md, references/lock-advisory.md, references/lock-deadlock-prevention.md, references/lock-short-transactions.md, references/lock-skip-locked.md, references/monitor-explain-analyze.md, references/monitor-pg-stat-statements.md, references/monitor-vacuum-analyze.md, references/query-composite-indexes.md, references/query-covering-indexes.md, references/query-index-types.md, references/query-missing-indexes.md, references/query-partial-indexes.md, references/schema-constraints.md, references/schema-data-types.md, references/schema-foreign-key-indexes.md, references/schema-lowercase-identifiers.md, references/schema-partitioning.md, references/schema-primary-keys.md, references/security-privileges.md, references/security-rls-basics.md, references/security-rls-performance.md
---

# Supabase Postgres Best Practices

Comprehensive performance optimization guide for Postgres, maintained by Supabase. Contains rules across 8 categories, prioritized by impact to guide automated query optimization and schema design.

## When to Apply

Reference these guidelines when:
- Writing SQL queries or designing schemas
- Implementing indexes or query optimization
- Reviewing database performance issues
- Configuring connection pooling or scaling
- Optimizing for Postgres-specific features
- Working with Row-Level Security (RLS)

## Rule Categories by Priority

| Priority | Category | Impact | Prefix |
|----------|----------|--------|--------|
| 1 | Query Performance | CRITICAL | `query-` |
| 2 | Connection Management | CRITICAL | `conn-` |
| 3 | Security & RLS | CRITICAL | `security-` |
| 4 | Schema Design | HIGH | `schema-` |
| 5 | Concurrency & Locking | MEDIUM-HIGH | `lock-` |
| 6 | Data Access Patterns | MEDIUM | `data-` |
| 7 | Monitoring & Diagnostics | LOW-MEDIUM | `monitor-` |
| 8 | Advanced Features | LOW | `advanced-` |

## How to Use

Read individual rule files for detailed explanations and SQL examples:

```
references/query-missing-indexes.md
references/query-partial-indexes.md
references/_sections.md
```

Each rule file contains:
- Brief explanation of why it matters
- Incorrect SQL example with explanation
- Correct SQL example with explanation
- Optional EXPLAIN output or metrics
- Additional context and references
- Supabase-specific notes (when applicable)

## References

- https://www.postgresql.org/docs/current/
- https://supabase.com/docs
- https://wiki.postgresql.org/wiki/Performance_Optimization
- https://supabase.com/docs/guides/database/overview
- https://supabase.com/docs/guides/auth/row-level-security

## When to Use

- **Designing a Supabase schema** — use RLS for multi-tenant
  security, indexes for hot queries, and views for complex reads.
- **Setting up Auth + RLS** — enable RLS on every table by default;
  use `auth.uid()` for row ownership.
- **Migrating from another DB** — use `pg_dump`/`pg_restore` for
  schema, then `supabase db push` for migrations.
- **Adding realtime subscriptions** — use `postgres_changes` filter
  for narrow payloads, not full table.
- **Performance tuning** — `EXPLAIN ANALYZE` is your friend; check
  `pg_stat_statements` for slow queries.

Avoid using this skill for:
- Pure Postgres without Supabase (use `@postgres-best-practices`).
- Non-RLS multi-tenancy (Supabase assumes RLS).
- Simple CRUD apps (Supabase is overkill).

## Anti-Patterns

- **Don't disable RLS "for testing"** — RLS off = public
  data. Always test with RLS on using a test user.
- **Don't store PII in plain text** — use `pgcrypto` for sensitive
  fields, even when RLS is in place.
- **Don't use `select *`** — fetch only the columns you need.
  Realtime subscriptions especially suffer from wide rows.
- **Don't skip the index on foreign keys** — Supabase RLS uses
  `auth.uid()` which joins on `id`. Without index, RLS check is
  slow.
- **Don't use `service_role` key in client code** — it's a server
  key, never expose to the browser.
- **Don't ignore RLS recursion** — a policy on `comments` that
  queries `posts` triggers RLS on `posts` too, which can
  cause infinite recursion. Use SECURITY DEFINER functions.
- **Don't put business logic in RLS policies** — keep policies
  simple (column = auth.uid()), put logic in views or functions.

## Changelog

- **1.0.0** (2026-05-13): Initial version
