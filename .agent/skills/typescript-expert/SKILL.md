---
name: typescript-expert
description: TypeScript strict-mode patterns, type system advanced usage, OpenAPI-to-TypeScript generation, SDK type design, and type-safe API contract tooling.
version: 1.0.0
---

# TypeScript Expert

> TypeScript is not just "JavaScript with types." It is a design language. The type system encodes your domain model — if the types are wrong, the code is wrong.

---

## 1. Strict Mode (Non-Negotiable)

Always enable in `tsconfig.json`:

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true
  }
}
```

| Flag | Why It Matters |
|------|---------------|
| `strict` | Enables all strict checks as a bundle |
| `noUncheckedIndexedAccess` | `arr[0]` is `T \| undefined`, not `T` |
| `exactOptionalPropertyTypes` | `{a?: string}` ≠ `{a: string \| undefined}` |
| `noImplicitReturns` | Every code path must return a value |

---

## 2. Type System Patterns

### Branded Types (Domain Primitives)

```typescript
type UserId = string & { readonly __brand: 'UserId' };
type OrderId = string & { readonly __brand: 'OrderId' };

function createUserId(raw: string): UserId {
  return raw as UserId;
}

// Compiler prevents mixing up IDs:
function getOrder(id: OrderId): Order { ... }
getOrder(userId); // ❌ Type error — caught at compile time
```

### Discriminated Unions (Exhaustive Matching)

```typescript
type Result<T, E = Error> =
  | { readonly ok: true;  readonly value: T }
  | { readonly ok: false; readonly error: E };

function handleResult<T>(result: Result<T>): T {
  if (result.ok) {
    return result.value;
  }
  throw result.error;
}
```

### Template Literal Types (API Routes)

```typescript
type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
type ApiVersion = 'v1' | 'v2';
type Route = `/${ApiVersion}/${string}`;
type EndpointKey = `${HttpMethod} ${Route}`;
```

### `satisfies` Operator (Validate Without Widening)

```typescript
const config = {
  baseUrl: 'https://api.example.com',
  timeout: 5000,
} satisfies ApiConfig; // Validates shape, keeps literal types
```

---

## 3. OpenAPI → TypeScript Tooling

### Recommended: `openapi-typescript`

```bash
npx openapi-typescript openapi.yaml -o src/types/api.d.ts
```

Generates fully-typed path/operation interfaces from the OpenAPI spec:

```typescript
// Auto-generated — DO NOT EDIT
export interface paths {
  '/orders': {
    get: operations['listOrders'];
    post: operations['createOrder'];
  };
}
export interface components {
  schemas: {
    Order: { id: string; status: 'pending' | 'confirmed' | 'shipped'; };
    ErrorResponse: { type: string; title: string; status: number; };
  };
}
```

### Type-Safe Fetch with `openapi-fetch`

```typescript
import createClient from 'openapi-fetch';
import type { paths } from './types/api.d.ts';

const client = createClient<paths>({ baseUrl: 'https://api.example.com' });

const { data, error } = await client.GET('/orders/{id}', {
  params: { path: { id: '123' } },
});
// data: components['schemas']['Order'] | undefined
// error: components['schemas']['ErrorResponse'] | undefined
```

---

## 4. Utility Types Reference

| Utility | Use Case | Example |
|---------|----------|---------|
| `Partial<T>` | Optional all fields | PATCH request body |
| `Required<T>` | Make all required | Validated internal type |
| `Readonly<T>` | Immutable value | Config, constants |
| `Pick<T, K>` | Select subset | Response projection |
| `Omit<T, K>` | Exclude fields | Remove sensitive fields |
| `Record<K, V>` | Key-value map | Route handlers map |
| `Extract<T, U>` | Filter union | Status code subset |
| `Exclude<T, U>` | Remove union members | Non-error states |
| `ReturnType<F>` | Infer return type | Function composition |
| `Awaited<T>` | Unwrap Promise | Async return types |
| `Parameters<F>` | Infer param tuple | Middleware wrappers |

---

## 5. API SDK Design Patterns

### Zod for Runtime Validation at Boundaries

```typescript
import { z } from 'zod';

const OrderSchema = z.object({
  id: z.string().uuid(),
  status: z.enum(['pending', 'confirmed', 'shipped']),
  total: z.string().regex(/^\d+\.\d{2}$/),
  createdAt: z.string().datetime(),
});

type Order = z.infer<typeof OrderSchema>;

const order = OrderSchema.parse(rawApiResponse); // throws on invalid
```

### `const` over `enum` (Zero Runtime Cost)

```typescript
// ❌ enum has runtime overhead
enum Status { Pending = 'pending', Active = 'active' }

// ✅ const object — zero runtime cost
const Status = { Pending: 'pending', Active: 'active' } as const;
type Status = typeof Status[keyof typeof Status]; // 'pending' | 'active'
```

---

## 6. Anti-Patterns

| ❌ Anti-Pattern | ✅ Correct Pattern |
|----------------|------------------|
| `any` type | `unknown` + type guard |
| Type assertions (`as X`) everywhere | Proper narrowing with `if`/`instanceof` |
| Non-null assertion (`!`) | Optional chaining + fallback |
| `Object` / `{}` as type | Specific interface |
| `enum` | `const` object + `typeof` |
| Hand-written API types | Generated from OpenAPI spec |

---

## 7. Pre-Delivery Checklist

- [ ] `npx tsc --noEmit` — zero errors
- [ ] No `any` types (use `unknown` + narrowing)
- [ ] No unexplained `!` non-null assertions
- [ ] All exported functions have explicit return types
- [ ] API boundary types generated from OpenAPI, not hand-written
- [ ] Zod validates all external data (API responses, env vars, user input)
- [ ] `eslint @typescript-eslint/recommended` passes clean

## Changelog

- **1.0.0** (2026-04-26): Initial version
