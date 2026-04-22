> [!IMPORTANT]
> !SILENT execution: No dialogue allowed. ZERO-TEXT finalization required.

# [STORY] Story Title

## Context

Epic: [epic name]. PRD Section: [N]. Persona: [user persona name].
[Background: why this story is needed now and what larger goal it serves.]

## Impact

[Business metric this unlocks. User benefit. Severity if not done: Low / Medium / High / Critical.]

## Fix Hint / Implementation Guide

- Target files to create or modify: `path/to/file.ext`
- API contract: `POST /endpoint → { field: type }` (if applicable)
- Patterns to follow: [reference `.agent/KNOWLEDGE.md` section or `wiki/ARCHITECTURE.md` ADR]
- Edge cases to handle: [list specific scenarios]
- Related components: [what else might be affected]

## Acceptance Criteria

- [ ] Given [precondition] When [action] Then [expected outcome]
- [ ] Given [precondition] When [action] Then [expected outcome]
- [ ] Unit tests written and passing
- [ ] Integration test passes (if applicable)
- [ ] No regression in related module
- [ ] Tests passed with `-race` (Go projects)
