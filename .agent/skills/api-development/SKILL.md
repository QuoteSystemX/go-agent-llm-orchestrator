---
name: api-development
description: Unified API development router. Automatically routes to language-specific backend skills, security layers, and type-safe contract generators based on project context. Use when building APIs, designing endpoints, implementing REST/GraphQL/gRPC/tRPC, or any API-related work.
trigger-keys: api, endpoint, rest, graphql, grpc, trpc, http, server, route, post, get, put, patch, delete, openapi, swagger, json-rpc, webhook
version: 1.0.0
---

# API Development Router

> Unified entry point for all API development work. Routes to appropriate skills based on stack, language, and requirements.

## 🎯 How It Works

1. **Analyze** project context (language, framework, existing patterns)
2. **Route** to language-specific skill for implementation
3. **Security** apply vulnerability-scanner and auth patterns
4. **Contract** generate type-safe contracts
5. **Document** create API reference

---

## 🛠️ Routing Matrix

| Context | Route To | When |
|---------|----------|------|
| **Node.js/Express** | `@[skills/nodejs-best-practices]` | Express, NestJS, Fastify |
| **Python** | `@[skills/python-patterns]` | FastAPI, Flask, Django |
| **Go** | `@[skills/go-patterns]` | Gin, Echo, Fiber, gRPC |
| **Rust** | `@[skills/rust-pro]` | Axum, Actix, Tide |
| **TypeScript Fullstack** | `@[skills/typescript-expert]` + `@[skills/api-patterns]` | tRPC, Next.js API routes |
| **Mobile Backend** | `@[skills/mobile-design]` (mobile-backend.md) | Push notifications, sync |
| **Blockchain (TON)** | `@[skills/ton-blockchain]` | toncenter, API providers |
| **Security Review** | `@[skills/vulnerability-scanner]` + `@[skills/better-auth-best-practices]` | Always recommended |
| **Type Contracts** | `@[skills/typed-service-contracts]` | For typed TS/JS services |
| **Documentation** | `@[skills/documentation-templates]` | API reference section |
| **API Design** | `@[skills/api-patterns]` | Decision tree, versioning |

---

## 📋 Workflow

### Step 1: Determine Stack

```
# Check for language indicators
go.mod → Go
package.json → Node.js
pyproject.toml / requirements.txt → Python
Cargo.toml → Rust
```

### Step 2: Apply Security Layer

```
Always recommend:
1. @[skills/vulnerability-scanner] - OWASP API Top 10
2. @[skills/better-auth-best-practices] - Auth patterns
```

### Step 3: Generate Contracts

```
For TypeScript: @[skills/typed-service-contracts]
For OpenAPI: Generate swagger/openapi.yaml
```

### Step 4: Document

```
@[skills/documentation-templates] - API reference format
```

---

## 🎓 API Pattern Decision Tree

```
Need API type?
    │
    ├─ REST → @[skills/api-patterns] rest.md
    ├─ GraphQL → @[skills/api-patterns] graphql.md
    ├─ tRPC → @[skills/typescript-expert] (TypeScript projects)
    ├─ gRPC → @[skills/go-patterns] (Go) OR @[skills/rust-pro] (Rust)
    └─ Webhook → @[skills/api-patterns] + @[skills/vulnerability-scanner]
```

---

## 🔗 Integration with Other Skills

| Skill | Purpose | Integration Point |
|-------|---------|-------------------|
| `@[skills/api-patterns]` | Design decisions, versioning | Always first |
| `@[skills/nodejs-best-practices]` | Node.js implementation | backend-specialist |
| `@[skills/python-patterns]` | Python async, FastAPI | backend-specialist |
| `@[skills/go-patterns]` | Go, gRPC, performance | backend-specialist |
| `@[skills/typescript-expert]` | Type-safe APIs | frontend-specialist |
| `@[skills/vulnerability-scanner]` | Security audit | Always after design |
| `@[skills/better-auth-best-practices]` | Auth implementation | Security layer |
| `@[skills/typed-service-contracts]` | Type-safe contracts | TS/JS projects |
| `@[skills/documentation-templates]` | API docs | Always last |

---

## 📁 Content Map

| File | Description | When to Read |
|------|-------------|--------------|
| `ROUTING.md` | This file - routing logic | Always first |
| `security-checklist.md` | API security requirements | Before implementation |
| `contract-patterns.md` | Type-safe contract patterns | When defining API |
| `versioning-strategies.md` | API evolution patterns | When planning changes |

---

## ⚡ Quick Actions

### Start API Project
```
1. @[skills/api-development] - This skill
2. @[skills/api-patterns] - Design decisions
3. [Language skill] - Implementation
```

### Review Existing API
```
1. @[skills/api-development] - This skill
2. @[skills/vulnerability-scanner] - Security audit
3. @[skills/api-patterns] - Design review
```

### Add New Endpoint
```
1. Check routing matrix above
2. Route to appropriate skill
3. Apply security layer
4. Document in API reference
```

---

## 📊 Meta Information

**Created**: 2026-05-10
**Purpose**: Unify ~25 scattered API-related skills under single router
**Related Skills**: api-patterns, nodejs-best-practices, python-patterns, go-patterns, rust-pro, typescript-expert, vulnerability-scanner, better-auth-best-practices, typed-service-contracts, documentation-templates

**Skill Hierarchy**:
```
api-development (router)
    │
    ├── api-patterns (design decisions)
    ├── nodejs-best-practices (implementation)
    ├── python-patterns (implementation)
    ├── go-patterns (implementation)
    ├── rust-pro (implementation)
    ├── typescript-expert (type contracts)
    ├── vulnerability-scanner (security)
    ├── better-auth-best-practices (auth)
    ├── typed-service-contracts (contracts)
    └── documentation-templates (docs)
```