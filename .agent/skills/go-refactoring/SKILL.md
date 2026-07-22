---
name: go-refactoring
description: Go refactoring — the safe, at-scale process for restructuring existing Go code — coverage-adaptive safety net, tool-driven behavior-preserving transforms, the Fowler catalog mapped to Go, breaking import cycles, moving types across packages, and a human-in-the-loop workflow of small stacked PRs. Apply when code is hard to maintain, a function/type has grown too large, adding a feature is blocked by structure, or the user asks to clean up, refactor, or restructure Go code. Target styles owned elsewhere: go-naming (renames), go-modernize (idioms), go-code-style (control flow), go-design-patterns (patterns/DI).
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0.0
source: Adapted from samber/cc-skills-golang@golang-refactoring (MIT License) — https://github.com/samber/cc-skills-golang
---

# Go Refactoring — Safe Change at Scale

Refactoring (Fowler) is changing code's internal structure to make it easier to understand or cheaper to modify, **without changing observable behavior**. Go tooling (gopls Rename/Inline/Extract) can prove several transforms are behavior-preserving by construction — but that guarantee is silent on anything reflection can reach (struct tags, `text/template` field references), so a safety net still matters.

## The Core Loop

**Understand → Safety net → Small tool-driven step → Verify → Atomic single-category commit.** Repeat.

1. **Understand** — map the change's blast radius (references, call hierarchy, package API) before touching anything.
2. **Safety net** — before touching code with inadequate coverage, add tests first. Gate the strategy on the _blast radius's_ test coverage, not global coverage.
3. **Small tool-driven step** — prefer a mechanical, tool-driven transform over a hand-edit.
4. **Verify** — `go build ./... && go vet ./... && go test ./...`; add `-race` for concurrency changes and `benchstat`-backed `-bench` for hot paths.
5. **Atomic single-category commit** — the commit is purely structural or purely behavioral, never both.

## Hard Rules

- **Never mix structural and behavioral changes in one commit or PR.** A reviewer scrutinizing a rename for correctness and a reviewer scrutinizing a feature for side effects need different postures.
- **Split a code move from a code optimization into two sequential PRs**, even though both are structural — they need different verification. Aim for **100–500 lines per PR**.
- **Prefer gopls Rename/Inline over hand-edits.** Both are behavior-preserving by construction — Rename refuses on shadowing or interface-satisfaction breakage.
- **When a change recurs across many sites, generate a rewrite tool instead of hand-editing each site** — escalate `gofmt -r` → `eg` → `gopatch` → a `go/analysis` fixer.
- **Use a type alias (`type A = B`) for every type moved across packages** — the old and new names stay interchangeable while callers migrate incrementally.
- **Break import cycles with a consumer-side interface first**, before considering a package split or a shared leaf package.
- **Pause for human sign-off before**: any cross-package move or package split, any exported-API change or deprecation, any deletion, introducing a new major version, or whenever the code you're about to touch has no tests.
- **Grep for tag and reflection references after any rename** — a compiler-safe rename can still desync a struct tag (`json`/`db`) from its field.
- **Treat "changes what the code does" as the trigger for a security-and-safety pass** (see go-security, go-safety), not an afterthought.
- **Start every step from a clean, committed baseline, and revert rather than debug forward when it goes red.**

## When Not to Refactor

- **The code works and nothing planned will touch it again** — a stable, rarely-read package earns nothing from being restructured for its own sake.
- **It's critical production code with no tests** — don't refactor it directly; add a characterization-test baseline first.
- **The deadline is tight** — make the minimal safe change now and stage the larger refactor for when there's room.
- **There's no clear purpose** — "refactor this" with no upcoming feature or bug class it closes off is refactoring for its own sake.

## Risk Stratification

| Risk | Transforms | Safety requirement |
| --- | --- | --- |
| **Low** | gopls Rename, Extract Variable/Constant, Inline Variable, `gofmt -s`, organize imports | Build/vet/test after the step is enough |
| **Medium** | Extract Function/Method, Inline Call across packages, single-parameter add/remove, introducing generics | Add or confirm targeted tests over the blast radius first |
| **High** | Change signature across many callers, moving types/functions across packages, splitting/merging packages, breaking import cycles, exported-API or major-version changes | Full safety net + human checkpoint before landing |

**Diagnose:** gopls refusing a Rename/Inline is a real semantic hazard — investigate the conflict before forcing the change by hand. `go vet`/`golangci-lint` flagging a new issue after a step — fix before committing. `go test -race` reporting any race — stop, the concurrency behavior changed. `benchstat` reporting anything other than `~` on a hot path — stop and revert or optimize.

## Workflow: Plan → Stage → Land

A refactor of any real size does not land as one commit or even one PR — it lands as an ordered sequence of small, independently reviewable PRs, staged on a refactoring branch, with a human approving each merge.

## Cross-References

- go-naming — what to rename identifiers _to_ (this skill owns _how_ to apply it safely at scale)
- go-modernize — version-driven idiom updates, a distinct concern from structural refactoring
- go-code-style — control-flow clarity and function-shape rules this skill helps apply mechanically
- go-design-patterns — target patterns (options struct, DI, consumer-side interfaces) to migrate toward
- go-testing — the test-writing practices that make the safety net trustworthy
- go-security, go-safety — reviewing any step that changes code logic, not just its shape
