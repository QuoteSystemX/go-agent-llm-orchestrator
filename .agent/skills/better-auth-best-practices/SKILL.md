---
name: better-auth-best-practices
description: Configure Better Auth server and client, set up database adapters, manage sessions, add plugins, and handle environment variables.
version: 1.0.0
---

# 🔐 Better Auth Best Practices

Expert guidelines for implementing secure, robust, and user-friendly authentication using the Better Auth framework.

## 🛡 Security Hardening

Authentication is the most critical part of your application. Follow these rules strictly:

- **Secure Cookies**: Always set `useSecureCookies: true` and appropriate `sameSite` flags for all session cookies in production.
- **CSRF & Origin**: **NEVER** disable CSRF or Origin checks. Better Auth handles these by default to prevent cross-site attacks.
- **Encryption**: Use a strong `BETTER_AUTH_SECRET` (min 32 chars). Generate it using `openssl rand -base64 32`.
- **Storage Strategy**: Use `secondaryStorage` (Redis/KV) for high-performance session handling while keeping persistence in the database.

## 🔌 Plugin & Middleware Patterns

- **Plugin Isolation**: Import plugins from dedicated paths (e.g., `better-auth/plugins/two-factor`) for better tree-shaking and performance.
- **Hooks**: Use `hooks.before` and `hooks.after` to implement custom logging or additional validation during the auth lifecycle.
- **API Keys**: Leverage the `apiKey` plugin for secure inter-agent communication within the Paperclip ecosystem.

## 🚀 Tools & Verification

### 1. Auth Config Auditor
Run the internal security scanner on your Better Auth configuration files:

```bash
python3 .agent/skills/better-auth-best-practices/scripts/audit_auth_config.py
```

### 2. CLI Tools
Use the official CLI for schema management and migrations:
```bash
npx @better-auth/cli@latest migrate
```

## 📈 Security Checklist
- [ ] Is `BETTER_AUTH_SECRET` generated securely?
- [ ] Is `useSecureCookies` enabled for production?
- [ ] are plugins imported from specific paths?
- [ ] Is a session storage strategy defined (DB + KV)?
- [ ] Have you audited the config using `audit_auth_config.py`?

---
> **Note**: This skill ensures that Paperclip's authentication layer is resilient and follows modern security standards.

## Changelog

- **1.0.0** (2026-05-13): Initial version
