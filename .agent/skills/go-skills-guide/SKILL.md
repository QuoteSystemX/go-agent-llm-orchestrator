---
name: go-skills-guide
description: Go skills router — for any Go coding, review, debug, or setup task, identifies which of the go-* skills apply (often several at once) and disambiguates overlapping clusters (performance vs troubleshooting, samber/lo vs mo vs ro, DI cluster, safety vs security). Read this first when unsure which go-* skill(s) to load for a task.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-how-to (MIT License) — https://github.com/samber/cc-skills-golang
---

# Go Skills Router

For most Go tasks, more than one skill applies at once — load the primary skill and its secondary skills together rather than one at a time.

## Skill Loading Table

| Intent | Primary | Also load |
| --- | --- | --- |
| Design an API, choose a pattern | go-design-patterns | go-data-structures, go-naming |
| Name a type, function, or package | go-naming | go-code-style |
| Handle errors idiomatically | go-error-handling | go-safety (nil-heavy code) |
| Write goroutines, channels, sync | go-concurrency | go-context (if cancellation) |
| Pass deadlines / cancel operations | go-context | go-concurrency (if goroutines) |
| Database queries and transactions | go-database | go-error-handling, go-security |
| Write tests | go-testing | go-stretchr-testify (if using testify) |
| Debug a panic or unexpected behavior | go-troubleshooting | go-safety |
| Audit security vulnerabilities | go-security | go-safety |
| Review formatting and style | go-code-style | go-naming |
| Refactor or restructure existing code | go-refactoring | go-naming, go-code-style |
| Adopt new Go language features | go-modernize | — |
| Use samber/lo (slice/map helpers) | go-samber-lo | go-data-structures |
| Use samber/oops (structured errors) | go-samber-oops | go-error-handling |
| Use log/slog | go-samber-slog | go-error-handling |
| Use samber/mo (Option/Result/Either) | go-samber-mo | go-error-handling |
| Use samber/hot (in-memory cache) | go-samber-hot | go-database |
| Use samber/ro (reactive streams) | go-samber-ro | go-samber-lo, go-concurrency |
| Use samber/do (dependency injection) | go-samber-do | go-design-patterns |
| Build a CLI (cobra/viper) | go-cli | go-spf13-cobra, go-spf13-viper, go-naming |
| gRPC / Protobuf service work | grpc-architect agent's guidance | go-testing, go-error-handling |
| Financial-precision / xsync / zero-alloc patterns | go-patterns | go-safety |
| GoDoc / README / package documentation | godoc-patterns | go-naming |

## Competing Clusters — Boundary Lines

- **Errors**: go-error-handling (idioms) · go-samber-oops (structured errors) · go-safety (prevent panics)
- **samber/\***: go-samber-lo (finite transforms on slices/maps) · go-samber-ro (reactive/infinite streams) · go-samber-mo (monadic types: Option/Result/Either)
- **Style**: go-code-style (control flow, function shape) · go-naming (identifiers) · godoc-patterns (doc comments)
- **Gap — correctness vs threat**: go-safety (internal bugs, our own mistakes) vs go-security (external attackers)
- **Gap — features vs rules**: go-modernize (language adoption) vs lint config (not covered here)
- **Gap — process vs target rules**: go-refactoring (the safe, staged, at-scale _process_ of changing existing code) vs go-naming/go-code-style/go-design-patterns/go-modernize (what the resulting code should look like) — load go-refactoring alongside whichever of these owns the target shape

## Cross-References

Every go-* skill listed above cross-references its neighbors in its own "Cross-References" section — follow those links for the specific boundary between two adjacent skills once you've loaded the primary one.
