---
name: postgres-best-practices
description: Postgres performance optimization and best practices for schema design, migrations, and query optimization.
version: 1.0.0
---

# 🐘 Postgres Best Practices

Expert guidelines for designing high-performance, scalable, and maintainable PostgreSQL databases.

## 🏗 Schema Design

- **Naming Conventions**: Use `snake_case` for all table and column names. Postgres is case-insensitive by default, making CamelCase painful.
- **Primary Keys**: Use `UUID` or `BIGINT` for primary keys. UUIDs are better for distributed systems; BIGINT is more efficient for local storage.
- **Timestamps**: Always use `TIMESTAMPTZ` (TIMESTAMP WITH TIME ZONE) to avoid timezone-related bugs.

## 🚀 Performance & Optimization

- **Indexing**: Always index foreign keys. Use `CREATE INDEX CONCURRENTLY` in production to avoid locking the table.
- **Partial Indexes**: Use partial indexes (`WHERE status = 'active'`) to reduce index size and speed up specific queries.
- **Normalization**: Aim for 3NF (Third Normal Form) but don't be afraid to denormalize for read-heavy operations if measured.

## 🛠 Tools & Verification

### 1. Schema Auditor
Run the internal script to check for missing indexes and naming violations in SQL migrations:

```bash
python3 .agent/skills/postgres-best-practices/scripts/verify_schema.py
```

### 2. Standard Patterns
Refer to `examples/schema-migration.sql` for a "Golden Path" implementation of a relational schema.

## 📈 Database Hygiene Checklist
- [ ] Are all table and column names `snake_case`?
- [ ] Are foreign keys indexed?
- [ ] Is `TIMESTAMPTZ` used for all date/time fields?
- [ ] Are `UUID`s used where appropriate?
- [ ] Is there an `updated_at` trigger?

---
> **Note**: This skill ensures that Paperclip's data layer is robust, fast, and ready for scale.

## Changelog

- **1.0.0** (2026-05-13): Initial version
