# Codex And Claude Code Skill Compatibility

The suite is intentionally conservative:

- Every skill is a directory with a required `SKILL.md`.
- Frontmatter uses only `name` and `description`.
- Platform-specific metadata should live in `agents/openai.yaml`, not in
  frontmatter — none of the 11 `arbor-*` skills ship one yet, so add it when
  packaging for a platform that needs it. See `.agent/skills/acton/agents/openai.yaml`
  for the expected shape (`display_name`, `short_description`, `default_prompt`).
- Resources are one level below the skill directory: `references/` and
  `scripts/`.
- Instructions use progressive disclosure: the orchestrator loads phase
  skills only when needed.

When porting to Claude Code, the same `SKILL.md` bodies remain valid. If a
Claude-specific field such as `allowed-tools` or `context: fork` is desired,
add it only in a platform-specific copy or adapter, not in the shared
frontmatter.
