---
name: better-auth-best-practices
description: Configure Better Auth server and client, set up database adapters, manage sessions, add plugins, and handle environment variables.
version: 1.0.0
---

# 🛡 Better Auth Best Practices

Expert guidelines for integrating and managing authentication using the Better Auth framework within the Paperclip ecosystem.

## 🏗 Setup & Configuration

1.  **Environment Variables**:
    - `BETTER_AUTH_SECRET`: Encryption secret (min 32 chars). Use `openssl rand -base64 32`.
    - `BETTER_AUTH_URL`: Base URL of the application.
2.  **File Location**: CLI looks for `auth.ts` in `./`, `./lib`, `./utils`, or `./src`.
3.  **Database Migration**: Use `npx @better-auth/cli@latest migrate` to apply schema.

## 🔑 Session Management

- **Storage Strategy**:
  1. Use `secondaryStorage` (Redis/KV) for high-performance session handling.
  2. Set `session.storeSessionInDatabase: true` for persistence.
- **Cookie Caching**:
  - `compact` (default): Base64url + HMAC. Smallest size.
  - `jwt`: Signed but readable.
  - `jwe`: Encrypted. Maximum security.

## 🔌 Plugin Integration

Import plugins from dedicated paths for better tree-shaking:
```typescript
import { twoFactor } from "better-auth/plugins/two-factor";
// NOT from "better-auth/plugins"
```

### Essential Plugins for Auth Hub:
- `oauthProvider`: For managing Google/Claude OAuth flows.
- `apiKey`: For secure inter-agent communication.
- `bearer`: For API-based access control.

## 🛡 Security Controls

- Always use `useSecureCookies: true` in production.
- **NEVER** disable CSRF or Origin checks unless absolutely necessary for specific debug scenarios.
- Use `crossSubDomainCookies.enabled: true` if Paperclip plugins run on separate subdomains.

## 🛠 Hooks & Middleware

Use `hooks.before` and `hooks.after` for custom logic during the auth lifecycle.
Access `ctx.context.session` and `ctx.path` to enforce domain-specific rules.

---

> **Note**: This skill was imported from `skills.sh` to support the Paperclip Auth Hub implementation.
