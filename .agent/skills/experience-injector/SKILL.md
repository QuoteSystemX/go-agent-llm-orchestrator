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
