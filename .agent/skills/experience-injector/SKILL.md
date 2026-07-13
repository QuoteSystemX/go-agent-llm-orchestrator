---
name: experience-injector
description: "Automatically queries the repository lessons learned database and injects relevant historical insights into agent prompts. Implements the FOXY reflection loop method."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 1.0
priority: NORMAL
---
# Experience Injector

This skill enables agents to dynamically check the `LESSONS_LEARNED.md` database and inject relevant technical lessons into active context before planning or execution.

## Protocol

1. **Query Formulation**: Match the current task keywords or intent.
2. **Retrieve Lessons**: Use `inject_experience.py` script to run semantic/keyword matching.
3. **Inject Context**: Format matched lessons and append them directly to the agent's task description or active prompt.
4. **Enforce**: Keep agents aware of past mistakes to avoid repeats (e.g. GLIBC versioning, Go private dependencies, drift detection errors).


## When to Use

- **Injecting relevant past experience into a new task** —
  use `experience_injector.py` at task start.
- **Tuning the snippet budget** — too few = useless, too many =
  context bloat.
- **Ranking by relevance** — use `query_lessons(query, top_n=N)` to
  get the top-N most relevant.
- **Combining with the Squeeze loop** — `archivist_trigger.py`
  and `experience_injector.py` form the knowledge loop.

Avoid using this skill for:
- New lessons (use `@knowledge-distillation` to capture).
- Generic search (use `Grep` tool).

## Anti-Patterns

- **Don't inject lessons the agent already knows** —
  dedupe by `lesson_id` before injection.
- **Don't inject too many lessons** — 3-5 is usually enough.
  More = context bloat.
- **Don't inject low-quality lessons** — garbage in, garbage out.
  Prune via TTL.
- **Don't inject without the format** — use the standard
  `### [date] [tag] [skill] title` format for parser compatibility.
- **Don't ignore the FOXY (Find Optimally eXtracted Yours) method**
  — the standard `markers_block` format is what agents parse.
  Custom formats break the loop.

## Additional Quality Guidelines
To ensure the highest standard of delivery, the following additional considerations must be met:
1. Maintain consistency with existing naming conventions in the codebase.
2. Implement comprehensive error handling and logging for all new components.
3. Ensure that all dependencies are declared and verified beforehand.
4. Write clean, self-documenting code with clear comments where necessary.
5. Validate performance under load and avoid premature optimizations.
