---
name: godoc-patterns
description: Go documentation standards — package doc-comments, func/type/method docs, doc.go files, Example tests, pkg.go.dev conventions, Deprecated markers, and godoc-driven API design. Universal — works in Antigravity (Gemini) and Claude Code.
version: 1.0.0
---

# GoDoc Patterns Skill

GoDoc is Go's built-in documentation system. Doc-comments are rendered on [pkg.go.dev](https://pkg.go.dev) and surfaced by `go doc`, IDEs, and `godoc -http`. A well-documented package is self-explanatory without a README.

> "GoDoc comments are API contracts written in prose." — Go team

---

## 📐 COMMENT SYNTAX RULES

### The one mandatory rule

A doc-comment immediately precedes the declaration with **no blank line** between them:

```go
// Package auth implements JWT-based session management.
package auth

// ErrTokenExpired is returned when a token's expiry time has passed.
var ErrTokenExpired = errors.New("token expired")

// New creates a TokenStore backed by the given cache.
// The TTL controls how long tokens remain valid after issuance.
func New(cache Cache, ttl time.Duration) *TokenStore {
```

### Blank line = not a doc-comment

```go
// This comment is NOT a doc-comment — blank line separates it.

func Bad() {}

// This IS a doc-comment.
func Good() {}
```

---

## 📦 PACKAGE-LEVEL DOCUMENTATION

### Short packages — inline comment

```go
// Package uuid generates and parses RFC 4122 UUIDs.
package uuid
```

### Complex packages — use doc.go

For packages with substantial explanation, create a `doc.go` file:

```go
// Package cache provides a thread-safe in-memory cache with TTL eviction.
//
// # Basic usage
//
//	c := cache.New(5 * time.Minute)
//	c.Set("key", value)
//	v, ok := c.Get("key")
//
// # Eviction
//
// Items are evicted lazily on access and eagerly by a background goroutine
// that runs every [Cache.CleanupInterval]. To disable background cleanup,
// set CleanupInterval to zero.
//
// # Concurrency
//
// All methods are safe for concurrent use. The implementation uses
// [sync.RWMutex] for reads and an exclusive lock for writes.
package cache
```

### Package doc structure (for large packages)

```
// Package <name> <one-line summary>.
//
// # Overview
// [2-4 sentences: what problem this solves, what the main abstraction is]
//
// # Usage
// [Minimal working example using code blocks]
//
// # Configuration
// [Key options and their effect]
//
// # Concurrency
// [Whether types are safe for concurrent use]
//
// # Errors
// [Sentinel errors exported by this package]
package <name>
```

---

## ✍️ FUNCTION & METHOD DOCUMENTATION

### The three-part formula

```
// <FuncName> <what it does, starting with the name>.
// [Blank line]
// [When to use it / what the caller needs to know]
// [Errors / panics / special return values]
```

### Examples

```go
// ParseToken validates a signed JWT and returns the embedded Claims.
// The token must be signed with the same key passed to [New].
//
// It returns [ErrTokenExpired] if the token is past its expiry time,
// or [ErrInvalidSignature] if the signature does not match.
func (s *TokenStore) ParseToken(raw string) (*Claims, error) {

// Shutdown gracefully drains in-flight requests and stops background workers.
// It blocks until all work is done or ctx is cancelled.
// After Shutdown returns, the server cannot be restarted.
func (s *Server) Shutdown(ctx context.Context) error {

// Set stores v under key, overwriting any existing value.
// The entry expires after the store's configured TTL.
func (c *Cache) Set(key string, v any) {
```

### Short functions — one line is fine

```go
// Len returns the number of items currently in the cache.
func (c *Cache) Len() int { return len(c.items) }
```

### Constructors

Always document: what is returned, what the zero/nil values of parameters mean, when errors occur.

```go
// NewClient creates an HTTP client with the given base URL and options.
// If opts is nil, default timeouts (30s connect, 60s total) are used.
// NewClient panics if baseURL is empty.
func NewClient(baseURL string, opts *ClientOptions) *Client {
```

---

## 🏷️ TYPES & CONSTANTS

### Structs

Document the type, then each field that is not self-evident:

```go
// Config holds the runtime configuration for a Worker.
// Zero value is not valid — use [NewConfig] or [DefaultConfig].
type Config struct {
    // Concurrency is the maximum number of jobs processed simultaneously.
    // Defaults to runtime.NumCPU() if zero.
    Concurrency int

    // Queue is the name of the Redis queue to consume from.
    Queue string

    // Timeout is the per-job execution deadline.
    // Jobs that exceed this are cancelled and retried.
    Timeout time.Duration
}
```

### Interfaces

Document the contract, not the implementation:

```go
// Cache is a key-value store with expiry semantics.
// Implementations must be safe for concurrent use by multiple goroutines.
type Cache interface {
    // Get returns the value stored for key and whether the key was found.
    Get(key string) (any, bool)

    // Set stores v under key until the implementation-defined TTL elapses.
    Set(key string, v any)

    // Delete removes key from the cache. It is a no-op if key does not exist.
    Delete(key string)
}
```

