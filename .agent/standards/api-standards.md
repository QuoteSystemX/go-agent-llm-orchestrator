# API Design Standards

## Error Handling
- Use RFC 7807 Problem Details for HTTP APIs (`application/problem+json`).
- Always return a machine-readable `type` URI, a `title`, and a `status` code.
- Include a `detail` field for human-readable explanation.
- Use `instance` to point to the specific request that caused the error.

## Versioning
- Version APIs via URL path prefix: `/v1/`, `/v2/`.
- Never break existing versions; deprecate with `Sunset` and `Deprecation` headers.
- Maintain at least one prior major version for 6 months after a new release.

## Authentication
- Use Bearer tokens (OAuth 2.0 / JWT) for public APIs.
- Never pass credentials in query parameters.
- Rotate signing keys on a schedule; support key ID (`kid`) in JWT headers.

## Rate Limiting
- Return `429 Too Many Requests` with `Retry-After` header.
- Document rate limit tiers in OpenAPI spec under `x-ratelimit-*` extensions.

## Idempotency
- All mutating endpoints (POST/PUT/PATCH/DELETE) must support `Idempotency-Key` header.
- Store idempotency keys for at least 24 hours.

## Pagination
- Prefer cursor-based pagination over offset for large datasets.
- Return `next`, `prev` links in response envelope or `Link` header.

## Caching
- Use `ETag` + `If-None-Match` for resource caching.
- Set `Cache-Control: no-store` on sensitive endpoints (auth, payments).

## OpenAPI
- All APIs must have an OpenAPI 3.1 spec committed alongside code.
- Spec must include examples for every request/response schema.
