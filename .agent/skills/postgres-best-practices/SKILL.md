---
name: postgres-best-practices
description: Postgres performance optimization and best practices for schema design, migrations, and query optimization.
version: 1.0.0
---

# 🐘 Postgres Best Practices

Expert guidelines for designing and managing high-performance PostgreSQL databases within the Paperclip platform.

## 🏗 Schema Design

- **Normalization**: Aim for 3NF but denormalize strategically for read-heavy operations (e.g., dashboard stats).
- **Data Types**: Use `UUID` for primary keys, `TIMESTAMPTZ` for dates, and `JSONB` only for unstructured or frequently changing metadata.
- **Indexes**: Create indexes for all foreign keys and frequently filtered columns (`WHERE` clauses). Use `GIN` indexes for `JSONB`.

## 🚀 Performance Optimization

- **Query Analysis**: Use `EXPLAIN ANALYZE` to identify slow queries.
- **Connection Pooling**: Always use a pooler (e.g., PgBouncer) in high-concurrency environments.
- **Batching**: Use `INSERT ... ON CONFLICT` for bulk updates to reduce round-trips.

## 🛠 Migrations & Maintenance

- **Zero-Downtime**: Use `ALTER TABLE ... ADD COLUMN ... DEFAULT NULL` to avoid locking tables.
- **Backup Strategy**: Regular snapshots and WAL-based point-in-time recovery.

---
> **Note**: This skill was imported from `skills.sh` to ensure Auth Hub's OAuth storage is stable and scalable.
