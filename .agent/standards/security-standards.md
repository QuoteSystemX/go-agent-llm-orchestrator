# Security Standards

## Secret Management
- Never hardcode secrets, API keys, or tokens in source code.
- Store secrets in environment variables or a secrets manager (Vault, AWS SSM).
- Rotate secrets on a schedule; rotate immediately on suspected exposure.
- Use `.gitignore` and pre-commit hooks to block accidental secret commits.

## Input Validation
- Validate and sanitise all inputs at system boundaries.
- Use allowlist (not blocklist) validation for user-controlled data.
- Apply maximum length limits to all string inputs.
- Reject unexpected content types; never infer from content body alone.

## Dependency Management
- Pin all dependencies to exact versions in lockfiles.
- Run automated dependency vulnerability scanning on every CI build (e.g., `pip-audit`, `trivy`).
- Upgrade vulnerable dependencies within 7 days for critical CVEs, 30 days for high.

## Logging
- Never log sensitive data (passwords, tokens, PII).
- Structured logs must include: timestamp, level, service, trace-id.
- Centralise logs; retain for at least 90 days.

## Least Privilege
- Each service/process must run with the minimum permissions required.
- Use separate service accounts per microservice; never share credentials.
- Audit IAM roles and permissions quarterly.

## Supply Chain
- Verify checksums/signatures for all downloaded artifacts.
- Use trusted base images; pin to specific digest (not `latest`).
- SBOM (Software Bill of Materials) must be generated for every release.

## Cryptography
- Use TLS 1.2+ for all network communication; prefer TLS 1.3.
- Use AES-256-GCM for symmetric encryption; RSA-4096 or EC P-256 for asymmetric.
- Never implement custom cryptographic primitives.
- Use constant-time comparison for secrets and tokens.
