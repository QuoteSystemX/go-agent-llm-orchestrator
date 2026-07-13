---
name: security-audit
description: Principles and procedures for conducting comprehensive codebase security audits. Focuses on OWASP compliance, injection protection, credential scanning, and data flow analysis.
allowed-tools: Read, Glob, Grep, Bash
version: 1.0.0
---

# Security Audit Skill

> Maintain a robust security posture through continuous code review, threat modeling, and defensive validation.

## 🎯 When to Use This Skill

- **Trigger**: Auditing codebase changes for security vulnerabilities before pull requests are merged.
- **Trigger**: Reviewing authentication, authorization, session management, and encryption modules.
- **Trigger**: Identifying and remediating potential injection vectors (SQL, OS command, LDAP, log injection).
- **Trigger**: Ensuring secrets, credentials, API keys, or sensitive data are never leaked or hardcoded.

---

## 📋 Security Audit Guidelines & Rules

### 1. OWASP Top 10 Compliance Rules

Every auditor agent **must** enforce the following rules:
- **Injection Prevention**: Always ensure parameterized queries or ORMs are used for databases. Input **must** be validated and sanitized before being executed in subprocesses or shell commands. Never concatenate raw strings to build SQL queries or shell commands.
- **Broken Authentication**: Verify that session IDs, JSON Web Tokens (JWT), and password storage schemes use modern cryptographic algorithms (e.g., bcrypt, Argon2). Never use weak MD5 or SHA1 for password hashing.
- **Sensitive Data Exposure**: Confirm that private keys, API tokens, and personal data (PII) are stored securely in environment variables (never in source code) and are never logged to console or logs in plain text.

### 2. Secret & Credential Scanning

Do not allow any of the following to be checked into source control:
- API Keys (e.g., OpenAI, AWS, GitHub tokens)
- Private cryptographic keys (.pem, .key)
- Database passwords and connection strings

If a secret is detected during triage or audit:
1. **Rule**: Immediately flag it to the user.
2. **Rule**: Ensure the file is excluded from the commit index.
3. **Rule**: Recommend rotating the leaked secret immediately.

---

## 💻 Code Examples & Audit Patterns

### Incorrect vs Correct SQL Query Construction

| Wrong Pattern (Vulnerable to SQLi) | Correct Pattern (Secure) |
|---|---|
| `query := fmt.Sprintf("SELECT * FROM users WHERE name='%s'", input)` | `query := "SELECT * FROM users WHERE name=?"` |
| `db.Raw(query).Scan(&result)` | `db.Raw(query, input).Scan(&result)` |

### Shell Command Execution

```go
// Secure command execution - arguments are separated, no shell invocation
cmd := exec.Command("git", "log", "-n", "5")
output, err := cmd.Output()
```

---

## ❌ Anti-Patterns & Pitfalls to Avoid

- **Anti-Pattern (Hardcoding Credentials)**: Avoid placing API tokens or private keys directly in config files or codebase files. This is a critical security vulnerability.
- **Anti-Pattern (Blind SQL Trust)**: Never assume that internal database inputs are safe. Always sanitize them.
- **Anti-Pattern (Weak Cryptography)**: Don't use obsolete cryptographic hash functions (such as MD5, SHA-1, or DES) for securing sensitive operations.
- **Anti-Pattern (Insecure Subprocesses)**: Never execute user input strings directly in `exec.Command` with shell wrappers or unvalidated parameters.
