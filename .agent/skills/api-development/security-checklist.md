# API Security Checklist

> Required security measures for all API implementations

## 🔒 OWASP API Top 10 (2023)

| # | Vulnerability | Prevention |
|---|--------------|------------|
| API1 | Broken Object Level Authorization | Validate permissions on every endpoint |
| API2 | Broken Authentication | Use strong auth, rotate tokens |
| API3 | Broken Object Property Level Authorization | Validate input schemas |
| API4 | Unrestricted Resource Consumption | Rate limiting, pagination |
| API5 | Broken Function Level Authorization | Scope checks on admin routes |
| API6 | Unrestricted Access to Sensitive Business Flows | Business logic rate limits |
| API7 | Server Side Request Forgery | Validate URLs, allowlist |
| API8 | Security Misconfiguration | Hardened configs, minimal surface |
| API9 | Improper Inventory Management | Document all endpoints, deprecate old |
| API10 | Unsafe Consumption | Validate third-party data |

---

## ✅ Pre-Deployment Checklist

- [ ] Input validation on all endpoints
- [ ] Rate limiting configured
- [ ] Auth tokens properly validated
- [ ] No sensitive data in logs
- [ ] CORS configured correctly
- [ ] HTTPS only
- [ ] API keys rotated
- [ ] Documentation updated