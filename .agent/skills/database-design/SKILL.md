---
name: database-design
description: Database design principles and decision-making. Schema design, indexing strategy, ORM selection, serverless databases.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 1.0.0
---

# 🏗 Database Design & Architecture

Expert guidelines for designing scalable, maintainable, and efficient database architectures for the Paperclip ecosystem.

## 🏗 Core Principles

- **Normalization**: Aim for 3NF (Third Normal Form) to eliminate data redundancy. Denormalize only after measuring performance bottlenecks.
- **Relational Integrity**: Use Foreign Keys with appropriate `ON DELETE` actions (`CASCADE`, `SET NULL`) to ensure data consistency.
- **Atomic Operations**: Design transactions to be as small and fast as possible to minimize locking.

## 📡 Relationship Patterns

- **One-to-Many (1:N)**: Use foreign keys on the "many" side.
- **Many-to-Many (M:N)**: Use a join table with composite primary keys.
- **Polymorphic**: Use "exclusive belongs to" or a central "entity" table to avoid brittle polymorphic associations.

## 🚀 Tools & Verification

### 1. Normalization Auditor
Run the internal script to check for missing primary keys and potential denormalization issues:

```bash
python3 .agent/skills/database-design/scripts/analyze_normalization.py
```

### 2. Standard Designs
Refer to `examples/normalized-schema.md` for a "Golden Path" ER diagram of a core Paperclip module.

## 📈 Architecture Checklist
- [ ] Are all tables in at least 3NF?
- [ ] Do all tables have a Primary Key?
- [ ] Are Foreign Keys used for all relationships?
- [ ] Is data types consistency maintained across tables?
- [ ] Is there an ER diagram for the proposed change?

---
> **Note**: This skill ensures that Paperclip's foundation is built on solid data architectural principles.

## Changelog

- **1.0.0** (2026-05-13): Initial version
