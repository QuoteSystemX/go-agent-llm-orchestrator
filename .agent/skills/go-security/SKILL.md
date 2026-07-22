---
name: go-security
description: Security best practices and vulnerability prevention for Go. Covers injection (SQL, command, XSS), cryptography, filesystem safety, network security, cookies, secrets management, memory safety, and logging. Apply when writing, reviewing, or auditing Go code for security, or when working on any risky code involving crypto, I/O, secrets management, user input handling, or authentication.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-security (MIT License) — https://github.com/samber/cc-skills-golang
---

# Go Security

## Overview

Security in Go follows **defense in depth**: protect at multiple layers, validate all inputs, use secure defaults, leverage the standard library's security-aware design.

## Security Thinking Model

Before writing or reviewing code, ask three questions:

1. **What are the trust boundaries?** — Where does untrusted data enter (HTTP requests, file uploads, env vars, DB rows written by other services)?
2. **What can an attacker control?** — Which inputs flow into sensitive operations (SQL queries, shell commands, HTML output, file paths, crypto operations)?
3. **What is the blast radius?** — If this defense fails, what's the worst outcome (data leak, RCE, privilege escalation, DoS)?

## Severity Levels

| Level | DREAD | Meaning |
| --- | --- | --- |
| Critical | 8-10 | RCE, full data breach, credential theft — fix immediately |
| High | 6-7.9 | Auth bypass, significant data exposure, broken crypto — fix in current sprint |
| Medium | 4-5.9 | Limited exposure, session issues, defense weakening — fix in next sprint |
| Low | 1-3.9 | Minor info disclosure, best-practice deviations — fix opportunistically |

## Research Before Reporting

Before flagging a security issue, trace the full data flow — don't assess a code snippet in isolation. Trace the data origin, check for upstream validation, examine the trust boundary, read the surrounding code. Upstream protection does not eliminate a finding, but it changes severity — report with adjusted severity and note which upstream defenses exist.

## Threat Modeling (STRIDE)

Apply STRIDE to every trust boundary crossing: **S**poofing (auth), **T**ampering (integrity), **R**epudiation (audit logging), **I**nformation Disclosure (encryption), **D**enial of Service (rate limiting), **E**levation of Privilege (authorization). Score each threat using DREAD to prioritize remediation.

## Quick Reference

| Severity | Vulnerability | Defense | Standard Library Solution |
| --- | --- | --- | --- |
| Critical | SQL Injection | Parameterized queries separate data from code | `database/sql` with `?`/`$1` placeholders |
| Critical | Command Injection | Pass args separately, never via shell concatenation | `exec.Command` with separate args |
| High | XSS | Auto-escaping renders user data as text, not HTML/JS | `html/template`, `text/template` |
| High | Path Traversal | Scope untrusted file access to an allowed root | Go 1.24+: `os.Root`. Pre-1.24: `filepath.IsLocal` + `filepath.Rel` + separator-aware checks — never rely on `filepath.Clean` + `strings.HasPrefix` alone |
| Medium | Timing Attacks | Constant-time comparison avoids byte-by-byte leaks | `crypto/subtle.ConstantTimeCompare` |
| High | Crypto Issues | Use vetted algorithms; never roll your own | `crypto/aes`, `crypto/rand` |
| Medium | HTTP Security | TLS + security headers prevent downgrade attacks | `net/http`, configure TLSConfig |
| Low | Missing Headers | HSTS, CSP, X-Frame-Options prevent browser attacks | Security headers middleware |
| Medium | Rate Limiting | Rate limits prevent brute-force and resource exhaustion | `golang.org/x/time/rate`, server timeouts |
| High | Race Conditions | Protect shared state to prevent data corruption | `sync.Mutex`, channels, avoid shared state |

## Tooling & Verification

```bash
# Go security checker (SAST)
go get -tool github.com/securego/gosec/v2/cmd/gosec@latest
go tool gosec ./...

# Vulnerability scanner
go get -tool golang.org/x/vuln/cmd/govulncheck@latest
go tool govulncheck ./...

# Race detector
go test -race ./...

# Fuzz testing
go test -fuzz=Fuzz
```

Security-relevant linters: `bodyclose`, `sqlclosecheck`, `nilerr`, `errcheck`, `govet`, `staticcheck`.

## Common Mistakes

| Severity | Mistake | Fix |
| --- | --- | --- |
| High | `math/rand` for tokens | Output is predictable. Use `crypto/rand` |
| Critical | SQL string concatenation | Attacker can modify query logic. Parameterized queries keep data and code separate |
| Critical | `exec.Command("bash -c")` | Shell interprets metacharacters (`;`, `\|`, `` ` ``). Pass args separately |
| High | Trusting unsanitized input | Validate at trust boundaries |
| Critical | Hardcoded secrets | Secrets in source code end up in version history, CI logs, backups. Use env vars or secret managers |
| Medium | Comparing secrets with `==` | Leaks timing info. Use `crypto/subtle.ConstantTimeCompare` |
| Medium | Returning detailed errors | Stack traces/DB errors help attackers map your system. Return generic messages, log details server-side |
| High | Ignoring `-race` findings | Races cause data corruption and can bypass authorization checks |
| High | MD5/SHA1 for passwords | Known collision attacks, fast to brute-force. Use Argon2id or bcrypt |
| High | AES without GCM | ECB/CBC lack authentication. GCM provides encrypt+authenticate |
| Medium | Binding to 0.0.0.0 | Exposes service to all network interfaces. Bind to specific interface |

## Security Anti-Patterns

| Severity | Anti-Pattern | Why It Fails | Fix |
| --- | --- | --- | --- |
| High | Security through obscurity | Hidden URLs are discoverable via fuzzing, logs | Authentication + authorization on all endpoints |
| High | Trusting client headers | `X-Forwarded-For`, `X-Is-Admin` trivially forged | Server-side identity verification |
| High | Client-side authorization | JS checks bypassed by any HTTP client | Server-side permission checks on every handler |
| High | Shared secrets across envs | Staging breach compromises production | Per-environment secrets via secret manager |
| Critical | Ignoring crypto errors | `_, _ = encrypt(data)` silently proceeds unencrypted | Always check errors — fail closed, never open |
| Critical | Rolling your own crypto | Custom encryption hasn't been analyzed by cryptographers | Use `crypto/aes` GCM, `golang.org/x/crypto/argon2` |

## Additional Resources

- [Go Security Best Practices](https://go.dev/doc/security/best-practices)
- [gosec Security Linter](https://github.com/securego/gosec)
- [govulncheck](https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck)
- [OWASP Go Secure Coding Practices](https://owasp.org/www-project-go-secure-coding-practices-guide/)

## Cross-References

- go-database — SQL injection prevention patterns in detail
- go-safety — memory safety, integer overflow, internal-correctness pitfalls
