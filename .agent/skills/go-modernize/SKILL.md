---
name: go-modernize
description: Modernize Go code to use recent language features, standard library improvements, and idiomatic patterns (Go 1.21-1.26). Trigger when writing or reviewing Go code and old-style patterns are detected, when encountering a deprecation warning, or when the user explicitly asks for modernization or a Go version upgrade.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-modernize (MIT License) — https://github.com/samber/cc-skills-golang
---

# Go Code Modernization Guide

Continuously modernize Go codebases by replacing outdated patterns with modern equivalents.

**Scope**: last 3 years of Go modernization (Go 1.21 through 1.26). Some older modernizations (`any` instead of `interface{}`, `errors.Is`/`errors.As`, `strings.Cut`) are included because they are still commonly missed.

Never conduct large refactoring if the developer is working on a different task — mention opportunities but let the developer decide, unless explicitly asked to modernize.

## Workflow

1. Check the project's `go.mod`/`go.work` for the current Go version
2. Check the latest Go version against the changelog table below and suggest upgrading if behind
3. Scan the codebase for modernization opportunities based on the target Go version
4. Run `golangci-lint` with the `modernize` linter if available
5. If actively coding, only suggest improvements related to the current file/feature — don't refactor unrelated files
6. Before suggesting a dependency update, run `go mod tidy` and the test suite to verify compatibility

## Go Version Changelogs

| Version | Release | Changelog |
| --- | --- | --- |
| Go 1.21 | August 2023 | <https://go.dev/doc/go1.21> |
| Go 1.22 | February 2024 | <https://go.dev/doc/go1.22> |
| Go 1.23 | August 2024 | <https://go.dev/doc/go1.23> |
| Go 1.24 | February 2025 | <https://go.dev/doc/go1.24> |
| Go 1.25 | August 2025 | <https://go.dev/doc/go1.25> |
| Go 1.26 | February 2026 | <https://go.dev/doc/go1.26> |

## Deprecated Packages Migration

| Deprecated | Replacement | Since |
| --- | --- | --- |
| `math/rand` | `math/rand/v2` | Go 1.22 |
| `crypto/elliptic` (most functions) | `crypto/ecdh` | Go 1.21 |
| `reflect.SliceHeader`, `StringHeader` | `unsafe.Slice`, `unsafe.String` | Go 1.21 |
| `reflect.PtrTo` | `reflect.PointerTo` | Go 1.22 |
| `runtime.GOROOT()` | `go env GOROOT` | Go 1.24 |
| `runtime.SetFinalizer` | `runtime.AddCleanup` | Go 1.24 |
| `crypto/cipher.NewOFB`, `NewCFB*` | AEAD modes or `NewCTR` | Go 1.24 |
| `golang.org/x/crypto/sha3` | `crypto/sha3` | Go 1.24 |
| `golang.org/x/crypto/hkdf` | `crypto/hkdf` | Go 1.24 |
| `golang.org/x/crypto/pbkdf2` | `crypto/pbkdf2` | Go 1.24 |
| `testing/synctest.Run` | `testing/synctest.Test` | Go 1.25 |
| `crypto/rsa.EncryptPKCS1v15` for new encryption use | RSA-OAEP or HPKE/KEM | Go 1.26 |
| `net/http/httputil.ReverseProxy.Director` | `ReverseProxy.Rewrite` | Go 1.26 |

## Migration Priority Guide

### High priority (safety and correctness)

1. Remove loop variable shadow copies _(Go 1.22+)_ — prevents subtle bugs
2. Replace `math/rand` with `math/rand/v2` _(Go 1.22+)_ — remove `rand.Seed` calls
3. Use `os.Root` for user-supplied file paths _(Go 1.24+)_ — prevents path traversal
4. Run `govulncheck` _(Go 1.22+)_ — catch known vulnerabilities
5. Use `errors.Is`/`errors.As` instead of direct comparison
6. Migrate deprecated crypto packages _(Go 1.24+)_ — security critical

### Medium priority (readability and maintainability)

7. Replace `interface{}` with `any` _(Go 1.18+)_
8. Use `min`/`max` builtins _(Go 1.21+)_
9. Use `range` over int _(Go 1.22+)_
10. Use `slices` and `maps` packages _(Go 1.21+)_
11. Use `cmp.Or` for default values _(Go 1.22+)_
12. Use `sync.OnceValue`/`sync.OnceFunc` _(Go 1.21+)_
13. Use `sync.WaitGroup.Go` _(Go 1.25+)_
14. Use `t.Context()` in tests _(Go 1.24+)_
15. Use `b.Loop()` in benchmarks _(Go 1.24+)_

### Lower priority (gradual improvement)

16. Migrate to `slog` from third-party loggers _(Go 1.21+)_
17. Adopt iterators where they simplify code _(Go 1.23+)_
18. Replace `sort.Slice` with `slices.SortFunc` _(Go 1.21+)_
19. Use `strings.SplitSeq` and iterator variants _(Go 1.24+)_
20. Move tool deps to `go.mod` tool directives _(Go 1.24+)_
21. Enable PGO for production builds _(Go 1.21+)_
22. Upgrade to golangci-lint v2 with modernize linter
23. Add `govulncheck` to CI pipeline

## Using the modernize linter

The `modernize` linter (golangci-lint v2.6.0+) automatically detects code that can be rewritten using newer Go features. It originates from `golang.org/x/tools/go/analysis/passes/modernize`.

## Cross-References

- go-concurrency, go-testing, go-error-handling, go-lint
- go-refactoring — staging a large modernization sweep as small human-reviewed PRs