### Enums / iota constants

```go
// Status represents the lifecycle state of a Job.
type Status int

const (
    // StatusPending means the job has been queued but not yet started.
    StatusPending Status = iota

    // StatusRunning means the job is currently executing.
    StatusRunning

    // StatusDone means the job completed successfully.
    StatusDone

    // StatusFailed means the job completed with an error.
    StatusFailed
)
```

### Sentinel errors

```go
var (
    // ErrNotFound is returned when the requested key does not exist.
    ErrNotFound = errors.New("not found")

    // ErrConflict is returned when a resource already exists at the given key.
    ErrConflict = errors.New("conflict")
)
```

---

## 🧪 EXAMPLE FUNCTIONS (testable docs)

Examples appear in `*_test.go` files and are rendered on pkg.go.dev. They also run as tests.

### Function example

```go
// In file: cache_test.go

func ExampleCache_Set() {
    c := cache.New(5 * time.Minute)
    c.Set("greeting", "hello")

    v, ok := c.Get("greeting")
    fmt.Println(ok, v)
    // Output:
    // true hello
}
```

### Package-level example (shown first on pkg.go.dev)

```go
func Example() {
    store := auth.New(myCache, 24*time.Hour)

    token, _ := store.IssueToken(userID)
    claims, _ := store.ParseToken(token)

    fmt.Println(claims.UserID == userID)
    // Output:
    // true
}
```

### Naming rules

| Name | Renders as |
|------|-----------|
| `ExampleFoo()` | Example for `Foo` |
| `ExampleFoo_bar()` | Example for `Foo`, variant "bar" |
| `ExampleCache_Set()` | Example for method `Cache.Set` |
| `Example()` | Package-level example |

---

## 🔗 CROSS-REFERENCES

Use `[Name]` syntax (Go 1.19+) to link to other identifiers in the same package, or `[pkg.Name]` for other packages:

```go
// ParseToken validates a JWT issued by [New].
// On success it returns [Claims]; on failure it returns one of
// [ErrTokenExpired], [ErrInvalidSignature], or [ErrMalformed].
//
// See also [TokenStore.RefreshToken] for extending a valid token.
func (s *TokenStore) ParseToken(raw string) (*Claims, error) {
```

---

## ⚠️ DEPRECATED MARKERS

```go
// Deprecated: Use [NewClientV2] instead, which supports connection pooling.
// NewClient will be removed in v3.0.
func NewClient(addr string) *Client {
```

`Deprecated:` must be at the start of a paragraph (after a blank line in longer comments) for tooling to recognize it.

---

## 📋 FORMATTING IN COMMENTS (Go 1.19+)

```go
// # Section headings use # prefix (renders as h3 on pkg.go.dev)
//
// Paragraphs are separated by blank comment lines.
//
// Indented lines render as code blocks:
//
//	c := cache.New(5 * time.Minute)
//	c.Set("key", value)
//
// Lists use a dash:
//   - First item
//   - Second item
//
// [Links] to identifiers work automatically.
```

---

## ✅ GODOC QUALITY CHECKLIST

### Package

- [ ] Every exported package has a package doc-comment
- [ ] Complex packages have `doc.go` with overview + usage example
- [ ] Package comment starts with `Package <name>`

### Functions & Methods

- [ ] Every exported function/method has a doc-comment
- [ ] Comment starts with the function name
- [ ] Error return values documented (which errors can be returned)
- [ ] Nil/zero parameter behaviour documented
- [ ] Panics documented if any

### Types

- [ ] Every exported type has a doc-comment
- [ ] Non-obvious struct fields have field-level comments
- [ ] Interfaces document the concurrency contract
- [ ] iota constants each have a doc-comment

### Examples

- [ ] At least one `Example()` function per package
- [ ] Complex methods have `ExampleType_Method()` functions
- [ ] All examples have `// Output:` blocks (makes them testable)

### Cross-references & markers

- [ ] `[Name]` links used to connect related identifiers
- [ ] `Deprecated:` markers on obsolete APIs
- [ ] No TODO/FIXME left in exported doc-comments

---

## 🔍 VERIFICATION COMMANDS

```bash
# Render docs locally (browse at http://localhost:6060)
godoc -http=:6060

# Check a specific package
go doc ./pkg/auth
go doc ./pkg/auth TokenStore.ParseToken

# Lint doc-comments (requires go install golang.org/x/tools/cmd/godoc)
staticcheck ./...   # includes doc-comment style checks

# Find exported identifiers missing doc-comments
go vet ./...        # basic checks
golangci-lint run --enable godot,godox   # godot: periods, godox: TODO in docs
```

---

## Changelog

- **1.0.0** (2026-04-26): Initial version — full GoDoc syntax, doc.go, Examples, cross-references, Deprecated, formatting, quality checklist

<!-- EMBED_END -->
