---
name: go-naming
description: Go naming conventions — packages, constructors, structs, interfaces, constants, enums, errors, booleans, receivers, getters/setters, functional options, acronyms, test functions, and subtest names. Use when writing new Go code, reviewing or refactoring, or choosing between naming alternatives (New vs NewTypeName, isConnected vs connected, ErrNotFound vs NotFoundError). Also trigger on MixedCaps vs snake_case, ALL_CAPS constants, Get-prefix on getters, or error string casing.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-naming (MIT License) — https://github.com/samber/cc-skills-golang
---

# Go Naming Conventions

Go favors short, readable names. Capitalization controls visibility — uppercase is exported, lowercase is unexported. All identifiers MUST use MixedCaps, NEVER underscores.

> "Clear is better than clever." — Go Proverbs
> "Design the architecture, name the components, document the details." — Go Proverbs

## Quick Reference

| Element | Convention | Example |
| --- | --- | --- |
| Package | lowercase, single word | `json`, `http`, `tabwriter` |
| File | lowercase, underscores OK | `user_handler.go` |
| Exported name | UpperCamelCase | `ReadAll`, `HTTPClient` |
| Unexported | lowerCamelCase | `parseToken`, `userCount` |
| Interface | method name + `-er` | `Reader`, `Closer`, `Stringer` |
| Struct | MixedCaps noun | `Request`, `FileHeader` |
| Constant | MixedCaps (not ALL_CAPS) | `MaxRetries`, `defaultTimeout` |
| Receiver | 1-2 letter abbreviation | `func (s *Server)`, `func (b *Buffer)` |
| Error variable | `Err` prefix | `ErrNotFound`, `ErrTimeout` |
| Error type | `Error` suffix | `PathError`, `SyntaxError` |
| Constructor | `New` (single type) or `NewTypeName` (multi-type) | `ring.New`, `http.NewRequest` |
| Boolean field | `is`, `has`, `can` prefix | `isReady`, `IsConnected()` |
| Test function | `Test` + function name | `TestParseToken` |
| Acronym | all caps or all lower | `URL`, `HTTPServer`, `xmlParser` |
| Variant: context | `WithContext` suffix | `FetchWithContext`, `QueryContext` |
| Variant: error | `Must` prefix | `MustParse()`, `MustLoadConfig()` |
| Option func | `With` + field name | `WithPort()`, `WithLogger()` |
| Enum (iota) | type name prefix, zero-value = unknown | `StatusUnknown` at 0, `StatusReady` |
| Error string | lowercase (incl. acronyms), no punctuation | `"image: unknown format"`, `"invalid id"` |
| Import alias | short, only on collision | `mrand "math/rand"`, `pb "app/proto"` |
| Format func | `f` suffix | `Errorf`, `Wrapf`, `Logf` |

## MixedCaps

All Go identifiers MUST use `MixedCaps` (or `mixedCaps`). NEVER use underscores — the only exceptions are test subcases (`TestFoo_InvalidInput`), generated code, and OS/cgo interop.

```go
// ✓ Good
MaxPacketSize
userCount
parseHTTPResponse

// ✗ Bad
MAX_PACKET_SIZE   // C/Python style
max_packet_size   // snake_case
```

## Avoid Stuttering

Go call sites always include the package name, so repeating it in the identifier wastes the reader's time:

```go
// Good
http.Client       // not http.HTTPClient
json.Decoder      // not json.JSONDecoder
user.New()        // not user.NewUser()
config.Parse()    // not config.ParseConfig()

// In package dbpool:
type Pool struct{}        // not DBPool
type Status struct{}      // not PoolStatus
```

## Frequently Missed Conventions

**Constructor naming:** When a package exports a single primary type, the constructor is `New()`, not `NewTypeName()`. Use `NewTypeName()` only when a package has multiple constructible types.

**Boolean struct fields:** Unexported boolean fields MUST use `is`/`has`/`can` prefix — `isConnected`, `hasPermission`, not bare `connected`. The exported getter keeps the prefix: `IsConnected() bool`.

**Error strings are fully lowercase — including acronyms.** Write `"invalid message id"` not `"invalid message ID"`, because error strings are often concatenated with other context. Sentinel errors should include the package name as prefix: `errors.New("apiclient: not found")`.

**Enum zero values:** Always place an explicit `Unknown`/`Invalid` sentinel at iota position 0. A `var s Status` silently becomes 0 — if that maps to a real state, code can behave as if a status was deliberately chosen when it wasn't.

**Subtest names:** Table-driven test case names in `t.Run()` should be fully lowercase descriptive phrases: `"valid id"`, `"empty input"`.

## Common Mistakes

| Mistake | Fix |
| --- | --- |
| `ALL_CAPS` constants | Go reserves casing for visibility, not emphasis — use `MixedCaps` |
| `GetName()` getter | Go omits `Get` because `user.Name()` reads naturally. But `Is`/`Has`/`Can` prefixes are kept for booleans |
| `Url`, `Http`, `Json` acronyms | Mixed-case acronyms create ambiguity — use all caps or all lower |
| `this` or `self` receiver | Use 1-2 letter abbreviation (`s` for `Server`) |
| `util`, `helper` packages | Say nothing about content — use specific names |
| `http.HTTPClient` stuttering | `http.Client` avoids reading "HTTP" twice |
| `user.NewUser()` constructor | Single primary type uses `New()` |
| `connected bool` field | Use `isConnected` so the field reads as a true/false question |
| `"invalid message ID"` error | Fully lowercase including acronyms — `"invalid message id"` |
| `StatusReady` at iota 0 | Zero value should be a sentinel — `StatusUnknown` at 0 |
| `snake_case` identifiers | Conflicts with Go's MixedCaps convention and tooling |
| Naming constants by value | Values change, roles don't — `DefaultPort` survives a port change, `Port8080` doesn't |
| `sort()` in-place but no `In` | Readers assume functions return new values. `SortIn()` signals mutation |
| `parse()` panicking on error | `MustParse()` warns callers that failure panics |
| Plural package names | Go convention is singular (`net/url` not `net/urls`) |
| Unnecessary import aliases | Only alias on collision — `mrand "math/rand"` |

## Enforce with Linters

Many naming issues are caught automatically: `revive`, `predeclared`, `misspell`, `errname`.

## Cross-References

- go-code-style — broader formatting and style decisions
- go-refactoring — how to apply a rename safely at scale
