# Type-Safe Contract Patterns

## 🎯 When to Use

- TypeScript/JavaScript projects
- Microservices with inter-service communication
- OpenAPI specification needed

## 📦 Pattern: Request/Response Types

```typescript
// Good: Explicit types
interface CreateUserRequest {
  email: string;
  password: string;
  role: 'admin' | 'user';
}

interface CreateUserResponse {
  id: string;
  email: string;
  createdAt: string;
}

// Better: Use Zod for runtime validation
import { z } from 'zod';

const CreateUserSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  role: z.enum(['admin', 'user']),
});
```

## 🔄 OpenAPI Generation

```yaml
# Auto-generate from types
paths:
  /users:
    post:
      requestBody:
        content:
          application/json:
            schema: $ref: '#/components/schemas/CreateUserRequest'
      responses:
        201:
          content:
            application/json:
              schema: $ref: '#/components/schemas/CreateUserResponse'
```

## 📋 Integration with typed-service-contracts

See `@[skills/typed-service-contracts]` for the "Spec and Handler" pattern.